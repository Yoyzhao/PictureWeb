<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useImageStore } from '@/stores/image'
import { useAuthStore } from '@/stores/auth'
import { storeToRefs } from 'pinia'
import { Refresh, Delete, Back, Warning, Grid, List } from '@element-plus/icons-vue'
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

const isSelected = (id: number) => selectedTrashIds.value.includes(id)

const toggleSelection = (id: number) => {
  const index = selectedTrashIds.value.indexOf(id)
  if (index > -1) {
    selectedTrashIds.value.splice(index, 1)
  } else {
    selectedTrashIds.value.push(id)
  }
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
    // Restore logic in backend doesn't automatically re-index, 
    // but the file is back. User might need to scan.
    ElMessage.info('图片已恢复至原始路径，请重新扫描文件夹以在相册中显示。')
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
  return new Date(dateStr).toLocaleString()
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
          :buffer="1000"
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
              <img :src="`/api/images/trash/${img.id}/thumbnail?size=medium&token=${token}`" loading="lazy" :alt="img.file_name" />
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
  display: flex;
  flex-direction: column;
}

.trash-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 15px;
}

.header-left h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
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
  border-radius: 8px;
  overflow: auto; /* Changed from hidden to allow waterfall scroll if needed */
  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.05);
}

.file-info-cell {
  display: flex;
  align-items: center;
}

/* Waterfall Styles */
.img-card {
  position: relative;
  background: var(--bg-card);
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  box-sizing: border-box;
  width: 100%;
  user-select: none;
}

.img-card:hover:not(.selected) {
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.img-card.selected::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  border: 3px solid var(--el-color-primary);
  border-radius: inherit;
  pointer-events: none;
  z-index: 15; /* Above image and overlay, below checkbox */
  box-sizing: border-box;
}

.img-card.selected {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
  transform: none;
}

.img-card.selected .card-checkbox {
  background: var(--el-color-primary);
  opacity: 1;
}

.img-card img {
  width: 100%;
  display: block;
  object-fit: cover;
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
  background: rgba(0, 0, 0, 0.3);
  display: flex;
  justify-content: center;
  align-items: center;
  opacity: 0;
  transition: opacity 0.2s;
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
