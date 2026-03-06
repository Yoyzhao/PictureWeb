# PicGallery - 个人智能相册管理系统

PicGallery 是一个轻量级、响应式的个人相册管理系统。它支持本地文件夹扫描、瀑布流展示、图片预览及基础编辑功能，旨在为用户提供流畅的图片浏览与管理体验。

## 🌟 主要功能

- **本地文件夹扫描**: 支持添加多个本地绝对路径，自动递归扫描图片并生成缩略图。
- **瀑布流展示**: 响应式布局，支持根据窗口宽度自动调整列数。
- **深度预览 (Lightbox)**:
  - 鼠标滚轮缩放、键盘上下键缩放。
  - 图片顺时针 90 度旋转。
  - 支持上一张/下一张快速切换。
  - 自动隐藏/显示控制栏。
- **图片管理**: 支持批量移动、批量删除（应用内回收站）、下载原图、查看详细元数据。
- **收藏夹**: 一键收藏心仪图片，支持仅查看收藏内容。
- **后台管理**: 管理扫描目录、用户权限以及查看扫描统计结果。

## 🛠️ 技术栈

- **前端**: Vue 3 (Composition API), Vite, TypeScript, Pinia, Element Plus, Axios.
- **后端**: Python, Flask, SQLite3, Pillow (图片处理).
- **样式**: CSS Variables, Tailwind-like utility classes.

## 🚀 快速开始

### 前提条件

- Node.js (建议 v16+)
- Python (建议 3.8+)

### 后端启动 (Server)

1. 进入后端目录:
   ```bash
   cd server
   ```
2. 安装依赖:
   ```bash
   pip install -r requirements.txt
   ```
3. 启动服务:
   ```bash
   python run.py
   ```
   *默认运行在 `http://localhost:5000`*

### 前端启动 (Web)

1. 进入前端目录:
   ```bash
   cd web
   ```
2. 安装依赖:
   ```bash
   npm install
   ```
3. 启动开发服务器:
   ```bash
   npm run dev
   ```
   *默认运行在 `http://localhost:5173`*

## 📁 项目结构

- `server/`: Flask 后端逻辑、数据库操作及图片处理服务。
- `web/`: Vue 3 前端源代码、组件及状态管理。
- `data/`: (运行时生成) 存储数据库文件及缩略图缓存。

## 📝 使用建议

- 建议在添加文件夹时使用**绝对路径**以确保扫描稳定性。
- 大量图片扫描时，系统会在后台异步生成缩略图，初次加载可能稍有延迟。
