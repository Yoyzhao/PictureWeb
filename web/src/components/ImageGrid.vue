<script setup lang="ts">
import { onMounted, ref, watch, computed } from 'vue'
import { useImageStore } from '@/stores/image'
import { useFolderStore } from '@/stores/folder'
import { storeToRefs } from 'pinia'
import { useIntersectionObserver } from '@vueuse/core'
import { Star, More, Loading, InfoFilled, Download, Delete, Rank } from '@element-plus/icons-vue'
import { ElMessageBox, ElMessage } from 'element-plus'

const imageStore = useImageStore()
const { images, loading, total, showOnlyFavorites, sortBy, sortOrder, selectedImageIds } = storeToRefs(imageStore)
const folderStore = useFolderStore()
const { folders, currentFolderId } = storeToRefs(folderStore)

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

const handleBatchMove = () => {
  if (targetFolderId.value) {
    if (isBatchMove.value) {
      imageStore.batchMove(targetFolderId.value)
    } else if (singleMoveImageId.value) {
      imageStore.batchMoveImages([singleMoveImageId.value], targetFolderId.value)
        .then(() => {
          ElMessage.success('移动成功')
          imageStore.fetchImages(true)
        })
    }
    showMoveDialog.value = false
    targetFolderId.value = null
  } else {
    ElMessage.warning('请选择目标文件夹')
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

const showDetails = (img: any) => {
  selectedImage.value = img
  showInfoDialog.value = true
}

const loadMoreTrigger = ref(null)

const currentTitle = computed(() => {
  if (showOnlyFavorites.value) return '收藏夹'
  if (currentFolderId.value === undefined) return '所有照片'
  const folder = folders.value.find(f => f.id === currentFolderId.value)
  return folder ? folder.name : '未知文件夹'
})

onMounted(() => {
  imageStore.fetchImages(true)
})

useIntersectionObserver(
  loadMoreTrigger,
  ([{ isIntersecting }]) => {
    if (isIntersecting && !loading.value && images.value.length < total.value) {
      imageStore.fetchImages()
    }
  }
)

const emit = defineEmits(['open-lightbox'])

const getThumbnailUrl = (id: number) => `/api/images/${id}/thumbnail?size=small`

const toggleFavorite = (img: any) => {
  imageStore.toggleFavorite(img)
}

const isSelected = (id: number) => selectedImageIds.value.includes(id)

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
    <div class="content-header">
        <h2 class="current-folder">{{ currentTitle }}</h2>
        <div class="view-options">
            <span class="item-count">共 {{ total }} 张图片</span>
            <el-radio-group v-model="sortBy" size="small" class="sort-radio">
                <el-radio-button label="modified_time">修改日期</el-radio-button>
                <el-radio-button label="file_name">文件名</el-radio-button>
                <el-radio-button label="file_size">大小</el-radio-button>
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

    <div class="waterfall">
      <div 
        v-for="img in images" 
        :key="img.id" 
        class="img-card"
        :class="{ selected: isSelected(img.id) }"
        @click="handleCardClick(img, $event)"
      >
        <div class="card-checkbox" @click.stop="toggleSelection(img.id)">
            <el-checkbox :model-value="isSelected(img.id)" size="large"></el-checkbox>
        </div>
        <img :src="getThumbnailUrl(img.id)" loading="lazy" :alt="img.file_name" />
        <div class="card-overlay">
            <button class="action-btn fav-btn" :class="{ active: img.is_favorite }" @click.stop="toggleFavorite(img)">
                <el-icon><Star /></el-icon>
            </button>
            <el-dropdown trigger="click">
                <button class="action-btn more-btn" @click.stop>
                    <el-icon><More /></el-icon>
                </button>
                <template #dropdown>
                    <el-dropdown-menu>
                        <el-dropdown-item :icon="InfoFilled" @click="showDetails(img)">查看详情</el-dropdown-item>
                        <el-dropdown-item :icon="Download" @click="handleDownload(img)">下载原图</el-dropdown-item>
                        <el-dropdown-item :icon="Rank" @click="openMoveDialog(img.id)">移动图片</el-dropdown-item>
                        <el-dropdown-item :icon="Delete" @click="handleSingleDelete(img)" divided style="color: #f56c6c">删除图片</el-dropdown-item>
                    </el-dropdown-menu>
                </template>
            </el-dropdown>
        </div>
        <div class="img-info">
          <div class="img-name">{{ img.file_name }}</div>
          <div class="img-meta">
            {{ img.width }} x {{ img.height }} | {{ (img.file_size / 1024 / 1024).toFixed(2) }} MB | 
            {{ isNaN(new Date(img.modified_time).getTime()) ? (new Date(img.modified_time * 1000).toLocaleDateString()) : (new Date(img.modified_time).toLocaleDateString()) }}
          </div>
        </div>
      </div>
    </div>

    <div v-if="images.length === 0 && !loading" class="empty-state">
      <el-empty :description="showOnlyFavorites ? '收藏夹还是空的' : '当前文件夹下没有照片'"></el-empty>
    </div>
    
    <div ref="loadMoreTrigger" class="load-more">
      <el-icon v-if="loading" class="is-loading"><Loading /></el-icon>
      <span v-else-if="images.length >= total && total > 0">没有更多图片了</span>
    </div>

    <footer class="status-bar">
        <div class="status-info">
            <span>当前文件夹: <strong>{{ currentTitle }}</strong></span>
            <span class="separator">|</span>
            <span>图片数量: <strong>{{ total }}</strong></span>
            <span class="separator">|</span>
            <span>已选中: <strong>{{ selectedImageIds.length }}</strong></span>
        </div>
        <div class="batch-actions" v-if="selectedImageIds.length > 0">
            <el-button size="small" type="primary" link @click="imageStore.selectAll()">全选</el-button>
            <el-button size="small" type="primary" link @click="imageStore.clearSelection()">取消</el-button>
            <el-divider direction="vertical" />
            <el-button size="small" type="primary" @click="showMoveDialog = true">移动</el-button>
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
</template>

<style scoped>
.content-wrapper {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
    padding-bottom: calc(var(--status-bar-height) + 24px);
    position: relative;
}

.content-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    margin-bottom: 24px;
}

.current-folder {
    font-size: 24px;
    font-weight: 600;
    margin: 0;
}

.view-options {
    display: flex;
    align-items: center;
    gap: 16px;
}

.item-count {
    font-size: 13px;
    color: var(--text-secondary);
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
    box-shadow: 0 0 0 2px var(--primary);
}

.card-checkbox {
    position: absolute;
    top: 10px;
    left: 10px;
    z-index: 5;
    opacity: 0;
    transition: opacity 0.2s;
}

.img-card:hover .card-checkbox,
.img-card.selected .card-checkbox {
    opacity: 1;
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
    background: rgba(255, 255, 255, 0.8);
    border-color: var(--primary);
}

:deep(.card-checkbox .el-checkbox__input.is-checked .el-checkbox__inner) {
    background-color: var(--primary);
}

.waterfall {
    column-count: 5;
    column-gap: 16px;
}

@media (max-width: 1600px) { .waterfall { column-count: 4; } }
@media (max-width: 1200px) { .waterfall { column-count: 3; } }
@media (max-width: 800px) { .waterfall { column-count: 2; } }

.img-card {
    break-inside: avoid;
    margin-bottom: 16px;
    background: var(--bg-card);
    border-radius: 8px;
    overflow: hidden;
    position: relative;
    cursor: pointer;
    transition: transform 0.2s;
    border: 1px solid transparent;
}

.img-card:hover {
    transform: translateY(-4px);
    border-color: var(--primary);
}

.img-card img {
    width: 100%;
    height: auto;
    display: block;
    background: #333;
}

.img-info {
    padding: 10px;
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

.card-overlay {
    position: absolute;
    top: 10px;
    right: 10px;
    display: flex;
    gap: 8px;
    opacity: 0;
    transition: opacity 0.2s;
}

.img-card:hover .card-overlay {
    opacity: 1;
}

.action-btn {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: rgba(0,0,0,0.6);
    border: none;
    color: white;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
}

.action-btn:hover {
    background: var(--primary);
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
    left: var(--sidebar-width);
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
