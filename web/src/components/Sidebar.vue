<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import api from '@/api'
import { useFolderStore } from '@/stores/folder'
import { useAuthStore } from '@/stores/auth'
import { useImageStore } from '@/stores/image'
import { useUIStore } from '@/stores/ui'
import { storeToRefs } from 'pinia'
import { Folder, Plus, Refresh, Monitor, Star, SwitchButton, User, Setting, Expand, Fold } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const folderStore = useFolderStore()
const { folders, currentFolderId } = storeToRefs(folderStore)
const authStore = useAuthStore()
const { isLoggedIn, user } = storeToRefs(authStore)
const imageStore = useImageStore()
const { showOnlyFavorites, showAdminView } = storeToRefs(imageStore)
const uiStore = useUIStore()
const { isSidebarCollapsed } = storeToRefs(uiStore)

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
  showAdminView.value = false
  showOnlyFavorites.value = false
  folderStore.selectFolder(id as any)
}

const handleSelectFavorites = () => {
  showAdminView.value = false
  showOnlyFavorites.value = true
  folderStore.selectFolder(undefined as any)
}

const handleSelectAdmin = () => {
  showAdminView.value = true
  showOnlyFavorites.value = false
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
    
    // 登录成功后刷新文件夹列表
    await folderStore.fetchFolders()
    
    ElMessage.success('登录成功')
    showLoginDialog.value = false
  } catch (err: any) {
    ElMessage.error(err.response?.data?.error || '登录失败')
  }
}

const handleLogout = async () => {
  showAdminView.value = false
  await authStore.logout()
  // 登出后刷新文件夹列表（只显示公开文件夹）
  await folderStore.fetchFolders()
  ElMessage.success('已退出登录')
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
  <div class="sidebar" :class="{ collapsed: isSidebarCollapsed }">
    <div class="sidebar-header">
      <div class="logo-icon-wrapper" @click="uiStore.toggleSidebar">
        <svg t="1772303653694" class="logo-icon-svg" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="16823" xmlns:xlink="http://www.w3.org/1999/xlink">
          <path d="M512 0c281.6 0 512 230.4 512 512s-230.4 512-512 512S0 793.6 0 512 230.4 0 512 0z" fill="#25B279" opacity=".1" p-id="16824"></path>
          <path d="M314.7776 317.44h394.24c28.16 0 48.64 23.04 48.64 48.64v184.32l-117.76-117.76c-7.68-7.68-17.92-7.68-25.6 0l-84.48 84.48-43.52-46.08c-2.56-2.56-7.68-2.56-12.8 0l-161.28 161.28h-46.08V366.08c0-28.16 20.48-48.64 48.64-48.64m478.72 271.36v-222.72c0-46.08-38.4-84.48-84.48-84.48h-394.24c-46.08 0-84.48 38.4-84.48 84.48v291.84c0 46.08 38.4 84.48 84.48 84.48h394.24c46.08 0 84.48-38.4 84.48-84.48v-61.44-7.68" fill="#25B279" p-id="16825"></path>
          <path d="M358.2976 409.6c0 15.36 10.24 25.6 25.6 25.6s25.6-10.24 25.6-25.6-10.24-25.6-25.6-25.6-25.6 10.24-25.6 25.6" fill="#25B279" p-id="16826"></path>
        </svg>
      </div>
      <span class="logo-text" v-if="!isSidebarCollapsed">PictureWeb</span>
      <el-button 
        class="toggle-btn" 
        type="primary" 
        link 
        :icon="isSidebarCollapsed ? Expand : Fold" 
        @click="uiStore.toggleSidebar"
      ></el-button>
    </div>
    
    <nav class="sidebar-nav">
        <div class="nav-group">
            <div class="nav-title" v-if="!isSidebarCollapsed">管理</div>
            <a href="#" class="nav-item" :title="isSidebarCollapsed ? '所有照片' : ''" :class="{ active: currentFolderId === undefined && !showOnlyFavorites && !showAdminView }" @click.prevent="handleSelect(undefined)">
                <el-icon><Folder /></el-icon> <span v-if="!isSidebarCollapsed">所有照片</span>
            </a>
            <a v-if="isLoggedIn" href="#" class="nav-item" :title="isSidebarCollapsed ? '收藏夹' : ''" :class="{ active: showOnlyFavorites }" @click.prevent="handleSelectFavorites">
                <el-icon><Star /></el-icon> <span v-if="!isSidebarCollapsed">收藏夹</span>
            </a>
            <a v-if="isLoggedIn && user?.role === 'admin'" href="#" class="nav-item" :title="isSidebarCollapsed ? '系统管理' : ''" :class="{ active: showAdminView }" @click.prevent="handleSelectAdmin">
                <el-icon><Setting /></el-icon> <span v-if="!isSidebarCollapsed">系统管理</span>
            </a>
        </div>
        
        <div class="nav-group">
            <div class="nav-title" v-if="!isSidebarCollapsed">
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
                    :title="isSidebarCollapsed ? folder.name : ''"
                    :class="{ active: currentFolderId === folder.id }"
                    @click="handleSelect(folder.id)"
                >
                    <el-icon><Folder /></el-icon> <span v-if="!isSidebarCollapsed">{{ folder.name }}</span>
                </div>
            </div>
        </div>
    </nav>

    <div class="sidebar-footer">
        <div class="user-info">
            <div class="avatar">{{ isLoggedIn ? user?.username[0] : 'G' }}</div>
            <div class="user-details" v-if="!isSidebarCollapsed">
                <span class="username">{{ isLoggedIn ? user?.username : '访客用户' }}</span>
                <span class="user-role">{{ isLoggedIn ? (authStore.isAdmin ? '管理员' : '普通用户') : '只读权限' }}</span>
            </div>
        </div>
        <button v-if="!isLoggedIn" class="btn-login" :title="isSidebarCollapsed ? '登录' : ''" @click="showLoginDialog = true">
            <el-icon><User /></el-icon> <span v-if="!isSidebarCollapsed">登录</span>
        </button>
        <button v-else class="btn-login" :title="isSidebarCollapsed ? '退出' : ''" @click="handleLogout">
            <el-icon><SwitchButton /></el-icon> <span v-if="!isSidebarCollapsed">退出</span>
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
    transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    z-index: 100;
}

