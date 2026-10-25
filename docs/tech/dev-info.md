# 开发环境信息

> 作用：让 Agent 在进入架构、实现、联调、测试、部署前，先通过本文件快速理解项目技术栈、版本、运行方式、端口、数据库和环境变量边界。
>
> 约束：只写非敏感信息；真实密码、密钥、Token 通过 `.env`（未跟踪）或平台密钥服务注入。所有含真实凭证的本地文件不得入库。
>
> 建档依据：2026-10-24 对 `web/package.json`、`server/requirements.txt`、`server/app/`、`web/src/`、根 `config.yaml`、`prod_run.py`、生产部署副本 `D:\Workspace\_deploy\PicGallery\` 与 Git 历史的实测核对；同日完成 Python 3.12 虚拟环境重建、测试/生产库分离、鉴权改造与目录整理。

## 1. 技术栈说明

| 维度 | 内容 | 备注 |
|------|------|------|
| 项目形态 | 分离式源码（`server/` + `web/`），生产由 Flask 托管 `web/dist` 一体化运行 | 开发期前端 Vite 代理 `/api` 到后端 |
| 前端/全栈框架 | Vue 3（Composition API + `<script setup>`）+ Vite 7 + TypeScript | 入口 `web/src/main.ts` |
| 后端实现 | Python 3.12 + Flask 3（Blueprint 分模块） | 开发入口 `server/run.py`；生产入口根 `prod_run.py` |
| UI 方案 | Element Plus 2.13 + Tailwind CSS 3.4 + 自定义 CSS Variables + MiSans 字体 | 图标同时使用 `@element-plus/icons-vue` 与 `lucide-vue-next` |
| 数据库类型 | 关系型：SQLite3 单文件 | 开发/测试库与生产库物理分离 |
| 数据访问 | Python 标准库 `sqlite3` + 手写 SQL（参数绑定） | 无 ORM、无迁移框架；`server/app/utils/db.py` 内做启动建表与轻量迁移 |
| 鉴权方案 | `itsdangerous` 签名 Token（`SECRET_KEY` 来自 `.env`，默认有效期 7 天） | 不再使用 `token-{id}` 或 `admin-token` 等硬编码 Token |
| 配置管理 | `config.yaml`（非敏感运行配置）+ `.env`（密钥与管理员初始账号） | `python-dotenv` 加载；真实值不入库 |
| 测试方案 | 无自动化测试；前端 `vue-tsc` 类型检查，后端 `py_compile` + Flask test client 冒烟 | 浏览器验证可用 Chrome DevTools MCP / Browser Use |
| 部署形态 | Windows 主机 + Waitress + Servy（Windows 服务） | 生产副本独立部署，见第 5 节 |

## 2. 版本信息

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | 3.12.7（`D:\Python\Python312\python.exe`） | `D:\Python` 下同时存在 3.12.7 与 3.13.13（`Python313`）；`server/venv` 于 2026-10-24 使用 3.12.7 重建，依赖全部安装成功 |
| Node.js | v24.9.0 | 本机实测 |
| 包管理器 | npm 11.19.0（前端）；pip 26.2.2（后端 venv） | 仓库有 `package-lock.json`，后端仅 `requirements.txt` |
| 前端框架 | Vue ^3.4.15 + Vite ^7.3.1 + TypeScript ~5.3.3 | 依赖锁定见 `web/package-lock.json` |
| 后端框架 | Flask 3.0.0 + Flask-Cors 4.0.0 | Werkzeug 3.1.9、Jinja2 3.1.6 |
| 数据库 | SQLite3（随 Python 内置） | 测试库 `data/db/database.db` |
| 图片处理 | Pillow 12.2.0 | 缩略图生成 |
| 视频处理 | FFmpeg / ffprobe N-124437（`D:\FFmpeg`） | M4 视频封面与元数据；生产服务需在 `config.yaml` 配置绝对路径 |
| 安全/配置库 | itsdangerous 2.2.0、python-dotenv 1.0.1 | Token 签名与 `.env` 加载 |
| 文件监听 | watchdog 6.0.0（已列入依赖，当前代码未接入文件监听） | 扫描由手动/新增文件夹触发 |

## 3. 目录与入口

| 项目部分 | 路径 | 备注 |
|----------|------|------|
| 前端目录 | `web/` | 源码 `web/src/`，构建产物 `web/dist/` |
| 前端页面 | `web/src/pages/` | `HomePage.vue`、`AdminPage.vue`、`TrashPage.vue` |
| 前端路由 | `web/src/router/index.ts` | 仅 `/` 与 `/about`；管理页与回收站是 HomePage 内视图状态，不是独立路由 |
| 前端组件 | `web/src/components/` | `Sidebar.vue`、`TopBar.vue`、`ImageGrid.vue`、`Lightbox.vue`、`ImageInfoDialog.vue`、`BookmarksDrawer.vue`、`common/VirtualWaterfall.vue` |
| 状态管理 | `web/src/stores/` | Pinia：`auth`、`folder`、`image`、`bookmark`、`hotkey`、`ui` |
| API 封装 | `web/src/api/index.ts` | axios 实例，`baseURL=/api`，注入 Bearer Token；401 时清理失效凭证 |
| 后端目录 | `server/app/` | Flask 应用包 |
| 后端路由 | `server/app/routes/` | `auth.py`、`folder.py`、`image.py`、`bookmarks.py`、`admin.py`、`settings.py` |
| 后端服务 | `server/app/services/` | `scanner.py`（扫描）、`thumbnail.py`（缩略图） |
| 数据模型 | `server/app/models/schema.sql` | 10 张业务表：users/folders/images/user_favorites/tags/image_tags/thumbnails/permissions/trash/image_bookmarks |
| 数据访问 | `server/app/utils/db.py` | 连接管理、`init_db()`、`migrate_db()`、管理员/访客初始化、`reset_admin_password()` |
| 测试数据库 | `data/db/database.db` | 开发/测试专用；生产库在部署副本 |
| 缩略图/回收站 | `data/cache/`、`data/trash/` | 本地开发专用；生产使用部署副本配置 |
| 日志目录 | `data/app_logs/` | 本地运行日志；生产日志在部署副本 `logs/` |
| 数据库脚本 | `scripts/sql-script/` | `init_db.py`、`normalize_db.py` |
| 部署脚本 | `scripts/deploy-script/` | `deploy_windows.ps1` |
| 历史原型 | `docs/prototype/` | 早期静态 HTML/CSS/JS，仅作历史参考，不参与构建 |
| 配置示例 | `config.example.yaml`、`.env.example` | 不含真实凭证 |
| 文档 | `docs/` | `prd/`、`tech/`、`plan/`、`deploy/`、`rules/`、`prototype/` |

### 3.1 后端模块与 API 前缀（实测）

| 模块 | 文件 | 前缀 | 主要能力 |
|------|------|------|----------|
| 认证 | `routes/auth.py` | `/api/auth` | `POST /login`、`GET /me`；签名 Token，管理员凭据来自 `.env` |
| 文件夹 | `routes/folder.py` | `/api/folders` | 列表（按角色过滤）、新增并异步扫描、PATCH、删除（可选硬删除到回收站）、重新扫描 |
| 图片 | `routes/image.py` | `/api/images` | 分页列表（keyset cursor/next_cursor、FTS5 搜索）、锚点窗口（书签恢复/定位）、详情、重命名、收藏切换、缩略图/原图/下载、批量移动/删除、回收站列表/缩略图/恢复/清空 |
| 书签 | `routes/bookmarks.py` | `/api/bookmarks` | 手动书签 CRUD、自动进度 upsert、按锚点恢复视图窗口；锚点缺失时按保存的排序键兜底 |
| 管理 | `routes/admin.py` | `/api/admin` | 全模块管理员校验；缓存统计/清理、用户 CRUD、文件夹列表/删除、权限 CRUD、系统设置读写 |
| 公开设置 | `routes/settings.py` | `/api/settings` | 匿名可读；仅返回 `HOTKEYS` 与 `ENABLE_PRELOAD`，供前端快捷键/预加载使用 |
| 健康检查 | `app/__init__.py` | `/api/health` | 返回 `{"status":"ok"}` |

> 架构文档第 4 节已按当前实现更新；独立 `docs/tech/api-contract.md` 尚未建立，涉及复杂接口的迭代前按需补建。

## 4. 启动与构建命令

| 场景 | 命令 | 备注 |
|------|------|------|
| 创建虚拟环境 | `py -3.12 -m venv server\venv` | 固定在 `server/venv`，不提交 Git |
| 安装后端依赖 | `.\server\venv\Scripts\python.exe -m pip install -r server\requirements.txt` | 2026-10-24 已安装成功 |
| 前端开发 | `cd web; npm install; npm run dev` | Vite 默认 `5173`，`/api` 代理到 `http://127.0.0.1:5001` |
| 前端类型检查 | `cd web; npm run check` | `vue-tsc -b`，2026-10-24 通过 |
| 前端构建 | `cd web; npm run build` | 输出 `web/dist`，2026-10-24 通过 |
| 后端开发 | `.\server\venv\Scripts\python.exe server\run.py` | 读取根 `config.yaml`，端口 5001 |
| 后端语法检查 | `python -m py_compile server\run.py prod_run.py` + 遍历 `server\app` 下全部 `.py` | 2026-10-24 通过 |
| 数据库初始化 | `.\server\venv\Scripts\python.exe scripts\sql-script\init_db.py` | 建表并按 `.env` 创建管理员/访客（已有管理员不覆盖密码） |
| 重置管理员密码 | `.\server\venv\Scripts\python.exe scripts\sql-script\init_db.py --reset-admin-password` | 将 `.env` 的 `DEFAULT_ADMIN_PASSWORD` 同步到数据库 |
| 时间字段规范化 | `.\server\venv\Scripts\python.exe scripts\sql-script\normalize_db.py` | 历史脚本，会把时间字段中的 `T` 替换为空格 |
| 重建搜索索引 | `.\server\venv\Scripts\python.exe scripts\sql-script\init_db.py --rebuild-search-index` | 重建 FTS5 `images_fts`；FTS5 不可用时搜索回退 LIKE |
| 缩略图预生成 | `.\server\venv\Scripts\python.exe scripts\sql-script\prebuild_thumbnails.py --limit 500 [--folder ID]` | 分批补齐缺失的 small 缩略图；全库执行耗 CPU，建议低峰分批 |
| 生产运行 | 部署副本内 `python prod_run.py` | Waitress，读取部署副本 `config.yaml` 与 `.env`，端口 5000 |
| 自动化测试 | 无 | 仓库无 pytest / vitest / playwright 配置 |
| 浏览器验证 | Chrome DevTools MCP 或 Browser Use | 开发入口 `http://localhost:5173`，生产入口 `http://127.0.0.1:5000` |

