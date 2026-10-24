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
  scan_status?: string
  scan_total?: number
  scan_processed?: number
  scan_error?: string | null
}

export const useFolderStore = defineStore('folder', () => {
  const folders = ref<Folder[]>([])
  const currentFolderId = ref<number | undefined>(undefined)

  const fetchFolders = async () => {
    try {
      const res = await getFolders()
      folders.value = res.data.map((f: any) => ({
        ...f,
        is_public: !!f.is_public
      }))

      // 当前文件夹被删除或已失去权限时回到“所有照片”，避免继续显示失效数据。
      if (currentFolderId.value !== undefined && !folders.value.some(f => f.id === currentFolderId.value)) {
        currentFolderId.value = undefined
      }
    } catch (error) {
      console.error('Failed to fetch folders', error)
      ElMessage.error('Failed to fetch folders')
    }
  }

  const createFolder = async (path: string, name?: string): Promise<boolean> => {
    try {
      await addFolder(path, name)
      ElMessage.success('Folder added successfully')
      await fetchFolders()
      return true
    } catch (error: any) {
      console.error('Failed to add folder', error)
      ElMessage.error(error.response?.data?.error || 'Failed to add folder')
      return false
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
