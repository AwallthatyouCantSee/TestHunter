<script setup>
import { ref, nextTick, onMounted } from 'vue'
import ChatMessage from './components/ChatMessage.vue'
import ChatInput from './components/ChatInput.vue'
import ConversationList from './components/ConversationList.vue'
import {
  streamChat, listFiles, downloadUrl, uploadFiles,
  createSessionId, createSession, listSessions, loadHistory, deleteSession,
} from './api/chat.js'

const messages = ref([])
const isStreaming = ref(false)
const abortCtrl = ref(null)
const files = ref([])
const showFiles = ref(false)
const sessions = ref([])
const currentSessionId = ref(null)

let streamingIdx = -1

async function scrollToBottom() {
  await nextTick()
  const area = document.querySelector('.messages-area')
  if (area) area.scrollTop = area.scrollHeight
}

async function refreshFiles() {
  try {
    const data = currentSessionId.value
      ? await listFiles(currentSessionId.value)
      : await listFiles()
    files.value = data.files
  }
  catch { /* ignore */ }
}

async function refreshSessions() {
  try { const data = await listSessions(); sessions.value = data.sessions }
  catch { /* ignore */ }
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

/** 切换到指定会话 */
async function switchSession(sid) {
  if (sid === currentSessionId.value) return
  currentSessionId.value = sid
  messages.value = []
  try {
    const history = await loadHistory(sid)
    for (const m of history) {
        messages.value.push({ role: m.role, text: m.text, isStreaming: false, status: null, files: m.files || [] })
      }
    await scrollToBottom()
  } catch { /* ignore */ }
  // 切换会话后刷新文件列表
  await refreshFiles()
}

/** 新建对话 */
async function handleNewSession() {
  const sid = createSessionId()
  try {
    await createSession(sid, '新对话')
    await refreshSessions()
    currentSessionId.value = sid
    messages.value = []
    await refreshFiles()
  } catch (e) {
    console.warn('创建会话失败', e)
  }
}

/** 删除指定会话 */
async function handleDeleteSession(sid) {
  if (isStreaming.value) return
  try { await deleteSession(sid) } catch { /* ignore */ }
  await refreshSessions()
  if (currentSessionId.value === sid) {
    // 切换到第一个剩余会话，或新建
    const updated = await listSessions()
    sessions.value = updated.sessions
    if (updated.sessions.length > 0) {
      await switchSession(updated.sessions[0].id)
    } else {
      messages.value = []
      currentSessionId.value = null
    }
  }
  // 删除会话后必须刷新文件列表
  await refreshFiles()
}

/** 发送消息 */
async function handleSend(text, fileList) {
  if (isStreaming.value) return

  // 如果还没有 session，创建新的
  if (!currentSessionId.value) {
    currentSessionId.value = createSessionId()
    try {
      await createSession(currentSessionId.value, text.slice(0, 40) || '新对话')
    } catch (e) {
      console.warn('创建会话失败', e)
    }
  }

  let filePaths = []
  let uploadedNames = []

  if (fileList && fileList.length > 0) {
    try {
      const result = await uploadFiles(currentSessionId.value, fileList)
      filePaths = result.files
      uploadedNames = filePaths.map((f) => f.name)
    } catch (e) {
      messages.value.push({ role: 'agent', text: `❌ 文件上传失败: ${e.message}`, isStreaming: false, status: null, files: [] })
      return
    }
  }

  messages.value.push({ role: 'user', text: text || '(上传文件)', status: null, files: uploadedNames })
  await scrollToBottom()
  messages.value.push({ role: 'agent', text: '', isStreaming: true, status: { text: '正在分析任务', done: false } })
  streamingIdx = messages.value.length - 1
  isStreaming.value = true

  const ctrl = new AbortController()
  abortCtrl.value = ctrl

  let lastToolName = ''

  try {
    for await (const event of streamChat(currentSessionId.value, text || '', filePaths, ctrl.signal)) {
      const msg = messages.value[streamingIdx]
      if (!msg) break
      switch (event.type) {
        case 'TEXT_BLOCK_DELTA':
          // 收到第一个文本块时清除"正在分析任务"状态
          if (!msg.text && msg.status && !msg.status.done) {
            msg.status = null
          }
          msg.text += event.delta
          break
        case 'TOOL_CALL_START':
          lastToolName = event.tool_call_name
          msg.status = {
            text: `正在调用 ${lastToolName}`,
            done: false,
          }
          break
        case 'TOOL_CALL_END':
          msg.status = {
            text: '工具调用完成',
            done: true,
          }
          break
        case 'REPLY_END':
          msg.isStreaming = false
          msg.status = {
            text: `任务已完成`,
            done: true,
          }
          break
      }
      await scrollToBottom()
    }
    // 回复完成后刷新会话列表（标题可能更新）
    await refreshSessions()
    await refreshFiles()
  } catch (err) {
    if (err.name !== 'AbortError') {
      const msg = messages.value[streamingIdx]
      if (msg) { msg.text += `\n\n❌ 错误: ${err.message}`; msg.isStreaming = false; msg.status = null }
    }
  } finally {
    isStreaming.value = false
    streamingIdx = -1
    abortCtrl.value = null
    await scrollToBottom()
  }
}

function handleAbort() { abortCtrl.value?.abort() }

onMounted(async () => {
  await refreshSessions()
  refreshFiles()
})
</script>

<template>
  <div class="app-layout">
    <!-- 会话侧边栏 -->
    <ConversationList
      :sessions="sessions"
      :current-id="currentSessionId"
      @select="switchSession"
      @delete="handleDeleteSession"
      @new="handleNewSession"
    />

    <!-- 聊天区 -->
    <div class="chat-panel">
      <header class="chat-header">
        <span class="title">Friday - 测试服务助手</span>
        <div class="header-actions">
          <button class="files-toggle" @click="showFiles = !showFiles; if (showFiles) refreshFiles()">
            📁 {{ showFiles ? '隐藏文件' : `文件 (${files.length})` }}
          </button>
          <button v-if="isStreaming" class="abort-btn" @click="handleAbort">停止生成</button>
        </div>
      </header>

      <div class="messages-area">
        <div class="messages-list">
          <template v-for="(msg, i) in messages" :key="i">
            <ChatMessage :role="msg.role" :text="msg.text" :is-streaming="msg.isStreaming" :status="msg.status" :files="msg.files || []" />
          </template>
          <div v-if="!currentSessionId" class="empty-hint">
            点击左侧「＋」新建对话，或选择已有对话
          </div>
          <div v-else-if="messages.length === 0" class="empty-hint">
            输入消息开始对话
          </div>
        </div>
      </div>

      <ChatInput @send="handleSend" />
    </div>

    <!-- 文件面板 -->
    <aside v-if="showFiles" class="file-panel">
      <div class="file-header">
        <span class="file-title">生成的文件</span>
        <button class="refresh-btn" @click="refreshFiles">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/>
            <polyline points="21.5 2 16 7.5 21.5 8 22 2.5"/>
          </svg>
        </button>
      </div>
      <div v-if="files.length === 0" class="file-empty">暂无文件</div>
      <ul class="file-list">
        <li v-for="f in files" :key="f.name" class="file-item">
          <span class="file-name" :title="f.name">{{ f.name }}</span>
          <span class="file-size">{{ formatSize(f.size) }}</span>
          <a :href="downloadUrl(f.session_id + '/' + f.name)" :download="f.name" class="file-download">⬇</a>
        </li>
      </ul>
    </aside>
  </div>
</template>

<style scoped>
.app-layout { display: flex; height: 100vh; }
.chat-panel { flex: 1; display: flex; flex-direction: column; min-width: 0; }

.chat-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 20px; background: #fff; border-bottom: 1px solid #e5e7eb;
}
.title { font-size: 16px; font-weight: 600; color: #1f2937; }
.header-actions { display: flex; gap: 8px; align-items: center; }

.files-toggle {
  padding: 6px 12px; background: #f0f0f0; border: 1px solid #d1d5db;
  border-radius: 6px; font-size: 13px; cursor: pointer;
}
.files-toggle:hover { background: #e5e7eb; }

.abort-btn {
  padding: 6px 14px; background: #fef2f2; color: #dc2626;
  border: 1px solid #fecaca; border-radius: 6px; font-size: 13px; cursor: pointer;
}
.abort-btn:hover { background: #fee2e2; }

.messages-area { flex: 1; overflow-y: auto; padding: 0 20px; }
.messages-list { display: flex; flex-direction: column; padding: 16px 0; }
.empty-hint { text-align: center; color: #9ca3af; margin-top: 120px; font-size: 15px; }

.file-panel {
  width: 260px; border-left: 1px solid #e5e7eb; background: #fff;
  display: flex; flex-direction: column; flex-shrink: 0;
}
.file-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 16px; border-bottom: 1px solid #e5e7eb;
}
.file-title { font-size: 14px; font-weight: 600; color: #1f2937; }
.refresh-btn { background: none; border: none; cursor: pointer; padding: 4px 6px; border-radius: 4px; display: flex; align-items: center; justify-content: center; color: #6b7280; }
.refresh-btn:hover { color: #4f46e5; background: #f3f4f6; }
.file-empty { padding: 24px 16px; text-align: center; color: #9ca3af; font-size: 13px; }
.file-list { list-style: none; padding: 0; margin: 0; overflow-y: auto; flex: 1; }
.file-item { display: flex; align-items: center; gap: 8px; padding: 8px 16px; border-bottom: 1px solid #f3f4f6; font-size: 13px; }
.file-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #374151; }
.file-size { color: #9ca3af; flex-shrink: 0; font-size: 12px; }
.file-download { color: #4f46e5; text-decoration: none; font-size: 16px; flex-shrink: 0; }
.file-download:hover { color: #4338ca; }
</style>
