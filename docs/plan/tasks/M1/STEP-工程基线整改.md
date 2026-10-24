# M1 / 工程基线整改 — 阶段任务文档

- **里程碑**：M1 工程基线整改
- **阶段**：配置、鉴权与目录整理（5D + 工程整理）
- **状态**：已完成，待用户验收
- **关联 CHG**：`CHG-20261024-01`（`docs/tech/功能变更.md`）
- **更新日期**：2026-10-24

## 任务索引

| 任务ID | 名称 | 状态 | 负责人 | 主要产出 |
|--------|------|------|--------|----------|
| T-002 | 重建后端虚拟环境 | 已完成 | main | `server/venv`（Python 3.12.7）、依赖安装 |
| T-003 | 测试库与生产库分离 | 已完成 | main | `config.yaml`、`data/db`、`data/cache`、`data/trash` |
| T-004 | 鉴权与管理员凭证外置 | 已完成 | main | `.env`、`.env.example`、签名 Token、管理员重置脚本 |
| T-005 | 物理目录整理与引用更新 | 已完成 | main | `docs/prototype/`、`scripts/sql-script/`、`scripts/deploy-script/`、`config.example.yaml` |
| T-006 | 文档与基线同步 | 已完成 | main | `dev-info.md`、`project-rules.md`、`project-progress.md`、架构文档、README、部署文档 |
| T-007 | 同步本地测试库管理员密码并复验 | 已完成 | main | 测试库密码按 `.env` 重置，登录/me/管理员设置 200、旧 Token 401 |

## T-002 重建后端虚拟环境

- **问题**：旧 `server/venv` 的 `pyvenv.cfg` 指向 `D:\Python\python.exe`，该路径已不存在；`venv\Scripts\python.exe` 无法启动。
- **实施**：使用 `py -3.12 -m venv --clear server\venv` 重建；升级 pip；按 `server/requirements.txt` 安装依赖。
- **结果**：`Python 3.12.7`，pip 26.2.2，已安装 Flask 3.0.0、Flask-Cors 4.0.0、PyYAML 6.0.1、watchdog 6.0.0、Pillow 12.2.0、waitress 3.0.1、python-dotenv 1.0.1、itsdangerous 2.2.0 及其依赖。
- **说明**：`D:\Python` 下同时存在 `Python312`（3.12.7）与 `Python313`（3.13.13），本项目选择 3.12.7 以匹配既有固定版本依赖。

## T-003 测试库与生产库分离

- **原行为**：仓库根 `config.yaml` 的 `DB_PATH` 指向生产部署库，`CACHE_DIR`/`TRASH_DIR` 指向生产缓存目录；本地启动会直接操作生产数据。
- **实施**：
  - 测试库移动到 `data/db/database.db`；
  - 仓库 `config.yaml` 改为 `DB_PATH: data/db/database.db`、`CACHE_DIR: data/cache`、`TRASH_DIR: data/trash`，端口保持 5001；
  - 新建 `data/cache/`、`data/trash/`、`data/app_logs/`；
  - 生产副本 `D:\Workspace\_deploy\PicGallery\config.yaml` 保持原值（生产库、`F:\_PicCache`、端口 5000），未改动。
- **验证**：`create_app()` 输出的 `DB_PATH/CACHE_DIR/TRASH_DIR` 均落在仓库 `data/`；测试库仍为 4 个文件夹、23,851 条图片、3 个用户。

## T-004 鉴权与管理员凭证外置

- **原行为**：Token 为 `token-{id}`，并保留 `admin-token`/`guest-token` 硬编码分支；管理员初始密码 `admin123` 写在 `server/app/utils/db.py`；登录弹窗直接提示账号密码。
- **实施**：
  - `server/app/__init__.py`：加载根 `.env`；`SECRET_KEY` 缺失时拒绝启动；读取 `TOKEN_MAX_AGE_SECONDS`、`DEFAULT_ADMIN_USERNAME`、`DEFAULT_ADMIN_PASSWORD`。
  - `server/app/routes/auth.py`：改用 `itsdangerous.URLSafeTimedSerializer` 签名 Token（salt `picgallery-auth-token`，默认 7 天）；移除全部硬编码 Token 分支；登录请求体缺失时返回 400。
  - `server/app/utils/db.py`：管理员初始账号/密码来自 `.env`；访客账号独立初始化；新增 `reset_admin_password()`。
  - `scripts/sql-script/init_db.py`：新增 `--reset-admin-password`，将 `.env` 密码同步到已有库。
  - `server/app/routes/admin.py` + `web/src/pages/AdminPage.vue`：删除用户保护改为“配置的管理员 + guest + 最后一个管理员”，不再按硬编码用户名 `admin` 判断。
  - `web/src/components/Sidebar.vue`：移除登录弹窗中的 `admin / admin123` 提示。
  - `web/src/api/index.ts` + `web/src/stores/auth.ts`：401 时清理失效 Token（排除登录接口），并重置 Pinia 登录状态。
