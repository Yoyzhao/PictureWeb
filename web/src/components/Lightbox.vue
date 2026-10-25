<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch, nextTick } from 'vue'
import api from '@/api'
import { Close, ArrowLeft, ArrowRight, RefreshRight, Crop, Edit, Star, FullScreen, Delete, Loading, Rank, InfoFilled, CollectionTag, View, Hide, Monitor, Link, Download, More, VideoPlay, VideoPause, DArrowLeft, DArrowRight, Mute, Microphone, Setting } from '@element-plus/icons-vue'
import { storeToRefs } from 'pinia'
import type { Image as ImageItem } from '@/stores/image'
import { useImageStore } from '@/stores/image'
import { useFolderStore } from '@/stores/folder'
import { useAuthStore } from '@/stores/auth'
import { useBookmarkStore } from '@/stores/bookmark'
import { useHotkeyStore } from '@/stores/hotkey'
import { useUIStore } from '@/stores/ui'
import { ElMessageBox, ElMessage } from 'element-plus'
import ImageInfoDialog from './ImageInfoDialog.vue'
import {
  buildRawUrl,
  copyPlayUrl,
  detectPlatform,
  downloadM3U,
  downloadOriginal,
  openInVlc
} from '@/utils/externalPlayer'

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
const uiStore = useUIStore()
const { showLightboxImageInfo } = storeToRefs(uiStore)
const hotkeyStore = useHotkeyStore()
const hotkeys = computed(() => hotkeyStore.hotkeys)
const canEdit = computed(() => !!authStore.user && authStore.user.role !== 'guest')
const isImageBookmarked = computed(() =>
  !!props.image && bookmarkStore.bookmarkedImageIds.has(props.image.id)
)

const isVideo = computed(() => props.image?.media_type === 'video')
const videoError = ref(false)
const videoRef = ref<HTMLVideoElement | null>(null)
const videoPoster = computed(() =>
  props.image ? `/api/images/${props.image.id}/thumbnail?size=medium` : ''
)
const platform = detectPlatform()

const videoFormatHint = computed(() => {
  const format = String(props.image?.format || '').toLowerCase()
  if (format === 'flv') {
    return 'FLV 是 Flash 容器，现代浏览器已不再支持；请用本地播放器（如 VLC）打开'
  }
  if (['mkv', 'avi', 'wmv'].includes(format)) {
    return '该容器通常不被浏览器支持；请用本地播放器（如 VLC）打开'
  }
  return '可用本地播放器（如 VLC）打开这个视频，不会下载文件'
})

const formatDuration = (seconds?: number | null) => {
  const total = Math.floor(Number(seconds) || 0)
  if (total <= 0) return ''
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const secs = total % 60
  const pad = (value: number) => String(value).padStart(2, '0')
  return hours > 0 ? `${hours}:${pad(minutes)}:${pad(secs)}` : `${minutes}:${pad(secs)}`
}

// --- Video playback state -------------------------------------------------
const VIDEO_IDLE_MS = 2500
const VIDEO_POSITION_PREFIX = 'picgallery.videoPosition.'
const VIDEO_RESUME_MIN_SECONDS = 5

const videoPlaying = ref(false)
const videoCurrentTime = ref(0)
const videoDuration = ref(0)
const videoMuted = ref(false)
const videoUiIdle = ref(false)
const videoBuffering = ref(false)
const videoRate = ref(1)
const resumePosition = ref<number | null>(null)
const PLAYBACK_RATES = [0.5, 0.75, 1, 1.25, 1.5, 2]
let videoIdleTimer: number | undefined
let resumeChipTimer: number | undefined
let lastSavedSecond = -1

const videoAspectRatio = computed(() => {
  const width = Number(props.image?.width) || 0
  const height = Number(props.image?.height) || 0
  return width > 0 && height > 0 ? width / height : 16 / 9
})

const videoTimeText = computed(() =>
  `${formatDuration(videoCurrentTime.value) || '0:00'} / ${formatDuration(videoDuration.value) || '0:00'}`
)
const uiHidden = computed(() => (isVideo.value ? videoUiIdle.value : !showUI.value))

const positionKey = (id?: number) => (id ? `${VIDEO_POSITION_PREFIX}${id}` : '')

