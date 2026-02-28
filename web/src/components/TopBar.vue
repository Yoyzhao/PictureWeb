<script setup lang="ts">
import { Search, Setting, Plus, Sunny, Moon } from '@element-plus/icons-vue'
import { ref, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useImageStore } from '@/stores/image'
import { storeToRefs } from 'pinia'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { useTheme } from '@/composables/useTheme'

const authStore = useAuthStore()
const imageStore = useImageStore()
const { searchQuery } = storeToRefs(imageStore)
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
    router.push('/admin')
  } else {
    ElMessage.info('设置功能开发中...')
  }
}
</script>

<template>
  <header class="top-bar">
    <div class="search-container">
      <el-icon class="search-icon"><Search /></el-icon>
      <input 
        v-model="searchQuery" 
        type="text" 
        placeholder="搜索文件名..." 
        class="search-input"
      >
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
    flex: 0 0 400px;
    position: relative;
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
    gap: 12px;
}

.btn-icon {
    background: transparent;
    border: none;
    color: var(--text-primary);
    font-size: 18px;
    margin-left: 16px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
}

.btn-icon:hover {
    color: var(--primary);
}
</style>
