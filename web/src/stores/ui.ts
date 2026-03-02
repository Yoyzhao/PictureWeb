import { defineStore } from 'pinia'
import { ref, onMounted, onUnmounted } from 'vue'

export const useUIStore = defineStore('ui', () => {
  const isSidebarCollapsed = ref(false)

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
    toggleSidebar,
    checkOrientation
  }
})