const readSavedPosition = (id?: number) => {
  if (!id) return null
  const raw = Number(localStorage.getItem(positionKey(id)))
  return Number.isFinite(raw) && raw >= VIDEO_RESUME_MIN_SECONDS ? raw : null
}

const saveVideoPosition = () => {
  if (!isVideo.value || !props.image || videoError.value) return
  const element = videoRef.value
  if (!element) return
  const time = element.currentTime
  if (!Number.isFinite(time) || time < VIDEO_RESUME_MIN_SECONDS || element.ended) return
  localStorage.setItem(positionKey(props.image.id), String(Math.floor(time)))
}

const clearVideoPosition = (id?: number) => {
  if (id) localStorage.removeItem(positionKey(id))
}

const clearVideoIdleTimer = () => {
  if (videoIdleTimer) {
    clearTimeout(videoIdleTimer)
    videoIdleTimer = undefined
  }
}

const clearResumeChipTimer = () => {
  if (resumeChipTimer) {
    clearTimeout(resumeChipTimer)
    resumeChipTimer = undefined
  }
}

const showVideoChrome = () => {
  videoUiIdle.value = false
  clearVideoIdleTimer()
  const element = videoRef.value
  // Keep the controls visible while paused; only auto-hide during playback.
  if (!isVideo.value || videoError.value || !element || element.paused) return
  videoIdleTimer = window.setTimeout(() => {
    videoUiIdle.value = true
  }, VIDEO_IDLE_MS)
}

const markVideoActivity = () => {
  if (!isVideo.value) return
  showVideoChrome()
}

const handleStageClick = () => {
  if (isVideo.value) {
    markVideoActivity()
    return
  }
  toggleUI()
}

const handleVideoSurfaceClick = () => {
  markVideoActivity()
}

const handleVideoLoaded = () => {
  const element = videoRef.value
  videoDuration.value = element?.duration || props.image?.duration || 0
  videoCurrentTime.value = element?.currentTime || 0
  videoBuffering.value = false
  if (element) element.playbackRate = videoRate.value

  const saved = readSavedPosition(props.image?.id)
  const duration = videoDuration.value
  if (saved && (!duration || saved < duration * 0.95)) {
    resumePosition.value = saved
    clearResumeChipTimer()
    resumeChipTimer = window.setTimeout(() => {
      resumePosition.value = null
    }, 8000)
  }
}

const handleVideoTimeUpdate = () => {
  const element = videoRef.value
  if (!element) return
  videoCurrentTime.value = element.currentTime

  if (resumePosition.value !== null && element.currentTime > 2) {
    resumePosition.value = null
    clearResumeChipTimer()
  }

  if (!element.paused && !element.ended) {
    // timeupdate fires several times per second; persist at second granularity.
    const second = Math.floor(element.currentTime)
    if (second !== lastSavedSecond) {
      lastSavedSecond = second
      saveVideoPosition()
    }
  }
}

const handleVideoPlay = () => {
  videoPlaying.value = true
  videoBuffering.value = false
  showVideoChrome()
}

const handleVideoPause = () => {
  videoPlaying.value = false
  videoBuffering.value = false
  showVideoChrome()
  saveVideoPosition()
}

const handleVideoWaiting = () => {
  if (!videoError.value) videoBuffering.value = true
}

const handleVideoCanPlay = () => {
  videoBuffering.value = false
}

const handleVideoEnded = () => {
  videoPlaying.value = false
  videoBuffering.value = false
  videoCurrentTime.value = videoDuration.value
  videoUiIdle.value = false
  clearVideoIdleTimer()
  clearVideoPosition(props.image?.id)
}

const handleVideoVolumeChange = () => {
  const element = videoRef.value
  videoMuted.value = !!element && (element.muted || element.volume === 0)
}

const resumePlayback = () => {
  const element = videoRef.value
  if (!element || resumePosition.value === null) return
  element.currentTime = resumePosition.value
  element.play().catch(() => { /* user can press play manually */ })
  resumePosition.value = null
  clearResumeChipTimer()
  showVideoChrome()
}

