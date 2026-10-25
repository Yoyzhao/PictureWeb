<script setup lang="ts">
import { onMounted, ref, watch, computed, nextTick } from 'vue'
import { useImageStore } from '@/stores/image'
import { useFolderStore } from '@/stores/folder'
import { useAuthStore } from '@/stores/auth'
import { storeToRefs } from 'pinia'
import { useIntersectionObserver } from '@vueuse/core'
import { Star, More, Loading, InfoFilled, Download, Delete, Rank, Edit, CollectionTag, Select, View, Hide, VideoPlay } from '@element-plus/icons-vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import VirtualWaterfall from './common/VirtualWaterfall.vue'
import ImageInfoDialog from './ImageInfoDialog.vue'
import { useBookmarkStore } from '@/stores/bookmark'
import { useUIStore } from '@/stores/ui'

const imageStore = useImageStore()
const bookmarkStore = useBookmarkStore()
const uiStore = useUIStore()
const { showGridImageInfo } = storeToRefs(uiStore)
const multiSelectMode = ref(false)
const {
  images, imagesVersion, loading, total, showOnlyFavorites, sortBy, sortOrder,
  searchQuery, mediaFilter, selectedImageIds, gridSize, scrollAnchorId, scrollAnchorVersion
} = storeToRefs(imageStore)
const currentViewAnchorId = ref<number | null>(null)
const currentPositionBookmarked = computed(() =>
  currentViewAnchorId.value !== null && bookmarkStore.bookmarkedImageIds.has(currentViewAnchorId.value)
)

const handleViewAnchor = (id: number) => {
  currentViewAnchorId.value = id
  bookmarkStore.saveAutoProgress(id)
}

const handleSaveBookmark = () => {
  if (!currentViewAnchorId.value) {
    ElMessage.warning('请先浏览图片后再保存当前位置')
    return
  }
  bookmarkStore.toggleAt(currentViewAnchorId.value)
}
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
// Source folders of the images being moved; moving into the same folder is rejected by the backend.
const moveSourceFolderIds = ref<number[]>([])

const showInfoDialog = ref(false)
const selectedImage = ref<any>(null)

