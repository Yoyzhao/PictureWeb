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
- **后端**: Python 3.12, Flask, SQLite3, Pillow (图片处理), Waitress (生产 WSGI).
- **鉴权**: `itsdangerous` 签名 Token，密钥来自未跟踪的 `.env`。
- **样式**: CSS Variables, Tailwind-like utility classes.

## 🚀 快速开始

### 前提条件

- Node.js v18+
- Python 3.12（本机 `D:\Python\Python312`；`D:\Python\Python313` 也可用，但项目 venv 使用 3.12）

### 本地配置

1. 复制环境变量示例并填写密钥与管理员初始账号：
   ```powershell
   Copy-Item .env.example .env
   ```
   `.env` 已被 Git 忽略，请勿提交真实 `SECRET_KEY` 与密码。
2. 如需调整端口/路径，修改根目录 `config.yaml`（默认开发端口 5001，测试库 `data/db/database.db`）。

### 后端启动 (Server)

1. 创建虚拟环境（首次或环境重建时）：
   ```powershell
   py -3.12 -m venv server\venv
   ```
2. 安装依赖：
   ```powershell
   .\server\venv\Scripts\python.exe -m pip install -r server\requirements.txt
   ```
3. 初始化数据库（首次运行；已有管理员密码不会被覆盖）：
   ```powershell
   .\server\venv\Scripts\python.exe scripts\sql-script\init_db.py
   ```
   *修改 `.env` 的 `DEFAULT_ADMIN_PASSWORD` 后，执行同脚本并追加 `--reset-admin-password` 才会同步到已有数据库。*
4. 启动服务：
   ```powershell
   .\server\venv\Scripts\python.exe server\run.py
   ```
   *端口由项目根目录 `config.yaml` 的 `SERVER_PORT` 决定（当前开发配置为 `5001`）*

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
   *默认运行在 `http://localhost:5173`，`/api` 请求代理到 `http://127.0.0.1:5001`*

### 生产运行

生产使用独立部署副本（不要直接用仓库开发配置跑生产）：

1. 在部署副本中创建独立的 `config.yaml` 与 `.env`（生产库、缓存目录、端口 5000、独立 `SECRET_KEY` 与管理员密码）。
2. 构建前端并启动 Waitress：
   ```powershell
   cd web
   npm run build
   cd ..
   python prod_run.py
   ```

## 📁 项目结构

- `server/`: Flask 后端逻辑、数据库操作及图片处理服务；虚拟环境在 `server/venv/`。
- `web/`: Vue 3 前端源代码、组件及状态管理，构建产物输出到 `web/dist/`。
- `docs/`: 需求、技术架构、开发计划、项目规则、部署文档与历史原型。
- `scripts/deploy-script/`: Windows 部署脚本。
- `scripts/sql-script/`: 数据库初始化与时间字段规范化脚本。
- `data/`: 本地运行数据（`db/`、`cache/`、`trash/`、`app_logs/`），已被 Git 忽略。
- `config.yaml`: 非敏感运行配置（端口、数据库、缓存、回收站、缩略图质量、快捷键）。
- `config.example.yaml`: 配置示例。
- `.env.example`: 密钥与管理员初始账号示例；真实 `.env` 不入库。
- `prod_run.py`: 生产启动入口（Waitress）。

> 技术栈、版本、端口、目录入口与配置项的权威记录见 [`docs/tech/dev-info.md`](docs/tech/dev-info.md)。

## 📝 使用建议

- 建议在添加文件夹时使用**绝对路径**以确保扫描稳定性。
- 大量图片扫描时，系统会在后台异步生成缩略图，初次加载可能稍有延迟；扫描完成后还会后台预生成 small 缩略图。
- 维护命令：
  - 重建文件名搜索索引：`.\server\venv\Scripts\python.exe scripts\sql-script\init_db.py --rebuild-search-index`
  - 分批补齐缩略图：`.\server\venv\Scripts\python.exe scripts\sql-script\prebuild_thumbnails.py --limit 500`
