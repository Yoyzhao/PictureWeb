import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

// Add a request interceptor to attach the token
api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export const getFolders = () => api.get('/folders')
export const addFolder = (path: string, name?: string) => api.post('/folders', { path, name })
export const scanFolder = (id: number) => api.post(`/folders/${id}/scan`)

export const getImages = (params: { 
  page: number; 
  per_page: number; 
  folder_id?: number; 
  is_favorite?: string;
  sort_by?: string;
  sort_order?: string;
  q?: string;
}) => 
  api.get('/images', { params })

export const updateImage = (id: number, data: any) => api.patch(`/images/${id}`, data)
export const toggleImageFavorite = (id: number) => api.post(`/images/${id}/favorite`)

export const batchMoveImages = (imageIds: number[], targetFolderId: number) => 
  api.post('/images/batch/move', { image_ids: imageIds, target_folder_id: targetFolderId })

export const batchDeleteImages = (imageIds: number[]) => 
  api.post('/images/batch/delete', { image_ids: imageIds })

export const getImage = (id: number) => api.get(`/images/${id}`)
export const deleteFolder = (id: number, hard = false) => api.delete(`/folders/${id}`, { params: { hard } })

// Trash APIs
export const getTrash = () => api.get('/images/trash/items')
export const restoreTrash = (trashIds: number[]) => api.post('/images/trash/restore', { trash_ids: trashIds })
export const clearTrash = (trashIds?: number[]) => api.post('/images/trash/clear', { trash_ids: trashIds })

export default api
