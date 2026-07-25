# -*- coding: utf-8 -*-
"""协调者工具函数 - 封装子智能体为可被协调者调用的工具

这些函数会被包装为 FunctionTool 并注册到协调者的 Toolkit 中，
LLM 可以像调用 Bash 一样调用它们。

内部通过模块级单例共享 FileGenerationContext 和 AgentMonitor。
"""
import json
import asyncio

from agentscope.tool import ToolChunk
from agentscope.message import UserMsg, TextBlock, ToolResultState

from agents.problem_parser import create_problem_parser
from agents.file_gen_agent import create_file_gen_agent
from agents.context import FileGenerationContext
from agents.monitor import AgentMonitor


# 模块级共享状态
file_context: FileGenerationContext | None = None
monitor: AgentMonitor | None = None


def set_shared_context(ctx: FileGenerationContext, mon: AgentMonitor) -> None:
    global file_context, monitor
    file_context = ctx
    monitor = mon


# ============================================================
# 内部核心函数：单文件生成逻辑（不创建新 Agent，避免重复）
# ============================================================

async def _generate_single_file(
    instruction: str,
    file_type: str = "",
    output_path: str = "",
    is_modification: bool = False,
    previous_content_json: str = "",
    agent: object = None,  # 复用 Agent 实例
) -> dict:
    """内部函数：执行单文件生成，返回 {output_path, content, result_text}"""
    parts = [instruction]

    if is_modification and previous_content_json:
        try:
            original = json.loads(previous_content_json)
            # 紧凑格式减少输入 token（对大 Excel 数据效果显著）
            parts.append(
                f"\n\n## 原始数据（修改后覆盖）\n"
                f"{json.dumps(original, ensure_ascii=False)}"
            )
        except json.JSONDecodeError:
            parts.append(f"\n\n## 原始内容数据\n{previous_content_json}")
    elif file_type and output_path:
        parts.append(f"\n\n文件类型: {file_type}\n输出路径: {output_path}")

    user_msg = UserMsg("协调者", "\n".join(parts))

    result_text = ""
    last_content = None
    last_file_type = None
    last_output_path = None

    async for evt in agent.reply_stream(user_msg):
        if "TEXT_BLOCK_DELTA" in str(getattr(evt, 'type', '')):
            result_text += evt.delta
        elif "TOOL_CALL" in str(getattr(evt, 'type', '')):
            if hasattr(evt, 'tool_call_args'):
                args = evt.tool_call_args
                if args.get('name') == 'FileGenerator':
                    inp = args.get('input', {})
                    last_file_type = inp.get('file_type')
                    last_output_path = inp.get('output_path')
                    last_content = inp.get('content')
        elif hasattr(evt, 'delta') and "TEXT" in str(getattr(evt, 'type', '')):
            result_text += evt.delta

    return {
        "output_path": last_output_path or output_path,
        "file_type": last_file_type or file_type,
        "content": last_content,
        "result_text": result_text.strip(),
    }


# ============================================================
# 工具函数 1: call_problem_parser
# ============================================================

async def call_problem_parser(
    task_description: str,
    context_summary: str = "",
) -> ToolChunk:
    """分析用户的测试需求，输出结构化的文件生成方案。

    调用时机：用户首次提出测试需求，或用户大幅变更需求方向。

    Args:
        task_description (str):
            用户的测试需求描述
        context_summary (str):
            已生成文件的上下文摘要（续接对话时提供）
    """
    parser = create_problem_parser()

    if context_summary:
        full_task = (
            f"# 当前上下文\n{context_summary}\n\n"
            f"# 新需求\n{task_description}"
        )
    else:
        full_task = task_description

    result_text = ""
    async for evt in parser.reply_stream(UserMsg("协调者", full_task)):
        if monitor:
            monitor.handle_event(evt)
        if "TEXT_BLOCK_DELTA" in str(getattr(evt, 'type', '')):
            result_text += evt.delta
        elif hasattr(evt, 'delta') and "TEXT" in str(getattr(evt, 'type', '')):
            result_text += evt.delta

    return ToolChunk(
        content=[TextBlock(text=result_text or "分析完成")],
        state=ToolResultState.RUNNING,
    )