## 5. 端口与访问地址

| 服务 | 本地地址 | 端口 | 备注 |
|------|---------|------|------|
| 生产应用（Flask + Waitress） | `http://0.0.0.0:5000` | 5000 | 部署副本 `D:\Workspace\_deploy\PicGallery`，使用生产库 `data\database.db`；2026-10-25 02:00 更新并运行 |
| 开发后端（Flask dev server） | `http://127.0.0.1:5001` | 5001 | 仓库根 `config.yaml`，使用测试库；当前为开发验证运行中 |
| 前端开发（Vite） | `http://localhost:5173` | 5173 | Vite 默认值，`/api` 代理到 5001 |
| 数据库 | 本地文件 | - | 无网络端口 |
| 缓存/回收站 | `data/cache`、`data/trash` | - | 本地开发目录，已被 Git 忽略 |

## 6. 数据库与中间件

| 组件 | 版本 | 连接方式/备注 |
|------|------|---------------|
| 主数据库（测试） | SQLite3 | `data/db/database.db`；4 个文件夹、21,159 条图片记录、3 个用户（2026-10-25 实测） |
| 主数据库（生产） | SQLite3 | 部署副本 `D:\Workspace\_deploy\PicGallery\data\database.db`；不得用于测试写入 |
| 缓存 | 无独立缓存服务 | 缩略图文件缓存 + 浏览器端预加载 |
| 对象存储 | 无 | 直接读写本地文件系统 |
| 消息队列 | 无 | 扫描任务使用 Python 线程（`Thread`） |
| 文件监听 | watchdog 6.0.0 | 已安装未使用 |

