<script setup>
import { computed } from 'vue'

const props = defineProps({
  sessions: { type: Array, default: () => [] },
  currentId: { type: String, default: '' },
})
const emit = defineEmits(['select', 'delete', 'new'])

const sorted = computed(() =>
  [...props.sessions].sort((a, b) =>
    (b.created_at || '').localeCompare(a.created_at || '')
  )
)
</script>

<template>
  <div class="conv-sidebar">
    <div class="sidebar-header">
      <span class="sidebar-title">对话列表</span>
      <button class="new-btn" @click="emit('new')" title="新建对话">＋</button>
    </div>

    <div class="conv-list">
      <div
        v-for="s in sorted"
        :key="s.id"
        :class="['conv-item', { active: s.id === currentId }]"
        @click="emit('select', s.id)"
      >
        <div class="conv-main">
          <span class="conv-title">{{ s.title || '未命名' }}</span>
          <span class="conv-preview">{{ s.preview }}</span>
        </div>
        <button
          class="conv-del"
          title="删除此对话"
          @click.stop="emit('delete', s.id)"
        >✕</button>
      </div>
      <div v-if="sorted.length === 0" class="conv-empty">
        暂无对话
      </div>
    </div>
  </div>
</template>

<style scoped>
.conv-sidebar {
  width: 240px;
  border-right: 1px solid #e5e7eb;
  background: #fafafa;
  display: flex;
  flex-direction: column;
  height: 100vh;
  flex-shrink: 0;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 14px 10px;
  height: 62px;
  border-bottom: 1px solid #e5e7eb;
}

.sidebar-title {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
}

.new-btn {
  width: 28px;
  height: 28px;
  font-size: 18px;
  line-height: 1;
  background: #4f46e5;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.new-btn:hover {
  background: #4338ca;
}

.conv-list {
  flex: 1;
  overflow-y: auto;
}

.conv-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
  transition: background 0.1s;
}

.conv-item:hover {
  background: #f3f4f6;
}

.conv-item.active {
  background: #eef2ff;
  border-left: 3px solid #4f46e5;
}

.conv-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.conv-title {
  font-size: 13px;
  font-weight: 500;
  color: #1f2937;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-preview {
  font-size: 11px;
  color: #9ca3af;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-del {
  background: none;
  border: none;
  color: #d1d5db;
  font-size: 14px;
  cursor: pointer;
  padding: 2px 6px;
  flex-shrink: 0;
  border-radius: 4px;
}

.conv-del:hover {
  color: #dc2626;
  background: #fee2e2;
}

.conv-empty {
  padding: 24px 12px;
  text-align: center;
  color: #9ca3af;
  font-size: 13px;
}
</style>