const seekBy = (delta: number) => {
  const element = videoRef.value
  if (!element) return
  const duration = Number.isFinite(element.duration) ? element.duration : 0
  const next = Math.min(Math.max(element.currentTime + delta, 0), duration || element.currentTime + delta)
  element.currentTime = Math.max(next, 0)
  videoCurrentTime.value = element.currentTime
  showVideoChrome()
}

const adjustVolume = (delta: number) => {
  const element = videoRef.value
  if (!element) return
  element.volume = Math.min(1, Math.max(0, element.volume + delta))
  if (element.volume > 0) element.muted = false
  handleVideoVolumeChange()
  showVideoChrome()
}

const toggleMute = () => {
  const element = videoRef.value
  if (!element) return
  element.muted = !element.muted
  handleVideoVolumeChange()
  showVideoChrome()
}

const toggleVideoFullscreen = () => {
  const element = videoRef.value as (HTMLVideoElement & { webkitEnterFullscreen?: () => void }) | null
  if (!element) return
  if (document.fullscreenElement) {
    document.exitFullscreen?.()
    return
  }
  if (element.webkitEnterFullscreen) {
    element.webkitEnterFullscreen()
    return
  }
  element.requestFullscreen?.()
}

const setPlaybackRate = (rate: number) => {
  videoRate.value = rate
  const element = videoRef.value
  if (element) element.playbackRate = rate
  showVideoChrome()
}

const togglePictureInPicture = async () => {
  const element = videoRef.value as (HTMLVideoElement & { requestPictureInPicture?: () => Promise<unknown> }) | null
  if (!element) return
  try {
    if (document.pictureInPictureElement) {
      await document.exitPictureInPicture?.()
    } else if (element.requestPictureInPicture) {
      await element.requestPictureInPicture()
    } else {
      ElMessage.warning('当前浏览器不支持画中画')
    }
  } catch (error) {
    ElMessage.warning('画中画启动失败，请检查浏览器权限')
  }
}

const retryVideo = () => {
  // Re-mount the <video> element; no-store ensures a fresh range request.
  videoError.value = false
  videoBuffering.value = false
  nextTick(() => videoRef.value?.load())
}
// -------------------------------------------------------------------------

const handleCopyPlayUrl = async () => {
  if (!props.image) return
  const ok = await copyPlayUrl(buildRawUrl(props.image.id))
  if (ok) {
    ElMessage.success('播放地址已复制，可粘贴到播放器的“网络串流”')
  } else {
    ElMessage.warning('复制失败，请手动复制地址栏中的播放链接')
  }
}

const handleOpenVlc = () => {
  if (!props.image) return
  if (platform === 'desktop') {
    // Desktops cannot launch a local player from the browser; fall back to copying.
    handleCopyPlayUrl()
    return
  }
  openInVlc(props.image.id, props.image.file_name)
}

const handleDownloadM3U = () => {
  if (!props.image) return
  downloadM3U(props.image.id, props.image.file_name)
}