## 7. 环境变量清单

非敏感运行配置来自根目录 `config.yaml`（生产副本为部署目录下同名文件）；密钥与管理员初始账号来自 `.env`（生产副本需单独创建，不提交 Git）。

| 变量名 | 作用 | 配置来源（不记录取值） | 是否敏感 |
|--------|------|----------|----------|
| `APP_ENV` | 运行环境标识（dev/prd） | `.env` | 否 |
| `SECRET_KEY` | 登录 Token 与 Flask 会话签名密钥，缺失时应用拒绝启动 | `.env` / 平台密钥服务 | 是 |
| `TOKEN_MAX_AGE_SECONDS` | 登录 Token 有效期（秒），默认 604800 | `.env` | 否 |
| `DEFAULT_ADMIN_USERNAME` | 初始化/重置管理员账号 | `.env` | 否（账号名） |
| `DEFAULT_ADMIN_PASSWORD` | 初始化/重置管理员密码 | `.env` / 平台密钥服务 | 是 |
| `SERVER_PORT` | 后端监听端口 | `config.yaml` | 否 |
| `DB_PATH` | SQLite 数据库文件路径 | `config.yaml` | 否 |
| `CACHE_DIR` | 缩略图缓存目录 | `config.yaml` | 否 |
| `TRASH_DIR` | 应用内回收站目录 | `config.yaml` | 否 |
| `LOG_LEVEL` | 日志级别 | `config.yaml` | 否 |
| `ANONYMOUS_ACCESS` | 是否允许匿名访问公开文件夹 | `config.yaml` | 否 |
| `THUMBNAIL_FORMAT` | 缩略图输出格式（`webp`/`jpeg`），存量 jpg 缓存仍可读取 | `config.yaml` | 否 |
| `THUMBNAIL_QUALITY` | 缩略图质量 | `config.yaml` | 否 |
| `THUMBNAIL_PREGENERATE` | 扫描完成后是否后台预生成小尺寸缩略图 | `config.yaml` | 否 |
| `SCAN_RECURSIVE` | 是否递归扫描 | `config.yaml` | 否 |
| `SCAN_EXTENSIONS` | 扫描的图片后缀 | `config.yaml` | 否 |
| `SCAN_VIDEO_EXTENSIONS` | 扫描的视频后缀（M4 规划，未实现） | `config.yaml` | 否 |
| `FFMPEG_PATH` | FFmpeg 可执行文件路径（M4 规划，未实现） | `config.yaml` | 否 |
| `FFPROBE_PATH` | ffprobe 可执行文件路径（M4 规划，未实现） | `config.yaml` | 否 |
| `VIDEO_THUMBNAIL_PREGENERATE` | 扫描后是否后台预生成视频封面（M4 规划，未实现） | `config.yaml` | 否 |
| `VIDEO_THUMBNAIL_TIMEOUT` | 视频抽帧超时秒数（M4 规划，未实现） | `config.yaml` | 否 |
| `ENABLE_PRELOAD` | Lightbox 预加载开关 | `config.yaml` | 否 |
| `HOTKEYS.*` | 图片浏览快捷键映射 | `config.yaml` | 否 |

