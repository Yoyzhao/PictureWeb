<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch, nextTick } from 'vue'
import api from '@/api'
import { Close, ArrowLeft, ArrowRight, RefreshRight, Crop, Edit, Star, FullScreen, Delete, Loading } from '@element-plus/icons-vue'
import type { Image as ImageItem } from '@/stores/image'
import { useImageStore } from '@/stores/image'
import { useHotkeyStore } from '@/stores/hotkey'
import { ElMessageBox, ElMessage } from 'element-plus'

const props = defineProps<{
  visible: boolean
  image: ImageItem | null
  prevImage: ImageItem | null
  nextImage: ImageItem | null
  hasPrev: boolean
  hasNext: boolean
  currentIndex?: number
  totalImages?: number
  loading?: boolean
}>()

const emit = defineEmits(['close', 'prev', 'next'])
const imageStore = useImageStore()
const hotkeyStore = useHotkeyStore()
const hotkeys = computed(() => hotkeyStore.hotkeys)

const isPreloadEnabled = ref(true)

const fetchPreloadSetting = async () => {
  try {
    const res = await api.get('/admin/settings')
    if (res.data && res.data.ENABLE_PRELOAD !== undefined) {
      isPreloadEnabled.value = !!res.data.ENABLE_PRELOAD
    }
  } catch (err) {
    // 默认开启，如果获取失败也不影响
    console.warn('Failed to fetch preload setting, using default: enabled')
  }
}

const imageUrl = computed(() => props.image ? `/api/images/${props.image.id}/raw` : '')

// Preload logic
const preloadedUrls = new Set<string>()

const preloadImage = (image: ImageItem | null, isNext: boolean) => {
  if (!image || !isPreloadEnabled.value) return
  
  // Preload medium thumbnail first (fast, reliable fallback)
  const thumbUrl = `/api/images/${image.id}/thumbnail?size=medium`
  if (!preloadedUrls.has(thumbUrl)) {
    const thumbImg = new Image()
    thumbImg.src = thumbUrl
    preloadedUrls.add(thumbUrl)
  }

  // Only preload raw image for the NEXT one to save cache/bandwidth
  // Most users browse forward. Preloading 10MB+ for the previous image is often wasteful.
  if (isNext) {
    const rawUrl = `/api/images/${image.id}/raw`
    if (!preloadedUrls.has(rawUrl)) {
      const rawImg = new Image()
      // Use decode() to ensure the image is ready in memory without blocking main thread
      rawImg.src = rawUrl
      if ('decode' in rawImg) {
        rawImg.decode().catch(() => { /* ignore error */ })
      }
      preloadedUrls.add(rawUrl)
    }
  }
}

watch(() => props.image?.id, (newId) => {
  if (newId) {
    if (!isPreloadEnabled.value) return

    // Priority 1: Next image medium thumb (immediate-ish)
    setTimeout(() => {
      if (props.nextImage) preloadImage(props.nextImage, true)
    }, 300)

    // Priority 2: Prev image medium thumb (short delay)
    setTimeout(() => {
      if (props.prevImage) preloadImage(props.prevImage, false)
    }, 800)
    
    // Priority 3: Next image RAW (Delay depends on file size)
    const nextImg = props.nextImage
    if (nextImg) {
      const isLarge = (nextImg.file_size || 0) > 10 * 1024 * 1024
      const rawDelay = isLarge ? 3000 : 1200
      
      setTimeout(() => {
        if (props.image?.id === newId && props.nextImage?.id === nextImg.id) {
          const rawUrl = `/api/images/${nextImg.id}/raw`
          if (!preloadedUrls.has(rawUrl)) {
            const rawImg = new Image()
            rawImg.src = rawUrl
            preloadedUrls.add(rawUrl)
          }
        }
      }, rawDelay)
    }
  }
}, { immediate: true })

watch(() => props.visible, (visible) => {
  if (visible) {
    fetchPreloadSetting()
  }
})

