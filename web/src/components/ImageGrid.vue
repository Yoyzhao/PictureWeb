<script setup lang="ts">
import { onMounted, ref, watch, computed, nextTick } from 'vue'
import { useImageStore } from '@/stores/image'
import { useFolderStore } from '@/stores/folder'
import { useAuthStore } from '@/stores/auth'
import { storeToRefs } from 'pinia'
import { useIntersectionObserver } from '@vueuse/core'
import { Star, More, Loading, InfoFilled, Download, Delete, Rank, Edit } from '@element-plus/icons-vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import VirtualWaterfall from './common/VirtualWaterfall.vue'

const imageStore = useImageStore()
const { images, imagesVersion, loading, total, showOnlyFavorites, sortBy, sortOrder, selectedImageIds, gridSize } = storeToRefs(imageStore)
const folderStore = useFolderStore()
const { folders, currentFolderId } = storeToRefs(folderStore)
const authStore = useAuthStore()
const { user, isLoggedIn } = storeToRefs(authStore)

const isGuest = computed(() => !isLoggedIn.value || user.value?.role === 'guest')
const selectedIdSet = computed(() => new Set(selectedImageIds.value))

const showMoveDialog = ref(false)
const targetFolderId = ref<number | null>(null)
const isBatchMove = ref(false)
const singleMoveImageId = ref<number | null>(null)

const showInfoDialog = ref(false)
const selectedImage = ref<any>(null)

const handleBatchDelete = () => {
  ElMessageBox.confirm(
    `确定要将选中的 ${selectedImageIds.value.length} 张图片移至回收站吗？`,
    '批量删除',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }
  ).then(() => {
    imageStore.batchDelete()
  })
}

const handleSingleDelete = (img: any) => {
  ElMessageBox.confirm(
    `确定要将图片 "${img.file_name}" 移至回收站吗？`,
    '确认删除',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }
  ).then(async () => {
    try {
      const res = await imageStore.batchDeleteImages([img.id])
      if (res.data.success) {
        ElMessage.success('已移至回收站')
        imageStore.fetchImages(true)
      }
    } catch (err) {
      ElMessage.error('删除失败')
    }
  })
}

const handleBatchMove = async () => {
  if (!targetFolderId.value) {
    ElMessage.warning('请选择目标文件夹')
    return
  }

  try {
    if (isBatchMove.value) {
      await imageStore.batchMove(targetFolderId.value)
    } else if (singleMoveImageId.value) {
      const res = await imageStore.batchMoveImages([singleMoveImageId.value], targetFolderId.value)
      if (res.data.success) {
        ElMessage.success('移动成功')
        imageStore.fetchImages(true)
      }
    }
    showMoveDialog.value = false
    targetFolderId.value = null
  } catch (err: any) {
    ElMessage.error('移动失败: ' + (err.response?.data?.error || err.message))
  }
}

const openMoveDialog = (id?: number) => {
  if (id) {
    isBatchMove.value = false
    singleMoveImageId.value = id
  } else {
    isBatchMove.value = true
    singleMoveImageId.value = null
  }
  showMoveDialog.value = true
}

