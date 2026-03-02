import { defineStore, storeToRefs } from 'pinia'
import { ref, shallowRef, watch } from 'vue'
import { getImages, updateImage, batchMoveImages, batchDeleteImages, toggleImageFavorite } from '../api'
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
  const total = ref(0)
  const page = ref(1)
  const perPage = ref(50)
  const loading = ref(false)
  const showOnlyFavorites = ref(false)
  const showAdminView = ref(false)
  const sortBy = ref('modified_time')
  const sortOrder = ref('DESC')
  const searchQuery = ref('')
  const selectedImageIds = ref<number[]>([])
  const gridSize = ref<'small' | 'medium' | 'large'>('medium')
  
  const folderStore = useFolderStore()
  const authStore = useAuthStore()
  const { currentFolderId } = storeToRefs(folderStore)
  const { user, token } = storeToRefs(authStore)

  const fetchImages = async (reset = false) => {
    if (loading.value || showAdminView.value) return
    loading.value = true
    
    if (reset) {
      page.value = 1
      images.value = []
    }

    try {
      const res = await getImages({
        page: page.value,
        per_page: perPage.value,
        folder_id: currentFolderId.value,
        is_favorite: showOnlyFavorites.value ? 'true' : undefined,
        sort_by: sortBy.value,
        sort_order: sortOrder.value,
        q: searchQuery.value || undefined
      })
      
      // Transform is_favorite to boolean if it comes as 0/1 from backend
      const data = res.data.data.map((img: any) => ({
        ...img,
        is_favorite: !!img.is_favorite
      }))

      if (reset) {
        images.value = data
      } else {
        images.value = [...images.value, ...data]
      }
      
      total.value = res.data.total
      page.value += 1
    } catch (error) {
      console.error('Failed to fetch images', error)
    } finally {
      loading.value = false
    }
  }

  // Watch folder, favorites, sort, or search change to reset images
  watch([currentFolderId, showOnlyFavorites, sortBy, sortOrder, searchQuery], () => {
    fetchImages(true)
  })

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
      
      // Update the image in the list
      const index = images.value.findIndex(img => img.id === image.id)
      if (index !== -1) {
        const updatedImages = [...images.value]
        updatedImages[index] = { ...updatedImages[index], is_favorite: newState }
        images.value = updatedImages
      }
      
      // If we are in favorites view and unfavorite, remove from list
      if (showOnlyFavorites.value && !newState) {
        images.value = images.value.filter(img => img.id !== image.id)
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
    total.value = Math.max(0, total.value - 1)
  }

  const renameImage = async (id: number, newName: string) => {
    try {
      const res = await updateImage(id, { file_name: newName })
      if (res.data.success) {
        // Update the image in the list
        const index = images.value.findIndex(img => img.id === id)
        if (index !== -1) {
          const updatedImages = [...images.value]
          updatedImages[index] = { ...updatedImages[index], file_name: newName }
          images.value = updatedImages
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
    total,
    loading,
    showOnlyFavorites,
    showAdminView,
    sortBy,
    sortOrder,
    searchQuery,
    selectedImageIds,
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
    gridSize
  }
})