const truncatedFileName = computed(() => {
  if (!props.image?.file_name) return ''
  const name = props.image.file_name
  return name.length > 20 ? name.slice(0, 17) + '...' : name
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

// Touch handling state
const touchStartX = ref(0)
const touchStartY = ref(0)
const touchEndX = ref(0)
const touchEndY = ref(0)
const initialPinchDistance = ref(0)
const initialScale = ref(1)
const isSwiping = ref(false)
const isPinching = ref(false)

const getDistance = (touches: TouchList) => {
  return Math.hypot(
    touches[0].clientX - touches[1].clientX,
    touches[0].clientY - touches[1].clientY
  )
}

const handleTouchStart = (e: TouchEvent) => {
  if (e.touches.length === 1) {
    touchStartX.value = e.touches[0].clientX
    touchStartY.value = e.touches[0].clientY
    isSwiping.value = true
    isPinching.value = false
  } else if (e.touches.length === 2) {
    isPinching.value = true
    isSwiping.value = false
    initialPinchDistance.value = getDistance(e.touches)
    initialScale.value = scale.value
  }
}

const handleTouchMove = (e: TouchEvent) => {
  if (isPinching.value && e.touches.length === 2) {
    if (e.cancelable) e.preventDefault()
    const currentDistance = getDistance(e.touches)
    const ratio = currentDistance / initialPinchDistance.value
    scale.value = Math.max(0.1, Math.min(5, initialScale.value * ratio))
  } else if (isSwiping.value && e.touches.length === 1 && scale.value === 1) {
    touchEndX.value = e.touches[0].clientX
    touchEndY.value = e.touches[0].clientY
  } else if (scale.value > 1 && e.touches.length === 1) {
    if (e.cancelable) e.preventDefault()
    // Optional: Add image panning when zoomed in
    const dx = e.touches[0].clientX - touchStartX.value
    const dy = e.touches[0].clientY - touchStartY.value
    translateX.value += dx
    translateY.value += dy
    touchStartX.value = e.touches[0].clientX
    touchStartY.value = e.touches[0].clientY
  }
}

const handleTouchEnd = (e: TouchEvent) => {
  if (isSwiping.value && scale.value === 1) {
    const deltaX = touchEndX.value - touchStartX.value
    const deltaY = touchEndY.value - touchStartY.value
    const threshold = 50

    if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > threshold) {
      if (deltaX > 0 && props.hasPrev) {
        emit('prev')
      } else if (deltaX < 0 && props.hasNext) {
        emit('next')
      }
    }
  }
  isSwiping.value = false
  isPinching.value = false
}

const imageStyle = computed(() => ({
  transform: `translate(${translateX.value}px, ${translateY.value}px) scale(${scale.value}) rotate(${rotate.value}deg)`,
  transition: isPinching.value || (scale.value > 1 && isSwiping.value) ? 'none' : 'transform 0.2s cubic-bezier(0.25, 0.46, 0.45, 0.94)'
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
    const isCurrentlyFavorite = props.image.is_favorite
    const isInFavoritesView = imageStore.showOnlyFavorites
    
    // If we're unfavoriting while in favorites view, we need to move to the next image
    // BEFORE the store update removes this image from the list.
    if (isCurrentlyFavorite && isInFavoritesView) {
      if (props.hasNext) {
        emit('next')
      } else if (props.hasPrev) {
        emit('prev')
      } else {
        emit('close')
      }
      // Wait for the transition to start
      await nextTick()
    }
    
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
      const deletedId = props.image.id
      ElMessage.success('删除成功')
      
      // 1. Move to next/prev image first to keep the lightbox open
      if (props.hasNext) {
        emit('next')
      } else if (props.hasPrev) {
        emit('prev')
      } else {
        emit('close')
      }
      
      // 2. Remove from local store silently instead of full refresh
      imageStore.removeImageLocally(deletedId)
      
      // 3. Optional: Trigger a silent load for more images if list is getting short
      if (imageStore.images.length < 20 && imageStore.total > imageStore.images.length) {
        imageStore.fetchImages()
      }
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败: ' + (error.response?.data?.error || error.message))
    }
  }
}

const handleRename = async () => {
  if (!props.image) return
  
  try {
    const result = await ElMessageBox.prompt(
      '请输入新的文件名',
      '重命名',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        inputValue: props.image.file_name,
        inputPattern: /^[^\\/:*?"<>|]+$/,
        inputErrorMessage: '文件名包含非法字符',
      }
    )
    const newName = (result as any).value
    
    if (newName && newName !== props.image.file_name) {
      const res = await imageStore.renameImage(props.image.id, newName)
      if (res.success) {
        ElMessage.success('重命名成功')
      }
    }
  } catch (error) {
    // User cancelled
  }
}

const handleKeydown = (e: KeyboardEvent) => {
  if (!props.visible) return
  
  const key = e.key
  const hk = hotkeys.value

  if (key === hk.CLOSE) emit('close')
  if (key === hk.PREV && props.hasPrev) emit('prev')
  if (key === hk.NEXT && props.hasNext) emit('next')
  if (key === hk.DELETE) {
    e.preventDefault()
    handleDelete()
  }
  if (key === hk.ZOOM_IN) {
    e.preventDefault()
    scale.value = Math.min(5, scale.value + 0.2)
  }
  if (key === hk.ZOOM_OUT) {
    e.preventDefault()
    scale.value = Math.max(0.1, scale.value - 0.2)
  }
  if (key === hk.ROTATE) handleRotate()
  if (key === hk.FAVORITE) handleFavorite()
  if (key === hk.RESET) handleReset()
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
  <div 
    v-if="visible" 
    class="lightbox" 
    @click.self="emit('close')" 
    @wheel="handleWheel"
    @touchstart="handleTouchStart"
    @touchmove="handleTouchMove"
    @touchend="handleTouchEnd"
  >
    <div class="lightbox-overlay"></div>
    
    <div class="image-counter" v-if="currentIndex !== undefined && totalImages !== undefined">
      {{ currentIndex + 1 }} / {{ totalImages }}
    </div>

    <div class="loading-overlay" v-if="loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>正在加载更多图片...</span>
    </div>

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
        <button title="重命名" @click="handleRename"><el-icon><Edit /></el-icon></button>
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
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
}

.lightbox-content img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    box-shadow: 0 0 40px rgba(0,0,0,0.5);
    will-change: transform, opacity;
    user-select: none;
    -webkit-user-drag: none;
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
    background: rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.2);
    color: white;
    font-size: 24px;
    padding: 12px;
    cursor: pointer;
    border-radius: 50%;
    width: 56px;
    height: 56px;
    display: flex;
    align-items: center;
    justify-content: center;
    /* Default hidden */
    opacity: 0;
    visibility: hidden;
    transition: all 0.3s ease;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.loading-overlay {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: rgba(0, 0, 0, 0.7);
    padding: 20px 30px;
    border-radius: 12px;
    color: white;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    z-index: 1002;
    font-size: 14px;
}