const handleDownload = (img: any) => {
  const link = document.createElement('a')
  link.href = `/api/images/${img.id}/download`
  link.download = img.file_name
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

const handleRename = async (img: any) => {
  try {
    const result = await ElMessageBox.prompt(
      '请输入新的文件名',
      '重命名',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        inputValue: img.file_name,
        inputPattern: /^[^\\/:*?"<>|]+$/,
        inputErrorMessage: '文件名包含非法字符',
      }
    )
    const newName = (result as any).value
    
    if (newName && newName !== img.file_name) {
      const res = await imageStore.renameImage(img.id, newName)
      if (res.success) {
        ElMessage.success('重命名成功')
      }
    }
  } catch (error) {
    // User cancelled
  }
}

const showDetails = (img: any) => {
  selectedImage.value = img
  showInfoDialog.value = true
}

const currentTitle = computed(() => {
  if (showOnlyFavorites.value) return '收藏夹'
  if (currentFolderId.value === undefined) return '所有照片'
  const folder = folders.value.find(f => f.id === currentFolderId.value)
  return folder ? folder.name : '未知文件夹'
})

const scrollableRef = ref<HTMLElement | null>(null)

onMounted(() => {
  imageStore.fetchImages(true)
})

const emit = defineEmits(['open-lightbox'])

const getThumbnailUrl = (id: number) => `/api/images/${id}/thumbnail?size=${thumbnailSize.value}`

const columnWidthMap = {
  small: 180,
  medium: 280,
  large: 400
}

const currentColumnWidth = computed(() => columnWidthMap[gridSize.value])
const thumbnailSize = computed(() => gridSize.value === 'large' ? 'medium' : 'small')
const metaHeight = computed(() => gridSize.value === 'small' ? 32 : 68)

const formatDate = (value: any) => {
  if (value === null || value === undefined || value === '') return '-'
  let date = new Date(value)
  if (isNaN(date.getTime())) {
    date = new Date(Number(value) * 1000)
  }
  return isNaN(date.getTime()) ? '-' : date.toLocaleDateString()
}

// Reserve the image box before the thumbnail finishes decoding to avoid CLS.
const imageAspectRatio = (img: any) => {
  const width = Number(img.width) || 0
  const height = Number(img.height) || 0
  return width > 0 && height > 0 ? `${width} / ${height}` : '4 / 3'
}

const toggleFavorite = (img: any) => {
  imageStore.toggleFavorite(img)
}

const isSelected = (id: number) => selectedIdSet.value.has(id)

const handleCardClick = (img: any, event: MouseEvent) => {
  if (event.ctrlKey || event.metaKey) {
    imageStore.toggleImageSelection(img.id)
  } else {
    emit('open-lightbox', img)
  }
}

const toggleSelection = (id: number) => {
  imageStore.toggleImageSelection(id)
}
</script>

<template>
  <div class="content-wrapper">
    <div class="fixed-header-container">
      <div class="content-header">
          <h2 class="current-folder">{{ currentTitle }}</h2>
          <div class="view-options">
              <span class="item-count">共 {{ total }} 张图片</span>
              <el-radio-group v-model="gridSize" size="small" class="grid-size-radio">
                  <el-radio-button value="small">小</el-radio-button>
                  <el-radio-button value="medium">中</el-radio-button>
                  <el-radio-button value="large">大</el-radio-button>
              </el-radio-group>
              <el-divider direction="vertical" />
              <el-radio-group v-model="sortBy" size="small" class="sort-radio">
                  <el-radio-button value="modified_time">修改日期</el-radio-button>
                  <el-radio-button value="file_name">文件名</el-radio-button>
                  <el-radio-button value="file_size">大小</el-radio-button>
              </el-radio-group>
              <el-button 
                size="small" 
                class="sort-order-btn" 
                @click="sortOrder = sortOrder === 'ASC' ? 'DESC' : 'ASC'"
              >
                {{ sortOrder === 'ASC' ? '升序' : '降序' }}
              </el-button>
          </div>
      </div>
    </div>

    <div class="scrollable-content" ref="scrollableRef">
      <VirtualWaterfall 
        :items="images" 
        :items-version="imagesVersion"
        :column-width="currentColumnWidth"
        :gap="16" 
        :buffer="600"
        :meta-height="metaHeight"
        @load-more="imageStore.fetchImages()"
      >
      <template #default="{ item: img, index }">
        <div 
          class="img-card"
          :class="{ selected: isSelected(img.id) }"
          @click="handleCardClick(img, $event)"
        >
          <div class="card-checkbox" @click.stop="toggleSelection(img.id)">
              <el-checkbox :model-value="isSelected(img.id)" :aria-label="`选择 ${img.file_name}`"></el-checkbox>
          </div>
          <img
            :src="getThumbnailUrl(img.id)"
            :loading="index < 15 ? 'eager' : 'lazy'"
            :fetchpriority="index < 15 ? 'high' : 'auto'"
            decoding="async"
            :width="img.width || undefined"
            :height="img.height || undefined"
            :style="{ aspectRatio: imageAspectRatio(img) }"
            :alt="img.file_name"
            :title="img.file_name"
          />
          <div class="card-overlay">
              <button v-if="isLoggedIn && !isGuest" class="action-btn fav-btn" :class="{ active: img.is_favorite }" :aria-label="img.is_favorite ? '取消收藏' : '收藏'" @click.stop="toggleFavorite(img)">
                  <el-icon><Star /></el-icon>
              </button>
              <el-dropdown trigger="click">
                  <button class="action-btn more-btn" aria-label="更多操作" @click.stop>
                      <el-icon><More /></el-icon>
                  </button>
                  <template #dropdown>
                      <el-dropdown-menu>
                          <el-dropdown-item :icon="InfoFilled" @click="showDetails(img)">查看详情</el-dropdown-item>
                          <el-dropdown-item :icon="Download" @click="handleDownload(img)">下载原图</el-dropdown-item>
                          <el-dropdown-item v-if="!isGuest" :icon="Edit" @click="handleRename(img)">重命名</el-dropdown-item>
                          <el-dropdown-item v-if="!isGuest" :icon="Rank" @click="openMoveDialog(img.id)">移动图片</el-dropdown-item>
                          <el-dropdown-item v-if="!isGuest" :icon="Delete" @click="handleSingleDelete(img)" divided style="color: #f56c6c">删除图片</el-dropdown-item>
                      </el-dropdown-menu>
                  </template>
              </el-dropdown>
          </div>
          <div class="img-info" v-if="gridSize !== 'small'">
            <div class="img-name">{{ img.file_name }}</div>
            <div class="img-meta">
              {{ img.width }} x {{ img.height }} | {{ (img.file_size / 1024 / 1024).toFixed(2) }} MB | 
              {{ formatDate(img.modified_time) }}
            </div>
          </div>
          <div class="img-info-mini" v-else>
             <div class="img-name-mini">{{ img.file_name }}</div>
          </div>
        </div>
      </template>
    </VirtualWaterfall>

    <div v-if="loading && images.length === 0" class="skeleton-grid" aria-hidden="true">
      <div v-for="i in 10" :key="i" class="skeleton-card"></div>
    </div>

    <div v-if="images.length === 0 && !loading" class="empty-state">
      <el-empty :description="showOnlyFavorites ? '收藏夹还是空的' : '当前文件夹下没有照片'"></el-empty>
    </div>
    
    <div v-if="loading && images.length > 0" class="load-more">
      <el-icon class="is-loading"><Loading /></el-icon>
    </div>
    <div v-else-if="images.length >= total && total > 0" class="load-more">
      <span>没有更多图片了</span>
    </div>

    <footer class="status-bar">
        <div class="status-info">
            <span>当前文件夹: <strong>{{ currentTitle }}</strong></span>
            <span class="separator">|</span>
            <span>图片数量: <strong>{{ total }}</strong></span>
            <span class="separator">|</span>
            <span>已选中: <strong>{{ selectedImageIds.length }}</strong></span>
        </div>
        <div class="batch-actions" v-if="selectedImageIds.length > 0 && !isGuest">
            <el-button size="small" type="primary" link @click="imageStore.selectAll()">全选</el-button>
            <el-button size="small" type="primary" link @click="imageStore.clearSelection()">取消</el-button>
            <el-divider direction="vertical" />
            <el-button size="small" type="primary" @click="openMoveDialog()">移动</el-button>
            <el-button size="small" type="danger" @click="handleBatchDelete">删除</el-button>
        </div>
    </footer>

    <!-- 移动文件夹对话框 -->
    <el-dialog v-model="showMoveDialog" title="移动图片" width="400px">
      <el-form label-position="top">
        <el-form-item label="选择目标文件夹">
          <el-select v-model="targetFolderId" placeholder="请选择" style="width: 100%">
            <el-option
              v-for="folder in folders"
              :key="folder.id"
              :label="folder.name"
              :value="folder.id"
              :disabled="folder.id === currentFolderId"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showMoveDialog = false">取消</el-button>
        <el-button type="primary" @click="handleBatchMove">确定移动</el-button>
      </template>
    </el-dialog>

    <!-- 图片详情对话框 -->
    <el-dialog v-model="showInfoDialog" title="图片详情" width="500px">
      <div v-if="selectedImage" class="image-details">
        <div class="detail-item">
          <span class="label">文件名:</span>
          <span class="value">{{ selectedImage.file_name }}</span>
        </div>
        <div class="detail-item">
          <span class="label">文件大小:</span>
          <span class="value">{{ (selectedImage.file_size / 1024 / 1024).toFixed(2) }} MB</span>
        </div>
        <div class="detail-item">
          <span class="label">分辨率:</span>
          <span class="value">{{ selectedImage.width }} x {{ selectedImage.height }}</span>
        </div>
        <div class="detail-item">
          <span class="label">文件格式:</span>
          <span class="value">{{ selectedImage.format.toUpperCase() }}</span>
        </div>
        <div class="detail-item">
          <span class="label">修改时间:</span>
          <span class="value">{{ isNaN(new Date(selectedImage.modified_time).getTime()) ? (new Date(selectedImage.modified_time * 1000).toLocaleString()) : (new Date(selectedImage.modified_time).toLocaleString()) }}</span>
        </div>
        <div class="detail-item">
          <span class="label">存储路径:</span>
          <span class="value path-value">{{ selectedImage.file_path }}</span>
        </div>
      </div>
    </el-dialog>
    </div>
  </div>
</template>

<style scoped>
.content-wrapper {
    flex: 1;
    display: flex;
    flex-direction: column;
    position: relative;
    overflow: hidden; /* 防止外层出现滚动条 */
    background: var(--bg-body); /* 确保背景色统一 */
}

.fixed-header-container {
    padding: 18px 24px 14px 24px;
    background: var(--bg-main);
    border-bottom: 1px solid var(--border-color);
    z-index: 10;
    flex-shrink: 0;
}

.scrollable-content {
    flex: 1;
    overflow-y: auto;
    padding: 16px 24px 24px 24px;
    scrollbar-gutter: stable;
    /* 留出底部状态栏的空间 */
    padding-bottom: calc(var(--status-bar-height) + 24px);
}

.content-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    margin-bottom: 0;
}

