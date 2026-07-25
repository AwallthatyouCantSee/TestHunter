/**
 * AgentScope SSE 聊天客户端 + 文件 API + 会话管理
 */

// ==================== 会话管理 ====================

/** 生成新 session_id */
export function createSessionId() {
  return crypto.randomUUID()
}

/** 列出所有会话 */
export async function listSessions() {
  const res = await fetch('/api/sessions/')
  if (!res.ok) throw new Error('获取会话列表失败')
  return res.json()
}

/** 立即创建新会话（不等第一次聊天） */
export async function createSession(sessionId, title) {
  const res = await fetch('/api/sessions/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, title: title || '新对话' }),
  })
  if (!res.ok) throw new Error('创建会话失败')
  return res.json()
}

/** 加载指定会话的历史消息 */
export async function loadHistory(sessionId) {
  const res = await fetch(`/api/sessions/${sessionId}/messages`)
  if (!res.ok) throw new Error('加载历史失败')
  const data = await res.json()
  return data.messages || []
}

/** 删除指定会话 */
export async function deleteSession(sessionId) {
  const res = await fetch(`/api/sessions/${sessionId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('删除会话失败')
  return res.json()
}

// ==================== 聊天 ====================

export async function* streamChat(sessionId, content, filePaths, signal) {
  const blocks = []
  const files = []

  if (content) blocks.push({ type: 'text', text: content })
  if (filePaths && filePaths.length > 0) {
    for (const f of filePaths) {
      files.push(f.name)
      blocks.push({
        type: 'text',
        text: `\n[用户上传文件: ${f.name}]\n  ${f.path}`,
      })
    }
  }

  const res = await fetch('/api/chat/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-User-ID': 'default' },
    body: JSON.stringify({
      agent_id: 'friday',
      session_id: sessionId,
      files,
      input: { name: 'user', content: blocks, role: 'user' },
    }),
    signal,
  })

  if (!res.ok) {
    const detail = await res.text()
    throw new Error(`请求失败 (${res.status}): ${detail}`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const json = line.slice(6).trim()
        if (json) {
          try { yield JSON.parse(json) }
          catch (e) { console.warn('[SSE parse error]', e, json) }
        }
      }
    }
  }
}

// ==================== 文件 ====================

export async function uploadFiles(sessionId, fileList) {
  const formData = new FormData()
  for (const file of fileList) formData.append('files', file)
  const url = `/api/upload/?session_id=${encodeURIComponent(sessionId)}`
  const res = await fetch(url, { method: 'POST', body: formData })
  if (!res.ok) { const d = await res.text(); throw new Error(`上传失败 (${res.status}): ${d}`) }
  return res.json()
}

export async function listFiles(sessionId) {
  const url = sessionId ? `/api/files/?session_id=${encodeURIComponent(sessionId)}` : '/api/files/'
  const res = await fetch(url)
  if (!res.ok) throw new Error('获取文件列表失败')
  return res.json()
}

export function downloadUrl(name) {
  // name 格式为 "session_id/filename"
  const idx = name.indexOf('/')
  if (idx > 0) {
    const sid = name.slice(0, idx)
    const fn = name.slice(idx + 1)
    return `/api/files/${encodeURIComponent(sid)}/${encodeURIComponent(fn)}`
  }
  return `/api/files/${encodeURIComponent(name)}`
}
