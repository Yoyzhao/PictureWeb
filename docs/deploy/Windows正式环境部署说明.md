# Windows 正式环境部署说明

本文档说明 PicGallery 在 Windows 环境下的生产部署流程。生产环境使用**独立部署副本**，不要直接用仓库开发配置运行生产。

## 1. 环境准备

- **Python 3.12**（本机为 `D:\Python\Python312\python.exe`；3.13 也可用，但项目依赖按 3.12 验证）
- **Node.js v18+ & npm**
- **PowerShell 7**
- 可选：**NSSM**（注册 Windows 服务）

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

### 7.1 直接运行（推荐）

```powershell
cd D:\Workspace\_deploy\PicGallery
python prod_run.py
```

服务监听 `http://0.0.0.0:5000`，由 Waitress 托管。

### 7.2 作为 Windows 服务运行

1. 下载 NSSM：https://nssm.cc/download
2. 安装服务：
   ```powershell
   nssm install PicGallery
   ```
3. 配置：
   - **Path**: `D:\Workspace\_deploy\PicGallery\server\venv\Scripts\python.exe`
   - **Startup directory**: `D:\Workspace\_deploy\PicGallery`
   - **Arguments**: `prod_run.py`

## 8. 维护与备份

- **数据库备份**：定期备份 `data\database.db`
- **升级注意**：升级到含索引优化的版本时，首次启动会在现有库上执行 `CREATE INDEX IF NOT EXISTS`；10 万级数据可能耗时较久，建议升级前先备份数据库
- **缓存清理**：可安全删除 `data\cache` 内容，系统按需重新生成
- **日志**：查看部署副本 `logs\` 目录；日志按启动时间滚动
- **配置变更**：修改 `config.yaml` 后重启服务；修改 `.env` 后必须重启（密钥在启动时加载）

## 9. 常见问题

- **启动报 `SECRET_KEY is not configured`**：部署目录缺少 `.env` 或未填写 `SECRET_KEY`
- **端口冲突**：修改生产 `config.yaml` 的 `SERVER_PORT`；先确认占用进程归属，不要终止无关进程
- **登录后立即失效**：`SECRET_KEY` 变更会使旧 Token 失效，重新登录即可（前端会自动清理失效凭证）
- **路径问题**：`DB_PATH`、`CACHE_DIR`、`TRASH_DIR` 可使用相对部署根目录的路径或 Windows 绝对路径
- **权限不足**：扫描与删除操作需要文件系统读写权限；建议以具备权限的账号运行服务