- `.env` 已被 `.gitignore` 忽略，只有 `.env.example` 入库
- 已有数据库不会因启动而覆盖管理员密码；修改 `.env` 的 `DEFAULT_ADMIN_PASSWORD` 后必须执行 `init_db.py --reset-admin-password` 才会生效（2026-10-24 曾出现未同步导致 401，已于同日 13:07 同步并复验登录 200）
- `GET /api/admin/settings` 只返回 `config.yaml` 内容，不返回 `.env` 密钥

## 8. 测试账号与测试数据

| 项目 | 内容 | 备注 |
|------|------|------|
| 测试账号 | 管理员账号见 `.env` 的 `DEFAULT_ADMIN_USERNAME`；另有 `user`、`guest` | 真实密码只存在于 `.env`，不写入仓库 |
| 测试数据准备 | 通过侧边栏“添加文件夹”或 `POST /api/folders` 触发后台扫描 | 需传入本机存在的绝对路径 |
| 本地数据快照 | `data/db/database.db`：4 个文件夹、23,851 张图片记录、3 个用户（2026-10-24 实测） | 仅本地，已被 `.gitignore` 忽略 |
| 生产数据 | 部署副本数据库 | 不得用于测试写入 |
| 自动化验证入口 | 无测试套件；使用 `npm run check` + `py_compile` + Flask test client / 浏览器冒烟 | |

