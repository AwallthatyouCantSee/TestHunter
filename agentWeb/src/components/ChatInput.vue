<script setup>
import { ref, computed } from 'vue'

const emit = defineEmits(['send'])
const MAX_FILES = 3

const input = ref('')
const fileInputRef = ref(null)
const pendingFiles = ref([])  // 待上传的 File 对象
const uploading = ref(false)

const canSend = computed(() => input.value.trim() || pendingFiles.value.length > 0)

function handleSend() {
  const text = input.value.trim()
  if (!canSend.value || uploading.value) return
  emit('send', text, [...pendingFiles.value])
  input.value = ''
  pendingFiles.value = []
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

function handleUploadClick() {
  if (pendingFiles.value.length >= MAX_FILES) return
  fileInputRef.value?.click()
}

function handleFileChange(e) {
  const files = e.target.files
  if (!files || files.length === 0) return
  for (const f of files) {
    if (pendingFiles.value.length >= MAX_FILES) break
    // 去重
    if (!pendingFiles.value.some((x) => x.name === f.name && x.size === f.size)) {
      pendingFiles.value.push(f)
    }
  }
  e.target.value = ''
}

function removeFile(index) {
  pendingFiles.value.splice(index, 1)
}
</script>

<template>
  <div class="input-wrapper">
    <!-- 文件标签 -->
    <div v-if="pendingFiles.length > 0" class="file-tags">
      <div
        v-for="(f, i) in pendingFiles"
        :key="f.name + f.size"
        class="file-tag"
      >
        <span class="tag-icon">📄</span>
        <span class="tag-name">{{ f.name }}</span>
        <span class="tag-size">{{ (f.size / 1024).toFixed(1) }}KB</span>
        <button class="tag-remove" @click="removeFile(i)" :disabled="uploading">✕</button>
      </div>
      <span v-if="pendingFiles.length >= MAX_FILES" class="tag-limit">已达上限 {{ MAX_FILES }} 个</span>
    </div>

    <div class="input-area">
      <textarea
        v-model="input"
        class="input-box"
        placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
        rows="1"
        @keydown="handleKeydown"
        :disabled="uploading"
      ></textarea>
      <button class="send-btn" @click="handleSend" :disabled="!canSend || uploading">
        {{ uploading ? '上传中...' : '发送' }}
      </button>
      <button
        class="upload-btn"
        title="上传文件（最多3个）"
        @click="handleUploadClick"
        :disabled="pendingFiles.length >= MAX_FILES || uploading"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <circle cx="12" cy="12" r="10"/>
          <line x1="12" y1="8" x2="12" y2="16"/>
          <line x1="8" y1="12" x2="16" y2="12"/>
        </svg>
      </button>
      <input
        ref="fileInputRef"
        type="file"
        multiple
        accept=".py,.js,.ts,.java,.go,.rs,.c,.cpp,.cs,.rb,.php,.swift,.kt,.sql,.json,.xml,.yaml,.yml,.toml,.ini,.cfg,.md,.txt,.csv,.html,.css,.vue,.jsx,.tsx,.sh,.bat,.ps1,.xlsx,.xls,.docx,.doc,.pdf,.png,.jpg,.jpeg,.gif,.bmp,.svg,.zip,.tar,.gz"
        style="display: none"
        @change="handleFileChange"
      />
    </div>
  </div>
</template>

<style scoped>
.input-wrapper {
  max-width: 768px;
  width: 100%;
  margin: 0 auto;
  padding: 0 20px 24px;
  background: #f9fafb;
}

/* 文件标签 */
.file-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.file-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: #eef2ff;
  border: 1px solid #c7d2fe;
  border-radius: 6px;
  font-size: 12px;
  color: #3730a3;
}

.tag-icon {
  font-size: 13px;
}

.tag-name {
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tag-size {
  color: #6b7280;
  flex-shrink: 0;
}

.tag-remove {
  background: none;
  border: none;
  color: #9ca3af;
  cursor: pointer;
  font-size: 12px;
  padding: 0 2px;
  line-height: 1;
}

.tag-remove:hover:not(:disabled) {
  color: #dc2626;
}

.tag-limit {
  font-size: 12px;
  color: #f59e0b;
  align-self: center;
}

.input-area {
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  align-items: flex-end;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.input-box {
  flex: 1;
  padding: 8px 4px;
  border: none;
  border-radius: 0;
  font-size: 14px;
  resize: none;
  outline: none;
  font-family: inherit;
  line-height: 1.5;
  max-height: 120px;
  background: transparent;
}

.send-btn {
  padding: 8px 18px;
  background: #4f46e5;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s;
}

.send-btn:hover:not(:disabled) {
  background: #4338ca;
}

.send-btn:disabled {
  background: #a5b4fc;
  cursor: not-allowed;
}

.upload-btn {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  color: #6b7280;
  border: 1.5px dashed #d1d5db;
  border-radius: 8px;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.15s;
}

.upload-btn:hover:not(:disabled) {
  color: #4f46e5;
  border-color: #4f46e5;
  background: rgba(79, 70, 229, 0.06);
}

.upload-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