.loading-overlay .el-icon {
    font-size: 32px;
}

.image-counter {
    position: absolute;
    top: 20px;
    left: 20px;
    color: white;
    font-size: 14px;
    font-weight: 500;
    background: rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    padding: 6px 14px;
    border-radius: 20px;
    z-index: 1001;
    pointer-events: none;
    user-select: none;
    opacity: 0;
    visibility: hidden;
    transition: all 0.3s ease;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

.lightbox:hover .control-btn,
.lightbox:hover .lightbox-toolbar,
.lightbox:hover .image-counter,
.lightbox:hover .image-meta {
    opacity: 1;
    visibility: visible;
}

.prev-btn { left: 20px; }
.next-btn { right: 20px; }

.lightbox-controls .control-btn:hover {
    background: rgba(0, 0, 0, 0.7);
    border-color: var(--primary);
    transform: translateY(-50%) scale(1.05);
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
    background: rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.2);
    color: white;
    width: 44px;
    height: 44px;
    border-radius: 8px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    transition: all 0.2s ease;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

.lightbox-toolbar button:hover {
    background: rgba(0, 0, 0, 0.7);
    border-color: var(--primary);
    transform: translateY(-2px);
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
    background: rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    padding: 10px 25px;
    border-radius: 30px;
    color: white;
    font-size: 14px;
    display: flex;
    gap: 15px;
    align-items: center;
    z-index: 1010;
    opacity: 0;
    visibility: hidden;
    transition: all 0.3s ease;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
}

.meta-divider {
    opacity: 0.3;
    color: #fff;
    font-weight: 300;
}

/* 移动端优化 */
@media (max-width: 768px) {
    .lightbox-controls .control-btn {
        display: none; /* 移动端使用手势切换，隐藏按钮 */
    }

    .lightbox-toolbar {
        top: 10px;
        right: 10px;
        gap: 8px;
    }

    .lightbox-toolbar button {
        width: 38px;
        height: 38px;
        font-size: 16px;
    }

    .image-meta {
        bottom: 20px;
        padding: 8px 16px;
        font-size: 12px;
        width: 90%;
        max-width: none;
        justify-content: center;
    }

    #meta-filename {
        max-width: 150px;
    }

    .image-counter {
        top: 10px;
        left: 10px;
        font-size: 12px;
        padding: 4px 10px;
    }
}
</style>
