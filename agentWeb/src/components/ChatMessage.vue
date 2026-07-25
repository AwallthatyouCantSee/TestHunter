<script setup>
defineProps({
  role: {
    type: String,
    required: true, // 'user' | 'agent'
  },
  text: {
    type: String,
    default: '',
  },
  isStreaming: {
    type: Boolean,
    default: false,
  },
  /** { text: '正在调用 xxx', done: false } | { text: 'xxx 已完成', done: true } */
  status: {
    type: Object,
    default: null,
  },
  /** 用户上传的文件名列表 */
  files: {
    type: Array,
    default: () => [],
  },
})
</script>

<template>
  <div :class="['message', role]">
    <div class="avatar">{{ role === 'user' ? '👤' : '🤖' }}</div>
    <div class="body">
      <!-- 用户上传的文件标签 -->
      <div v-if="role === 'user' && files.length > 0" class="file-badges">
        <div v-for="(f, i) in files" :key="i" class="file-badge">
          <span class="fb-icon">📄</span>
          <span class="fb-name">{{ f }}</span>
        </div>
      </div>
      <div class="bubble">
        <template v-if="text">
          <div class="content" v-text="text"></div>
          <span v-if="isStreaming" class="cursor">|</span>
        </template>
        <div v-else-if="isStreaming && role === 'agent'" class="streaming-placeholder">正在完成任务...</div>
        <div v-else class="content">...</div>
      </div>
      <!-- 状态指示器 -->
      <div v-if="status" :class="['status-line', status.done ? 'done' : 'running']">
        <span v-if="!status.done" class="spinner-icon"></span>
        <span v-else class="check-icon">✓</span>
        <span class="status-text">{{ status.text }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.message {
  display: flex;
  gap: 12px;
  padding: 12px 0;
  max-width: 85%;
}

.message.user {
  flex-direction: row-reverse;
  align-self: flex-end;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
  background: #f0f0f0;
}

.body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.bubble {
  padding: 10px 16px;
  border-radius: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.user .bubble {
  background: #4f46e5;
  color: #fff;
}

.agent .bubble {
  background: #f3f4f6;
  color: #1f2937;
}

.cursor {
  animation: blink 0.8s infinite;
  color: #4f46e5;
}

.streaming-placeholder {
  color: #6b7280;
  font-size: 13px;
  font-style: italic;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

/* 状态指示器 */
.status-line {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding-left: 4px;
  font-size: 12px;
}

.status-line.running {
  color: #6366f1;
}

.status-line.done {
  color: #16a34a;
}

.spinner-icon {
  width: 13px;
  height: 13px;
  border: 2px solid #c7d2fe;
  border-top-color: #6366f1;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  flex-shrink: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.check-icon {
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
}

.status-text {
  white-space: nowrap;
}

/* 文件标签（用户上传） */
.file-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
}

.file-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  background: #fff;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 11px;
  color: #374151;
  max-width: 180px;
  cursor: default;
}

.fb-icon {
  font-size: 13px;
  flex-shrink: 0;
}

.fb-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
