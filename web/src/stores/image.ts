import { defineStore, storeToRefs } from 'pinia'
import { ref, watch } from 'vue'
import { getImages, updateImage, batchMoveImages, batchDeleteImages } from '../api'
import { useFolderStore } from './folder'
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
  const images = ref<Image[]>([])
  const total = ref(0)
  const page = ref(1)
  const perPage = ref(50)
  const loading = ref(false)
  const showOnlyFavorites = ref(false)
  const sortBy = ref('modified_time')
  const sortOrder = ref('DESC')
  const searchQuery = ref('')
  const selectedImageIds = ref<number[]>([])
  
  const folderStore = useFolderStore()
  const { currentFolderId } = storeToRefs(folderStore)

  const fetchImages = async (reset = false) => {
    if (loading.value) return
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
      
      if (reset) {
        images.value = res.data.data
      } else {
        images.value.push(...res.data.data)
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

  const toggleFavorite = async (image: Image) => {
    try {
      const newState = !image.is_favorite
      await updateImage(image.id, { is_favorite: newState })
      image.is_favorite = newState
      
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
      const res = await batchMoveImages(selectedImageIds.value, targetFolderId)
      if (res.data.success) {
        ElMessage.success(`成功移动 ${res.data.moved} 张图片`)
        clearSelection()
        fetchImages(true)
      }
    } catch (error: any) {
      ElMessage.error('批量移动失败: ' + (error.response?.data?.error || error.message))
    }
  }

  const batchDelete = async () => {
    if (selectedImageIds.value.length === 0) return
    try {
      const res = await batchDeleteImages(selectedImageIds.value)
      if (res.data.success) {
        ElMessage.success(`成功将 ${res.data.deleted} 张图片移至回收站`)
        clearSelection()
        fetchImages(true)
      }
    } catch (error: any) {
      ElMessage.error('批量删除失败: ' + (error.response?.data?.error || error.message))
    }
  }

  return {
    images,
    total,
    loading,
    showOnlyFavorites,
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
    batchDeleteImages
  }
})