# ============================================================
# 工具函数 2: call_file_generator（单文件）
# ============================================================

async def call_file_generator(
    generation_instruction: str,
    file_type: str = "",
    output_path: str = "",
    is_modification: bool = False,
    previous_content_json: str = "",
) -> ToolChunk:
    """生成或修改单个测试文件。仅在只有1个文件时使用，>=2个文件请使用 call_batch_file_generator。

    Args:
        generation_instruction (str):
            文件生成/修改的具体要求
        file_type (str):
            文件类型（首次生成时提供）
        output_path (str):
            输出路径
        is_modification (bool):
            是否为修改模式
        previous_content_json (str):
            原始 content JSON 字符串（修改模式时提供）
    """
    agent = create_file_gen_agent()
    result = await _generate_single_file(
        generation_instruction, file_type, output_path,
        is_modification, previous_content_json, agent=agent,
    )

    if file_context and result["content"] and result["output_path"]:
        file_context.record(result["output_path"], result["file_type"], result["content"])

    return ToolChunk(
        content=[TextBlock(text=result["result_text"] or "文件已生成")],
        state=ToolResultState.RUNNING,
    )


# ============================================================
# 工具函数 3: call_batch_file_generator（批量并发）
# ============================================================

async def call_batch_file_generator(
    tasks_json: str,
) -> ToolChunk:
    """批量并发生成多个测试文件。使用 asyncio.gather 并发执行，大幅缩短多文件生成时间。

    调用时机：
    - 问题解析完成后，有 >= 2 个文件需要生成
    - 需求变更后有多个新文件需要生成

    Args:
        tasks_json (str):
            JSON 字符串，格式为任务列表。每个任务包含：
            - instruction (str, 必填): 文件生成指令
            - file_type (str, 必填): 文件类型 (xlsx/docx/pdf/md/py/js/sql/java/txt)
            - output_path (str, 必填): 输出路径，统一在 ./test/ 下
            示例：
            '[{"instruction":"生成登录测试用例","file_type":"py","output_path":"./test/test_login.py"},
              {"instruction":"生成测试数据","file_type":"xlsx","output_path":"./test/login_data.xlsx"}]'
    """
    try:
        tasks = json.loads(tasks_json)
    except json.JSONDecodeError as e:
        return ToolChunk(
            content=[TextBlock(text=f"tasks_json 解析失败: {e}")],
            state=ToolResultState.ERROR,
        )

    if not isinstance(tasks, list) or len(tasks) == 0:
        return ToolChunk(
            content=[TextBlock(text="tasks_json 必须为非空数组")],
            state=ToolResultState.ERROR,
        )

    # 为每个任务创建独立的 Agent 实例并并发执行
    async def _run_one(task: dict) -> dict:
        agent = create_file_gen_agent()
        return await _generate_single_file(
            task.get("instruction", ""),
            task.get("file_type", ""),
            task.get("output_path", ""),
            task.get("is_modification", False),
            task.get("previous_content_json", ""),
            agent=agent,
        )

    results = await asyncio.gather(*[_run_one(t) for t in tasks])

    # 汇总结果并记录到上下文
    lines = []
    for r in results:
        if file_context and r["content"] and r["output_path"]:
            file_context.record(r["output_path"], r["file_type"], r["content"])
        if r["output_path"]:
            lines.append(f"✅ {r['output_path']}")
        else:
            lines.append(f"⚠️ 生成失败: {r['result_text'][:100]}")

    return ToolChunk(
        content=[TextBlock(text="\n".join(lines))],
        state=ToolResultState.RUNNING,
    )