const handleDownloadOriginal = () => {
  if (!props.image) return
  downloadOriginal(props.image.id, props.image.file_name)
}

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
  if (nextImg && nextImg.media_type !== 'video' && (nextImg.file_size || 0) <= MAX_RAW_PRELOAD_BYTES) {
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
    videoUiIdle.value = false
  } else {
    saveVideoPosition()
    clearVideoIdleTimer()
    clearResumeChipTimer()
    videoUiIdle.value = false
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
  // Video controls need their own touch handling (seek bar); do not treat it as a swipe.
  if (isVideo.value) return
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

// Reset transformations when the media changes
watch(() => props.image?.id, () => {
  scale.value = 1
  rotate.value = 0
  translateX.value = 0
  translateY.value = 0
  imageLoaded.value = false
  videoError.value = false
  clearVideoIdleTimer()
  clearResumeChipTimer()
  videoPlaying.value = false
  videoCurrentTime.value = 0
  videoDuration.value = 0
  videoMuted.value = false
  videoUiIdle.value = false
  videoBuffering.value = false
  videoRate.value = 1
  resumePosition.value = null
  lastSavedSecond = -1
})

let wheelRaf = 0
let pendingScale = 1

const handleWheel = (e: WheelEvent) => {
  if (!props.visible) return
  e.preventDefault()
  // Videos keep their native controls; wheel zoom only applies to images.
  if (isVideo.value) return

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
      '确定要删除这个项目吗？',
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

const toggleVideoPlayback = () => {
  const element = videoRef.value
  if (!element) return
  if (element.paused) {
    element.play().catch(() => { /* autoplay/permission failures are non-fatal */ })
  } else {
    element.pause()
  }
}

const handleKeydown = (e: KeyboardEvent) => {
  if (!props.visible) return
  // Dialogs own the keyboard while they are open; shortcuts must not mutate the gallery underneath.
  if (showMoveDialog.value || showInfoDialog.value) return

  const key = e.key
  const hk = hotkeys.value

  if (isVideo.value) {
    const target = e.target as HTMLElement | null
    const onVideo = target?.tagName === 'VIDEO'

    if (key === ' ') {
      // Native controls already handle space when the video element has focus.
      if (onVideo) return
      e.preventDefault()
      toggleVideoPlayback()
      return
    }

    if (key === 'ArrowLeft' || key === 'ArrowRight') {
      if (e.shiftKey) {
        // Shift + arrows keep switching media, matching the image lightbox.
        e.preventDefault()
        if (key === 'ArrowLeft' && props.hasPrev) goPrev()
        if (key === 'ArrowRight' && props.hasNext) goNext()
        return
      }
      if (onVideo) return // Native seek bar owns the arrow keys when focused.
      e.preventDefault()
      seekBy(key === 'ArrowLeft' ? -5 : 5)
      return
    }

    if (key === 'ArrowUp' || key === 'ArrowDown') {
      if (onVideo) return
      e.preventDefault()
      adjustVolume(key === 'ArrowUp' ? 0.1 : -0.1)
      return
    }

    if (key.toLowerCase() === 'm') {
      e.preventDefault()
      toggleMute()
      return
    }

    // Image-only shortcuts do not apply to video.
    if (key === hk.ZOOM_IN || key === hk.ZOOM_OUT || key === hk.ROTATE || key === hk.RESET) return
  }

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
  clearVideoIdleTimer()
  clearResumeChipTimer()
  saveVideoPosition()
  if (wheelRaf) cancelAnimationFrame(wheelRaf)
})
</script>

<template>
  <div
    v-if="visible"
    class="lightbox"
    :class="{ 'ui-visible': !uiHidden, 'ui-hidden': uiHidden, 'video-mode': isVideo }"
    role="dialog"
    aria-modal="true"
    aria-label="媒体预览"
    @click="handleStageClick"
    @mousemove="markVideoActivity"
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
      <span>正在加载更多内容...</span>
    </div>

    <div class="lightbox-content">
      <transition :name="transitionName">
        <div :key="imageUrl" class="image-wrapper">
          <template v-if="isVideo">
            <div v-if="videoError" class="video-error" @click.stop>
              <el-icon class="video-error-icon"><Monitor /></el-icon>
              <p class="video-error-title">该格式无法在浏览器中直接播放</p>
              <p class="video-error-hint">{{ videoFormatHint }}</p>
              <div class="video-error-actions">
                <el-button type="primary" size="small" @click.stop="handleOpenVlc">
                  {{ platform === 'desktop' ? '复制播放地址' : '用 VLC 打开' }}
                </el-button>
                <el-button v-if="platform !== 'desktop'" size="small" @click.stop="handleCopyPlayUrl">
                  复制播放地址
                </el-button>
                <el-button v-if="platform === 'desktop'" size="small" @click.stop="handleDownloadM3U">
                  下载播放列表
                </el-button>
                <el-button size="small" @click.stop="retryVideo">重试</el-button>
                <el-button size="small" @click.stop="handleDownloadOriginal">下载原文件</el-button>
              </div>
            </div>
            <div v-else class="video-stage" :style="{ '--video-ar': String(videoAspectRatio) }">
              <video
                ref="videoRef"
                :src="imageUrl"
                :poster="videoPoster"
                class="lightbox-video"
                controls
                playsinline
                preload="metadata"
                @click="handleVideoSurfaceClick"
                @loadedmetadata="handleVideoLoaded"
                @timeupdate="handleVideoTimeUpdate"
                @play="handleVideoPlay"
                @playing="handleVideoPlay"
                @pause="handleVideoPause"
                @ended="handleVideoEnded"
                @waiting="handleVideoWaiting"
                @stalled="handleVideoWaiting"
                @canplay="handleVideoCanPlay"
                @seeked="handleVideoCanPlay"
                @volumechange="handleVideoVolumeChange"
                @error="videoError = true"
                @touchstart.stop="markVideoActivity"
                @touchend.stop
              ></video>
              <div v-if="videoBuffering" class="video-buffering" role="status" aria-live="polite" @click.stop>
                <el-icon class="is-loading"><Loading /></el-icon>
                <span>缓冲中…</span>
              </div>
            </div>
          </template>
          <img
            v-else
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

      <button
        v-if="isVideo && !videoError && resumePosition !== null"
        class="resume-chip"
        @click.stop="resumePlayback"
        @touchstart.stop
      >
        <el-icon><VideoPlay /></el-icon>
        <span>从 {{ formatDuration(resumePosition) }} 继续播放</span>
      </button>

      <div
        v-if="isVideo && !videoError"
        class="video-controls"
        :class="{ 'with-meta': showLightboxImageInfo }"
        @click.stop
        @touchstart.stop
        @touchend.stop
      >
        <button class="vc-btn vc-skip" title="快退 10 秒" aria-label="快退 10 秒" @click="seekBy(-10)">
          <el-icon><DArrowLeft /></el-icon><span>10s</span>
        </button>
        <button class="vc-btn vc-play" :title="videoPlaying ? '暂停' : '播放'" :aria-label="videoPlaying ? '暂停' : '播放'" @click="toggleVideoPlayback">
          <el-icon>
            <VideoPause v-if="videoPlaying" />
            <VideoPlay v-else />
          </el-icon>
        </button>
        <button class="vc-btn vc-skip" title="快进 10 秒" aria-label="快进 10 秒" @click="seekBy(10)">
          <span>10s</span><el-icon><DArrowRight /></el-icon>
        </button>
        <span class="vc-time">{{ videoTimeText }}</span>
        <span v-if="videoRate !== 1" class="vc-rate">{{ videoRate }}×</span>
        <button class="vc-btn" :title="videoMuted ? '取消静音' : '静音'" :aria-label="videoMuted ? '取消静音' : '静音'" @click="toggleMute">
          <el-icon>
            <Mute v-if="videoMuted" />
            <Microphone v-else />
          </el-icon>
        </button>
        <el-dropdown trigger="click" placement="top" class="vc-settings">
          <button class="vc-btn" title="播放设置" aria-label="播放设置">
            <el-icon><Setting /></el-icon>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-for="rate in PLAYBACK_RATES" :key="rate" @click="setPlaybackRate(rate)">
                {{ videoRate === rate ? '✓ ' : '' }}{{ rate }}×
              </el-dropdown-item>
              <el-dropdown-item divided :icon="Monitor" @click="togglePictureInPicture">画中画</el-dropdown-item>
              <el-dropdown-item :icon="FullScreen" @click="toggleVideoFullscreen">全屏</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
      <div class="lightbox-controls" @click.stop>
        <button v-if="hasPrev" class="control-btn prev-btn" aria-label="上一张" @click.stop="goPrev" @touchstart.stop @touchend.stop>
          <el-icon><ArrowLeft /></el-icon>
        </button>
        <button v-if="hasNext" class="control-btn next-btn" aria-label="下一张" @click.stop="goNext" @touchstart.stop @touchend.stop>
          <el-icon><ArrowRight /></el-icon>
        </button>
      </div>

      <div class="lightbox-toolbar" @touchstart.stop @touchend.stop @click.stop>
        <template v-if="isVideo">
          <el-dropdown trigger="click" class="player-dropdown">
            <button title="用本地播放器打开" aria-label="用本地播放器打开" class="player-btn">
              <el-icon><Monitor /></el-icon>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-if="platform !== 'desktop'" :icon="Monitor" @click="handleOpenVlc">用 VLC 打开</el-dropdown-item>
                <el-dropdown-item :icon="Link" @click="handleCopyPlayUrl">复制播放地址</el-dropdown-item>
                <el-dropdown-item v-if="platform === 'desktop'" :icon="Download" @click="handleDownloadM3U">下载播放列表（M3U）</el-dropdown-item>
                <el-dropdown-item :icon="Download" @click="handleDownloadOriginal">下载原文件</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <button
            title="收藏"
            aria-label="收藏"
            class="btn-fav"
            :class="{ active: image?.is_favorite }"
            @click="handleFavorite"
          >
            <el-icon><Star /></el-icon>
          </button>
          <el-dropdown trigger="click" class="more-dropdown">
            <button title="更多操作" aria-label="更多操作" class="more-btn">
              <el-icon><More /></el-icon>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item :icon="InfoFilled" @click="showInfoDialog = true">媒体信息</el-dropdown-item>
                <el-dropdown-item :icon="View" @click="uiStore.toggleLightboxImageInfo()">
                  {{ showLightboxImageInfo ? '隐藏底部信息' : '显示底部信息' }}
                </el-dropdown-item>
                <el-dropdown-item v-if="canEdit" :icon="Edit" @click="handleRename">重命名</el-dropdown-item>
                <el-dropdown-item v-if="canEdit" :icon="Rank" @click="openMoveDialog">移动</el-dropdown-item>
                <el-dropdown-item v-if="canEdit" :icon="CollectionTag" @click="handleSaveBookmark">
                  {{ isImageBookmarked ? '取消书签' : '保存书签' }}
                </el-dropdown-item>
                <el-dropdown-item v-if="canEdit" :icon="Delete" divided class="danger-item" @click="handleDelete">删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <button title="关闭" aria-label="关闭" class="close-btn" @click="emit('close')"><el-icon><Close /></el-icon></button>
        </template>

        <template v-else>
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
            class="btn-info-toggle"
            :class="{ active: showLightboxImageInfo }"
            :title="showLightboxImageInfo ? '隐藏底部图片信息' : '显示底部图片信息'"
            :aria-label="showLightboxImageInfo ? '隐藏底部图片信息' : '显示底部图片信息'"
            @click="uiStore.toggleLightboxImageInfo()"
          >
            <el-icon>
              <View v-if="showLightboxImageInfo" />
              <Hide v-else />
            </el-icon>
          </button>
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
        </template>
      </div>

      <div class="image-meta" v-if="image && showLightboxImageInfo" @touchstart.stop @touchend.stop @click.stop>
        <span id="meta-filename" :title="image.file_name">{{ truncatedFileName }}</span>
        <span class="meta-divider">|</span>
        <span id="meta-resolution">{{ image.width }} x {{ image.height }}</span>
        <template v-if="isVideo && formatDuration(image.duration)">
          <span class="meta-divider">|</span>
          <span id="meta-duration">时长 {{ formatDuration(image.duration) }}</span>
        </template>
        <span class="meta-divider">|</span>
        <span id="meta-filesize">{{ fileSizeMB }}</span>
      </div>
    </div>

    <el-dialog v-model="showMoveDialog" title="移动文件" width="400px" append-to-body>
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

.video-stage {
    /* Reserve space for the bottom control bar and the native control strip. */
    --video-reserved: 120px;
    position: relative;
    width: min(100%, calc((100dvh - var(--video-reserved)) * var(--video-ar, 1.7778)));
    aspect-ratio: var(--video-ar, 1.7778);
    display: flex;
    align-items: center;
    justify-content: center;
}

.lightbox-video {
    width: 100%;
    height: 100%;
    object-fit: contain;
    background: #000;
    border-radius: 4px;
    box-shadow: 0 0 40px rgba(0, 0, 0, 0.5);
}

.video-buffering {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    color: #fff;
    font-size: 12.5px;
    background: rgba(0, 0, 0, 0.28);
    border-radius: 4px;
    pointer-events: none;
}

.video-buffering .el-icon {
    font-size: 30px;
}

.video-error {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    padding: 28px 32px;
    max-width: min(520px, calc(100vw - 40px));
    text-align: center;
    color: rgba(255, 255, 255, 0.9);
    background: rgba(15, 18, 22, 0.72);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: var(--radius-lg);
    backdrop-filter: blur(10px);
}

.video-error-icon {
    font-size: 44px;
    color: rgba(255, 255, 255, 0.7);
}

.video-error-title {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
}

.video-error-hint {
    margin: 0;
    font-size: 12.5px;
    color: rgba(255, 255, 255, 0.65);
    line-height: 1.6;
}

.video-error-actions {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 8px;
    margin-top: 6px;
}

.player-dropdown {
    display: flex;
}

.player-btn {
    /* Matches the toolbar buttons; the dropdown wraps it, so restate the sizing. */
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
}

.player-btn:hover {
    background: rgba(255, 255, 255, 0.12);
    color: #fff;
}

.more-dropdown {
    display: flex;
}

.more-btn {
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
}

.more-btn:hover {
    background: rgba(255, 255, 255, 0.12);
    color: #fff;
}

:deep(.danger-item) {
    color: #f56c6c;
}

/* 视频专用底部控制条：原生控件负责进度条，这里补充快进/快退与状态 */
.video-controls {
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 14px;
    border-radius: var(--radius-pill);
    background: rgba(15, 18, 22, 0.62);
    border: 1px solid rgba(255, 255, 255, 0.08);
    backdrop-filter: blur(14px);
    opacity: 0;
    visibility: hidden;
    transition: opacity 200ms ease;
    z-index: 1012;
}

.video-controls.with-meta {
    bottom: 80px;
}

.vc-btn {
    background: transparent;
    border: none;
    color: rgba(255, 255, 255, 0.9);
    height: 40px;
    min-width: 40px;
    border-radius: 10px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 2px;
    font-size: 14px;
    transition: background-color var(--motion-fast) var(--ease-out),
                color var(--motion-fast) var(--ease-out);
}

.vc-btn:hover {
    background: rgba(255, 255, 255, 0.12);
    color: #fff;
}

.vc-play {
    background: rgba(255, 255, 255, 0.14);
}

.vc-skip span {
    font-size: 11px;
    opacity: 0.85;
}

.vc-time {
    color: rgba(255, 255, 255, 0.78);
    font-size: 12px;
    font-variant-numeric: tabular-nums;
    padding: 0 6px;
    white-space: nowrap;
}

.vc-rate {
    color: var(--primary);
    font-size: 11px;
    font-weight: 600;
    margin-left: -2px;
}

.vc-settings {
    display: flex;
}

.resume-chip {
    position: fixed;
    bottom: 84px;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 10px 18px;
    border-radius: var(--radius-pill);
    border: 1px solid rgba(255, 255, 255, 0.16);
    background: rgba(15, 18, 22, 0.82);
    color: #fff;
    font-size: 13px;
    cursor: pointer;
    backdrop-filter: blur(12px);
    z-index: 1013;
    transition: background-color var(--motion-fast) var(--ease-out);
}

.resume-chip:hover {
    background: var(--primary);
    border-color: var(--primary);
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
.lightbox.ui-visible .video-controls,
.lightbox:not(.video-mode):hover .control-btn,
.lightbox:not(.video-mode):hover .lightbox-toolbar,
.lightbox:not(.video-mode):hover .image-counter,
.lightbox:not(.video-mode):hover .image-meta {
    opacity: 1;
    visibility: visible;
}

.lightbox.ui-hidden .control-btn,
.lightbox.ui-hidden .lightbox-toolbar,
.lightbox.ui-hidden .image-counter,
.lightbox.ui-hidden .image-meta,
.lightbox.ui-hidden .video-controls {
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

.lightbox-toolbar .btn-bookmark.active,
.lightbox-toolbar .btn-info-toggle.active {
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

    .player-btn {
        width: 44px;
        height: 44px;
    }

    .more-btn {
        width: 44px;
        height: 44px;
    }

    .lightbox-video {
        width: 100%;
        height: 100%;
    }

    .video-stage {
        --video-reserved: 168px;
    }

    .video-controls {
        bottom: 18px;
        gap: 4px;
        padding: 6px 10px;
        max-width: calc(100vw - 20px);
    }

    .video-controls.with-meta {
        bottom: 86px;
    }

    .vc-btn {
        min-width: 44px;
        height: 44px;
    }

    .vc-time {
        font-size: 11px;
        padding: 0 2px;
    }

    .resume-chip {
        bottom: 92px;
        max-width: calc(100vw - 40px);
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
