<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { User, Folder, Setting, Plus, Delete, Edit } from '@element-plus/icons-vue'

const activeTab = ref('users')
const users = ref<any[]>([])
const permissions = ref<any[]>([])
const folders = ref<any[]>([])
const settings = ref<any>({})

const showUserDialog = ref(false)
const showPermissionDialog = ref(false)
const userForm = ref({
  id: null as number | null,
  username: '',
  password: '',
  role: 'user'
})

const permissionForm = ref({
  user_id: null as number | null,
  folder_id: null as number | null,
  permission_types: [] as string[]
})

const fetchUsers = async () => {
  try {
    const res = await api.get('/admin/users')
    users.value = res.data
  } catch (err) {
    ElMessage.error('获取用户列表失败')
  }
}

const fetchFolders = async () => {
  try {
    const res = await api.get('/admin/folders')
    folders.value = res.data
  } catch (err) {
    ElMessage.error('获取文件夹列表失败')
  }
}

const fetchPermissions = async () => {
  try {
    const res = await api.get('/admin/permissions')
    permissions.value = res.data
  } catch (err) {
    ElMessage.error('获取权限列表失败')
  }
}

const fetchSettings = async () => {
  try {
    const res = await api.get('/admin/settings')
    settings.value = res.data
  } catch (err) {
    ElMessage.error('获取系统设置失败')
  }
}

onMounted(() => {
  fetchUsers()
  fetchFolders()
  fetchPermissions()
  fetchSettings()
})

const showFolderDialog = ref(false)
const folderForm = ref({
  path: '',
  name: ''
})

const handleAddFolder = () => {
  folderForm.value = { path: '', name: '' }
  showFolderDialog.value = true
}

const saveFolder = async () => {
  try {
    if (!folderForm.value.path) {
      ElMessage.warning('请输入物理路径')
      return
    }
    await api.post('/folders', folderForm.value)
    ElMessage.success('文件夹已添加')
    showFolderDialog.value = false
    fetchFolders()
  } catch (err: any) {
    ElMessage.error(err.response?.data?.error || '添加失败')
  }
}

const handleScanFolder = async (id: number) => {
  try {
    ElMessage.info('扫描任务已提交，请稍候...')
    const res = await api.post(`/folders/${id}/scan`)
    const { processed, removed, total } = res.data
    
    ElMessageBox.alert(
      `扫描已完成：<br/>
       - 处理图片: <strong>${processed}</strong> 张<br/>
       - 清理失效图片: <strong>${removed}</strong> 张<br/>
       - 当前文件夹总数: <strong>${total}</strong> 张`,
      '扫描结果',
      {
        dangerouslyUseHTMLString: true,
        confirmButtonText: '确定',
        type: 'success'
      }
    )
  } catch (err) {
    ElMessage.error('扫描失败')
  }
}

