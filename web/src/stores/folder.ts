import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getFolders, addFolder } from '../api'
import { ElMessage } from 'element-plus'

export interface Folder {
  id: number
  path: string
  name: string
  user_id: number
  is_public: boolean
}

export const useFolderStore = defineStore('folder', () => {
  const folders = ref<Folder[]>([])
  const currentFolderId = ref<number | undefined>(undefined)

  const fetchFolders = async () => {
    try {
      const res = await getFolders()
      folders.value = res.data
    } catch (error) {
      console.error('Failed to fetch folders', error)
      ElMessage.error('Failed to fetch folders')
    }
  }

  const createFolder = async (path: string, name?: string) => {
    try {
      await addFolder(path, name)
      ElMessage.success('Folder added successfully')
      await fetchFolders()
    } catch (error: any) {
      console.error('Failed to add folder', error)
      ElMessage.error(error.response?.data?.error || 'Failed to add folder')
    }
  }

  const selectFolder = (id: number | undefined) => {
    currentFolderId.value = id
  }

  return {
    folders,
    currentFolderId,
    fetchFolders,
    createFolder,
    selectFolder,
  }
})
