<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import api from '@/api'
import { useFolderStore } from '@/stores/folder'
import { useAuthStore } from '@/stores/auth'
import { useImageStore } from '@/stores/image'
import { storeToRefs } from 'pinia'
import { Folder, Plus, Refresh, Monitor, Star, SwitchButton, User, Setting } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const folderStore = useFolderStore()
const authStore = useAuthStore()
const imageStore = useImageStore()
const { folders, currentFolderId } = storeToRefs(folderStore)
const { isLoggedIn, user } = storeToRefs(authStore)
const { showOnlyFavorites } = storeToRefs(imageStore)

const isAdmin = computed(() => user.value?.role === 'admin')
const isGuest = computed(() => user.value?.role === 'guest')

const showAddDialog = ref(false)
const showLoginDialog = ref(false)
const newFolderPath = ref('')
const newFolderName = ref('')

const loginForm = ref({
  username: '',
  password: ''
})

onMounted(() => {
  folderStore.fetchFolders()
})

const handleSelect = (id: number | undefined) => {
  showOnlyFavorites.value = false
  folderStore.selectFolder(id as any)
}

const handleSelectFavorites = () => {
  showOnlyFavorites.value = true
  folderStore.selectFolder(undefined as any)
}

const handleLogin = async () => {
  try {
    const res = await api.post('/auth/login', {
      username: loginForm.value.username,
      password: loginForm.value.password
    })
    
    const { user: loggedInUser, token } = res.data
    await authStore.login(loggedInUser.username, loggedInUser.role, token)
    
    ElMessage.success('登录成功')
    showLoginDialog.value = false
  } catch (err: any) {
    ElMessage.error(err.response?.data?.error || '登录失败')
  }
}

const handleLogout = () => {
  authStore.logout()
  ElMessage.info('已退出登录')
}

const handleAddFolder = async () => {
  if (!newFolderPath.value) return
  await folderStore.createFolder(newFolderPath.value, newFolderName.value || undefined)
  showAddDialog.value = false
  newFolderPath.value = ''
  newFolderName.value = ''
}
</script>

<template>
  <div class="sidebar">
    <div class="sidebar-header">
      <el-icon class="logo-icon"><Monitor /></el-icon>
      <span class="logo-text">PictureWeb</span>
    </div>
    
    <nav class="sidebar-nav">
        <div class="nav-group">
            <div class="nav-title">管理</div>
            <a href="#" class="nav-item" :class="{ active: currentFolderId === undefined && !showOnlyFavorites }" @click.prevent="handleSelect(undefined)">
                <el-icon><Folder /></el-icon> 所有照片
            </a>
            <a v-if="isLoggedIn" href="#" class="nav-item" :class="{ active: showOnlyFavorites }" @click.prevent="handleSelectFavorites">
                <el-icon><Star /></el-icon> 收藏夹
            </a>
            <router-link v-if="isLoggedIn && user?.role === 'admin'" to="/admin" class="nav-item">
                <el-icon><Setting /></el-icon> 系统管理
            </router-link>
        </div>
        
        <div class="nav-group">
            <div class="nav-title">
                文件夹
                <template v-if="isLoggedIn && !isGuest">
                  <el-button type="primary" link :icon="Plus" @click.stop="showAddDialog = true" size="small" style="float: right; color: var(--text-secondary);"></el-button>
                  <el-button link :icon="Refresh" @click.stop="folderStore.fetchFolders()" size="small" style="float: right; color: var(--text-secondary); margin-right: 5px;"></el-button>
                </template>
            </div>
            <div id="folder-list" class="folder-list">
                <div 
                    v-for="folder in folders" 
                    :key="folder.id" 
                    class="folder-item"
                    :class="{ active: currentFolderId === folder.id }"
                    @click="handleSelect(folder.id)"
                >
                    <el-icon><Folder /></el-icon> {{ folder.name }}
                </div>
            </div>
        </div>
    </nav>

    <div class="sidebar-footer">
        <div class="user-info">
            <div class="avatar">{{ isLoggedIn ? user?.username[0] : 'G' }}</div>
            <div class="user-details">
                <span class="username">{{ isLoggedIn ? user?.username : '访客用户' }}</span>
                <span class="user-role">{{ isLoggedIn ? (authStore.isAdmin ? '管理员' : '普通用户') : '只读权限' }}</span>
            </div>
        </div>
        <button v-if="!isLoggedIn" class="btn-login" @click="showLoginDialog = true">
            <el-icon><User /></el-icon> 登录
        </button>
        <button v-else class="btn-login" @click="handleLogout">
            <el-icon><SwitchButton /></el-icon> 退出
        </button>
    </div>

    <!-- Login Dialog -->
    <el-dialog v-model="showLoginDialog" title="用户登录" width="400px">
      <el-form :model="loginForm" label-width="60px">
        <el-form-item label="账号">
          <el-input v-model="loginForm.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="loginForm.password" type="password" placeholder="请输入密码" show-password />
        </el-form-item>
        <div style="font-size: 12px; color: #999; margin-left: 60px;">
          提示: admin / admin123
        </div>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showLoginDialog = false">取消</el-button>
          <el-button type="primary" @click="handleLogin">登录</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- Add Folder Dialog -->
    <el-dialog v-model="showAddDialog" title="添加文件夹" width="500px">
      <el-form label-width="80px">
        <el-form-item label="路径">
          <el-input v-model="newFolderPath" placeholder="文件夹绝对路径" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="newFolderName" placeholder="显示名称 (可选)" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showAddDialog = false">取消</el-button>
          <el-button type="primary" @click="handleAddFolder">添加</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.sidebar {
    width: var(--sidebar-width);
    background-color: var(--bg-sidebar);
    border-right: 1px solid var(--border-color);
    display: flex;
    flex-direction: column;
    height: 100%;
}