## 9. Agent 使用约定

- 若不了解系统架构或运行方式，先读取本文件，再按需读取 `PictureWeb技术架构文档.md`
- 前端渲染性能、虚拟列表与 10 万级优化方案见 `docs/tech/features/frontend-performance-前端渲染性能与UI优化.md`
- 本文件与代码冲突时，以代码与实测为准，并同步修正本文件
- 每次技术栈、版本、端口、数据库、配置键或鉴权方案发生变化时同步更新本文件
- 禁止在未授权情况下读写生产部署目录或生产数据库；本地验证使用测试库与只读接口
- 禁止在源码、文档、脚本或日志中写入真实 `SECRET_KEY`、管理员密码或 Token

## 10. Skill 使用记录

| 事项 | 内容 | 备注 |
|------|------|------|
| 创建时 Skill | fullstack-general | 对应 `SKILL.md` 的 `name` |
| 创建时版本 | general-1.20.1 | 对应 `metadata.version` |
| 最近接续 Skill | fullstack-general | 2026-10-24 |
| 最近接续版本 | general-1.20.1 | |
| 切换记录 | 2026-10-24：原生项目开发（无 Skill 文档体系）-> fullstack-general general-1.20.1 | 首次纳入本 Skill 流程，只做基线建档，未重写历史文档 |

## 11. AI Coding 工具链环境

| 维度 | 内容 | 备注 |
|------|------|------|
| 操作系统 | Windows 11 | 本机开发与生产部署同机 |
| 终端工具 | PowerShell 7+ | 默认终端；命令需兼容 PowerShell 语法 |
| 命令行工具 | `python` 3.12.7 / 3.13.13、`node` v24.9.0、`npm` 11.19.0、`git` 2.55.0、`rg` 15.0.0 | 两个 Python 均安装在 `D:\Python`；项目 venv 使用 3.12.7 |
| 可用插件 | 浏览器控制（内置浏览器/外部 Chrome）、电脑控制、office-plugin、ppt-generator、prd-authoring、web-app-development、deep-research-assistant、html-report-presentation、record-and-replay | 按任务选用 |
| 可用 Skill | `fullstack-general`（general-1.20.1，本项目主流程）、`TRAE-browseruse`、`webapp-testing`、`TRAE-debugger`、`TRAE-code-review`、`TRAE-security-review` 等 | |
| MCP 服务 | Chrome DevTools MCP（页面/网络/性能调试）、Knowledge Graph Memory（知识图谱记忆）、Record & Replay（操作录制） | |
| 其他 Agent 能力 | 浏览器自动化、桌面 UI 操作、图片/视频生成 | 无 GPU 相关探测 |

### 常用命令行工具

| 工具 | 是否可用 | 版本 | 用途 |
|------|---------|------|------|
| `rg`（ripgrep） | 是 | 15.0.0 | 全文内容检索 |
| `git` | 是 | 2.55.0 | 版本控制 |
| `python` | 是 | 3.12.7 / 3.13.13 | 后端运行、脚本、数据库检查（项目 venv 用 3.12.7） |
| `node` | 是 | v24.9.0 | 前端构建与开发服务器 |
| `npm` | 是 | 11.19.0 | 前端依赖与脚本 |
| `ffmpeg` | 是 | N-124437 | 视频抽帧/转封装（M4） |
| `ffprobe` | 是 | N-124437 | 视频元数据探测（M4） |
| `fd` | 未探测到 | - | 文件名/路径检索（可用 `Get-ChildItem` 或 Glob 替代） |
| `jq` | 未探测到 | - | JSON 处理（可用 PowerShell `ConvertFrom-Json` 替代） |

### 缺失与安装建议

| 缺失工具 | 影响 | 建议动作 | 用户确认 |
|----------|------|----------|----------|
| pytest / 前端测试框架 | 无自动化回归能力 | 下一轮功能开发前按需引入；当前以类型检查 + 接口冒烟 + 浏览器验证替代 | 待确认 |
| ESLint 配置 | `npm run lint` 脚本无对应配置文件，实际不可用 | 按需补 ESLint 配置或移除脚本；当前以 `vue-tsc` 为准 | 待确认 |

