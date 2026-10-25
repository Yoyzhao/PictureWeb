# Windows 正式环境部署说明

本文档说明 PicGallery 在 Windows 环境下的生产部署流程。生产环境使用**独立部署副本**，不要直接用仓库开发配置运行生产。

## 1. 环境准备

- **Python 3.12**（本机为 `D:\Python\Python312\python.exe`；3.13 也可用，但项目依赖按 3.12 验证）
- **Node.js v18+ & npm**
- **PowerShell 7**
- **Servy**（注册 Windows 服务，当前生产使用）：https://github.com/aelassas/servy

### 1.1 配置加速镜像（推荐）

```powershell
pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/
pip config set global.trusted-host mirrors.aliyun.com
npm config set registry https://registry.npmmirror.com
```

## 2. 部署副本与目录

建议将代码部署到独立目录（本机现网为 `D:\Workspace\_deploy\PicGallery`），与开发仓库分离：

```
D:\Workspace\_deploy\PicGallery\
├── server\                 # Flask 后端 + server\venv
├── web\                    # 前端源码 + dist 构建产物
├── data\
│   ├── database.db         # 生产数据库
│   └── cache\              # 生产缩略图缓存（也可指向独立磁盘）
├── logs\                   # 生产日志
├── config.yaml             # 生产配置（端口 5000、生产库/缓存/回收站路径）
├── .env                    # 生产密钥与管理员初始账号（不提交 Git）
└── prod_run.py
```

## 3. 前端构建 (Web)

```powershell
cd web
npm install
npm run build
```

构建产物输出到 `web/dist`，由 Flask 直接托管。

## 4. 后端环境与依赖

```powershell
cd D:\Workspace\_deploy\PicGallery
py -3.12 -m venv server\venv
.\server\venv\Scripts\Activate.ps1
.\server\venv\Scripts\python.exe -m pip install --upgrade pip
.\server\venv\Scripts\python.exe -m pip install -r server\requirements.txt
```

依赖包含 `python-dotenv`、`itsdangerous`（Token 签名）与 `waitress`（生产 WSGI）。

## 5. 生产配置

### 5.1 `config.yaml`（非敏感配置）

```yaml
SERVER_PORT: 5000
DB_PATH: "data/database.db"
CACHE_DIR: "data/cache"
TRASH_DIR: "data/trash"
LOG_LEVEL: "WARNING"
ANONYMOUS_ACCESS: true
THUMBNAIL_QUALITY: 95
SCAN_RECURSIVE: true
SCAN_EXTENSIONS: ".jpg,.jpeg,.png,.gif,.bmp,.webp,.tiff"
ENABLE_PRELOAD: true
HOTKEYS:
  PREV: "ArrowLeft"
  NEXT: "ArrowRight"
  CLOSE: "Escape"
  FAVORITE: "f"
  DELETE: "Delete"
  ROTATE: "r"
  ZOOM_IN: "ArrowUp"
  ZOOM_OUT: "ArrowDown"
  RESET: "h"
```

> 仓库根目录的 `config.yaml` 是开发/测试配置（端口 5001、测试库 `data/db/database.db`），不得直接用于生产。

### 5.2 `.env`（密钥与管理员初始账号）

从 `.env.example` 复制并填写，**不要提交到 Git**：

```ini
APP_ENV=prd
SECRET_KEY=<生产独立随机密钥>
TOKEN_MAX_AGE_SECONDS=604800
DEFAULT_ADMIN_USERNAME=<管理员账号>
DEFAULT_ADMIN_PASSWORD=<强密码>
```

- `SECRET_KEY` 缺失时后端会拒绝启动；生产密钥必须与开发/测试不同
- 已有生产库不会被启动流程覆盖管理员密码；如需同步 `.env` 中的新密码，执行：
  ```powershell
  .\server\venv\Scripts\python.exe scripts\sql-script\init_db.py --reset-admin-password
  ```

## 6. 初始化数据库

```powershell
.\server\venv\Scripts\python.exe scripts\sql-script\init_db.py
```

## 7. 启动服务

### 7.1 手动运行（调试/临时）

```powershell
cd D:\Workspace\_deploy\PicGallery
.\server\venv\Scripts\python.exe prod_run.py
```

服务监听 `http://0.0.0.0:5000`，由 Waitress 托管。

### 7.2 作为 Windows 服务运行（Servy，生产使用）