.sidebar-header {
    height: var(--top-bar-height);
    display: flex;
    align-items: center;
    padding: 0 20px;
    gap: 12px;
    border-bottom: 1px solid var(--border-color);
    flex-shrink: 0;
}

.logo-icon {
    font-size: 24px;
    color: var(--primary);
}

.logo-text {
    font-size: 18px;
    font-weight: bold;
    letter-spacing: 0.5px;
    color: var(--text-primary);
}

.sidebar-nav {
    flex: 1;
    overflow-y: auto;
    padding: 20px 0;
}

.nav-group {
    margin-bottom: 24px;
}

.nav-title {
    padding: 0 20px 8px;
    font-size: 11px;
    text-transform: uppercase;
    color: var(--text-secondary);
    letter-spacing: 1px;
}

.nav-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 20px;
    color: var(--text-primary);
    text-decoration: none;
    font-size: 14px;
    transition: background 0.2s;
    cursor: pointer;
}

.nav-item:hover, .nav-item.active {
    background-color: var(--accent);
}

.nav-item.active {
    color: var(--primary);
    border-right: 3px solid var(--primary);
}

.folder-list {
    margin-top: 4px;
}

.folder-item {
    padding: 8px 20px 8px 36px;
    font-size: 13px;
    color: var(--text-secondary);
    cursor: pointer;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: color 0.2s;
    display: flex;
    align-items: center;
    gap: 8px;
}

.folder-item:hover, .folder-item.active {
    color: var(--text-primary);
    background-color: var(--accent);
}

.sidebar-footer {
    padding: 16px;
    border-top: 1px solid var(--border-color);
    flex-shrink: 0;
}

.user-info {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 12px;
}

.avatar {
    width: 36px;
    height: 36px;
    background: var(--primary);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    font-size: 14px;
    color: white;
}

.user-details {
    display: flex;
    flex-direction: column;
}

.username {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-primary);
}

.user-role {
    font-size: 11px;
    color: var(--text-secondary);
}

.btn-login {
    width: 100%;
    padding: 8px;
    background: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-primary);
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
}

.btn-login:hover {
    background: var(--accent);
}
</style>
