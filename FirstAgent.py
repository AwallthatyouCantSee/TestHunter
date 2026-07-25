# -*- coding: utf-8 -*-
"""Friday - 测试服务多智能体协调者

基于 AgentScope Handoffs 模式，协调"问题解析助手"和"文件生成助手"两个子智能体，
为用户提供测试用例、测试数据文件、Mock 服务脚本的生成和增量修改服务。

架构：
  用户 → 协调者 → call_problem_parser / call_file_generator
                     ↕                      ↕
              问题解析助手              文件生成助手
                                         ↕
                                   FileGenerationContext
                                   (保存 content JSON 支持增量修改)
"""
from __future__ import annotations
import os
import sys
import asyncio
from pathlib import Path

from agentscope.agent import Agent
from agentscope.tool import (
    Toolkit,
    Bash,
    Grep,
    Glob,
    Read,
    Write,
    Edit,
    FunctionTool,
)
from agentscope.credential import DashScopeCredential
from agentscope.model import DashScopeChatModel
from agentscope.message import UserMsg
from agentscope.state import AgentState
from agentscope.permission import PermissionRule, PermissionBehavior
from dotenv import load_dotenv

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from agents.context import FileGenerationContext
from agents.monitor import AgentMonitor
from agents.tool_wrappers import (
    call_problem_parser,
    call_file_generator,
    call_batch_file_generator,
    set_shared_context,
)

load_dotenv()


def load_system_prompt() -> str:
    """从文件加载系统提示词"""
    prompt_file = Path(__file__).parent / "system_prompt.txt"
    try:
        with open(prompt_file, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"警告: 找不到提示词文件 {prompt_file}，使用默认提示词")
        return "你是一个测试服务协调者。"


async def main():
    """主函数：创建协调者 Agent 并启动交互式对话"""

    # ========== 1. 初始化共享上下文 ==========
    file_context = FileGenerationContext()
    monitor = AgentMonitor(prefix="协调者")

    # 将上下文注入到工具函数模块
    set_shared_context(file_context, monitor)

    # ========== 2. 创建协调者 Agent ==========
    # 权限配置：允许工具自动执行
    state = AgentState()
    all_tools = [
        "Bash", "Grep", "Glob", "Read", "Write", "Edit",
        "call_problem_parser", "call_file_generator", "call_batch_file_generator",
    ]
    for tool_name in all_tools:
        state.permission_context.allow_rules[tool_name] = [
            PermissionRule(
                tool_name=tool_name,
                rule_content=None,
                behavior=PermissionBehavior.ALLOW,
                source="userSettings",
            )
        ]

    # 工具包：基础工具 + 用 FunctionTool 包装的子智能体工具函数
    toolkit = Toolkit(
        tools=[
            Bash(),
            Grep(),
            Glob(),
            Read(),
            Write(),
            Edit(),
            FunctionTool(call_problem_parser),
            FunctionTool(call_file_generator),
            FunctionTool(call_batch_file_generator),
        ],
    )

    agent = Agent(
        name="Friday",
        system_prompt=load_system_prompt(),
        model=DashScopeChatModel(
            credential=DashScopeCredential(
                api_key=os.environ.get("DASHSCOPE_API_KEY", ""),
                base_url="https://api.xiaomimimo.com/v1",
            ),
            model="mimo-v2.5",
        ),
        toolkit=toolkit,
        state=state,
    )

    # ========== 3. 对话循环 ==========
    print("\n" + "=" * 60)
    print("  Friday - 测试服务多智能体协调者")
    print("=" * 60)
    print("\n子智能体:")
    print("  - 问题解析助手（测试需求分析）")
    print("  - 文件生成助手（xlsx/docx/pdf/md/py/js/sql）")
    print("\n可用命令:")
    print("  /files  - 查看已生成文件及其内容结构")
    print("  /stats  - 显示当前会话统计")
    print("  /clear  - 清屏")
    print("  /quit   - 退出")
    print("\n输入测试需求开始对话...\n")

    while True:
        try:
            user_input = input("👤 You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n再见！")
            break

        if not user_input:
            continue

        # 特殊命令
        if user_input.lower() == "/quit":
            print("\n再见！")
            break

        if user_input.lower() == "/files":
            print(f"\n{file_context.get_summary()}\n")
            continue

        if user_input.lower() == "/stats":
            monitor.print_header("会话统计")
            monitor.print_stats()
            continue

        if user_input.lower() == "/clear":
            os.system("cls" if os.name == "nt" else "clear")
            continue

        # ========== 智能路由判断（预检查） ==========
        # 如果是修改请求且有上下文，自动注入原始 content
        augmented_input = user_input
        if file_context.records and any(
            kw in user_input.lower()
            for kw in ["修改", "改一下", "换个", "改成", "补充", "加上", "删除", "去掉"]
        ):
            augmented_input = (
                f"{user_input}\n\n"
                f"[系统信息] 当前已生成文件列表：\n{file_context.get_summary()}\n"
                f"如需修改某个文件，请使用 call_file_generator 工具，"
                f"设置 is_modification=true，"
                f"并将该文件的 content 数据作为 previous_content_json 传入。"
            )

            # 尝试识别用户提到的文件名，自动注入对应的 content
            for path in file_context.list_files():
                if path.lower() in user_input.lower():
                    content = file_context.get_content(path)
                    if content:
                        import json
                        augmented_input += (
                            f"\n文件 '{path}' 的原始 content 数据：\n"
                            f"```json\n{json.dumps(content, ensure_ascii=False, indent=2)}\n```"
                        )
                    break

        # ========== 发送给协调者 ==========
        try:
            monitor.reset()
            async for evt in agent.reply_stream(UserMsg("User", augmented_input)):
                monitor.handle_event(evt)
        except Exception as e:
            print(f"\n错误: {e}")
            import traceback
            traceback.print_exc()

        # 打印上下文摘要（如果有新文件生成）
        print()


if __name__ == "__main__":
    asyncio.run(main())
