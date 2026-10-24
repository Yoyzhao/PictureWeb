import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { ElLoading } from 'element-plus'
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'
import 'element-plus/es/components/loading/style/css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import './style.css'
import App from './App.vue'
import router from './router'

// 创建Vue应用实例
const app = createApp(App)

// v-loading 指令（组件样式由 ElementPlusResolver 按需引入）
app.directive('loading', ElLoading.directive)

// 使用插件
app.use(createPinia())
app.use(router)

// 挂载应用
app.mount('#app')
