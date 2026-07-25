# coding: utf-8 format
r"""Friday Agent Web 服务入口

启动方式:
    cd c:\code\testHunter
    uvicorn service:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations
import json as _json
import os
import sys
import uuid
import datetime
import traceback
from pathlib import Path

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse

from agentscope.agent import Agent
from agentscope.agent._config import ReActConfig
from agentscope.tool import Toolkit, Bash, Grep, Glob, Read, Write, Edit, FunctionTool
from agentscope.credential import DashScopeCredential
from agentscope.model import DashScopeChatModel
from agentscope.message import UserMsg, Msg
from agentscope.state import AgentState
from agentscope.permission import PermissionRule, PermissionBehavior
from agentscope.skill import LocalSkillLoader
from dotenv import load_dotenv

import redis.asyncio as _aredis

sys.path.insert(0, str(Path(__file__).parent))

from agents.context import FileGenerationContext
from agents.monitor import AgentMonitor
from agents.tool_wrappers import (
    call_problem_parser, call_file_generator, call_batch_file_generator,
    set_shared_context,
)

load_dotenv()
from tools.format_read import FormatRead

# ==================== Redis ====================
redis_client = _aredis.Redis(host="localhost", port=6379, decode_responses=True)

SESSIONS_SET = "friday:sessions"

def _state_key(sid: str) -> str:  return f"friday:session:{sid}:state"
def _msg_key(sid: str) -> str:    return f"friday:session:{sid}:messages"
def _meta_key(sid: str) -> str:   return f"friday:session:{sid}:meta"

# ==================== Agent 工厂 ====================
file_context = FileGenerationContext()
monitor = AgentMonitor(prefix="协调者")
set_shared_context(file_context, monitor)

def load_system_prompt(session_id: str) -> str:
    prompt_file = Path(__file__).parent / "system_prompt.txt"
    try:
        prompt = prompt_file.read_text("utf-8")
    except FileNotFoundError:
        return "你是一个测试服务协调者。"
    session_dir = f"C:\\code\\testHunter\\test\\{session_id}"
    prompt = prompt.replace("{{SESSION_DIR}}", session_dir)
    prompt = prompt.replace("{{SESSION_ID}}", session_id)
    return prompt

def _make_agent(session_id: str = "default") -> Agent:
    state = AgentState()
    tools = [
        "Bash", "Grep", "Glob", "Read", "FormatRead", "Write", "Edit",
        "call_problem_parser", "call_file_generator", "call_batch_file_generator",
    ]
    for t in tools:
        state.permission_context.allow_rules[t] = [
            PermissionRule(tool_name=t, rule_content=None,
                           behavior=PermissionBehavior.ALLOW, source="userSettings")
        ]

    toolkit = Toolkit(tools=[
        Bash(), Grep(), Glob(), Read(), FormatRead(), Write(), Edit(),
        FunctionTool(call_problem_parser),
        FunctionTool(call_file_generator),
        FunctionTool(call_batch_file_generator),
    ], skills_or_loaders=[
        LocalSkillLoader(directory="./skills", scan_subdir=True),
    ])

    return Agent(
        name="Friday",
        system_prompt=load_system_prompt(session_id),
        model=DashScopeChatModel(
            credential=DashScopeCredential(
                api_key=os.environ.get("DASHSCOPE_API_KEY", ""),
                base_url="https://api.xiaomimimo.com/v1",
            ),
            model="mimo-v2.5",
        ),
        toolkit=toolkit,
        state=state,
        react_config=ReActConfig(max_iters=60),
    )

# ==================== FastAPI ====================
OUTPUT_DIR = Path(__file__).parent / "test"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Friday Agent")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _extract_text(content) -> str:
    if isinstance(content, list):
        return "".join(b.get("text", "") for b in content if b.get("type") == "text")
    return str(content)


def _get_agent_reply_text(agent: Agent) -> str:
    """从 AgentState.context 中提取最后一次 assistant 回复的纯文本"""
    for msg in reversed(agent.state.context):
        if isinstance(msg, Msg) and msg.role == "assistant":
            texts = [
                b.text for b in msg.content
                if hasattr(b, "text") and b.text
            ]
            return "".join(texts)
    return ""


# ==================== 聊天 API ====================

@app.post("/chat/")
async def chat(request: Request):
    body = await request.json()
    session_id = body.get("session_id", "default")
    text = _extract_text(body["input"]["content"])

    # 恢复 state
    saved = await redis_client.get(_state_key(session_id))

    # 创建 session 输出目录
    session_output_dir = Path(__file__).parent / "test" / session_id
    session_output_dir.mkdir(parents=True, exist_ok=True)

    agent = _make_agent(session_id)
    is_new = True
    if saved:
        try:
            agent.state = AgentState.model_validate_json(saved)
            is_new = False
            print(f"[LOAD] session={session_id} history={len(agent.state.context)}", flush=True)
        except Exception:
            print(f"[WARN] bad state for {session_id}", flush=True)

    now = datetime.datetime.now().isoformat()

    # 新会话 → 写入 meta
    if is_new:
        title = text[:40] + ("..." if len(text) > 40 else "") if text else "新对话"
        await redis_client.hset(_meta_key(session_id), mapping={"title": title, "created_at": now})
        await redis_client.zadd(SESSIONS_SET, {session_id: datetime.datetime.now().timestamp()})

    # 存用户消息（text 只含用户输入，files 单独存）
    files = body.get("files", [])
    # 提取用户真正输入的文本（过滤掉文件路径信息）
    user_text = "".join(
        b.get("text", "")
        for b in body["input"]["content"]
        if b.get("type") == "text" and "[用户上传文件:" not in b.get("text", "")
    ).strip()
    await redis_client.rpush(_msg_key(session_id),
        _json.dumps({"role": "user", "text": user_text, "files": files, "ts": now}))

    async def stream():
        # 累积缓冲区
        thinking_buf = []
        tool_output_buf = []
        try:
            async for event in agent.reply_stream(UserMsg("User", text)):
                event_type = getattr(event, 'type', type(event).__name__)
                detail = ""
                if event_type == "THINKING_BLOCK_DELTA":
                    d = getattr(event, "delta", "")
                    if d:
                        thinking_buf.append(d)
                elif event_type == "THINKING_BLOCK_END":
                    full = "".join(thinking_buf).strip()
                    thinking_buf.clear()
                    if full:
                        print(f"[THINKING]\n{full}\n", flush=True)
                elif event_type == "TOOL_RESULT_TEXT_DELTA":
                    d = getattr(event, "delta", "")
                    if d:
                        tool_output_buf.append(d)
                elif event_type == "TOOL_RESULT_END":
                    full = "".join(tool_output_buf).strip()
                    tool_output_buf.clear()
                    state = getattr(event, 'state', '?')
                    if full:
                        print(f"[TOOL_RESULT state={state}]\n{full}\n", flush=True)
                    else:
                        print(f"[TOOL_RESULT state={state}]", flush=True)
                elif event_type == "TOOL_CALL_START":
                    print(f"[TOOL] {event.tool_call_name}", flush=True)
                elif event_type == "TOOL_CALL_END":
                    pass
                elif event_type == "MODEL_CALL_START":
                    print(f"[MODEL] 调用 LLM...", flush=True)
                elif event_type == "MODEL_CALL_END":
                    usage = getattr(event, "usage", None)
                    if usage:
                        print(f"[MODEL] 返回 tokens={usage}", flush=True)
                    else:
                        print(f"[MODEL] 返回", flush=True)
                elif event_type == "EXCEED_MAX_ITERS":
                    print(f"[WARN] agent={event.name} 达到最大迭代次数，对话强制终止！", flush=True)
                elif event_type == "TOOL_CALL_DELTA":
                    continue
                elif event_type in ("TEXT_BLOCK_START", "TEXT_BLOCK_END", "REPLY_END",
                                    "THINKING_BLOCK_START", "TOOL_RESULT_START"):
                    pass

                try:
                    yield f"data: {event.model_dump_json()}\n\n"
                except Exception as de:
                    yield f"data: {_json.dumps({'type': event_type, 'error': str(de)}, default=str)}\n\n"
        except Exception as e:
            print(f"[STREAM ERROR] {e}", flush=True)
            traceback.print_exc()
            yield f"data: {_json.dumps({'type': 'ErrorEvent', 'error': str(e)})}\n\n"
        finally:
            # 存 state
            await redis_client.set(_state_key(session_id), agent.state.model_dump_json())
            # 存 agent 回复
            reply = _get_agent_reply_text(agent)
            if reply:
                await redis_client.rpush(_msg_key(session_id),
                    _json.dumps({"role": "agent", "text": reply, "ts": datetime.datetime.now().isoformat()}))
            print(f"[SAVE] session={session_id} history={len(agent.state.context)}", flush=True)

    return StreamingResponse(stream(), media_type="text/event-stream")


# ==================== 会话管理 API ====================

@app.post("/sessions/")
async def create_session(request: Request):
    """立即创建一个新会话（不等第一次聊天）"""
    body = await request.json()
    session_id = body.get("session_id", uuid.uuid4().hex)
    now = datetime.datetime.now().isoformat()
    # 写入 meta
    await redis_client.hset(_meta_key(session_id), mapping={
        "title": body.get("title", "新对话"),
        "created_at": now,
    })
    await redis_client.zadd(SESSIONS_SET, {session_id: datetime.datetime.now().timestamp()})
    # 创建输出目录
    session_dir = OUTPUT_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "session_id": session_id}

@app.get("/sessions/")
async def list_sessions():
    """列出所有会话（按创建时间倒序）"""
    ids = await redis_client.zrevrange(SESSIONS_SET, 0, -1)
    result = []
    for sid in ids:
        meta = await redis_client.hgetall(_meta_key(sid))
        # 获取最后一条消息作为预览
        msgs = await redis_client.lrange(_msg_key(sid), -1, -1)
        last_msg = ""
        if msgs:
            last_msg = _json.loads(msgs[0]).get("text", "")[:50]
        result.append({
            "id": sid,
            "title": meta.get("title", "未命名"),
            "created_at": meta.get("created_at", ""),
            "preview": last_msg,
        })
    return {"sessions": result}


@app.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str):
    items = await redis_client.lrange(_msg_key(session_id), 0, -1)
    messages = [_json.loads(item) for item in items]
    return {"session_id": session_id, "messages": messages}


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    await redis_client.delete(_state_key(session_id), _msg_key(session_id), _meta_key(session_id))
    await redis_client.zrem(SESSIONS_SET, session_id)
    # 清理 session 输出目录
    session_dir = OUTPUT_DIR / session_id
    if session_dir.is_dir():
        import shutil
        shutil.rmtree(session_dir, ignore_errors=True)
        print(f"[CLEAN] 已删除 session 目录: {session_dir}", flush=True)
    return {"ok": True}


# ==================== 文件 API ====================

@app.get("/files/")
async def list_files(session_id: str | None = None):
    files = []
    targets = [OUTPUT_DIR / session_id] if session_id else [d for d in sorted(OUTPUT_DIR.iterdir()) if d.is_dir()]
    for session_dir in targets:
        if session_dir.is_dir():
            for f in sorted(session_dir.iterdir()):
                if f.is_file():
                    s = f.stat()
                    files.append({
                        "name": f.name,
                        "session_id": session_dir.name,
                        "size": s.st_size,
                        "modified": datetime.datetime.fromtimestamp(s.st_mtime).isoformat(),
                    })
    return {"files": files}


@app.get("/files/{session_id}/{file_name}")
async def download_file(session_id: str, file_name: str):
    fp = (OUTPUT_DIR / session_id / file_name).resolve()
    if not str(fp).startswith(str(OUTPUT_DIR.resolve())):
        return {"error": "不允许访问该路径"}
    if not fp.is_file():
        return {"error": "文件不存在"}
    return FileResponse(str(fp), filename=file_name)


@app.post("/upload/")
async def upload_files(session_id: str, files: list[UploadFile] = File(...)):
    session_upload_dir = UPLOAD_DIR / session_id
    session_upload_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for f in files:
        safe_name = Path(f.filename or "unknown").name
        sp = session_upload_dir / safe_name
        c = 1
        stem, sfx = sp.stem, sp.suffix
        while sp.exists():
            sp = session_upload_dir / f"{stem}_{c}{sfx}"; c += 1
        content = await f.read()
        sp.write_bytes(content)
        saved.append({"name": safe_name, "path": str(sp.resolve()), "size": len(content)})
    return {"files": saved}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("service:app", host="0.0.0.0", port=8000, reload=True)
