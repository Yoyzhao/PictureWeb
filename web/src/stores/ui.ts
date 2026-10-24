import { defineStore } from 'pinia'
import { ref, onMounted, onUnmounted } from 'vue'
import { useStorage } from '@vueuse/core'

export const useUIStore = defineStore('ui', () => {
  const isSidebarCollapsed = ref(false)
  // Display preferences persist across sessions.
  const showGridImageInfo = useStorage('picgallery.showGridImageInfo', true)
  const showLightboxImageInfo = useStorage('picgallery.showLightboxImageInfo', true)

  const toggleGridImageInfo = () => {
    showGridImageInfo.value = !showGridImageInfo.value
  }

  const toggleLightboxImageInfo = () => {
    showLightboxImageInfo.value = !showLightboxImageInfo.value
  }

  const toggleSidebar = () => {
    isSidebarCollapsed.value = !isSidebarCollapsed.value
  }

  const checkOrientation = () => {
    // 竖屏或屏幕宽度较小时默认收起
    const isPortrait = window.innerHeight > window.innerWidth
    const isMobile = window.innerWidth <= 768
    isSidebarCollapsed.value = isPortrait || isMobile
  }

  onMounted(() => {
    checkOrientation()
    window.addEventListener('resize', checkOrientation)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', checkOrientation)
  })

  return {
    isSidebarCollapsed,
    showGridImageInfo,
    showLightboxImageInfo,
    toggleSidebar,
    toggleGridImageInfo,
    toggleLightboxImageInfo,
    checkOrientation
  }
})
