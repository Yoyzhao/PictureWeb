<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch, nextTick } from 'vue'
import api from '@/api'
import { Close, ArrowLeft, ArrowRight, RefreshRight, Crop, Edit, Star, FullScreen, Delete, Loading, Rank, InfoFilled, CollectionTag } from '@element-plus/icons-vue'
import type { Image as ImageItem } from '@/stores/image'
import { useImageStore } from '@/stores/image'
import { useFolderStore } from '@/stores/folder'
import { useAuthStore } from '@/stores/auth'
import { useBookmarkStore } from '@/stores/bookmark'
import { useHotkeyStore } from '@/stores/hotkey'
import { ElMessageBox, ElMessage } from 'element-plus'
import ImageInfoDialog from './ImageInfoDialog.vue'

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
const folderStore = useFolderStore()
const authStore = useAuthStore()
const bookmarkStore = useBookmarkStore()
const hotkeyStore = useHotkeyStore()
const hotkeys = computed(() => hotkeyStore.hotkeys)
const canEdit = computed(() => !!authStore.user && authStore.user.role !== 'guest')
const isImageBookmarked = computed(() =>
  !!props.image && bookmarkStore.bookmarkedImageIds.has(props.image.id)
)

const showMoveDialog = ref(false)
const targetFolderId = ref<number | null>(null)
const isMoving = ref(false)
const showInfoDialog = ref(false)

const isPreloadEnabled = ref(true)
const imageLoaded = ref(false)

const fetchPreloadSetting = async () => {
  try {
    const res = await api.get('/settings')
    if (res.data && res.data.ENABLE_PRELOAD !== undefined) {
      isPreloadEnabled.value = !!res.data.ENABLE_PRELOAD
    }
  } catch (err) {
    // 默认开启，如果获取失败也不影响
    console.warn('Failed to fetch preload setting, using default: enabled')
  }
}

const imageUrl = computed(() => props.image ? `/api/images/${props.image.id}/raw` : '')

// Preload logic (bounded to avoid unbounded URL/image-cache growth while browsing).
const MAX_PRELOADED = 120
const MAX_RAW_PRELOAD_BYTES = 6 * 1024 * 1024
const preloadedUrls = new Set<string>()
const preloadTimers = new Set<number>()

const rememberPreloaded = (url: string) => {
  if (preloadedUrls.size >= MAX_PRELOADED) preloadedUrls.clear()
  preloadedUrls.add(url)
}

const schedulePreload = (fn: () => void, delay: number) => {
  const timer = window.setTimeout(() => {
    preloadTimers.delete(timer)
    fn()
  }, delay)
  preloadTimers.add(timer)
}

const clearPreloadTimers = () => {
  preloadTimers.forEach(id => clearTimeout(id))
  preloadTimers.clear()
}

const preloadThumbnail = (image: ImageItem | null) => {
  if (!image || !isPreloadEnabled.value) return
  const thumbUrl = `/api/images/${image.id}/thumbnail?size=medium`
  if (preloadedUrls.has(thumbUrl)) return

  const thumbImg = new Image()
  thumbImg.src = thumbUrl
  rememberPreloaded(thumbUrl)
}

watch(() => props.image?.id, (newId) => {
  clearPreloadTimers()
  if (!newId || !isPreloadEnabled.value) return

  schedulePreload(() => {
    if (props.image?.id === newId) preloadThumbnail(props.nextImage)
  }, 200)

  schedulePreload(() => {
    if (props.image?.id === newId) preloadThumbnail(props.prevImage)
  }, 600)

  // Only preload raw for reasonably sized next images; large originals hurt bandwidth and decode time.
  const nextImg = props.nextImage
  if (nextImg && (nextImg.file_size || 0) <= MAX_RAW_PRELOAD_BYTES) {
    schedulePreload(() => {
      if (props.image?.id !== newId || props.nextImage?.id !== nextImg.id) return
      const rawUrl = `/api/images/${nextImg.id}/raw`
      if (preloadedUrls.has(rawUrl)) return
      const rawImg = new Image()
      rawImg.src = rawUrl
      if ('decode' in rawImg) rawImg.decode().catch(() => { /* ignore */ })
      rememberPreloaded(rawUrl)
    }, 1500)
  }
}, { immediate: true })

