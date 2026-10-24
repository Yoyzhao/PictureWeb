<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import api from '@/api'
import { useFolderStore } from '@/stores/folder'
import { useAuthStore } from '@/stores/auth'
import { useImageStore } from '@/stores/image'
import { useUIStore } from '@/stores/ui'
import { storeToRefs } from 'pinia'
import { Folder, Plus, Refresh, Monitor, Star, SwitchButton, User, Setting, Expand, Fold, Delete } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const folderStore = useFolderStore()
const { folders, currentFolderId } = storeToRefs(folderStore)
const authStore = useAuthStore()
const { isLoggedIn, user } = storeToRefs(authStore)
const imageStore = useImageStore()
const { showOnlyFavorites, showAdminView, showTrash } = storeToRefs(imageStore)
const uiStore = useUIStore()
const { isSidebarCollapsed } = storeToRefs(uiStore)

const isAdmin = computed(() => user.value?.role === 'admin')
const isGuest = computed(() => user.value?.role === 'guest')

const showAddDialog = ref(false)
const showLoginDialog = ref(false)
const newFolderPath = ref('')
const newFolderName = ref('')
const isLoggingIn = ref(false)

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
  showTrash.value = false
  folderStore.selectFolder(id as any)
}

const handleSelectFavorites = () => {
  showAdminView.value = false
  showOnlyFavorites.value = true
  showTrash.value = false
  folderStore.selectFolder(undefined as any)
}

const handleSelectAdmin = () => {
  showAdminView.value = true
  showOnlyFavorites.value = false
  showTrash.value = false
  folderStore.selectFolder(undefined as any)
}

const handleSelectTrash = () => {
  showAdminView.value = false
  showOnlyFavorites.value = false
  showTrash.value = true
  folderStore.selectFolder(undefined as any)
  imageStore.fetchTrash()
}

const handleLogin = async () => {
  if (isLoggingIn.value) return
  isLoggingIn.value = true
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
  } finally {
    isLoggingIn.value = false
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
            <div class="nav-title" v-if="!isSidebarCollapsed"><span>浏览</span></div>
            <button type="button" class="nav-item" :title="isSidebarCollapsed ? '所有照片' : ''" :aria-current="currentFolderId === undefined && !showOnlyFavorites && !showAdminView && !showTrash ? 'page' : undefined" :class="{ active: currentFolderId === undefined && !showOnlyFavorites && !showAdminView && !showTrash }" @click="handleSelect(undefined)">
                <el-icon><Folder /></el-icon> <span v-if="!isSidebarCollapsed">所有照片</span>
            </button>
            <button v-if="isLoggedIn" type="button" class="nav-item" :title="isSidebarCollapsed ? '收藏夹' : ''" :aria-current="showOnlyFavorites ? 'page' : undefined" :class="{ active: showOnlyFavorites }" @click="handleSelectFavorites">
                <el-icon><Star /></el-icon> <span v-if="!isSidebarCollapsed">收藏夹</span>
            </button>
            <button v-if="isLoggedIn && !isGuest" type="button" class="nav-item" :title="isSidebarCollapsed ? '回收站' : ''" :aria-current="showTrash ? 'page' : undefined" :class="{ active: showTrash }" @click="handleSelectTrash">
                <el-icon><Delete /></el-icon> <span v-if="!isSidebarCollapsed">回收站</span>
            </button>
            <button v-if="isLoggedIn && user?.role === 'admin'" type="button" class="nav-item" :title="isSidebarCollapsed ? '系统管理' : ''" :aria-current="showAdminView ? 'page' : undefined" :class="{ active: showAdminView }" @click="handleSelectAdmin">
                <el-icon><Setting /></el-icon> <span v-if="!isSidebarCollapsed">系统管理</span>
            </button>
        </div>

        <div class="nav-group">
            <div class="nav-title" v-if="!isSidebarCollapsed">
                <span>文件夹</span>
                <div v-if="isLoggedIn && !isGuest" class="nav-title-actions">
                  <el-button class="nav-icon-btn" text circle :icon="Plus" title="添加文件夹" aria-label="添加文件夹" @click.stop="showAddDialog = true" />
                  <el-button class="nav-icon-btn" text circle :icon="Refresh" title="刷新文件夹" aria-label="刷新文件夹" @click.stop="folderStore.fetchFolders()" />
                </div>
            </div>
            <div id="folder-list" class="folder-list">
                <button
                    v-for="folder in folders"
                    :key="folder.id"
                    type="button"
                    class="folder-item"
                    :title="isSidebarCollapsed ? folder.name : ''"
                    :aria-current="currentFolderId === folder.id ? 'page' : undefined"
                    :class="{ active: currentFolderId === folder.id }"
                    @click="handleSelect(folder.id)"
                >
                    <el-icon><Folder /></el-icon> <span v-if="!isSidebarCollapsed">{{ folder.name }}</span>
                </button>
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
        <button v-if="!isLoggedIn" class="btn-login" :title="isSidebarCollapsed ? '登录' : ''" aria-label="登录" @click="showLoginDialog = true">
            <el-icon><User /></el-icon> <span v-if="!isSidebarCollapsed">登录</span>
        </button>
        <button v-else class="btn-login" :title="isSidebarCollapsed ? '退出' : ''" aria-label="退出登录" @click="handleLogout">
            <el-icon><SwitchButton /></el-icon> <span v-if="!isSidebarCollapsed">退出</span>
        </button>
    </div>

    <!-- Login Dialog -->
    <el-dialog v-model="showLoginDialog" title="用户登录" width="400px" :close-on-click-modal="false" @closed="loginForm.username = ''; loginForm.password = ''">
      <el-form :model="loginForm" label-width="60px" @keyup.enter="handleLogin">
        <el-form-item label="账号">
          <el-input v-model="loginForm.username" placeholder="请输入用户名" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="loginForm.password" type="password" placeholder="请输入密码" show-password autocomplete="current-password" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showLoginDialog = false">取消</el-button>
          <el-button type="primary" :loading="isLoggingIn" @click="handleLogin">登录</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- Add Folder Dialog -->
    <el-dialog v-model="showAddDialog" title="添加文件夹" width="500px" :close-on-click-modal="false">
      <el-form label-width="80px" @keyup.enter="handleAddFolder">
        <el-form-item label="路径">
          <el-input v-model="newFolderPath" placeholder="文件夹绝对路径" autocomplete="off" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="newFolderName" placeholder="显示名称 (可选)" autocomplete="off" />
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
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    background: var(--primary-soft);
    border-radius: 10px;
    padding: 5px;
    transition: transform var(--motion-fast) var(--ease-out);
}

