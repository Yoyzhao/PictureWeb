import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import {
  getBookmarks,
  createBookmark,
  saveAutoBookmark,
  updateBookmark,
  deleteBookmark
} from '../api'
import { useImageStore } from './image'
import { useFolderStore } from './folder'
import { useAuthStore } from './auth'
import { ElMessage } from 'element-plus'

export interface Bookmark {
  id: number
  kind: 'manual' | 'auto'
  name: string
  folder_id: number
  folder_name: string | null
  is_favorites: boolean
  search_query: string
  sort_by: string
  sort_order: 'ASC' | 'DESC'
  anchor_image_id: number
  anchor_file_name: string | null
  image_file_name: string | null
  anchor_exists: boolean
  created_at: string
  updated_at: string
}

export const useBookmarkStore = defineStore('bookmark', () => {
  const bookmarks = ref<Bookmark[]>([])
  const loading = ref(false)

  const imageStore = useImageStore()
  const folderStore = useFolderStore()
  const authStore = useAuthStore()

  const canBookmark = computed(() => !!authStore.isLoggedIn && authStore.user?.role !== 'guest')

  // Manual bookmark anchors, used by the grid/lightbox toggle state.
  const bookmarkedImageIds = computed(() => {
    const ids = new Set<number>()
    for (const item of bookmarks.value) {
      if (item.kind === 'manual') ids.add(item.anchor_image_id)
    }
    return ids
  })

  const currentContext = () => ({
    folder_id: folderStore.currentFolderId ?? 0,
    is_favorites: imageStore.showOnlyFavorites ? 1 : 0,
    search_query: imageStore.searchQuery || '',
    sort_by: imageStore.sortBy,
    sort_order: imageStore.sortOrder
  })

  const fetchBookmarks = async () => {
    if (!canBookmark.value) {
      bookmarks.value = []
      return
    }
    loading.value = true
    try {
      const res = await getBookmarks()
      bookmarks.value = res.data
    } catch (error: any) {
      console.error('Failed to fetch bookmarks', error)
    } finally {
      loading.value = false
    }
  }

  // Load once for the restored session and after login; clear on logout/token reset.
  watch(() => authStore.token, () => {
    bookmarks.value = []
    if (canBookmark.value) fetchBookmarks()
  }, { immediate: true })

  const createAt = async (anchorId: number, name = '') => {
    if (!canBookmark.value) {
      ElMessage.warning('请登录后使用书签')
      return null
    }
    try {
      const res = await createBookmark({ ...currentContext(), anchor_image_id: anchorId, name })
      const created: Bookmark = res.data
      bookmarks.value = [created, ...bookmarks.value.filter(item => item.id !== created.id)]
      ElMessage.success('已保存当前位置')
      return created
    } catch (error: any) {
      ElMessage.error('保存书签失败: ' + (error.response?.data?.error || error.message))
      return null
    }
  }

  // Prefer a bookmark for the same view; otherwise use the newest bookmark of this image.
  const findManualBookmark = (imageId: number) => {
    const candidates = bookmarks.value.filter(
      item => item.kind === 'manual' && item.anchor_image_id === imageId
    )
    if (candidates.length === 0) return null

    const context = currentContext()
    const sameView = candidates.find(item =>
      item.folder_id === context.folder_id &&
      !!item.is_favorites === !!context.is_favorites &&
      (item.search_query || '') === (context.search_query || '')
    )
    if (sameView) return sameView
    return candidates.reduce((latest, item) => (item.id > latest.id ? item : latest), candidates[0])
  }

  const toggleAt = async (anchorId: number) => {
    if (!canBookmark.value) {
      ElMessage.warning('请登录后使用书签')
      return false
    }

    const existing = findManualBookmark(anchorId)
    if (existing) {
      await remove(existing.id, '已取消书签')
      return bookmarkedImageIds.value.has(anchorId)
    }

    const created = await createAt(anchorId)
    return !!created
  }

  // Automatic resume position. Debounced and skipped when the view changed meanwhile.
  let autoTimer: number | undefined
  let lastAutoKey = ''

  const saveAutoProgress = (anchorId: number) => {
    if (!canBookmark.value || !anchorId) return

    const context = currentContext()
    const key = [
      context.folder_id, context.is_favorites, context.search_query,
      context.sort_by, context.sort_order, anchorId
    ].join('|')
    if (key === lastAutoKey) return

    if (autoTimer) clearTimeout(autoTimer)
    autoTimer = window.setTimeout(async () => {
      autoTimer = undefined
      if (!canBookmark.value) return

      const now = currentContext()
      const sameView = now.folder_id === context.folder_id &&
        now.is_favorites === context.is_favorites &&
        now.search_query === context.search_query &&
        now.sort_by === context.sort_by &&
        now.sort_order === context.sort_order
      if (!sameView) return

      try {
        await saveAutoBookmark({ ...context, anchor_image_id: anchorId })
        lastAutoKey = key
      } catch (error) {
        // Auto progress is best-effort; manual bookmarks surface their errors.
        console.warn('Failed to save auto bookmark', error)
      }
    }, 1200)
  }

  const restore = async (bookmark: Bookmark) => {
    try {
      const result = await imageStore.restoreBookmarkWindow(bookmark.id)
      if (!result) return false
      if (result.total === 0) {
        ElMessage.warning('书签对应的视图已为空（文件夹可能已删除或无权限）')
        return false
      }
      if (result.anchor?.fallback) {
        ElMessage.warning('原图片已删除或移出当前视图，已定位到附近位置')
      } else {
        ElMessage.success('已回到书签位置')
      }
      return true
    } catch (error: any) {
      ElMessage.error('恢复书签失败: ' + (error.response?.data?.error || error.message))
      return false
    }
  }

  const rename = async (id: number, name: string) => {
    try {
      await updateBookmark(id, { name })
      await fetchBookmarks()
      ElMessage.success('书签已重命名')
      return true
    } catch (error: any) {
      ElMessage.error('重命名失败: ' + (error.response?.data?.error || error.message))
      return false
    }
  }

  const remove = async (id: number, successMessage = '书签已删除') => {
    try {
      await deleteBookmark(id)
      bookmarks.value = bookmarks.value.filter(item => item.id !== id)
      ElMessage.success(successMessage)
      return true
    } catch (error: any) {
      ElMessage.error('删除书签失败: ' + (error.response?.data?.error || error.message))
      return false
    }
  }

  return {
    bookmarks,
    loading,
    canBookmark,
    bookmarkedImageIds,
    fetchBookmarks,
    createAt,
    toggleAt,
    saveAutoProgress,
    restore,
    rename,
    remove
  }
})