## 12. 时区策略

| 层面 | 口径 | 备注 |
|------|------|------|
| 应用运行时区 | `Asia/Shanghai`（UTC+8，Windows 本地时区） | `datetime.fromtimestamp()` 使用本地时区 |
| 数据库存储 | 混用：`created_at/updated_at/deleted_at` 由 SQLite `CURRENT_TIMESTAMP` 生成（UTC）；`modified_time` 由 Python 本地时间写入（UTC+8） | 已知不一致，见第 13 节风险 |
| 接口传输 | naive ISO 8601 字符串（无时区偏移） | `datetime.isoformat()` 输出，前端按字符串展示 |
| 日志记录 | `Asia/Shanghai` | 本地 `data/app_logs/`，生产部署副本 `logs/` |
| 界面展示 | 浏览器本地时区，按后端字符串直接展示 | 无统一格式化工具 |
| 定时任务与统计 | 无定时任务 | 扫描为一次性后台线程 |

- 新增时间相关功能前，先统一口径（建议数据库与接口统一 UTC 或统一 UTC+8 带偏移），并同步更新本表
- 其余未单独说明的文档时间记录默认使用 `Asia/Shanghai`

## 13. 已知环境风险（2026-10-24 核对）

1. **生产副本已部署新版本（2026-10-24 22:36），服务未启动**：`D:\Workspace\_deploy\PicGallery` 已同步 `server/app`、`scripts/sql-script`、`web/dist`、`prod_run.py`，生产 `config.yaml`（`DB_PATH=data/database.db`、`CACHE_DIR=F:\_PicCache`、`TRASH_DIR=F:\_PicCache\trash`）与 `data/database.db` 未改动。已创建生产 `.env`（随机 `SECRET_KEY`；现有库管理员密码未重置，`.env` 中生成密码仅用于新建库或后续 `--reset-admin-password`）。生产 venv 为 Python 3.13.13，已安装 `python-dotenv==1.0.1`、`waitress==3.0.1`；首次启动会在生产库（20,993 张图片）上创建 FTS5 索引。部署前备份：`data\backups\database-20261024-222640.db` 与 `D:\Workspace\_deploy\_backup_PicGallery_20261024-222640`。
2. **Token 存在 localStorage**：签名 Token 无法被伪造，但仍受 XSS 影响；前端已改为 401 时自动清理失效凭证，后续可评估迁移到 httpOnly Cookie。
3. **图片读取接口未做权限校验**：`/api/images/<id>/raw`、`/thumbnail`、`/download` 等目前不校验登录与文件夹权限，已知历史问题；对外暴露前需补服务端权限校验。
4. **CORS 允许所有来源**：当前 `CORS(app)` 未限制 Origin；生产应按可信来源收紧。
5. **访客账号无密码**：`guest` 登录为匿名只读设计，仅在 `ANONYMOUS_ACCESS` 开启时存在；不得赋予其编辑权限。
6. **无自动化测试、无 ESLint 配置**：回归依赖人工，质量门控能力不足。
7. **独立 API 契约文档尚未建立**：`PictureWeb技术架构文档.md` 第 4 节已按当前代码更新；`docs/tech/api-contract.md` 尚未单独维护，复杂接口迭代前按需补建。
8. **时间字段口径混用**：SQLite `CURRENT_TIMESTAMP` 为 UTC、`modified_time` 为本地时间；排序、统计、跨时区展示可能偏差。
9. **FFmpeg 路径在服务环境可能不可见**：开发终端可调用 `D:\FFmpeg\ffmpeg.exe`；生产 Windows 服务账号的 PATH 可能不同。M4 需在 `config.yaml` 配置 `FFMPEG_PATH`/`FFPROBE_PATH` 绝对路径，并在启动时检查。
10. **移动端外部播放器深链依赖客户端环境**：Android `intent://` 需要 Chromium 内核浏览器与已安装 VLC；iOS `vlc-x-callback://` 需要 VLC 且版本支持。深链失败时必须回退“复制播放地址”，并在真机验证前不宣称通过。
11. **客户端视频缓存边界**：浏览器视频正文缓存可通过 `Cache-Control: no-store` 抑制，Web 应用不生成视频副本；外部播放器自身的缓冲/缓存由播放器管理，无法由本项目清理。