const handleDeleteFolder = async (id: number) => {
  try {
    await ElMessageBox.confirm('确定要删除此文件夹吗？这将清除所有关联的图片和权限记录，但不会删除硬盘上的物理文件。', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await api.delete(`/admin/folders/${id}`)
    ElMessage.success('文件夹已删除')
    fetchFolders()
    fetchPermissions()
  } catch (err) {
    if (err !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const handleAddUser = () => {
  userForm.value = { id: null, username: '', password: '', role: 'user' }
  showUserDialog.value = true
}

const handleEditUser = (user: any) => {
  userForm.value = { ...user, password: '' }
  showUserDialog.value = true
}

const saveUser = async () => {
  try {
    if (userForm.value.id) {
      await api.patch(`/admin/users/${userForm.value.id}`, userForm.value)
      ElMessage.success('用户已更新')
    } else {
      await api.post('/admin/users', userForm.value)
      ElMessage.success('用户已添加')
    }
    showUserDialog.value = false
    fetchUsers()
  } catch (err: any) {
    ElMessage.error(err.response?.data?.error || '操作失败')
  }
}

const deleteUser = async (id: number) => {
  try {
    await ElMessageBox.confirm('确定要删除此用户吗？', '提示', { type: 'warning' })
    await api.delete(`/admin/users/${id}`)
    ElMessage.success('用户已删除')
    fetchUsers()
  } catch (err) {}
}

const handleAddPermission = () => {
  permissionForm.value = { user_id: null, folder_id: null, permission_types: [] }
  showPermissionDialog.value = true
}

const savePermission = async () => {
  try {
    await api.post('/admin/permissions', permissionForm.value)
    ElMessage.success('权限已添加')
    showPermissionDialog.value = false
    fetchPermissions()
  } catch (err: any) {
    ElMessage.error(err.response?.data?.error || '添加失败')
  }
}

const deletePermission = async (id: number) => {
  try {
    await ElMessageBox.confirm('确定要删除此权限吗？', '提示', { type: 'warning' })
    await api.delete(`/admin/permissions/${id}`)
    ElMessage.success('权限已删除')
    fetchPermissions()
  } catch (err) {}
}

const saveSettings = async () => {
  try {
    await api.post('/admin/settings', settings.value)
    ElMessage.success('设置已保存')
  } catch (err) {
    ElMessage.error('保存设置失败')
  }
}
</script>

<template>
  <div class="admin-container">
    <div class="admin-header">
      <h1>系统管理</h1>
      <router-link to="/" class="back-link">返回首页</router-link>
    </div>

    <el-tabs v-model="activeTab" class="admin-tabs">
      <el-tab-pane label="文件夹管理" name="folders">
        <div class="tab-content">
          <div class="action-bar">
            <el-button type="primary" :icon="Plus" @click="handleAddFolder">添加文件夹</el-button>
          </div>
          <el-table :data="folders" style="width: 100%">
            <el-table-column prop="name" label="名称" />
            <el-table-column prop="path" label="物理路径" />
            <el-table-column label="操作" width="200">
              <template #default="{ row }">
                <el-button-group>
                  <el-button type="success" size="small" @click="handleScanFolder(row.id)">扫描</el-button>
                  <el-button type="danger" size="small" :icon="Delete" @click="handleDeleteFolder(row.id)">删除</el-button>
                </el-button-group>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>
      <el-tab-pane label="用户管理" name="users">
        <div class="tab-content">
          <div class="action-bar">
            <el-button type="primary" :icon="Plus" @click="handleAddUser">添加用户</el-button>
          </div>
          <el-table :data="users" style="width: 100%">
            <el-table-column prop="username" label="用户名" />
            <el-table-column prop="role" label="角色">
              <template #default="{ row }">
                <el-tag :type="row.role === 'admin' ? 'danger' : 'info'">{{ row.role }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" />
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button-group>
                  <el-button :icon="Edit" size="small" @click="handleEditUser(row)" />
                  <el-button :icon="Delete" size="small" type="danger" @click="deleteUser(row.id)" :disabled="row.username === 'admin' || row.username === 'guest'" />
                </el-button-group>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="文件夹权限" name="permissions">
        <div class="tab-content">
          <div class="action-bar">
            <el-button type="primary" :icon="Plus" @click="handleAddPermission">分配权限</el-button>
          </div>
          <el-alert title="提示" type="info" description="此处管理用户对各个文件夹的细粒度操作权限。" show-icon style="margin-bottom: 20px" />
          <el-table :data="permissions" style="width: 100%">
            <el-table-column prop="username" label="用户" />
            <el-table-column prop="folder_name" label="文件夹" />
            <el-table-column prop="permission_type" label="权限类型">
               <template #default="{ row }">
                <el-tag>{{ row.permission_type }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button :icon="Delete" size="small" type="danger" @click="deletePermission(row.id)" />
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="系统设置" name="settings">
        <div class="tab-content settings-form">
          <el-form :model="settings" label-width="150px">
            <el-form-item label="服务端口">
              <el-input-number v-model="settings.SERVER_PORT" :min="1" :max="65535" />
            </el-form-item>
            <el-form-item label="数据库路径">
              <el-input v-model="settings.DB_PATH" />
            </el-form-item>
            <el-form-item label="缓存目录">
              <el-input v-model="settings.CACHE_DIR" />
            </el-form-item>
            <el-form-item label="日志级别">
              <el-select v-model="settings.LOG_LEVEL">
                <el-option label="DEBUG" value="DEBUG" />
                <el-option label="INFO" value="INFO" />
                <el-option label="WARNING" value="WARNING" />
                <el-option label="ERROR" value="ERROR" />
              </el-select>
            </el-form-item>
            <el-form-item label="匿名访问">
              <el-switch v-model="settings.ANONYMOUS_ACCESS" />
            </el-form-item>
            <el-form-item label="缩略图质量">
              <el-slider v-model="settings.THUMBNAIL_QUALITY" :min="10" :max="100" />
            </el-form-item>
            <el-divider content-position="left">扫描设置</el-divider>
            <el-form-item label="递归扫描">
              <el-switch v-model="settings.SCAN_RECURSIVE" />
              <div class="form-tip">开启后将扫描子文件夹中的图片</div>
            </el-form-item>
            <el-form-item label="支持格式">
              <el-input v-model="settings.SCAN_EXTENSIONS" placeholder="例如: .jpg,.png,.webp" />
              <div class="form-tip">多个格式请用英文逗号隔开</div>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveSettings">保存设置</el-button>
            </el-form-item>
          </el-form>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="showUserDialog" :title="userForm.id ? '编辑用户' : '添加用户'" width="400px">
      <el-form :model="userForm" label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="userForm.username" :disabled="!!userForm.id" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="userForm.password" type="password" placeholder="留空则不修改" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="userForm.role">
            <el-option label="管理员" value="admin" />
            <el-option label="普通用户" value="user" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUserDialog = false">取消</el-button>
        <el-button type="primary" @click="saveUser">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showPermissionDialog" title="分配文件夹权限" width="400px">
      <el-form :model="permissionForm" label-width="80px">
        <el-form-item label="用户">
          <el-select v-model="permissionForm.user_id" placeholder="选择用户">
            <el-option 
              v-for="u in users" 
              :key="u.id" 
              :label="u.username" 
              :value="u.id"
              :disabled="u.role === 'admin' || u.role === 'guest'"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="文件夹">
          <el-select v-model="permissionForm.folder_id" placeholder="选择文件夹">
            <el-option v-for="f in folders" :key="f.id" :label="f.name" :value="f.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="权限类型">
          <el-select v-model="permissionForm.permission_types" multiple placeholder="选择权限">
            <el-option label="只读 (Read)" value="read" />
            <el-option label="写入 (Write)" value="write" />
            <el-option label="删除 (Delete)" value="delete" />
            <el-option label="重命名 (Rename)" value="rename" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPermissionDialog = false">取消</el-button>
        <el-button type="primary" @click="savePermission">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showFolderDialog" title="添加文件夹" width="500px">
      <el-form :model="folderForm" label-width="100px">
        <el-form-item label="物理路径">
          <el-input v-model="folderForm.path" placeholder="例如: D:\Photos" />
          <div class="form-tip">请输入服务器上的绝对路径</div>
        </el-form-item>
        <el-form-item label="显示名称">
          <el-input v-model="folderForm.name" placeholder="留空则使用文件夹名" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showFolderDialog = false">取消</el-button>
        <el-button type="primary" @click="saveFolder">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.admin-container {
  padding: 40px;
  max-width: 1200px;
  margin: 0 auto;
  min-height: 100vh;
  background: var(--bg-main);
  color: var(--text-primary);
}

.admin-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
}

.back-link {
  color: var(--primary);
  text-decoration: none;
}

.admin-tabs {
  background: var(--bg-card);
  padding: 20px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
}

.tab-content {
  padding: 20px 0;
}

.action-bar {
  margin-bottom: 20px;
  display: flex;
  justify-content: flex-start;
}

.form-tip {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}

.settings-form {
  max-width: 600px;
}

:deep(.el-tabs__item) {
  color: var(--text-secondary);
}

:deep(.el-tabs__item.is-active) {
  color: var(--primary);
}

:deep(.el-table) {
  background-color: transparent;
  color: var(--text-primary);
}

:deep(.el-table tr) {
  background-color: transparent;
}

:deep(.el-table th.el-table__cell) {
  background-color: var(--bg-card);
  color: var(--text-secondary);
}
</style>