.current-folder {
    font-size: 22px;
    font-weight: 650;
    letter-spacing: -0.01em;
    margin: 0;
}

.view-options {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
}

.item-count {
    font-size: 12px;
    color: var(--text-secondary);
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-pill);
    padding: 4px 10px;
}

.sort-select {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    color: var(--text-primary);
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 13px;
    outline: none;
}

.fav-btn.active {
    color: #ff4757;
}

.img-card.selected {
    border-color: var(--primary);
    box-shadow: 0 0 0 2px var(--primary), var(--shadow-sm);
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

.image-details {
  padding: 10px;
}

.detail-item {
  display: flex;
  margin-bottom: 12px;
  line-height: 1.6;
}

.detail-item .label {
  width: 80px;
  color: var(--text-secondary);
  font-weight: 500;
  flex-shrink: 0;
}

.detail-item .value {
  color: var(--text-primary);
  word-break: break-all;
}

.path-value {
  font-family: monospace;
  font-size: 12px;
  background: var(--bg-card);
  padding: 4px 8px;
  border-radius: 4px;
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

/* Removed .waterfall column layout in favor of VirtualWaterfall */

.img-card {
    background: var(--bg-card);
    border-radius: var(--radius-md);
    overflow: hidden;
    position: relative;
    cursor: pointer;
    transition: transform var(--motion-base) var(--ease-out),
                box-shadow var(--motion-base) var(--ease-out),
                border-color var(--motion-fast) var(--ease-out);
    border: 1px solid var(--border-color);
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    box-shadow: var(--shadow-sm);
}

@media (hover: hover) {
    .img-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-md);
    }

    .img-card:hover img {
        transform: scale(1.02);
    }

    .img-card.selected:hover {
        box-shadow: 0 0 0 2px var(--primary), var(--shadow-md);
    }
}

