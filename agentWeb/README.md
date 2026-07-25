# agentWeb - Friday 前端界面

基于 Vue 3 + Vite 构建的聊天交互界面，用于与 Friday 测试服务多智能体系统进行对话。

## 功能特性

- 流式对话（SSE）
- 多会话管理（新建、切换、删除）
- 文件上传（最多 3 个）
- 生成文件列表与下载
- 工具调用状态实时展示

## 本地开发

```bash
cd agentWeb
npm install
npm run dev
```

开发服务器默认启动在 `http://localhost:5173`，API 请求通过 Vite 代理到 `http://localhost:8000`。

## 构建

```bash
npm run build
```

输出为 `dist/` 目录。