watch(() => props.visible, (visible) => {
  if (visible) {
    fetchPreloadSetting()
    showUI.value = true // Reset UI visibility when opening
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
const showUI = ref(true) // 控制 UI 显示/隐藏

// Touch handling state
const touchStartX = ref(0)
const touchStartY = ref(0)
const touchEndX = ref(0)
const touchEndY = ref(0)
const initialPinchDistance = ref(0)
const initialScale = ref(1)
const isSwiping = ref(false)
const isPinching = ref(false)

const transitionName = ref('slide-left')

const goNext = () => {
  transitionName.value = 'slide-left'
  emit('next')
}

const goPrev = () => {
  transitionName.value = 'slide-right'
  emit('prev')
}

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
    // Reset end positions to prevent accidental swipes from previous touch data
    touchEndX.value = e.touches[0].clientX
    touchEndY.value = e.touches[0].clientY
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

    // Horizontal swipe
    if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > threshold) {
      if (deltaX > 0 && props.hasPrev) {
        goPrev()
      } else if (deltaX < 0 && props.hasNext) {
        goNext()
      }
    }
    // Vertical swipe
    else if (Math.abs(deltaY) > Math.abs(deltaX) && Math.abs(deltaY) > threshold) {
      if (deltaY > 0 && props.hasPrev) {
        // Swipe Down -> Previous image
        transitionName.value = 'slide-down'
        emit('prev')
      } else if (deltaY < 0 && props.hasNext) {
        // Swipe Up -> Next image
        transitionName.value = 'slide-up'
        emit('next')
      }
    }
  }
  isSwiping.value = false
  isPinching.value = false
}

const isTransforming = computed(() => (
  scale.value !== 1 || translateX.value !== 0 || translateY.value !== 0
))
const isInteracting = computed(() => (
  isPinching.value || (scale.value > 1 && isSwiping.value)
))

const imageStyle = computed(() => ({
  transform: `translate(${translateX.value}px, ${translateY.value}px) scale(${scale.value}) rotate(${rotate.value}deg)`
}))

// Reset transformations when image changes
watch(() => props.image?.id, () => {
  scale.value = 1
  rotate.value = 0
  translateX.value = 0
  translateY.value = 0
  imageLoaded.value = false
})

let wheelRaf = 0
let pendingScale = 1

