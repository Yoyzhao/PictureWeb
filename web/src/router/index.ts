import { createRouter, createWebHistory } from 'vue-router'
import HomePage from '@/pages/HomePage.vue'
import AdminPage from '@/pages/AdminPage.vue'
import { useAuthStore } from '@/stores/auth'

// 定义路由配置
const routes = [
  {
    path: '/',
    name: 'home',
    component: HomePage,
  },
  {
    path: '/admin',
    name: 'admin',
    component: AdminPage,
    meta: { requiresAdmin: true }
  },
  {
    path: '/about',
    name: 'about',
    component: {
      template: '<div class="text-center text-xl p-8">About Page - Coming Soon</div>',
    },
  },
]

// 创建路由实例
const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  
  if (to.meta.requiresAdmin) {
    if (authStore.isLoggedIn && authStore.user?.role === 'admin') {
      next()
    } else {
      next('/')
    }
  } else {
    next()
  }
})

export default router
