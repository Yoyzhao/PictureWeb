<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { Close, ArrowLeft, ArrowRight, RefreshRight, Crop, Edit, Star, FullScreen, Delete } from '@element-plus/icons-vue'
import type { Image } from '@/stores/image'
import { useImageStore } from '@/stores/image'
import { ElMessageBox, ElMessage } from 'element-plus'

const props = defineProps<{
  visible: boolean
  image: Image | null
  hasPrev: boolean
  hasNext: boolean
}>()

const emit = defineEmits(['close', 'prev', 'next'])
const imageStore = useImageStore()

const imageUrl = computed(() => props.image ? `/api/images/${props.image.id}/raw` : '')

const truncatedFileName = computed(() => {
  if (!props.image?.file_name) return ''
  const name = props.image.file_name
  return name.length > 50 ? name.slice(0, 47) + '...' : name
})

const fileSizeMB = computed(() => {
  if (!props.image?.file_size) return '0.00 MB'
  return (props.image.file_size / (1024 * 1024)).toFixed(2) + ' MB'
})

// Image transformation state
const scale = ref(1)
const rotate = ref(0)
const translateX = ref(0)
const translateY = ref(0)

const imageStyle = computed(() => ({
  transform: `translate(${translateX.value}px, ${translateY.value}px) scale(${scale.value}) rotate(${rotate.value}deg)`,
  transition: 'transform 0.2s cubic-bezier(0.25, 0.46, 0.45, 0.94)'
}))

// Reset transformations when image changes
watch(() => props.image?.id, () => {
  scale.value = 1
  rotate.value = 0
  translateX.value = 0
  translateY.value = 0
})

const handleWheel = (e: WheelEvent) => {
  if (!props.visible) return
  e.preventDefault()
  
  const delta = e.deltaY > 0 ? -0.1 : 0.1
  const newScale = Math.max(0.1, Math.min(5, scale.value + delta))
  scale.value = newScale
}

const handleRotate = () => {
  rotate.value = (rotate.value + 90) % 360
}

const handleReset = () => {
  scale.value = 1
  rotate.value = 0
  translateX.value = 0
  translateY.value = 0
}

const handleFavorite = async () => {
  if (props.image) {
    await imageStore.toggleFavorite(props.image)
  }
}

const handleDelete = async () => {
  if (!props.image) return
  
  try {
    await ElMessageBox.confirm(
      '确定要删除这张图片吗？',
      '提示',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    const res = await imageStore.batchDeleteImages([props.image.id])
    if (res.data.success) {
      ElMessage.success('删除成功')
      // If there's a next image, go to next, otherwise close
      if (props.hasNext) {
        emit('next')
      } else if (props.hasPrev) {
        emit('prev')
      } else {
        emit('close')
      }
      // Refresh the image list in the background
      imageStore.fetchImages(true)
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败: ' + (error.response?.data?.error || error.message))
    }
  }
}

const handleKeydown = (e: KeyboardEvent) => {
  if (!props.visible) return
  if (e.key === 'Escape') emit('close')
  if (e.key === 'ArrowLeft' && props.hasPrev) emit('prev')
  if (e.key === 'ArrowRight' && props.hasNext) emit('next')
  if (e.key === 'Delete') {
    e.preventDefault()
    handleDelete()
  }
  if (e.key === 'ArrowUp') {
    e.preventDefault()
    scale.value = Math.min(5, scale.value + 0.2)
  }
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    scale.value = Math.max(0.1, scale.value - 0.2)
  }
  if (e.key === 'r' || e.key === 'R') handleRotate()
}

