<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useImageStore } from '@/stores/image'
import { useAuthStore } from '@/stores/auth'
import { storeToRefs } from 'pinia'
import { Refresh, Delete, Back, Warning, Grid, List, VideoPlay } from '@element-plus/icons-vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import VirtualWaterfall from '@/components/common/VirtualWaterfall.vue'

const imageStore = useImageStore()
const authStore = useAuthStore()
const { trashItems, trashLoading, gridSize } = storeToRefs(imageStore)
const { token } = storeToRefs(authStore)
const selectedTrashIds = ref<number[]>([])
const viewMode = ref<'table' | 'waterfall'>('waterfall')

const columnWidthMap = {
  small: 180,
  medium: 280,
  large: 400
}

const currentColumnWidth = computed(() => columnWidthMap[gridSize.value])

const isSelected = (id: number) => selectedTrashSet.value.has(id)
const selectedTrashSet = computed(() => new Set(selectedTrashIds.value))
const trashMetaHeight = computed(() => gridSize.value === 'small' ? 0 : 56)
const trashThumbnailSize = computed(() => gridSize.value === 'large' ? 'medium' : 'small')

const toggleSelection = (id: number) => {
  const index = selectedTrashIds.value.indexOf(id)
  if (index > -1) {
    selectedTrashIds.value.splice(index, 1)
  } else {
    selectedTrashIds.value.push(id)
  }
}

const trashRetryKeys = new Set<string>()
const trashRetryVersion = ref(0)

const trashThumbnailUrl = (img: any) => {
  void trashRetryVersion.value
  const key = `${img.id}:${trashThumbnailSize.value}`
  const retry = trashRetryKeys.has(key) ? '&retry=1' : ''
  return `/api/images/trash/${img.id}/thumbnail?size=${trashThumbnailSize.value}&token=${token.value}${retry}`
}

const handleTrashThumbError = (img: any) => {
  const key = `${img.id}:${trashThumbnailSize.value}`
  if (trashRetryKeys.has(key)) return
  trashRetryKeys.add(key)
  trashRetryVersion.value++
}

onMounted(() => {
  imageStore.fetchTrash()
})

const handleRefresh = () => {
  imageStore.fetchTrash()
}

const handleRestore = async (id?: number) => {
  const ids = id ? [id] : selectedTrashIds.value
  if (ids.length === 0) return
  
  const success = await imageStore.restoreFromTrash(ids)
  if (success) {
    selectedTrashIds.value = []
    // Backend re-inserts the image row and refreshes the gallery automatically.
    ElMessage.info('已恢复到原文件夹。')
  }
}

const handlePermanentlyDelete = async (id?: number) => {
  const ids = id ? [id] : selectedTrashIds.value
  if (ids.length === 0) return
  
  try {
    await ElMessageBox.confirm(
      `确定要永久删除选中的 ${ids.length} 个项目吗？此操作不可撤销！`,
      '永久删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'error',
      }
    )
    
    const success = await imageStore.permanentlyDelete(ids)
    if (success) {
      selectedTrashIds.value = []
    }
  } catch (e) {
    // User cancelled
  }
}

const handleClearTrash = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要清空回收站吗？所有文件将被永久删除！',
      '清空回收站',
      {
        confirmButtonText: '清空',
        cancelButtonText: '取消',
        type: 'error',
      }
    )
    
    const success = await imageStore.permanentlyDelete()
    if (success) {
      selectedTrashIds.value = []
    }
  } catch (e) {
    // User cancelled
  }
}

