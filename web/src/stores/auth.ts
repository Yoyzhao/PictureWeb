import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<{ username: string; role: string } | null>(null)
  const token = ref<string | null>(localStorage.getItem('token'))

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  const login = async (username: string, role: string, userToken: string) => {
    user.value = { username, role }
    token.value = userToken
    localStorage.setItem('token', userToken)
    localStorage.setItem('user', JSON.stringify(user.value))
  }

  const logout = () => {
    user.value = null
    token.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  // Initialize from localStorage
  const init = () => {
    const savedUser = localStorage.getItem('user')
    if (savedUser) {
      try {
        user.value = JSON.parse(savedUser)
      } catch (e) {
        logout()
      }
    }
  }

  return {
    user,
    token,
    isLoggedIn,
    isAdmin,
    login,
    logout,
    init
  }
})
