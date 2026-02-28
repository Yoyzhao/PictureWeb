import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
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

export const batchMoveImages = (imageIds: number[], targetFolderId: number) => 
  api.post('/images/batch/move', { image_ids: imageIds, target_folder_id: targetFolderId })

export const batchDeleteImages = (imageIds: number[]) => 
  api.post('/images/batch/delete', { image_ids: imageIds })

export const getImage = (id: number) => api.get(`/images/${id}`)

export default api
