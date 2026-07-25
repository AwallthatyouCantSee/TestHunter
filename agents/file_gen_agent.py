# coding: utf-8 format
import os

from agentscope.agent import Agent
from agentscope.model import DashScopeChatModel
from agentscope.credential import DashScopeCredential
from agentscope.tool import Toolkit

from tools.file_generator import FileGenerator


def create_file_gen_agent() -> Agent:
    """创建文件生成助手 Agent（配备 FileGenerator 工具）"""
    params = DashScopeChatModel.Parameters(
        thinking_enable=False,  # 显式关闭思考链
        max_tokens=4096,         # 工具调用输出很短，不用默认值
        temperature=0,           # 不需要创造性，确定性输出
    )

    return Agent(
        name="文件生成助手",
        system_prompt=(
            "你是文件生成工具的执行器,收到指令后立即调用 FileGenerator 工具生成文件。\n\n"

            "**工作模式：**\n"
            "- 生产模式：根据 instruction 中的文件方案,直接调用 FileGenerator 生成文件\n"
            "- 修改模式：收到 original content 时,直接修改对应字段后调用 FileGenerator 覆盖文件\n\n"

            "**规则：**\n"
            "- 收到消息后立即调用工具，不需要任何解释或说明\n"
            "- 工具返回成功后,回复 'OK' 即可，不要说多余的话\n"
            "- 禁止验证目录是否存在,FileGenerator 会自动创建目录"
        ),
        model=DashScopeChatModel(
            credential=DashScopeCredential(
                api_key=os.environ.get("DASHSCOPE_API_KEY", ""),
                base_url="https://api.xiaomimimo.com/v1",
            ),
            model="mimo-v2.5",
            stream=False,
            parameters=params,
        ),
        toolkit=Toolkit(tools=[FileGenerator()]),
    )