.img-card img {
    width: 100%;
    height: auto;
    display: block;
    background: var(--bg-secondary);
    flex: 0 0 auto;
    transition: transform var(--motion-base) var(--ease-out);
}

.img-info {
    padding: 9px 10px;
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

.img-info-mini {
    padding: 6px 8px;
    background: var(--bg-card);
    flex: 1;
    min-height: 0;
    overflow: hidden;
}

.img-name-mini {
    font-size: 11px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: var(--text-primary);
}

/* 响应式调整列宽 UI */
@media (max-width: 768px) {
    .content-header {
        flex-direction: column;
        align-items: flex-start;
        gap: 12px;
    }
    .view-options {
        flex-wrap: wrap;
        gap: 8px;
    }
    .grid-size-radio {
        order: 1;
    }
    .sort-radio {
        order: 2;
    }
    .status-bar {
        padding: 0 12px;
    }
    .status-info {
        display: none;
    }
    .batch-actions {
        width: 100%;
        justify-content: flex-end;
    }
}

.card-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 88px;
    display: flex;
    justify-content: flex-end;
    align-items: flex-start;
    gap: 8px;
    padding: 10px;
    background: linear-gradient(to bottom, rgba(0, 0, 0, 0.42), transparent);
    opacity: 0;
    transition: opacity var(--motion-fast) var(--ease-out);
    pointer-events: none;
}

