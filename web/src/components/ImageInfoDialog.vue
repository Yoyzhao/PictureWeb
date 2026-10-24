<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { getImage } from '@/api'
import { useFolderStore } from '@/stores/folder'
import type { Image as ImageItem } from '@/stores/image'

const props = defineProps<{
  modelValue: boolean
  image: ImageItem | null
}>()

const emit = defineEmits(['update:modelValue'])

const folderStore = useFolderStore()
const details = ref<ImageItem | null>(null)
const loading = ref(false)

const folderName = computed(() => {
  const folder = folderStore.folders.find(f => f.id === details.value?.folder_id)
  return folder ? folder.name : '-'
})

const formatSize = (bytes?: number) => {
  const size = Number(bytes) || 0
  if (size <= 0) return '-'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / 1024 / 1024).toFixed(2)} MB`
  return `${(size / 1024 / 1024 / 1024).toFixed(2)} GB`
}

const formatTime = (value: any) => {
  if (value === null || value === undefined || value === '') return '-'
  let date = new Date(value)
  if (isNaN(date.getTime())) date = new Date(Number(value) * 1000)
  return isNaN(date.getTime()) ? '-' : date.toLocaleString()
}

// Always fetch the latest record so the physical path stays correct after moves/renames.
watch(() => props.modelValue, async (visible) => {
  if (!visible) return

  details.value = props.image
  if (!props.image) return

  loading.value = true
  try {
    const res = await getImage(props.image.id)
    details.value = { ...res.data, is_favorite: !!res.data.is_favorite }
  } catch (error) {
    console.warn('Failed to load image details, using cached data')
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="图片详情"
    width="500px"
    append-to-body
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div v-if="details" v-loading="loading" class="image-details">
      <div class="detail-item">
        <span class="label">文件名</span>
        <span class="value">{{ details.file_name }}</span>
      </div>
      <div class="detail-item">
        <span class="label">分辨率</span>
        <span class="value">{{ details.width || 0 }} x {{ details.height || 0 }}</span>
      </div>
      <div class="detail-item">
        <span class="label">文件大小</span>
        <span class="value">{{ formatSize(details.file_size) }}</span>
      </div>
      <div class="detail-item">
        <span class="label">文件格式</span>
        <span class="value">{{ details.format ? details.format.toUpperCase() : '-' }}</span>
      </div>
      <div class="detail-item">
        <span class="label">修改时间</span>
        <span class="value">{{ formatTime(details.modified_time) }}</span>
      </div>
      <div class="detail-item">
        <span class="label">收藏状态</span>
        <span class="value">{{ details.is_favorite ? '已收藏' : '未收藏' }}</span>
      </div>
      <div class="detail-item">
        <span class="label">所属文件夹</span>
        <span class="value">{{ folderName }}</span>
      </div>
      <div class="detail-item">
        <span class="label">存储路径</span>
        <span class="value path-value">{{ details.file_path }}</span>
      </div>
    </div>
  </el-dialog>
</template>

<style scoped>
.image-details {
  padding: 4px 0;
}

.detail-item {
  display: flex;
  margin-bottom: 12px;
  line-height: 1.6;
}

.detail-item:last-child {
  margin-bottom: 0;
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
</style>
