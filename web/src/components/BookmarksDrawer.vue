<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { CollectionTag, Delete, Edit, Picture, Position } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import { useBookmarkStore } from '@/stores/bookmark'
import type { Bookmark } from '@/stores/bookmark'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits(['update:modelValue'])

const bookmarkStore = useBookmarkStore()

const autoBookmarks = computed(() => bookmarkStore.bookmarks.filter(item => item.kind === 'auto'))
const manualBookmarks = computed(() => bookmarkStore.bookmarks.filter(item => item.kind === 'manual'))

const sortLabels: Record<string, string> = {
  modified_time: '修改日期',
  file_name: '文件名',
  file_size: '大小'
}

const contextLabel = (bookmark: Bookmark) => {
  const parts: string[] = []
  if (bookmark.is_favorites) {
    parts.push('收藏夹')
  } else if (bookmark.folder_id) {
    parts.push(bookmark.folder_name || '未知文件夹')
  } else {
    parts.push('所有照片')
  }
  if (bookmark.search_query) parts.push(`搜索「${bookmark.search_query}」`)
  const sort = sortLabels[bookmark.sort_by] || bookmark.sort_by
  parts.push(`${sort} ${bookmark.sort_order === 'ASC' ? '升序' : '降序'}`)
  return parts.join(' · ')
}

const anchorName = (bookmark: Bookmark) =>
  bookmark.image_file_name || bookmark.anchor_file_name || '原图已删除'

const thumbnailUrl = (bookmark: Bookmark) =>
  bookmark.anchor_exists ? `/api/images/${bookmark.anchor_image_id}/thumbnail?size=small` : ''

const formattedTime = (value: string) => {
  if (!value) return ''
  const date = new Date(value)
  return isNaN(date.getTime()) ? value : date.toLocaleString()
}

const close = () => emit('update:modelValue', false)

const handleRestore = async (bookmark: Bookmark) => {
  const ok = await bookmarkStore.restore(bookmark)
  if (ok) close()
}

const handleRename = async (bookmark: Bookmark) => {
  try {
    const result = await ElMessageBox.prompt('请输入新的书签名称', '重命名书签', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputValue: bookmark.name,
      inputPattern: /^.{1,100}$/,
      inputErrorMessage: '名称长度为 1-100 个字符'
    })
    const name = (result as any).value?.trim()
    if (name && name !== bookmark.name) {
      await bookmarkStore.rename(bookmark.id, name)
    }
  } catch {
    // cancelled
  }
}

const handleDelete = async (bookmark: Bookmark) => {
  try {
    await ElMessageBox.confirm(`确定删除书签“${bookmark.name}”吗？`, '删除书签', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await bookmarkStore.remove(bookmark.id)
  } catch {
    // cancelled
  }
}

watch(() => props.modelValue, (visible) => {
  if (visible) bookmarkStore.fetchBookmarks()
}, { immediate: true })
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    title="书签"
    size="min(380px, 92vw)"
    append-to-body
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="bookmarks-panel">
      <div v-if="autoBookmarks.length > 0" class="bookmark-section">
        <div class="section-title">
          <el-icon><Position /></el-icon>
          <span>继续浏览</span>
        </div>
        <button
          v-for="bookmark in autoBookmarks"
          :key="bookmark.id"
          class="bookmark-card auto-card"
          type="button"
          @click="handleRestore(bookmark)"
        >
          <div class="auto-icon">
            <el-icon><CollectionTag /></el-icon>
          </div>
          <div class="bookmark-body">
            <div class="bookmark-name">上次浏览位置</div>
            <div class="bookmark-meta">{{ contextLabel(bookmark) }}</div>
            <div class="bookmark-anchor">{{ anchorName(bookmark) }}</div>
          </div>
          <span class="restore-hint">继续</span>
        </button>
      </div>

      <div class="bookmark-section">
        <div class="section-title">
          <el-icon><CollectionTag /></el-icon>
          <span>我的书签</span>
        </div>

        <div v-if="manualBookmarks.length === 0" class="empty-bookmarks">
          在图片网格顶部或灯箱工具栏点击“书签”，即可保存当前位置。
        </div>

        <div
          v-for="bookmark in manualBookmarks"
          :key="bookmark.id"
          class="bookmark-card"
          @click="handleRestore(bookmark)"
        >
          <div class="bookmark-thumb">
            <img v-if="thumbnailUrl(bookmark)" :src="thumbnailUrl(bookmark)" :alt="anchorName(bookmark)" loading="lazy" decoding="async" />
            <el-icon v-else><Picture /></el-icon>
          </div>
          <div class="bookmark-body">
            <div class="bookmark-name" :title="bookmark.name">{{ bookmark.name }}</div>
            <div class="bookmark-meta">{{ contextLabel(bookmark) }}</div>
            <div class="bookmark-anchor" :title="anchorName(bookmark)">
              {{ anchorName(bookmark) }}
              <span v-if="!bookmark.anchor_exists" class="missing">（已删除）</span>
            </div>
            <div class="bookmark-time">{{ formattedTime(bookmark.updated_at) }}</div>
          </div>
          <div class="bookmark-actions" @click.stop>
            <button type="button" title="重命名" aria-label="重命名书签" @click="handleRename(bookmark)">
              <el-icon><Edit /></el-icon>
            </button>
            <button type="button" title="删除" aria-label="删除书签" @click="handleDelete(bookmark)">
              <el-icon><Delete /></el-icon>
            </button>
          </div>
        </div>

        <div v-if="autoBookmarks.length > 0" class="auto-note">
          自动进度会随浏览更新；手动书签固定保存你标记的位置。
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<style scoped>
.bookmarks-panel {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.bookmark-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--text-secondary);
  text-transform: uppercase;
}

.bookmark-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  width: 100%;
  padding: 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  color: var(--text-primary);
  text-align: left;
  cursor: pointer;
  transition: border-color var(--motion-fast) var(--ease-out),
              box-shadow var(--motion-fast) var(--ease-out),
              transform var(--motion-fast) var(--ease-out);
}

.bookmark-card:hover {
  border-color: var(--primary);
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}

.auto-card {
  background: var(--bg-secondary);
}

.auto-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent);
  color: var(--primary);
  font-size: 20px;
  flex-shrink: 0;
}

.bookmark-thumb {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--bg-secondary);
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 20px;
}

.bookmark-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.bookmark-body {
  flex: 1;
  min-width: 0;
}

.bookmark-name {
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.bookmark-meta,
.bookmark-anchor,
.bookmark-time {
  margin-top: 3px;
  font-size: 11.5px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.bookmark-anchor {
  color: var(--text-tertiary);
}

.missing {
  color: var(--danger, #f56c6c);
}

.restore-hint {
  align-self: center;
  font-size: 12px;
  color: var(--primary);
  flex-shrink: 0;
}

.bookmark-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity var(--motion-fast) var(--ease-out);
}

.bookmark-card:hover .bookmark-actions {
  opacity: 1;
}

.bookmark-actions button {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.bookmark-actions button:hover {
  background: var(--accent);
  color: var(--primary);
}

.empty-bookmarks {
  padding: 18px 12px;
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 12.5px;
  line-height: 1.7;
}

.auto-note {
  font-size: 11.5px;
  color: var(--text-tertiary);
  line-height: 1.6;
}

@media (hover: none) {
  .bookmark-actions {
    opacity: 1;
  }

  .bookmark-actions button {
    width: 44px;
    height: 44px;
  }
}
</style>
