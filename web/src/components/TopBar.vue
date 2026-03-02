<script setup lang="ts">
import { Search, Setting, Plus, Sunny, Moon, Expand, Fold } from '@element-plus/icons-vue'
import { ref, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useImageStore } from '@/stores/image'
import { useUIStore } from '@/stores/ui'
import { storeToRefs } from 'pinia'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { useTheme } from '@/composables/useTheme'

const authStore = useAuthStore()
const imageStore = useImageStore()
const uiStore = useUIStore()
const { searchQuery, showAdminView } = storeToRefs(imageStore)
const { isSidebarCollapsed } = storeToRefs(uiStore)
const router = useRouter()

const { isDark, toggleTheme } = useTheme()

const themeValue = computed({
  get: () => (isDark.value ? 'dark' : 'light'),
  set: () => toggleTheme(),
})

const handleUpload = () => {
  if (!authStore.isLoggedIn) {
    ElMessage.warning('请先登录后再上传图片')
    return
  }
  ElMessage.info('上传功能开发中...')
}

const handleSettings = () => {
  if (authStore.user?.role === 'admin') {
    showAdminView.value = !showAdminView.value
  } else {
    ElMessage.warning('需要管理员权限')
  }
}
</script>

<template>
  <header class="top-bar" :class="{ 'sidebar-collapsed': isSidebarCollapsed }">
    <div class="left-section">
      <div class="search-container">
        <el-icon class="search-icon"><Search /></el-icon>
        <input 
          v-model="searchQuery" 
          type="text" 
          placeholder="搜索文件名..." 
          class="search-input"
        >
      </div>
    </div>
    <div class="action-buttons">
      <el-radio-group v-model="themeValue" size="small" class="theme-toggle">
        <el-radio-button value="light">
          <el-icon><Sunny /></el-icon>
        </el-radio-button>
        <el-radio-button value="dark">
          <el-icon><Moon /></el-icon>
        </el-radio-button>
      </el-radio-group>
      <button class="btn-icon" title="上传" @click="handleUpload">
        <el-icon><Plus /></el-icon>
      </button>
      <button class="btn-icon" title="设置" @click="handleSettings">
        <el-icon><Setting /></el-icon>
      </button>
    </div>
  </header>
</template>

<style scoped>
.top-bar {
  height: var(--top-bar-height);
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-topbar);
  backdrop-filter: blur(10px);
  z-index: 10;
  flex-shrink: 0;
  transition: padding-left 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.top-bar.sidebar-collapsed {
  padding-left: 56px; /* 为侧边栏外的收起按钮预留空间 */
}

.left-section {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.theme-toggle {
  margin-right: 12px;
}

:deep(.theme-toggle .el-radio-button__inner) {
  padding: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.search-container {
    flex: 1;
    max-width: 400px;
    position: relative;
    min-width: 100px;
}

@media (max-width: 768px) {
    .top-bar {
        padding: 0 12px;
    }
    
    .top-bar.sidebar-collapsed {
        padding-left: 48px;
    }

    .search-container {
        max-width: 200px;
    }

    .theme-toggle {
        margin-right: 4px;
    }

    .btn-icon {
        margin-left: 8px;
    }
}

.search-icon {
    position: absolute;
    left: 12px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--text-secondary);
    pointer-events: none;
}

.search-input {
    width: 100%;
    padding: 8px 12px 8px 36px;
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 20px;
    color: var(--text-primary);
    outline: none;
    font-size: 14px;
}

.search-input:focus {
    border-color: var(--primary);
}

.action-buttons {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
}

.btn-icon {
    background: transparent;
    border: none;
    color: var(--text-primary);
    font-size: 18px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
}

.btn-icon:hover {
    color: var(--primary);
}
</style>