const handleBatchDelete = () => {
  ElMessageBox.confirm(
    confirmDeleteText(selectedImageIds.value.length),
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
    `确定要将“${img.file_name}”移至回收站吗？`,
    '确认删除',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }
  ).then(async () => {
    try {
      const res = await imageStore.batchDeleteImages([img.id])
      const body = res.data
      const deletedIds: number[] = body.deleted_ids || []
      const missingIds: number[] = body.missing_ids || []
      const errors: string[] = body.errors || []

      if (deletedIds.includes(img.id)) {
        if (missingIds.includes(img.id)) {
          ElMessage.warning('文件已缺失，仅移除了索引记录')
        } else {
          ElMessage.success('已移至回收站')
        }
        imageStore.fetchImages(true)
      } else if (errors.length > 0) {
        ElMessage.error(errors[0])
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
      const body = res.data
      const movedIds: number[] = body.moved_ids || []
      const errors: string[] = body.errors || []
      if (movedIds.includes(singleMoveImageId.value)) {
        ElMessage.success('移动成功')
        imageStore.fetchImages(true)
      } else if (errors.length > 0) {
        ElMessage.error('移动失败: ' + errors[0])
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
    const image = images.value.find(img => img.id === id)
    moveSourceFolderIds.value = image ? [image.folder_id] : []
  } else {
    isBatchMove.value = true
    singleMoveImageId.value = null
    const selected = new Set(selectedImageIds.value)
    moveSourceFolderIds.value = [...new Set(
      images.value.filter(img => selected.has(img.id)).map(img => img.folder_id)
    )]
  }
  targetFolderId.value = null
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
  if (currentFolderId.value === undefined) return '所有媒体'
  const folder = folders.value.find(f => f.id === currentFolderId.value)
  return folder ? folder.name : '未知文件夹'
})

const mediaCountLabel = computed(() => {
  if (mediaFilter.value === 'image') return `共 ${total.value} 张图片`
  if (mediaFilter.value === 'video') return `共 ${total.value} 个视频`
  return `共 ${total.value} 项`
})

const emptyLabel = computed(() => {
  if (showOnlyFavorites.value) return '收藏夹还是空的'
  if (mediaFilter.value === 'image') return '当前文件夹下没有图片'
  if (mediaFilter.value === 'video') return '当前文件夹下没有视频'
  return '当前文件夹下没有媒体文件'
})

const mediaFilterOptions = [
  { value: 'all', label: '全部' },
  { value: 'image', label: '图片' },
  { value: 'video', label: '视频' }
]

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
const metaHeight = computed(() => {
  if (!showGridImageInfo.value) return 0
  return gridSize.value === 'small' ? 32 : 68
})

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

const confirmDeleteText = (count: number) => `确定要将选中的 ${count} 个项目移至回收站吗？`

const toggleFavorite = (img: any) => {
  imageStore.toggleFavorite(img)
}

const isSelected = (id: number) => selectedIdSet.value.has(id)

const handleCardClick = (img: any) => {
  if (multiSelectMode.value) {
    imageStore.toggleImageSelection(img.id)
  } else {
    emit('open-lightbox', img)
  }
}

const toggleSelection = (id: number) => {
  if (!multiSelectMode.value) return
  imageStore.toggleImageSelection(id)
}

const toggleMultiSelect = () => {
  multiSelectMode.value = !multiSelectMode.value
  // Entering or leaving selection mode always starts from a clean selection.
  imageStore.clearSelection()
}

// Changing folder/search/sort/filter leaves selection mode to avoid accidental picking in a new view.
watch([currentFolderId, showOnlyFavorites, sortBy, sortOrder, searchQuery, mediaFilter], () => {
  if (!multiSelectMode.value) return
  multiSelectMode.value = false
  imageStore.clearSelection()
})
</script>

<template>
  <div class="content-wrapper">
    <div class="fixed-header-container">
      <div class="content-header">
          <h2 class="current-folder">{{ currentTitle }}</h2>
          <div class="view-options">
              <span class="item-count">{{ mediaCountLabel }}</span>
              <el-radio-group v-model="mediaFilter" size="small" class="media-filter-radio">
                  <el-radio-button
                    v-for="option in mediaFilterOptions"
                    :key="option.value"
                    :value="option.value"
                  >{{ option.label }}</el-radio-button>
              </el-radio-group>
              <el-button
                v-if="!isGuest"
                size="small"
                class="grid-toggle-btn"
                :class="{ 'is-active': multiSelectMode }"
                :title="multiSelectMode ? '退出多选并清空选择' : '进入多选模式'"
                @click="toggleMultiSelect"
              >
                <el-icon><Select /></el-icon>
                <span>{{ multiSelectMode ? '退出多选' : '多选' }}</span>
              </el-button>
              <el-button
                size="small"
                class="grid-toggle-btn"
                :class="{ 'is-active': showGridImageInfo }"
                :title="showGridImageInfo ? '隐藏卡片下方的图片信息' : '显示卡片下方的图片信息'"
                @click="uiStore.toggleGridImageInfo()"
              >
                <el-icon>
                  <View v-if="showGridImageInfo" />
                  <Hide v-else />
                </el-icon>
                <span>信息</span>
              </el-button>
              <el-button
                v-if="bookmarkStore.canBookmark"
                size="small"
                class="save-bookmark-btn"
                :class="{ 'is-active': currentPositionBookmarked }"
                :title="currentPositionBookmarked ? '再次点击取消书签' : '将当前顶部图片位置保存为书签'"
                @click="handleSaveBookmark"
              >
                <el-icon><CollectionTag /></el-icon>
                <span>{{ currentPositionBookmarked ? '已书签' : '记住这里' }}</span>
              </el-button>
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
        :scroll-to-id="scrollAnchorId"
        :scroll-request="scrollAnchorVersion"
        @load-more="imageStore.fetchImages()"
        @view-anchor="handleViewAnchor"
        @scroll-anchor-done="imageStore.clearScrollAnchor()"
      >
      <template #default="{ item: img, index }">
        <div 
          class="img-card"
          :class="{ selected: isSelected(img.id), 'multi-select': multiSelectMode }"
          @click="handleCardClick(img)"
        >
          <div v-if="multiSelectMode" class="card-checkbox" @click.stop="toggleSelection(img.id)">
              <el-checkbox :model-value="isSelected(img.id)" :aria-label="`选择 ${img.file_name}`"></el-checkbox>
          </div>
          <div class="thumb-wrap">
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
            <div v-if="img.media_type === 'video'" class="video-badge" aria-hidden="true">
              <el-icon><VideoPlay /></el-icon>
              <span v-if="formatDuration(img.duration)">{{ formatDuration(img.duration) }}</span>
            </div>
          </div>
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
                          <el-dropdown-item :icon="Download" @click="handleDownload(img)">下载原文件</el-dropdown-item>
                          <el-dropdown-item v-if="!isGuest" :icon="Edit" @click="handleRename(img)">重命名</el-dropdown-item>
                          <el-dropdown-item v-if="!isGuest" :icon="Rank" @click="openMoveDialog(img.id)">移动</el-dropdown-item>
                          <el-dropdown-item v-if="!isGuest" :icon="Delete" @click="handleSingleDelete(img)" divided style="color: #f56c6c">删除</el-dropdown-item>
                      </el-dropdown-menu>
                  </template>
              </el-dropdown>
          </div>
          <div class="img-info" v-if="showGridImageInfo && gridSize !== 'small'">
            <div class="img-name">{{ img.file_name }}</div>
            <div class="img-meta">
              <template v-if="img.media_type === 'video' && formatDuration(img.duration)">{{ formatDuration(img.duration) }} | </template>
              {{ img.width }} x {{ img.height }} | {{ (img.file_size / 1024 / 1024).toFixed(2) }} MB | 
              {{ formatDate(img.modified_time) }}
            </div>
          </div>
          <div class="img-info-mini" v-else-if="showGridImageInfo">
             <div class="img-name-mini">{{ img.file_name }}</div>
          </div>
        </div>
      </template>
    </VirtualWaterfall>

    <div v-if="loading && images.length === 0" class="skeleton-grid" aria-hidden="true">
      <div v-for="i in 10" :key="i" class="skeleton-card"></div>
    </div>

    <div v-if="images.length === 0 && !loading" class="empty-state">
      <el-empty :description="emptyLabel"></el-empty>
    </div>
    
    <div v-if="loading && images.length > 0" class="load-more">
      <el-icon class="is-loading"><Loading /></el-icon>
    </div>
    <div v-else-if="images.length >= total && total > 0" class="load-more">
      <span>没有更多项目了</span>
    </div>

    <footer class="status-bar">
        <div class="status-info">
            <span>当前文件夹: <strong>{{ currentTitle }}</strong></span>
            <span class="separator">|</span>
            <span>媒体数量: <strong>{{ total }}</strong></span>
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
    <el-dialog v-model="showMoveDialog" title="移动文件" width="400px">
      <el-form label-position="top">
        <el-form-item label="选择目标文件夹">
          <el-select v-model="targetFolderId" placeholder="请选择" style="width: 100%">
            <el-option
              v-for="folder in folders"
              :key="folder.id"
              :label="folder.name"
              :value="folder.id"
              :disabled="folder.id === currentFolderId || moveSourceFolderIds.includes(folder.id)"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showMoveDialog = false">取消</el-button>
        <el-button type="primary" @click="handleBatchMove">确定移动</el-button>
      </template>
    </el-dialog>

    <!-- 图片详情对话框（与灯箱共用） -->
    <ImageInfoDialog v-model="showInfoDialog" :image="selectedImage" />
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
    /* 移动端避免下拉刷新打断滚动 */
    overscroll-behavior-y: contain;
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

/* 多选模式：复选框常显，不依赖 hover */
.img-card.multi-select .card-checkbox {
    opacity: 1;
    transform: scale(1);
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

/* 触屏设备没有 hover：常显选择框与操作按钮，保证可选可点 */
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

    .img-card .card-overlay {
        opacity: 1;
        background: none;
    }

    .img-card .card-overlay .action-btn {
        width: 40px;
        height: 40px;
        background: rgba(15, 18, 22, 0.72);
        backdrop-filter: none;
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
    .media-filter-radio {
        order: 0;
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

.save-bookmark-btn.is-active,
.grid-toggle-btn.is-active {
    color: var(--primary);
    border-color: var(--primary);
    background: var(--primary-soft);
}

@media (max-width: 768px) {
    .save-bookmark-btn,
    .grid-toggle-btn {
        height: 44px;
    }
}
</style>