// Global event listener for keys
onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <div v-if="visible" class="lightbox" @click.self="emit('close')" @wheel="handleWheel">
    <div class="lightbox-overlay"></div>
    
    <div class="lightbox-content">
      <transition name="image-fade" mode="out-in">
        <img :key="imageUrl" :src="imageUrl" :alt="image?.file_name" :style="imageStyle" />
      </transition>
      <div class="lightbox-controls">
        <button v-if="hasPrev" class="control-btn prev-btn" @click.stop="emit('prev')">
          <el-icon><ArrowLeft /></el-icon>
        </button>
        <button v-if="hasNext" class="control-btn next-btn" @click.stop="emit('next')">
          <el-icon><ArrowRight /></el-icon>
        </button>
      </div>
      
      <div class="lightbox-toolbar">
        <button title="旋转" @click="handleRotate"><el-icon><RefreshRight /></el-icon></button>
        <button title="重置" @click="handleReset"><el-icon><FullScreen /></el-icon></button>
        <button title="裁剪" class="disabled"><el-icon><Crop /></el-icon></button>
        <button title="重命名" class="disabled"><el-icon><Edit /></el-icon></button>
        <button 
          title="收藏" 
          class="btn-fav" 
          :class="{ active: image?.is_favorite }" 
          @click="handleFavorite"
        >
          <el-icon><Star /></el-icon>
        </button>
        <button title="删除" class="btn-delete" @click="handleDelete">
          <el-icon><Delete /></el-icon>
        </button>
        <button title="关闭" class="close-btn" @click="emit('close')"><el-icon><Close /></el-icon></button>
      </div>

      <div class="image-meta" v-if="image">
        <span id="meta-filename" :title="image.file_name">{{ truncatedFileName }}</span>
        <span class="meta-divider">|</span>
        <span id="meta-resolution">{{ image.width }} x {{ image.height }}</span>
        <span class="meta-divider">|</span>
        <span id="meta-filesize">{{ fileSizeMB }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.lightbox {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
}

.lightbox-overlay {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.95);
}

.lightbox-content {
    position: relative;
    max-width: 90%;
    max-height: 85%;
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 100%;
    height: 100%;
    justify-content: center;
}

.lightbox-content img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    box-shadow: 0 0 40px rgba(0,0,0,0.5);
    will-change: transform, opacity;
}

/* 图片切换动画 */
.image-fade-enter-active,
.image-fade-leave-active {
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.image-fade-enter-from {
    opacity: 0;
    transform: scale(0.95);
}

.image-fade-leave-to {
    opacity: 0;
    transform: scale(1.05);
}

.lightbox-controls .control-btn {
    position: fixed;
    top: 50%;
    transform: translateY(-50%);
    background: rgba(255,255,255,0.1);
    border: none;
    color: white;
    font-size: 30px;
    padding: 20px;
    cursor: pointer;
    border-radius: 50%;
    width: 80px;
    height: 80px;
    display: flex;
    align-items: center;
    justify-content: center;
    /* Default hidden */
    opacity: 0;
    visibility: hidden;
    transition: all 0.3s ease;
}

.lightbox:hover .control-btn,
.lightbox:hover .lightbox-toolbar,
.lightbox:hover .image-meta {
    opacity: 1;
    visibility: visible;
}

.prev-btn { left: 40px; }
.next-btn { right: 40px; }

.lightbox-controls .control-btn:hover {
    background: rgba(255,255,255,0.2);
}

.lightbox-toolbar {
    position: fixed;
    top: 20px;
    right: 20px;
    display: flex;
    gap: 12px;
    opacity: 0;
    visibility: hidden;
    transition: all 0.3s ease;
}

.lightbox-toolbar button {
    background: rgba(255,255,255,0.1);
    border: none;
    color: white;
    width: 44px;
    height: 44px;
    border-radius: 8px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
}

.lightbox-toolbar button:hover {
    background: rgba(255,255,255,0.2);
}

.lightbox-toolbar .btn-fav.active {
    color: #ff9800;
}

.lightbox-toolbar .btn-delete:hover {
    background: rgba(245, 108, 108, 0.2);
    color: #f56c6c;
}

.lightbox-toolbar button.disabled {
    opacity: 0.3;
    cursor: not-allowed;
}

.image-meta {
    position: fixed;
    bottom: 30px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(0,0,0,0.6);
    padding: 10px 25px;
    border-radius: 30px;
    color: white;
    font-size: 14px;
    display: flex;
    gap: 15px;
    align-items: center;
    backdrop-filter: blur(10px);
    z-index: 1010;
    opacity: 0;
    visibility: hidden;
    transition: all 0.3s ease;
}

.meta-divider {
    opacity: 0.3;
    color: #fff;
    font-weight: 300;
}

#meta-filename {
    font-weight: 500;
    max-width: 400px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
</style>
