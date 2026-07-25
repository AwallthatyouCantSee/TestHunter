# Friday - 测试服务多智能体系统

基于 [AgentScope](https://github.com/modelscope/agentscope) 框架构建的测试服务多智能体协调系统，通过对话方式为用户提供测试用例、测试数据、Mock 服务脚本和测试报告的生成与增量修改服务。

## 架构概览

```
用户 -> Web 前端 (Vue 3) -> FastAPI 服务 -> 协调者 Agent (Friday)
                                      |
              +-----------------------+-----------------------+
              |                                               |
    问题解析助手                              文件生成助手
    (测试需求分析)                            (多格式文件生成)
```

- **协调者 (Friday)**：统一接收用户需求，智能调度子智能体，支持增量修改时的上下文注入
- **问题解析助手**：分析测试需求，判断测试类型，输出结构化文件生成方案
- **文件生成助手**：根据方案生成 `xlsx`/`docx`/`pdf`/`py`/`js`/`sql`/`java`/`md`/`txt` 等格式的测试文件

## 目录结构

```
.
├── FirstAgent.py           # 命令行入口（协调者交互式对话）
├── service.py              # FastAPI Web 服务入口
├── system_prompt.txt       # 协调者系统提示词
├── requirements.txt        # Python 依赖
├── .env.example            # 环境变量模板
├── agents/                 # 子智能体与上下文管理
│   ├── problem_parser.py   # 问题解析助手
│   ├── file_gen_agent.py   # 文件生成助手
│   ├── tool_wrappers.py    # 工具函数封装
│   ├── context.py          # 文件生成上下文（支持增量修改）
│   └── monitor.py          # Agent 执行监控器
├── tools/                  # 自定义工具
│   ├── file_generator.py   # 文件生成工具
│   └── format_read.py      # 格式化读取工具
├── skills/                 # AgentScope Skill 文档
│   ├── first_generation/
│   ├── incremental_modification/
│   └── script_execution/
├── agentWeb/               # Vue 3 前端
│   ├── src/
│   ├── package.json
│   └── README.md
└── AgentScopeDevTips/      # 开发技巧文档
```

## 环境要求

- Python 3.10+
- Node.js 18+（前端开发）
- Redis 6.0+（会话与状态存储）

## 快速开始

### 1. 克隆与安装

```bash
git clone <repo-url>
cd testHunter

# 安装 Python 依赖
pip install -r requirements.txt

# 安装前端依赖
cd agentWeb
npm install
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 DASHSCOPE_API_KEY
```

### 3. 启动 Redis

确保本地 Redis 运行在 `localhost:6379`，或通过环境变量自定义地址。

### 4. 启动后端服务

```bash
uvicorn service:app --host 0.0.0.0 --port 8000
```

### 5. 启动前端（开发模式）

```bash
cd agentWeb
npm run dev
```

前端默认地址：`http://localhost:5173`

### 命令行模式

如果不使用 Web 界面，也可以直接运行命令行版本：

```bash
python FirstAgent.py
```

## 核心特性

- **多智能体 Handoffs 协作**：协调者根据需求自动路由到解析或生成助手
- **批量并发生成**：多文件场景通过 `asyncio.gather` 并发执行
- **增量修改**：基于 `FileGenerationContext` 保存原始 content JSON，支持直接修改后重新生成
- **SSE 流式输出**：前端实时展示文本生成、工具调用和状态变化
- **会话持久化**：对话历史和 Agent 状态通过 Redis 持久化

## 模型配置

默认使用 DashScope `mimo-v2.5` 模型，通过环境变量配置：

| 变量 | 说明 | 默认值 |
|---|---|---|
| `DASHSCOPE_API_KEY` | API 密钥 | 必填 |
| `MODEL_BASE_URL` | 模型服务地址 | `https://api.xiaomimimo.com/v1` |

## License

MIT