- **验证**（Flask test client）：
  - 管理员登录 200，Token 长度 47 且不以 `token-` 开头；
  - `/api/auth/me` 200；旧 `token-1` 401；Token 追加字符 401；错误密码 401；空请求体 400；
  - `/api/admin/settings` 200，响应不含 `SECRET_KEY`；
  - 匿名 `/api/folders` 200；`/api/images` 200。

## T-005 物理目录整理与引用更新

- **移动**：
  - `prototype/` → `docs/prototype/`
  - `scripts/deploy/` → `scripts/deploy-script/`
  - `server/init_db.py`、`server/normalize_db.py` → `scripts/sql-script/`
  - `server/config.example.yaml` → 根 `config.example.yaml`
  - `data/database.db` → `data/db/database.db`
  - 空 `logs/` → `data/app_logs/`
- **引用更新**：
  - `scripts/sql-script/init_db.py` 重新计算项目根并加入 `server` 到 `sys.path`；
  - `scripts/sql-script/normalize_db.py` 改为按项目根解析 `config.yaml` 与相对 `DB_PATH`；
  - `scripts/deploy-script/deploy_windows.ps1` 更新 venv、配置、数据目录与 `.env` 检查；
  - `config.example.yaml` 更新为开发/测试路径，并注明生产使用独立配置；
  - `.gitignore` 新增 `.env`/`.env.*` 与 `*.pyc`，保留 `.env.example`。
- **验证**：后端启动、数据库初始化脚本、前端构建均在新路径下通过；无代码引用旧路径。

## T-006 文档与基线同步

- 更新：`docs/tech/dev-info.md`、`docs/rules/project-rules.md`、`docs/plan/project-progress.md`、`docs/plan/project-dev-plan.md`、`docs/tech/PictureWeb技术架构文档.md`、`docs/deploy/Windows正式环境部署说明.md`、`README.md`、`.trae/rules/project-rules.md`。
- 新增：`docs/tech/功能变更.md`、本阶段文档、`.env.example`。
- 未改动：生产部署副本任何文件。

## T-007 密码同步与复验（2026-10-24 12:59 发现，13:07 解决）

- **现象**：12:59 巡检时，使用当前 `.env` 的 `DEFAULT_ADMIN_USERNAME` / `DEFAULT_ADMIN_PASSWORD` 调用 `POST /api/auth/login` 返回 401。
- **原因**：`.env` 的管理员密码已被用户修改，但本地测试库仍是 12:44 按旧 `.env` 重置的密码；启动流程不会覆盖已有管理员密码。
- **处理**：用户确认后执行
  `.\server\venv\Scripts\python.exe scripts\sql-script\init_db.py --reset-admin-password`。
- **复验（13:07）**：登录 200、`/api/auth/me` 200、`/api/admin/settings` 200、旧 `token-1` 401、`/api/health` 200。
- **边界**：仅操作本地测试库；生产库未改动。

## 验证汇总

| 验证项 | 方法 | 结果 |
|--------|------|------|
| 虚拟环境 | `server\venv\Scripts\python.exe --version` + 导入依赖 | Python 3.12.7，依赖导入成功 |
| 数据库初始化/管理员重置 | `scripts/sql-script/init_db.py --reset-admin-password` | 成功，admin 角色为 admin |
| 认证与权限（12:44） | Flask test client 冒烟 | 登录/me/管理员设置 200；旧/篡改 Token 401；错误密码 401；空请求体 400 |
| 认证与权限（12:59 复检） | 使用当前 `.env` 管理员密码登录 | 401（测试库密码未同步，已由 T-007 处理） |
| 认证与权限（13:07 复验） | 密码同步后 Flask test client | 登录 200、me 200、管理员设置 200、旧 Token 401、health 200 |
| 管理员删除保护 | `DELETE /api/admin/users/1`（当前配置管理员） | 400，`Cannot delete system users` |
| 开发服务启动 | `server\run.py` → `http://127.0.0.1:5001/api/health` | 200，验证后已停止并释放端口 |
| 前端类型检查 | `cd web; npm run check` | 通过（最终前端改动后复跑，见交付记录） |
| 前端构建 | `cd web; npm run build` | 通过（最终前端改动后复跑，见交付记录） |
| 生产不受影响 | `http://127.0.0.1:5000/api/health` | 200，生产进程与配置未改动 |
| 测试数据完整性 | SQLite 计数 | 4 folders / 23,851 images / 3 users |

## 遗留与后续

1. 生产副本仍运行旧版本；按用户要求暂缓，待开发完成后统一同步代码、安装依赖、创建生产 `.env` 并重置生产管理员密码。
2. 图片读取接口（raw/thumbnail/download）尚未做服务端权限校验；对外暴露前需补。
3. CORS 仍允许所有来源；生产前应收紧。
4. 无自动化测试与 ESLint 配置；按需在后续迭代补齐。
5. 时间字段口径仍混用（SQLite UTC 与本地时间）。