const formatSize = (size: number) => {
  if (size === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(size) / Math.log(k))
  return parseFloat((size / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return isNaN(date.getTime()) ? '-' : date.toLocaleString()
}

const imageAspectRatio = (img: any) => {
  const width = Number(img.width) || 0
  const height = Number(img.height) || 0
  if (width > 0 && height > 0) return `${width} / ${height}`
  return img.media_type === 'video' ? '16 / 9' : '4 / 3'
}

const formatDuration = (seconds: number | null | undefined) => {
  const total = Math.floor(Number(seconds) || 0)
  if (total <= 0) return ''
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const secs = total % 60
  const pad = (value: number) => String(value).padStart(2, '0')
  return hours > 0 ? `${hours}:${pad(minutes)}:${pad(secs)}` : `${minutes}:${pad(secs)}`
}
</script>

<template>
  <div class="trash-page">
    <div class="trash-header">
      <div class="header-left">
        <h2>回收站</h2>
        <span class="count-info">共 {{ trashItems.length }} 个项目</span>
        
        <el-radio-group v-model="viewMode" size="small" class="view-mode-radio">
          <el-radio-button value="waterfall">
            <el-icon><Grid /></el-icon>
          </el-radio-button>
          <el-radio-button value="table">
            <el-icon><List /></el-icon>
          </el-radio-button>
        </el-radio-group>
        
        <el-radio-group v-if="viewMode === 'waterfall'" v-model="gridSize" size="small" class="grid-size-radio">
          <el-radio-button value="small">小</el-radio-button>
          <el-radio-button value="medium">中</el-radio-button>
          <el-radio-button value="large">大</el-radio-button>
        </el-radio-group>
      </div>
      <div class="header-actions">
        <el-button :icon="Refresh" @click="handleRefresh" :loading="trashLoading">刷新</el-button>
        <el-button 
          type="primary" 
          :icon="Back" 
          :disabled="selectedTrashIds.length === 0" 
          @click="handleRestore()"
        >还原选中</el-button>
        <el-button 
          type="danger" 
          :icon="Delete" 
          :disabled="selectedTrashIds.length === 0" 
          @click="handlePermanentlyDelete()"
        >永久删除</el-button>
        <el-button 
          type="danger" 
          plain 
          :icon="Warning" 
          :disabled="trashItems.length === 0" 
          @click="handleClearTrash"
        >清空回收站</el-button>
      </div>
    </div>

    <div class="trash-content" v-loading="trashLoading">
      <template v-if="trashItems.length > 0">
        <el-table 
          v-if="viewMode === 'table'" 
          :data="trashItems" 
          style="width: 100%"
          @selection-change="(val: any[]) => selectedTrashIds = val.map(i => i.id)"
        >
          <el-table-column type="selection" width="55" />
          <el-table-column label="文件名" min-width="200">
            <template #default="{ row }">
              <div class="file-info-cell">
                <span class="file-name">{{ row.file_name }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="原始路径" min-width="300">
            <template #default="{ row }">
              <span class="original-path">{{ row.original_path }}</span>
            </template>
          </el-table-column>
          <el-table-column label="删除时间" width="180">
            <template #default="{ row }">
              {{ formatDate(row.deleted_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button type="primary" link @click="handleRestore(row.id)">还原</el-button>
              <el-button type="danger" link @click="handlePermanentlyDelete(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <VirtualWaterfall 
          v-else
          :items="trashItems" 
          :column-width="currentColumnWidth"
          :gap="16" 
          :buffer="600"
          :meta-height="trashMetaHeight"
        >
          <template #default="{ item: img }">
            <div 
              class="img-card"
              :class="{ selected: isSelected(img.id) }"
              @click="toggleSelection(img.id)"
            >
              <div class="card-checkbox" @click.stop="toggleSelection(img.id)">
                  <el-checkbox :model-value="isSelected(img.id)"></el-checkbox>
              </div>
              <div class="thumb-wrap">
                <img
                  :src="trashThumbnailUrl(img)"
                  loading="lazy"
                  decoding="async"
                  :width="img.width || undefined"
                  :height="img.height || undefined"
                  :style="{ aspectRatio: imageAspectRatio(img) }"
                  :alt="img.file_name"
                  :title="img.file_name"
                  @error="handleTrashThumbError(img)"
                />
                <div v-if="img.media_type === 'video'" class="video-badge" aria-hidden="true">
                  <el-icon><VideoPlay /></el-icon>
                  <span v-if="formatDuration(img.duration)">{{ formatDuration(img.duration) }}</span>
                </div>
              </div>
              <div class="card-overlay">
                  <div class="trash-actions">
                    <el-button 
                      type="primary" 
                      :icon="Back" 
                      circle
                      @click.stop="handleRestore(img.id)"
                      title="还原"
                    ></el-button>
                    <el-button 
                      type="danger" 
                      :icon="Delete" 
                      circle
                      @click.stop="handlePermanentlyDelete(img.id)"
                      title="彻底删除"
                    ></el-button>
                  </div>
              </div>
              <div class="img-info" v-if="gridSize !== 'small'">
                <div class="img-name">{{ img.file_name }}</div>
                <div class="img-meta">
                  {{ formatDate(img.deleted_at) }}
                </div>
              </div>
            </div>
          </template>
        </VirtualWaterfall>
      </template>
      
      <el-empty v-else description="回收站是空的" />
    </div>
  </div>
</template>

<style scoped>
.trash-page {
  padding: 20px;
  height: calc(100vh - var(--top-bar-height) - 40px);
  height: calc(100dvh - var(--top-bar-height) - 40px);
  display: flex;
  flex-direction: column;
}

.trash-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 15px;
}

.header-left h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 650;
  letter-spacing: -0.01em;
  color: var(--text-primary);
}

.count-info {
  font-size: 14px;
  color: var(--text-secondary);
}

.view-mode-radio,
.grid-size-radio {
  margin-left: 5px;
}

.trash-content {
  flex: 1;
  background-color: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  overflow: auto;
  overscroll-behavior: contain;
  box-shadow: var(--shadow-sm);
}

.file-info-cell {
  display: flex;
  align-items: center;
}

/* Waterfall Styles */
.img-card {
  position: relative;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  overflow: hidden;
  cursor: pointer;
  border: 1px solid var(--border-color);
  transition: transform var(--motion-base) var(--ease-out),
              box-shadow var(--motion-base) var(--ease-out);
  box-shadow: var(--shadow-sm);
  box-sizing: border-box;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  user-select: none;
}

@media (hover: hover) {
  .img-card:hover:not(.selected) {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
  }

  .img-card:hover:not(.selected) img {
    transform: scale(1.02);
  }
}

.img-card.selected {
  border-color: var(--primary);
  box-shadow: 0 0 0 2px var(--primary), var(--shadow-sm);
  transform: none;
}

.img-card img {
  width: 100%;
  height: auto;
  display: block;
  background: var(--bg-secondary);
  flex: 0 0 auto;
  transition: transform var(--motion-base) var(--ease-out);
}

.thumb-wrap {
  position: relative;
  display: block;
  flex: 0 0 auto;
  overflow: hidden;
}

.video-badge {
  position: absolute;
  right: 8px;
  bottom: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: var(--radius-pill);
  background: rgba(15, 18, 22, 0.72);
  color: #fff;
  font-size: 11px;
  line-height: 1.2;
  pointer-events: none;
  backdrop-filter: blur(4px);
}

.video-badge .el-icon {
  font-size: 13px;
}

.img-info {
  padding: 8px 10px;
  background: var(--bg-card);
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.img-name {
  font-size: 12.5px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.img-meta {
  font-size: 10.5px;
  color: var(--text-secondary);
  margin-top: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-checkbox {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 10;
  opacity: 0;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  transform: scale(0.9);
  line-height: 1; /* Ensure no extra height */
}

:deep(.card-checkbox .el-checkbox) {
  height: auto;
  margin-right: 0;
}

.img-card:hover .card-checkbox,
.img-card.selected .card-checkbox {
  opacity: 1;
  transform: scale(1.15); /* Slightly larger on hover/selected for better visibility */
}

@media (hover: none) {
  .card-checkbox {
    top: 4px;
    left: 4px;
    width: 44px;
    height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    opacity: 1;
    transform: none;
  }

  :deep(.card-checkbox .el-checkbox__inner) {
    width: 18px;
    height: 18px;
  }

  /* 触屏选中后显示还原/删除操作，避免常驻遮罩 */
  .img-card.selected .card-overlay {
    opacity: 1;
  }

  .img-card .trash-actions .el-button {
    width: 44px;
    height: 44px;
  }
}

:deep(.card-checkbox .el-checkbox__inner) {
  background: rgba(0, 0, 0, 0.4);
  border: 1.2px solid rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(4px);
  border-radius: 4px;
}

:deep(.card-checkbox .el-checkbox__input.is-checked .el-checkbox__inner) {
  background-color: var(--primary);
  border-color: var(--primary);
}

:deep(.card-checkbox .el-checkbox__inner::after) {
  border-width: 2px;
}

.card-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(to bottom, rgba(0, 0, 0, 0.45), rgba(0, 0, 0, 0.15) 45%, rgba(0, 0, 0, 0.35));
  display: flex;
  justify-content: center;
  align-items: center;
  opacity: 0;
  transition: opacity var(--motion-fast) var(--ease-out);
}

.img-card:hover .card-overlay {
  opacity: 1;
}

.trash-actions {
  display: flex;
  gap: 15px;
}

.trash-actions .el-button {
  width: 40px;
  height: 40px;
  font-size: 18px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  transition: transform 0.2s, background-color 0.2s;
  border: none;
}

.trash-actions .el-button--primary {
  background-color: rgba(64, 158, 255, 0.9);
}

.trash-actions .el-button--danger {
  background-color: rgba(245, 108, 108, 0.9);
}

.trash-actions .el-button:hover {
  transform: scale(1.1);
}

.img-info {
  padding: 8px;
  background: var(--bg-card);
}

.img-name {
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.img-meta {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.file-name {
  font-weight: 500;
  color: var(--text-primary);
}

.original-path {
  font-size: 13px;
  color: var(--text-secondary);
  word-break: break-all;
}

:deep(.el-table) {
  --el-table-border-color: var(--border-color);
  --el-table-header-bg-color: var(--bg-main);
  --el-table-row-hover-bg-color: var(--accent);
}

/* Mobile responsive */
@media (max-width: 768px) {
  .trash-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 15px;
  }
  
  .header-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  
  .header-actions .el-button {
    margin-left: 0 !important;
  }
}
</style>
