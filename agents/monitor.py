# coding: utf-8 format
"""AgentMonitor - 从 FirstAgent.py 提取，供协调者和子智能体共用"""
from datetime import datetime
from agentscope.event import EventType


class AgentMonitor:
    """Agent 执行监控器，收集和显示执行统计信息"""

    def __init__(self, prefix: str = ""):
        self.prefix = prefix  # 在输出中添加前缀区分不同 Agent
        self.reset()

    def reset(self):
        """重置所有统计数据"""
        self.iteration = 0
        self.model_calls = 0
        self.tool_calls = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.thinking_content = []
        self.current_tool = None

    def print_header(self, title: str):
        """打印带格式的标题"""
        print(f"\n{'=' * 60}")
        print(f"  {self.prefix}{title}")
        print(f"{'=' * 60}")

    def print_stats(self):
        """打印执行统计"""
        print(f"\n[{self.prefix}] 执行统计:")
        print(f"   迭代次数: {self.iteration}")
        print(f"   模型调用: {self.model_calls}")
        print(f"   工具调用: {self.tool_calls}")
        print(
            f"   Token 用量: 输入 {self.total_input_tokens} | "
            f"输出 {self.total_output_tokens} | "
            f"总计 {self.total_input_tokens + self.total_output_tokens}"
        )

    def handle_event(self, evt):
        """处理事件并显示信息"""
        type_str = str(evt.type) if evt.type else ""

        # === 回复生命周期 ===
        if "REPLY_START" in type_str:
            self.iteration += 1
            self.print_header(f"Agent 回复 #{self.iteration}")
            print(f"[{self.prefix}] 开始时间: {datetime.now().strftime('%H:%M:%S')}")

        elif "REPLY_END" in type_str:
            self.print_stats()
            print(f"[{self.prefix}] 回复完成")

        # === 模型调用 ===
        elif "MODEL_CALL_START" in type_str:
            self.model_calls += 1
            print(f"\n[{self.prefix}] 调用模型: {getattr(evt, 'model_name', '?')}")

        elif "MODEL_CALL_END" in type_str:
            self.total_input_tokens += getattr(evt, 'input_tokens', 0)
            self.total_output_tokens += getattr(evt, 'output_tokens', 0)
            print(
                f"[{self.prefix}] Token 用量: "
                f"输入 {getattr(evt, 'input_tokens', 0)} | "
                f"输出 {getattr(evt, 'output_tokens', 0)}"
            )

        # === 文本输出 ===
        elif "TEXT_BLOCK_START" in type_str:
            print(f"\n[{self.prefix}] ", end="", flush=True)

        elif "TEXT_BLOCK_DELTA" in type_str:
            print(evt.delta, end="", flush=True)

        elif "TEXT_BLOCK_END" in type_str:
            print()

        # === 思考链 ===
        elif "THINKING_BLOCK_START" in type_str:
            print(f"\n[{self.prefix}] 思考过程:")

        elif "THINKING_BLOCK_DELTA" in type_str:
            print(f"   {evt.delta}", end="", flush=True)
            self.thinking_content.append(f"   {evt.delta}")

        elif "THINKING_BLOCK_END" in type_str:
            print()

        # === 工具调用 ===
        elif "TOOL_CALL_START" in type_str:
            self.tool_calls += 1
            self.current_tool = getattr(evt, 'tool_call_name', '?')
            print(f"\n[{self.prefix}] 工具调用: {self.current_tool}")

        elif "TOOL_CALL_END" in type_str:
            print(f"[{self.prefix}]   工具调用完成")

        # === 工具结果 ===
        elif "TOOL_RESULT_START" in type_str:
            print(f"\n[{self.prefix}] 工具结果 ({getattr(evt, 'tool_call_name', '?')}):")

        elif "TOOL_RESULT_TEXT_DELTA" in type_str:
            print(f"   {evt.delta}", end="", flush=True)

        elif "TOOL_RESULT_END" in type_str:
            print()

        # === 迭代限制 ===
        elif "EXCEED_MAX_ITERS" in type_str:
            print(f"\n[{self.prefix}] 警告: 超过最大迭代次数限制！")