生产环境使用 [Servy](https://github.com/aelassas/servy) 注册 Windows 服务，服务配置文件为仓库内 `docs/deploy/picweb.json`（服务名 `PictureWeb`）。

#### 7.2.1 安装 Servy

任选一种方式安装，并确保 `servy-cli` 已加入系统 PATH：

```powershell
winget install servy
# 或
choco install -y servy
# 或
scoop bucket add extras; scoop install servy
```

后续命令需在**管理员 PowerShell**中执行。

#### 7.2.2 配置文件关键字段

`docs/deploy/picweb.json` 当前配置：

| 字段 | 值 | 说明 |
|------|----|------|
| `Name` / `DisplayName` | `PictureWeb` | 服务名与显示名 |
| `ExecutablePath` | `D:\Workspace\_deploy\PicGallery\server\venv\Scripts\python.exe` | 生产 venv |
| `StartupDirectory` | `D:\Workspace\_deploy\PicGallery` | 工作目录 |
| `Parameters` | `D:\Workspace\_deploy\PicGallery\prod_run.py` | Waitress 入口 |
| `StartupType` | `2` | Automatic（随系统启动） |
| `Priority` | `2` | Normal |
| `StdoutPath` / `StderrPath` | `logs\app.log` / `logs\err.log` | 应用输出日志 |
| `EnableDateRotation` / `DateRotationType` / `MaxRotations` | `true` / `0` / `100` | 按日轮转，保留 100 份 |
| `EnableConsoleUI` | `false` | 后台运行并重定向 stdout/stderr |
| `EnableHealthMonitoring` | `false` | 当前未启用健康检查；`RecoveryAction` 仅在启用后生效 |

> 配置文件只包含路径与运行参数，不包含 `SECRET_KEY`、数据库密码等敏感信息；密钥仍由部署根目录 `.env` 提供。

#### 7.2.3 首次安装

```powershell
servy-cli import --config="json" --path="D:\Workspace\PicGallery\docs\deploy\picweb.json" --install
servy-cli status --name="PictureWeb"
servy-cli start --name="PictureWeb"
```

安装后可用 Windows 服务管理器确认 `PictureWeb` 的启动类型为“自动”。

#### 7.2.4 更新代码或服务配置

```powershell
servy-cli stop --name="PictureWeb"
# 部署新代码与 web/dist，按需修改 picweb.json
servy-cli import --config="json" --path="D:\Workspace\PicGallery\docs\deploy\picweb.json" --install
servy-cli start --name="PictureWeb"
servy-cli status --name="PictureWeb"
```

> 若当前 Servy 版本对已存在服务拒绝重复导入，先执行 `servy-cli uninstall --name="PictureWeb"`（仅移除服务注册，不删除应用数据），再重新 `import --install`。

#### 7.2.5 常用命令

| 操作 | 命令 |
|------|------|
| 查看状态 | `servy-cli status --name="PictureWeb"` |
| 启动/停止/重启 | `servy-cli start/stop/restart --name="PictureWeb"` |
| 查看服务配置 | `servy-cli show --name="PictureWeb"` |
| 列出服务 | `servy-cli show` |
| 导出配置 | `servy-cli export --name="PictureWeb" --config="json" --path="D:\Workspace\_deploy\PicGallery\picweb-export.json"` |
| 卸载服务 | `servy-cli uninstall --name="PictureWeb"` |

- 服务日志：`D:\Workspace\_deploy\PicGallery\logs\app.log` 与 `err.log`，按日轮转，最多 100 份。
- 默认以 LocalSystem 运行，需保证对部署目录、`F:\_PicCache` 与 `logs\` 有读写权限。
- 如需进程崩溃自动重启，可在 `picweb.json` 中启用 `EnableHealthMonitoring` 并设置 `RecoveryAction`，重新导入后重启服务。
- 首次启动仍会在生产库创建 FTS5 索引（约 20,993 行），请预留启动时间。

## 8. 维护与备份

- **数据库备份**：定期备份 `data\database.db`
- **升级注意**：升级到含索引优化与 FTS5 搜索的版本时，首次启动会在现有库上执行 `CREATE INDEX`、创建 `images_fts` 并重建索引；10 万级数据可能耗时较久，建议升级前先备份数据库并预留启动时间
- **缩略图补齐**：生产首次升级后可分批执行 `.\server\venv\Scripts\python.exe scripts\sql-script\prebuild_thumbnails.py --limit 500`，避免一次性占用过多 CPU
- **搜索索引维护**：如搜索异常，可执行 `init_db.py --rebuild-search-index` 重建 FTS5 索引
- **缓存清理**：可安全删除 `data\cache` 内容，系统按需重新生成
- **日志**：查看部署副本 `logs\` 目录；`app.log` / `err.log` 由 Servy 按日轮转，保留 100 份
- **配置变更**：修改 `config.yaml` 后重启服务；修改 `.env` 后必须重启（密钥在启动时加载）

## 9. 常见问题

- **启动报 `SECRET_KEY is not configured`**：部署目录缺少 `.env` 或未填写 `SECRET_KEY`
- **端口冲突**：修改生产 `config.yaml` 的 `SERVER_PORT`；先确认占用进程归属，不要终止无关进程
- **登录后立即失效**：`SECRET_KEY` 变更会使旧 Token 失效，重新登录即可（前端会自动清理失效凭证）
- **路径问题**：`DB_PATH`、`CACHE_DIR`、`TRASH_DIR` 可使用相对部署根目录的路径或 Windows 绝对路径
- **权限不足**：扫描与删除操作需要文件系统读写权限；建议以具备权限的账号运行服务

## 10. 本次部署记录（2026-10-24 22:36）

- **目标目录**：`D:\Workspace\_deploy\PicGallery`；服务已由用户停止，本次未启动。
- **部署内容**：`server/app`、`scripts/sql-script`、`web/dist`、`prod_run.py`、`server/run.py`、`server/requirements.txt`、`.env.example`。
- **保持不变**：生产 `config.yaml`、`data/database.db`、`data/` 其余数据、`F:\_PicCache`、`logs/`、`server/venv` 原有包；部署前后 `config.yaml` 与数据库 SHA256 一致。
- **生产配置**：`DB_PATH=D:\Workspace\_deploy\PicGallery\data\database.db`、`CACHE_DIR=F:\_PicCache`、`TRASH_DIR=F:\_PicCache\trash`、`SERVER_PORT=5000`。
- **生产 `.env`**：本次新建，含随机 `SECRET_KEY`；现有数据库管理员密码未重置，`.env` 中的 `DEFAULT_ADMIN_PASSWORD` 仅在新建库或执行 `--reset-admin-password` 时生效。
- **依赖**：生产 venv 为 Python 3.13.13，已安装 `python-dotenv==1.0.1`、`waitress==3.0.1`；`py_compile` 通过。
- **服务方式**：Servy，配置文件 `docs/deploy/picweb.json`（服务名 `PictureWeb`）；本次仅部署产物，未安装/启动服务。
- **烟测**：使用生产数据库副本临时启动 Flask test client，`/api/health`、`/api/settings`、`/api/images` 均 200；FTS5 在副本上成功创建（20,993 条），未改动生产库。
- **首次启动说明**：启动时会在生产库创建 FTS5 虚拟表/触发器并重建索引（20,993 行），可能耗时数秒；建议观察 `logs/`。
- **备份**：数据库 `data\backups\database-20261024-222640.db`；旧代码与旧 dist `D:\Workspace\_deploy\_backup_PicGallery_20261024-222640`。

## 11. 本次部署记录（2026-10-25 02:00）

- **目标目录**：`D:\Workspace\_deploy\PicGallery`；更新前 `PictureWeb` 服务已停止，更新完成后已启动并处于 Running。
- **部署内容**：`server/app`（11 个文件，含新增 `routes/bookmarks.py` 与本轮文件夹生命周期修复）、`scripts/sql-script`（3 个文件）、`web/dist`（30 个文件）、`prod_run.py`、`server/run.py`、`server/requirements.txt`、`.env.example`。源文件与部署副本逐文件 SHA256 一致。
- **保持不变**：生产 `config.yaml`、`.env`、`data/database.db`、`data/` 其余数据、`F:\_PicCache`、`logs/`、`server/venv`；同步前后 `config.yaml` 与数据库 SHA256 未变。
- **备份**：数据库 `data\backups\database-20261025-015336.db`（SHA256 `DAFB17D6EAC63E4B676F277EFBCCD6884E078729DD7474D4CBE01EDC6A6EC3A7`）；旧代码、旧 dist、旧入口与配置备份在 `D:\Workspace\_deploy\_backup_PicGallery_20261025-015336`。
- **依赖**：生产 venv 为 Python 3.13.13；`pip check` 无冲突，未新增依赖。
- **迁移验证**：先用生产库副本以新代码干跑，`image_bookmarks` 表创建成功，公开文件夹与图片接口正常，库内 5 文件夹/20,991 图片/204 收藏/69 回收站记录保持不变。
- **服务启动**：Windows 服务 `PictureWeb`（Servy 托管，LocalSystem）启动成功，监听 `0.0.0.0:5000`；`logs/app.log` 无新错误，`err.log` 无新增。
- **生产库结果**：`image_bookmarks` 表已创建；FTS docsize 20,991 与图片数一致；扫描状态均为 `completed`。
- **烟测**：`/api/health` 200、`/api/settings` 200、匿名 `/api/folders` 返回公开文件夹 `BG`、匿名 `/api/images` 返回 43 张公开图片、首页 `index.html` 引用新构建资源 `index-Da-Lftjn.js` / `index-Bl2zFTq.css`；匿名 `/api/bookmarks` 返回 401。
- **登录说明**：生产 `.env` 中的管理员密码与现有生产库密码不一致，使用 `.env` 密码登录返回 401（既有状态，非本次部署引入）；如需同步，需用户确认后执行 `init_db.py --reset-admin-password`。
- **注意**：`web/dist` 中保留了旧哈希静态资源，当前 `index.html` 仅引用新资源，不影响访问，可在下次部署时清理。

## 12. 本次部署记录（2026-10-25 13:05，M4 视频支持）

- **目标目录**：`D:\Workspace\_deploy\PicGallery`；更新前 `PictureWeb` 服务已处于 Stopped，更新后仍为 Stopped（当前终端无管理员权限，无法启动服务）。
- **部署内容**：
  - `server/app` 全量镜像（含新增 `services/video.py`、媒体字段迁移、`routes/image.py`、`routes/bookmarks.py`）。
  - `scripts/sql-script` 全量镜像（含 `prune_cache.py`、`remux_videos.py`、`prebuild_thumbnails.py --media`）。
  - `web/dist` 覆盖（新入口 `index-BS9mEKpn.js`、`index-8FPCqn8E.css`、`Lightbox-CpPVIcyn.js`）。
  - `prod_run.py`、`server/run.py`、`server/requirements.txt`、`.env.example`。
  - 生产 `config.yaml` 追加 `SCAN_VIDEO_EXTENSIONS`、`FFMPEG_PATH`、`FFPROBE_PATH`、`VIDEO_THUMBNAIL_PREGENERATE`、`VIDEO_THUMBNAIL_TIMEOUT`、`VIDEO_PROBE_TIMEOUT`（`D:/FFmpeg` 已确认存在）。
  - 关键文件源与副本 SHA256 一致：`video.py`、`image.py`、`thumbnail.py`、`remux_videos.py`、`prune_cache.py`。
- **保持不变**：生产 `.env`、`data/database.db` 数据内容（仅启动迁移新增字段）、`data/` 其余数据、`F:\_PicCache`、`logs/`、`server/venv`。
- **备份**：数据库 `data\backups\database-20261025-125858.db`（SHA256 `EF9A6390429EF6260E57CF45CD4FA05B3E6A734219B97C2249253C7351C5DA3E`）；旧代码、旧 dist、旧入口、旧脚本与配置在 `D:\Workspace\_deploy\_backup_PicGallery_20261025-125858`。
- **迁移验证**：以生产 venv 手动启动 `prod_run.py` 完成迁移，`images` 新增 `media_type/duration/video_codec/audio_codec`，`image_bookmarks` 新增 `media_filter`，自动书签唯一索引含 `media_filter`。
- **生产库结果**：5 文件夹、20,991 图片、204 收藏、69 回收站、2 书签、FTS docsize 20,991，均与部署前一致；`videos=0`（生产库尚无视频目录）。
- **烟测**：`/api/health` 200、`/api/settings` 200、匿名 `/api/folders` 返回 `BG`、匿名 `/api/images` total=43、`/api/images?media_type=video` total=0、首页引用新构建资源；启动日志无 FFmpeg 缺失警告。
- **服务状态**：验证用进程已停止，5000 端口已释放；`PictureWeb` 仍为 Stopped。需以管理员执行 `servy-cli start --name="PictureWeb"` 或 `Start-Service PictureWeb` 启动。
- **登录说明**：生产 `.env` 管理员密码与库内密码不一致的既有问题未处理。
- **注意**：`web/dist` 保留旧哈希资源，当前 `index.html` 只引用新资源。

## 13. 本次部署记录（2026-10-25 13:35，Bug-007/Bug-008 修复）

- **目标目录**：`D:\Workspace\_deploy\PicGallery`；更新前 `PictureWeb` 为 Stopped，更新后仍为 Stopped（当前终端无管理员权限）。
- **部署内容**：
  - `server/app` 全量镜像（含自动书签单条化：`utils/db.py`、`routes/bookmarks.py`）。
  - `web/dist` 覆盖（新入口 `index-BdRnK-ZH.js`、`index-4A3lJOzW.css`），包含网格工具栏容器查询与视频播放 UI。
  - `scripts/sql-script` 与 `config.yaml` 未再改动。
  - 源与副本 `db.py`、`bookmarks.py` SHA256 一致。
- **保持不变**：生产 `.env`、`data/` 其余数据、`F:\_PicCache`、`logs/`、`server/venv`。
- **备份**：数据库 `data\backups\database-20261025-133238.db`（SHA256 `9667B1DD47B2736DE7EF226C3E07CEF97A751685B35A80CED8696CC22E4A5F2E`）；旧代码与旧 dist 在 `D:\Workspace\_deploy\_backup_PicGallery_20261025-133238`。
- **迁移验证**：手动启动生产副本完成迁移，自动书签由 6 条合并为 1 条；索引变为 `idx_image_bookmarks_auto ON image_bookmarks(user_id) WHERE kind='auto'`；手动书签 0 条。
- **生产库现状**：6 文件夹、26,072 媒体记录（其中 118 个视频）、1 条自动书签；匿名可见图片 43。
- **视频烟测**：视频 raw 返回 `206`、`video/mp4`、`no-store`；封面返回 `200 image/webp`；视频封面记录 124 条。
- **服务状态**：验证进程已停止，5000 端口释放；需管理员执行 `servy-cli start --name="PictureWeb"` 或 `Start-Service PictureWeb`。
- **注意**：生产视频多为 HEVC（手机拍摄），浏览器通常不能直接播放，会进入错误层并提供本地播放器入口；离线 `remux_videos.py` 只处理 H.264，HEVC 需真转码或继续用 VLC。

## 14. 本次部署记录（2026-10-25 13:52，Bug-009 缩略图兜底）

- **目标目录**：`D:\Workspace\_deploy\PicGallery`；`PictureWeb` 更新前后均为 Stopped（终端无管理员权限）。
- **部署内容**：`web/dist` 更新为 `index-DYLv407X.js` / `index-wO6HYiUM.css`，包含网格、回收站、书签抽屉缩略图的一次性 `retry=1` 兜底；`server/app` 全量镜像（与上次一致，无后端变更）。
- **备份**：数据库 `data\backups\database-20261025-134929.db`（SHA256 `176893DAB76B0F2DE19BBDD7324D71BFB82E205F620EF46361DE6A2A93FFF6F3`）；旧 dist 与旧代码在 `D:\Workspace\_deploy\_backup_PicGallery_20261025-134929`。
- **迁移**：无表结构变更；自动书签仍为 1 条。
- **烟测**：`/api/health` 200、`/api/settings` 200、匿名图片 43、首页引用新资源；缩略图带 `&retry=1` 返回 `200 image/jpeg`、`public, max-age=86400`、`Content-Length` 正常。
- **服务状态**：验证进程已停止，5000 端口释放；需管理员执行 `servy-cli start --name="PictureWeb"` 或 `Start-Service PictureWeb`。
- **说明**：`ERR_CACHE_READ_FAILURE` 属客户端 Chrome 磁盘缓存损坏；除代码兜底外，用户首次访问建议硬刷新或清理“缓存的图片和文件”。

## 15. 本次部署记录（2026-10-25 14:11，Bug-010 视频灯箱控件避让）

- **目标目录**：`D:\Workspace\_deploy\PicGallery`；用户先以管理员手动停止 `PictureWeb`，当前终端无管理员权限。
- **部署内容**：仅更新 `web/dist`（`robocopy /MIR`），新产物 `index-j4ZioCTR.js`（SHA256 `B56CAD9C…389512`）、`index-wO6HYiUM.css`、`Lightbox-zrt9_P_O.js`（`0C4043EF…1B0A3`）、`Lightbox-DGkoUbau.css`（`3D3BCC6A…374BF`）；清理 70 个旧版本资源文件；后端代码与数据库无变更。
- **备份**：旧 dist 备份至 `D:\Workspace\_deploy\_backup_PicGallery_20261025-1411\web-dist`；数据库备份 `data\backups\database-20261025-1411.db`（SHA256 `AAF2822FC968E9557F20EDB2411A1F0222C575B777AF55B12AD7CD40D65EE537`）。
- **迁移**：无表结构变更，未执行迁移。
- **烟测**（手动启动 `prod_run.py`）：`/api/health` 200、`/api/settings` 200、匿名图片 43；首页引用 `index-j4ZioCTR.js` 与 `index-wO6HYiUM.css`；Lightbox chunk 含 `meta-open` 标记；旧资源 `index-DYLv407X.js` 返回 404（已清理）。
- **服务状态**：验证进程已停止，5000 端口已释放，`PictureWeb` 为 Stopped；需管理员执行 `Start-Service PictureWeb` 恢复生产服务。
- **说明**：本次只修复视频灯箱底部控制条遮挡原生进度条（`meta-open` 动态预留 + 续播按钮并入控制条），无后端与数据变更。