.logo-icon-wrapper:hover {
    transform: scale(1.05);
}

.logo-icon-svg {
    width: 100%;
    height: 100%;
}

.logo-text {
    font-size: 17px;
    font-weight: 700;
    letter-spacing: -0.01em;
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
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 18px 8px;
    font-size: 11px;
    color: var(--text-tertiary);
    letter-spacing: 0.06em;
    white-space: nowrap;
}

.nav-title-actions {
    display: flex;
    align-items: center;
    gap: 2px;
}

.nav-icon-btn {
    width: 26px;
    height: 26px;
    padding: 0 !important;
    color: var(--text-secondary) !important;
    border-radius: 6px;
}

.nav-icon-btn:hover {
    color: var(--text-primary) !important;
    background: var(--accent);
}

.nav-item {
    display: flex;
    align-items: center;
    gap: 10px;
    width: calc(100% - 20px);
    margin: 2px 10px;
    padding: 10px 12px;
    color: var(--text-primary);
    text-decoration: none;
    font-size: 13.5px;
    border: none;
    border-radius: 10px;
    background: transparent;
    text-align: left;
    transition: background-color var(--motion-fast) var(--ease-out),
                color var(--motion-fast) var(--ease-out);
    cursor: pointer;
    white-space: nowrap;
}

.sidebar.collapsed .nav-item {
    justify-content: center;
    width: calc(100% - 16px);
    margin: 2px 8px;
    padding: 10px 0;
}

.nav-item:hover {
    background-color: var(--accent);
}

.nav-item.active {
    background-color: var(--primary-soft);
    color: var(--primary);
}

.nav-item.active .el-icon {
    color: var(--primary);
}

.folder-list {
    margin-top: 2px;
}

.folder-item {
    display: flex;
    align-items: center;
    gap: 8px;
    width: calc(100% - 20px);
    margin: 1px 10px;
    padding: 8px 12px 8px 34px;
    font-size: 13px;
    color: var(--text-secondary);
    cursor: pointer;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    border: none;
    border-radius: 8px;
    background: transparent;
    text-align: left;
    transition: background-color var(--motion-fast) var(--ease-out),
                color var(--motion-fast) var(--ease-out);
}

.sidebar.collapsed .folder-item {
    width: calc(100% - 16px);
    margin: 1px 8px;
    padding: 8px 0;
    justify-content: center;
}

.folder-item:hover {
    color: var(--text-primary);
    background-color: var(--accent);
}

.folder-item.active {
    color: var(--primary);
    background-color: var(--primary-soft);
}

.sidebar-footer {
    padding: 12px;
    border-top: 1px solid var(--border-color);
    flex-shrink: 0;
}

.sidebar.collapsed .sidebar-footer {
    padding: 12px 0;
    display: flex;
    flex-direction: column;
    align-items: center;
}

.user-info {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
    padding: 8px;
    border-radius: 10px;
    background: var(--bg-secondary);
}

.sidebar.collapsed .user-info {
    margin-bottom: 8px;
    padding: 4px;
    background: transparent;
}

.avatar {
    width: 32px;
    height: 32px;
    background: linear-gradient(135deg, var(--primary), #6bb6ff);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 600;
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
    padding: 9px;
    background: var(--primary);
    border: 1px solid transparent;
    color: #fff;
    border-radius: 10px;
    cursor: pointer;
    font-size: 13px;
    transition: filter var(--motion-fast) var(--ease-out),
                background-color var(--motion-fast) var(--ease-out);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    white-space: nowrap;
}

.btn-login:hover {
    filter: brightness(1.06);
}

.sidebar.collapsed .btn-login {
    width: 32px;
    height: 32px;
    padding: 0;
    border-radius: 50%;
    background: var(--primary-soft);
    color: var(--primary);
}
</style>