const handleWheel = (e: WheelEvent) => {
  if (!props.visible) return
  e.preventDefault()

  if (!wheelRaf) pendingScale = scale.value
  const delta = e.deltaY > 0 ? -0.1 : 0.1
  pendingScale = Math.max(0.1, Math.min(5, pendingScale + delta))

  if (wheelRaf) return
  wheelRaf = requestAnimationFrame(() => {
    scale.value = pendingScale
    wheelRaf = 0
  })
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

const toggleUI = () => {
  showUI.value = !showUI.value
}

const handleFavorite = async () => {
  if (props.image) {
    const isCurrentlyFavorite = props.image.is_favorite
    const isInFavoritesView = imageStore.showOnlyFavorites

    // If we're unfavoriting while in favorites view, we need to move to the next image
    // BEFORE the store update removes this image from the list.
    if (isCurrentlyFavorite && isInFavoritesView) {
      if (props.hasNext) {
        goNext()
      } else if (props.hasPrev) {
        goPrev()
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
        goNext()
      } else if (props.hasPrev) {
        goPrev()
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

const handleSaveBookmark = () => {
  if (!props.image) return
  bookmarkStore.toggleAt(props.image.id)
}

const openMoveDialog = () => {
  if (!props.image) return
  if (folderStore.folders.length === 0) folderStore.fetchFolders()
  targetFolderId.value = null
  showMoveDialog.value = true
}

const handleMove = async () => {
  if (!props.image) return
  if (!targetFolderId.value) {
    ElMessage.warning('请选择目标文件夹')
    return
  }

  const imageId = props.image.id
  const targetId = targetFolderId.value
  if (targetId === props.image.folder_id) {
    ElMessage.warning('图片已在该文件夹中')
    return
  }

  isMoving.value = true
  try {
    const res = await imageStore.batchMoveImages([imageId], targetId)
    const body = res.data
    const movedIds: number[] = body.moved_ids || []
    const errors: string[] = body.errors || []

    if (movedIds.includes(imageId)) {
      ElMessage.success('移动成功')
      showMoveDialog.value = false
      targetFolderId.value = null

      // If the current view is a concrete folder the image no longer belongs to,
      // navigate away first and then drop it from the list (same flow as delete).
      if (folderStore.currentFolderId !== undefined && folderStore.currentFolderId !== targetId) {
        if (props.hasNext) {
          goNext()
        } else if (props.hasPrev) {
          goPrev()
        } else {
          emit('close')
        }
        imageStore.removeImageLocally(imageId)
      } else {
        // Keep the item in "all photos"/favorites views, but refresh its folder/path/name
        // so the next move dialog excludes the folder it now belongs to.
        await imageStore.refreshImage(imageId)
      }
    } else if (errors.length > 0) {
      ElMessage.error('移动失败: ' + errors[0])
    }
  } catch (error: any) {
    ElMessage.error('移动失败: ' + (error.response?.data?.error || error.message))
  } finally {
    isMoving.value = false
  }
}

const handleKeydown = (e: KeyboardEvent) => {
  if (!props.visible) return
  // Dialogs own the keyboard while they are open; shortcuts must not mutate the gallery underneath.
  if (showMoveDialog.value || showInfoDialog.value) return

  const key = e.key
  const hk = hotkeys.value

  if (key === hk.CLOSE) emit('close')
  if (key === hk.PREV && props.hasPrev) goPrev()
  if (key === hk.NEXT && props.hasNext) goNext()
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
  clearPreloadTimers()
  if (wheelRaf) cancelAnimationFrame(wheelRaf)
})
</script>

<template>
  <div
    v-if="visible"
    class="lightbox"
    :class="{ 'ui-visible': showUI, 'ui-hidden': !showUI }"
    role="dialog"
    aria-modal="true"
    aria-label="图片预览"
    @click="toggleUI"
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
      <transition :name="transitionName">
        <div :key="imageUrl" class="image-wrapper">
          <img
            :src="imageUrl"
            :alt="image?.file_name"
            :style="imageStyle"
            decoding="async"
            fetchpriority="high"
            :class="{ 'is-loaded': imageLoaded, 'is-transforming': isTransforming, 'is-interacting': isInteracting }"
            @load="imageLoaded = true"
            @error="imageLoaded = true"
            @click.stop="toggleUI"
            draggable="false"
          />
        </div>
      </transition>
      <div class="lightbox-controls" @click.stop>
        <button v-if="hasPrev" class="control-btn prev-btn" aria-label="上一张" @click.stop="goPrev" @touchstart.stop @touchend.stop>
          <el-icon><ArrowLeft /></el-icon>
        </button>
        <button v-if="hasNext" class="control-btn next-btn" aria-label="下一张" @click.stop="goNext" @touchstart.stop @touchend.stop>
          <el-icon><ArrowRight /></el-icon>
        </button>
      </div>

      <div class="lightbox-toolbar" @touchstart.stop @touchend.stop @click.stop>
        <button title="旋转" aria-label="旋转" @click="handleRotate"><el-icon><RefreshRight /></el-icon></button>
        <button title="重置" aria-label="重置视图" @click="handleReset"><el-icon><FullScreen /></el-icon></button>
        <button title="裁剪（开发中）" aria-label="裁剪（开发中）" class="disabled"><el-icon><Crop /></el-icon></button>
        <button title="重命名" aria-label="重命名" @click="handleRename"><el-icon><Edit /></el-icon></button>
        <button v-if="canEdit" title="移动" aria-label="移动" @click="openMoveDialog"><el-icon><Rank /></el-icon></button>
        <button
          title="收藏"
          aria-label="收藏"
          class="btn-fav"
          :class="{ active: image?.is_favorite }"
          @click="handleFavorite"
        >
          <el-icon><Star /></el-icon>
        </button>
        <button title="信息" aria-label="查看图片信息" @click="showInfoDialog = true"><el-icon><InfoFilled /></el-icon></button>
        <button
          v-if="canEdit"
          class="btn-bookmark"
          :class="{ active: isImageBookmarked }"
          :title="isImageBookmarked ? '取消书签' : '书签'"
          :aria-label="isImageBookmarked ? '取消书签' : '保存当前位置为书签'"
          @click="handleSaveBookmark"
        >
          <el-icon><CollectionTag /></el-icon>
        </button>
        <button title="删除" aria-label="删除" class="btn-delete" @click="handleDelete">
          <el-icon><Delete /></el-icon>
        </button>
        <button title="关闭" aria-label="关闭" class="close-btn" @click="emit('close')"><el-icon><Close /></el-icon></button>
      </div>

      <div class="image-meta" v-if="image" @touchstart.stop @touchend.stop @click.stop>
        <span id="meta-filename" :title="image.file_name">{{ truncatedFileName }}</span>
        <span class="meta-divider">|</span>
        <span id="meta-resolution">{{ image.width }} x {{ image.height }}</span>
        <span class="meta-divider">|</span>
        <span id="meta-filesize">{{ fileSizeMB }}</span>
      </div>
    </div>

    <el-dialog v-model="showMoveDialog" title="移动图片" width="400px" append-to-body>
      <el-form label-position="top">
        <el-form-item label="选择目标文件夹">
          <el-select v-model="targetFolderId" placeholder="请选择" style="width: 100%">
            <el-option
              v-for="folder in folderStore.folders"
              :key="folder.id"
              :label="folder.name"
              :value="folder.id"
              :disabled="folder.id === image?.folder_id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showMoveDialog = false">取消</el-button>
        <el-button type="primary" :loading="isMoving" @click="handleMove">确定移动</el-button>
      </template>
    </el-dialog>

    <ImageInfoDialog v-model="showInfoDialog" :image="image" />
  </div>
</template>

<style scoped>
.lightbox {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    height: 100dvh;
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
    overscroll-behavior: contain;
    /* 手势由组件内部处理，避免浏览器缩放/滚动抢占 */
    touch-action: none;
    user-select: none;
    -webkit-user-select: none;
    -webkit-tap-highlight-color: transparent;
}

.lightbox-overlay {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: radial-gradient(circle at 50% 32%, rgba(24, 26, 30, 0.94), rgba(0, 0, 0, 0.98));
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

.image-wrapper {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
}

.lightbox-content img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    box-shadow: 0 0 40px rgba(0,0,0,0.5);
    user-select: none;
    -webkit-user-drag: none;
    opacity: 0;
    transition: opacity 220ms ease, transform 180ms var(--ease-out);
}

.lightbox-content img.is-loaded {
    opacity: 1;
}

.lightbox-content img.is-transforming {
    will-change: transform;
}

.lightbox-content img.is-interacting {
    transition: none;
}

/* 图片切换动画 - 向左滑动 (下一页) */
.slide-left-enter-active,
.slide-left-leave-active,
.slide-right-enter-active,
.slide-right-leave-active,
.slide-up-enter-active,
.slide-up-leave-active,
.slide-down-enter-active,
.slide-down-leave-active {
    transition: transform 240ms var(--ease-out), opacity 200ms ease;
}
.slide-left-enter-from {
    opacity: 0;
    transform: translateX(100px);
}
.slide-left-leave-to {
    opacity: 0;
    transform: translateX(-100px);
}

/* 图片切换动画 - 向右滑动 (上一页) */
.slide-right-enter-from {
    opacity: 0;
    transform: translateX(-100px);
}
.slide-right-leave-to {
    opacity: 0;
    transform: translateX(100px);
}

/* 图片切换动画 - 向上滑动 (下一页) */
.slide-up-enter-from {
    opacity: 0;
    transform: translateY(100px);
}
.slide-up-leave-to {
    opacity: 0;
    transform: translateY(-100px);
}

/* 图片切换动画 - 向下滑动 (上一页) */
.slide-down-enter-from {
    opacity: 0;
    transform: translateY(-100px);
}
.slide-down-leave-to {
    opacity: 0;
    transform: translateY(100px);
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
    transition: opacity 200ms ease, background-color var(--motion-fast) var(--ease-out), transform 200ms var(--ease-out);
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
    transition: opacity 200ms ease, transform 200ms var(--ease-out);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

.lightbox.ui-visible .control-btn,
.lightbox.ui-visible .lightbox-toolbar,
.lightbox.ui-visible .image-counter,
.lightbox.ui-visible .image-meta,
.lightbox:hover .control-btn,
.lightbox:hover .lightbox-toolbar,
.lightbox:hover .image-counter,
.lightbox:hover .image-meta {
    opacity: 1;
    visibility: visible;
}

.lightbox.ui-hidden .control-btn,
.lightbox.ui-hidden .lightbox-toolbar,
.lightbox.ui-hidden .image-counter,
.lightbox.ui-hidden .image-meta {
    opacity: 0 !important;
    visibility: hidden !important;
    pointer-events: none;
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
    gap: 4px;
    padding: 6px;
    background: rgba(15, 18, 22, 0.55);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    backdrop-filter: blur(14px);
    opacity: 0;
    visibility: hidden;
    transition: opacity 200ms ease, transform 200ms var(--ease-out);
    transform: translateY(-6px);
}

.lightbox.ui-visible .lightbox-toolbar,
.lightbox:hover .lightbox-toolbar {
    transform: none;
}

.lightbox-toolbar button {
    background: transparent;
    border: none;
    color: rgba(255, 255, 255, 0.86);
    width: 40px;
    height: 40px;
    border-radius: 10px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    transition: background-color var(--motion-fast) var(--ease-out),
                color var(--motion-fast) var(--ease-out);
}

.lightbox-toolbar button:hover {
    background: rgba(255, 255, 255, 0.12);
    color: #fff;
}

.lightbox-toolbar .btn-fav.active {
    color: #ffb74d;
}

.lightbox-toolbar .btn-bookmark.active {
    color: var(--primary);
    background: var(--primary-soft);
}

.lightbox-toolbar .btn-delete:hover {
    background: rgba(245, 108, 108, 0.18);
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
    transition: opacity 200ms ease, transform 200ms var(--ease-out);
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
        /* 计数器位于左上角，工具栏下移避免按钮增多后换行遮挡 */
        top: 48px;
        right: 10px;
        gap: 8px;
        flex-wrap: wrap;
        justify-content: flex-end;
        max-width: calc(100vw - 20px);
    }

    .lightbox-toolbar button {
        width: 44px;
        height: 44px;
        font-size: 18px;
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
