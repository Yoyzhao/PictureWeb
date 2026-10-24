import { defineStore, storeToRefs } from 'pinia'
import { ref, shallowRef, watch, triggerRef } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { 
  getImages, 
  updateImage, 
  batchMoveImages, 
  batchDeleteImages, 
  toggleImageFavorite,
  getTrash,
  restoreTrash,
  clearTrash
} from '../api'
import { useFolderStore } from './folder'
import { useAuthStore } from './auth'
import { ElMessage } from 'element-plus'

export interface Image {
  id: number
  file_path: string
  file_name: string
  file_size: number
  modified_time: number
  width: number
  height: number
  format: string
  folder_id: number
  is_favorite: boolean
}

export const useImageStore = defineStore('image', () => {
  const images = shallowRef<Image[]>([])
  const imagesVersion = ref(0)
  const total = ref(0)
  const page = ref(1)
  const nextCursor = ref<string | null>(null)
  const perPage = ref(50)
  const loading = ref(false)
  const showOnlyFavorites = ref(false)
  const showAdminView = ref(false)
  const showTrash = ref(false)
  const sortBy = ref('modified_time')
  const sortOrder = ref('DESC')
  const searchQuery = ref('')
  const selectedImageIds = ref<number[]>([])
  const gridSize = ref<'small' | 'medium' | 'large'>('medium')

  // Request coordination: abort stale requests and ignore out-of-order responses.
  let activeController: AbortController | null = null
  let requestSeq = 0
  const loadedIds = new Set<number>()
  
  const folderStore = useFolderStore()
  const authStore = useAuthStore()
  const { currentFolderId } = storeToRefs(folderStore)
  const { user, token } = storeToRefs(authStore)

  const fetchImages = async (reset = false) => {
    if (showAdminView.value) return
    if (!reset && !nextCursor.value) return
    if (!reset && loading.value) return

    if (reset) {
      activeController?.abort()
      page.value = 1
      nextCursor.value = null
      images.value = []
      imagesVersion.value++
      total.value = 0
      loadedIds.clear()
      selectedImageIds.value = []
    }

    const seq = ++requestSeq
    const controller = new AbortController()
    activeController = controller
    loading.value = true

    try {
      const res = await getImages({
        page: page.value,
        per_page: perPage.value,
        folder_id: currentFolderId.value,
        is_favorite: showOnlyFavorites.value ? 'true' : undefined,
        sort_by: sortBy.value,
        sort_order: sortOrder.value,
        q: searchQuery.value || undefined,
        cursor: reset ? undefined : (nextCursor.value || undefined)
      }, controller.signal)

      if (controller.signal.aborted || seq !== requestSeq) return

      // Deduplicate in case two page requests overlap or the server data shifts.
      const data = res.data.data
        .map((img: any) => ({ ...img, is_favorite: !!img.is_favorite }))
        .filter((img: Image) => !loadedIds.has(img.id))

      for (const img of data) loadedIds.add(img.id)

      if (data.length > 0) {
        // Mutate in place and notify once instead of copying the whole array per page.
        images.value.push(...data)
        imagesVersion.value++
        triggerRef(images)
      }

      total.value = res.data.total
      nextCursor.value = res.data.next_cursor || null
      page.value += 1

      // If the server returns an empty page before reaching total, stop pagination.
      if (data.length === 0 && images.value.length < total.value) {
        total.value = images.value.length
        nextCursor.value = null
      }
    } catch (error: any) {
      const cancelled = error?.code === 'ERR_CANCELED' || error?.name === 'CanceledError'
      if (!cancelled && seq === requestSeq) {
        console.error('Failed to fetch images', error)
      }
    } finally {
      if (seq === requestSeq) {
        loading.value = false
        activeController = null
      }
    }
  }

  // Folder/filter/sort changes should react immediately.
  watch([currentFolderId, showOnlyFavorites, sortBy, sortOrder], () => {
    fetchImages(true)
  })

  // Typing in the search box should not trigger one request per keystroke.
  watchDebounced(searchQuery, () => {
    fetchImages(true)
  }, { debounce: 300 })

  // Watch user auth change to reset folder and images
  watch([user, token], () => {
    // 只有当用户或 Token 真正变化时才重置文件夹，因为新用户可能没有旧文件夹的权限
    folderStore.selectFolder(undefined)
    fetchImages(true)
  })

  const toggleFavorite = async (image: Image) => {
    const authStore = useAuthStore()
    if (!authStore.isLoggedIn || authStore.user?.role === 'guest') {
      ElMessage.warning('请登录后使用收藏功能')
      return
    }

    try {
      const res = await toggleImageFavorite(image.id)
      const newState = res.data.is_favorite
      
      // Update the image in the list without copying the whole array.
      const index = images.value.findIndex(img => img.id === image.id)
      if (index !== -1) {
        images.value[index] = { ...images.value[index], is_favorite: newState }
        triggerRef(images)
      }
      
      // If we are in favorites view and unfavorite, remove from list
      if (showOnlyFavorites.value && !newState) {
        images.value = images.value.filter(img => img.id !== image.id)
        loadedIds.delete(image.id)
        total.value -= 1
      }
      
      ElMessage.success(newState ? '已添加到收藏夹' : '已从收藏夹移除')
    } catch (error) {
      console.error('Failed to toggle favorite', error)
      ElMessage.error('操作失败')
    }
  }

  const toggleImageSelection = (id: number) => {
    const index = selectedImageIds.value.indexOf(id)
    if (index > -1) {
      selectedImageIds.value.splice(index, 1)
    } else {
      selectedImageIds.value.push(id)
    }
  }

  const clearSelection = () => {
    selectedImageIds.value = []
  }

  const selectAll = () => {
    selectedImageIds.value = images.value.map(img => img.id)
  }

  const batchMove = async (targetFolderId: number) => {
    if (selectedImageIds.value.length === 0) return
    try {
      const idsToMove = [...selectedImageIds.value]
      const res = await batchMoveImages(idsToMove, targetFolderId)
      if (res.data.success) {
        ElMessage.success(`成功移动 ${res.data.moved} 张图片`)
        clearSelection()
        
        // Remove locally from current view
        images.value = images.value.filter(img => !idsToMove.includes(img.id))
        idsToMove.forEach(id => loadedIds.delete(id))
        total.value = Math.max(0, total.value - res.data.moved)
        
        // If we're now low on images, fetch more without reset
        if (images.value.length < 20 && total.value > images.value.length) {
          fetchImages()
        }
      }
    } catch (error: any) {
      ElMessage.error('批量移动失败: ' + (error.response?.data?.error || error.message))
    }
  }

  const batchDelete = async () => {
    if (selectedImageIds.value.length === 0) return
    try {
      const idsToDelete = [...selectedImageIds.value]
      const res = await batchDeleteImages(idsToDelete)
      if (res.data.success) {
        ElMessage.success(`成功将 ${res.data.deleted} 张图片移至回收站`)
        clearSelection()
        
        // Remove locally instead of full refresh with reset
        images.value = images.value.filter(img => !idsToDelete.includes(img.id))
        idsToDelete.forEach(id => loadedIds.delete(id))
        total.value = Math.max(0, total.value - res.data.deleted)
        
        // If we're now low on images, fetch more without reset
        if (images.value.length < 20 && total.value > images.value.length) {
          fetchImages()
        }
      }
    } catch (error: any) {
      ElMessage.error('批量删除失败: ' + (error.response?.data?.error || error.message))
    }
  }

  const removeImageLocally = (id: number) => {
    images.value = images.value.filter(img => img.id !== id)
    loadedIds.delete(id)
    total.value = Math.max(0, total.value - 1)
  }

  const trashItems = ref<any[]>([])
  const trashLoading = ref(false)

  const fetchTrash = async () => {
    trashLoading.value = true
    try {
      const res = await getTrash()
      trashItems.value = res.data
    } catch (error: any) {
      ElMessage.error('获取回收站失败: ' + (error.response?.data?.error || error.message))
    } finally {
      trashLoading.value = false
    }
  }

  const restoreFromTrash = async (trashIds: number[]) => {
    try {
      const res = await restoreTrash(trashIds)
      if (res.data.success) {
        ElMessage.success(`成功恢复 ${res.data.restored} 张图片`)
        trashItems.value = trashItems.value.filter(item => !trashIds.includes(item.id))
        return true
      }
    } catch (error: any) {
      ElMessage.error('恢复失败: ' + (error.response?.data?.error || error.message))
    }
    return false
  }

  const permanentlyDelete = async (trashIds?: number[]) => {
    try {
      const res = await clearTrash(trashIds)
      if (res.data.success) {
        if (trashIds) {
          ElMessage.success(`成功彻底删除 ${res.data.deleted} 张图片`)
          trashItems.value = trashItems.value.filter(item => !trashIds.includes(item.id))
        } else {
          ElMessage.success('已清空回收站')
          trashItems.value = []
        }
        return true
      }
    } catch (error: any) {
      ElMessage.error('删除失败: ' + (error.response?.data?.error || error.message))
    }
    return false
  }

  const renameImage = async (id: number, newName: string) => {
    try {
      const res = await updateImage(id, { file_name: newName })
      if (res.data.success) {
        // Update the image in place and notify once.
        const index = images.value.findIndex(img => img.id === id)
        if (index !== -1) {
          images.value[index] = { ...images.value[index], file_name: newName }
          triggerRef(images)
        }
        return { success: true }
      }
    } catch (error: any) {
      const errorMsg = error.response?.data?.error || error.message
      ElMessage.error('重命名失败: ' + errorMsg)
      return { success: false, error: errorMsg }
    }
    return { success: false }
  }

  return {
    images,
    imagesVersion,
    total,
    loading,
    showOnlyFavorites,
    showAdminView,
    sortBy,
    sortOrder,
    searchQuery,
    selectedImageIds,
    showTrash,
    fetchImages,
    toggleFavorite,
    toggleImageSelection,
    clearSelection,
    selectAll,
    batchMove,
    batchDelete,
    batchMoveImages,
    batchDeleteImages,
    removeImageLocally,
    renameImage,
    trashItems,
    trashLoading,
    fetchTrash,
    restoreFromTrash,
    permanentlyDelete,
    gridSize
  }
})