.sidebar.collapsed {
    width: 64px;
}

.sidebar-header {
    height: var(--top-bar-height);
    display: flex;
    align-items: center;
    padding: 0 16px;
    gap: 12px;
    border-bottom: 1px solid var(--border-color);
    flex-shrink: 0;
    justify-content: space-between;
}

.logo-icon-wrapper {
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
}

.logo-icon-svg {
    width: 100%;
    height: 100%;
}

.logo-text {
    font-size: 18px;
    font-weight: bold;
    letter-spacing: 0.5px;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
}

.toggle-btn {
    padding: 8px;
    font-size: 18px;
    color: var(--text-secondary) !important;
}

.sidebar.collapsed .toggle-btn {
    position: absolute;
    right: -40px;
    top: 10px;
    background: var(--bg-sidebar);
    border: 1px solid var(--border-color);
    border-left: none;
    border-radius: 0 4px 4px 0;
    box-shadow: 2px 0 8px rgba(0,0,0,0.1);
}

/* 移动端特殊处理 */
@media (max-width: 768px) {
    .sidebar.collapsed {
        width: 0;
        border-right: none;
    }
    
    .sidebar.collapsed .toggle-btn {
        right: -40px;
        display: flex;
    }
}

.sidebar-nav {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
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
    white-space: nowrap;
}

.nav-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 20px;
    color: var(--text-primary);
    text-decoration: none;
    font-size: 14px;
    transition: all 0.2s;
    cursor: pointer;
    white-space: nowrap;
}

.sidebar.collapsed .nav-item {
    justify-content: center;
    padding: 10px 0;
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
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 8px;
}

.sidebar.collapsed .folder-item {
    padding: 8px 0;
    justify-content: center;
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

.sidebar.collapsed .sidebar-footer {
    padding: 16px 0;
    display: flex;
    flex-direction: column;
    align-items: center;
}

.user-info {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 12px;
}

.sidebar.collapsed .user-info {
    margin-bottom: 8px;
}

.avatar {
    width: 32px;
    height: 32px;
    background: var(--primary);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    font-size: 14px;
    color: white;
    flex-shrink: 0;
}

.user-details {
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.username {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-primary);
    white-space: nowrap;
    text-overflow: ellipsis;
    overflow: hidden;
}

.user-role {
    font-size: 11px;
    color: var(--text-secondary);
    white-space: nowrap;
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
    white-space: nowrap;
}

.sidebar.collapsed .btn-login {
    border: none;
    width: 32px;
    height: 32px;
    padding: 0;
    border-radius: 50%;
}
</style>