.img-card:hover .card-overlay,
.img-card.selected .card-overlay {
    opacity: 1;
}

.card-overlay .action-btn,
.card-overlay .el-dropdown {
    pointer-events: auto;
}

.action-btn {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: rgba(15, 18, 22, 0.55);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.18);
    color: white;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background-color var(--motion-fast) var(--ease-out),
                transform var(--motion-fast) var(--ease-out);
}

.action-btn:hover {
    background: var(--primary);
    border-color: var(--primary);
    transform: scale(1.06);
}

.load-more {
    height: 50px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-secondary);
}

/* Status Bar */
.status-bar {
    position: fixed;
    bottom: 0;
    left: var(--current-sidebar-width, var(--sidebar-width));
    right: 0;
    height: var(--status-bar-height);
    background: var(--bg-sidebar);
    border-top: 1px solid var(--border-color);
    padding: 0 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 12px;
    color: var(--text-secondary);
    z-index: 20;
    transition: left var(--motion-base) var(--ease-out);
}

.status-info {
    display: flex;
    align-items: center;
    min-width: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.status-info strong {
    color: var(--text-primary);
    font-weight: 600;
}

.batch-actions {
    display: flex;
    align-items: center;
    gap: 4px;
    animation: batch-in var(--motion-base) var(--ease-out);
}

@keyframes batch-in {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: none; }
}

.empty-state {
    padding: 60px 0;
}

.skeleton-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 16px;
    padding-top: 4px;
}

.skeleton-card {
    aspect-ratio: 4 / 5;
    border-radius: var(--radius-md);
    background: linear-gradient(100deg, var(--bg-secondary) 20%, var(--accent) 45%, var(--bg-secondary) 70%);
    background-size: 200% 100%;
    animation: skeleton-shimmer 1.4s linear infinite;
}

@keyframes skeleton-shimmer {
    from { background-position: 150% 0; }
    to { background-position: -50% 0; }
}

.separator {
    margin: 0 12px;
    color: var(--border-color);
}

.btn-sm {
    padding: 4px 12px;
    border-radius: 4px;
    border: none;
    font-size: 12px;
    cursor: pointer;
    margin-left: 8px;
}

.btn-primary { background: var(--primary); color: white; }
.btn-danger { background: #dc3545; color: white; }
</style>
