import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api'

export interface Hotkeys {
  PREV: string
  NEXT: string
  CLOSE: string
  FAVORITE: string
  DELETE: string
  ROTATE: string
  ZOOM_IN: string
  ZOOM_OUT: string
  RESET: string
}

export const DEFAULT_HOTKEYS: Hotkeys = {
  PREV: 'ArrowLeft',
  NEXT: 'ArrowRight',
  CLOSE: 'Escape',
  FAVORITE: 'f',
  DELETE: 'Delete',
  ROTATE: 'r',
  ZOOM_IN: 'ArrowUp',
  ZOOM_OUT: 'ArrowDown',
  RESET: 'h'
}

export const useHotkeyStore = defineStore('hotkey', () => {
  const hotkeys = ref<Hotkeys>({ ...DEFAULT_HOTKEYS })
  const loading = ref(false)

  const fetchHotkeys = async () => {
    loading.value = true
    try {
      const res = await api.get('/admin/settings')
      if (res.data && res.data.HOTKEYS) {
        hotkeys.value = { ...DEFAULT_HOTKEYS, ...res.data.HOTKEYS }
      }
    } catch (err) {
      console.error('Failed to fetch hotkeys, using defaults', err)
    } finally {
      loading.value = false
    }
  }

  const updateHotkeys = (newHotkeys: Partial<Hotkeys>) => {
    hotkeys.value = { ...hotkeys.value, ...newHotkeys }
  }

  return {
    hotkeys,
    loading,
    fetchHotkeys,
    updateHotkeys
  }
})
