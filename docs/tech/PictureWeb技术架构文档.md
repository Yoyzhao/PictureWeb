# PictureWeb 技术架构文档

## 1. 架构设计

```mermaid
graph TD
    A[用户浏览器] --> B[Vue3 前端应用]
    B --> C[Flask 后端服务]
    C --> D[SQLite 数据库]
    C --> E[文件系统]
    C --> F[缩略图缓存]
    C --> G[.env / config.yaml]
    
    subgraph "前端层"
        B
    end
    
    subgraph "后端服务层"
        C
    end
    
    subgraph "数据存储层"
        D
        F
    end
    
    subgraph "配置与密钥"
        G
    end

    subgraph "文件存储层"
        E
    end
```

## 2. 技术栈描述

- **前端**: Vue3 + Vite7 + Element Plus
- **初始化工具**: Vite
- **后端**: Python 3.12 + Flask 3（生产 Waitress）
- **数据库**: SQLite3
- **鉴权与配置**: `itsdangerous` 签名 Token（`SECRET_KEY` 来自未跟踪的 `.env`）；`python-dotenv` 加载 `.env`；`config.yaml` 只存非敏感运行配置
- **部署模式**: 非前后端分离，Flask托管静态资源

## 3. 路由定义

| 路由 | 用途 |
|------|------|
| / | 主页，显示图片瀑布流 |
| /about | 占位页面 |
| /login | 登录弹窗（非独立路由，由 Sidebar 控制） |
| /admin | 管理员面板（HomePage 内视图状态，非独立路由） |
| /api/* | API接口前缀 |

## 4. API接口定义

### 4.0 通用约定

- 基础前缀：`/api`
- 鉴权：`Authorization: Bearer <token>`；Token 由 `itsdangerous` 签名，`SECRET_KEY` 来自 `.env`，默认有效期 7 天
- 响应：JSON；错误统一为 `{"error": "..."}`，由 HTTP 状态码表达结果
- 分页：`page`（默认 1，最小 1）、`per_page`（默认 50，范围 1–200）
- 匿名访问：公开文件夹的读取接口允许无 Token；写操作和管理员接口要求登录
- 当前未实现独立的标签 CRUD 路由；标签表与关联表已存在，但接口能力有限

### 4.1 认证（`/api/auth`）

#### POST `/api/auth/login`

请求参数:
| 参数名 | 参数类型 | 是否必需 | 描述 |
|--------|----------|----------|------|
| username | string | 是 | 用户名 |
| password | string | 是 | 密码 |

响应参数:
| 参数名 | 参数类型 | 描述 |
|--------|----------|------|
| token | string | 签名 Token（`itsdangerous`，默认 7 天有效期，密钥来自 `.env`） |
| user | object | 用户信息对象 |
| user.id | integer | 用户 ID |
| user.username | string | 用户名 |
| user.role | string | 用户角色（admin / user / guest） |

#### GET `/api/auth/me`

- 权限：登录
- 响应：`{"user": {"id", "username", "role"}}`
- Token 缺失、被篡改或过期返回 401

### 4.2 文件夹管理（`/api/folders`）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/api/folders` | 可选登录 | 管理员返回全部；登录用户返回自己的文件夹、公开文件夹以及拥有任一权限的文件夹；匿名仅返回公开文件夹 |
| POST | `/api/folders` | 登录（非 guest） | 添加文件夹并触发后台异步扫描；参数 `path`、可选 `name`、`is_public`。路径必须为存在的绝对目录，入库前统一 `normpath`；重复路径（忽略大小写/分隔符/尾部分隔符）或与已有文件夹互为父子目录返回 409 |
| PATCH | `/api/folders/<id>` | 管理员 | 更新 `name`、`path`、`is_public`；修改物理路径时校验重复/嵌套，重置扫描状态并自动重扫；`pending/scanning` 时拒绝路径修改 |
| DELETE | `/api/folders/<id>?hard=false` | 管理员 | 删除文件夹索引；`hard=true` 时先把物理目录移动到应用回收站，并拒绝文件系统根目录及包含项目/数据库/缓存/回收站目录的路径；同时显式清理收藏、标签、缩略图记录与缓存文件、文件夹书签与权限；`pending/scanning` 时返回 409 |
| POST | `/api/folders/<id>/scan` | 管理员、文件夹所有者或 `write` 权限 | 手动触发重新扫描；以条件更新原子抢占，`pending/scanning` 返回 409 |

文件夹对象包含 `scan_status`（none/pending/scanning/completed/failed）、`scan_total`、`scan_processed`、`scan_error`。扫描线程在内存中运行，服务启动时会把遗留的 `pending/scanning` 重置为 `failed`，避免永久占用扫描状态。

### 4.3 图片管理（`/api/images`）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/api/images` | 可选登录 | 分页列表；非管理员仅返回自己的文件夹、公开文件夹或拥有任一权限的文件夹中的图片；`is_favorite=true` 对匿名用户返回空集；支持 `folder_id`、`is_favorite`、`q`、`sort_by`、`sort_order`、`cursor` |
| GET | `/api/images/window` | 可选登录 | 按 `anchor_id` 返回前后窗口（keyset，`before`≤100、`after`≤200），用于书签恢复与定位；锚点不在当前视图时可用 `fallback_value` 按保存的排序键定位最近位置；返回 `anchor.window_index/found/fallback` |
| GET | `/api/images/<id>` | 可选登录 | 图片详情，附带当前用户收藏状态；需要该文件夹的读取权限（公开文件夹允许匿名） |
| PATCH | `/api/images/<id>` | 登录（非 guest）+ `rename` 权限 | 重命名（仅 `file_name`，禁止通过该接口改 `folder_id`）；文件名必须是纯文件名 |
| POST | `/api/images/<id>/favorite` | 登录（非 guest）+ 读取权限 | 切换当前用户收藏状态 |
| GET | `/api/images/<id>/thumbnail?size=small\|medium` | 公开 | 读取缩略图（按需生成并缓存） |
| GET | `/api/images/<id>/raw` | 公开 | 读取原图 |
| GET | `/api/images/<id>/download` | 公开 | 以附件形式下载原图 |
| POST | `/api/images/batch/move` | 登录（非 guest）+ 源/目标 `write` 权限 | 批量移动；目标目录必须存在；同名自动加后缀；返回 `moved_ids` 与逐项 `errors` |
| POST | `/api/images/batch/delete` | 登录（非 guest）+ `delete` 权限 | 批量移动到回收站并记录元数据；返回 `deleted_ids`、`trashed`、`missing_ids`、`errors`；文件缺失时只删除索引 |

> 已知安全缺口：`raw`、`thumbnail`、`download` 当前未校验登录与文件夹权限，对外暴露前需补齐。
>
> 分页：首次请求不传 `cursor`，响应返回 `next_cursor`；后续将 `next_cursor` 作为 `cursor` 传入。游标为 base64(JSON)，绑定 `sort_by`/`sort_order`，与当前排序不一致返回 400。`total` 为完整筛选总数，不受游标边界影响。

### 4.4 回收站（`/api/images/trash`）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/api/images/trash/items` | 登录 | 管理员查看全部；普通用户仅查看自己的回收站记录 |
| GET | `/api/images/trash/<id>/thumbnail` | 登录（所有者/管理员） | 读取回收站文件缩略图 |
| POST | `/api/images/trash/restore` | 登录（所有者/管理员）+ 原文件夹 `write` 权限 | 批量恢复；原文件夹不存在或无权限时保留在回收站并返回错误；恢复后重新插入图片、收藏与标签，返回 `restored_ids` |
| POST | `/api/images/trash/clear` | 登录（所有者/管理员） | 彻底删除指定记录；`trash_ids` 为空时清空当前用户回收站；返回 `deleted_ids` |

### 4.5 管理接口（`/api/admin`）

所有 `/api/admin/*` 接口在 Blueprint `before_request` 中要求 `admin` 角色。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/cache/stats` | 缓存目录大小与路径 |
| POST | `/api/admin/cache/clear` | 清空缩略图缓存与 `thumbnails` 表 |
| GET / POST | `/api/admin/users` | 用户列表 / 新增用户 |
| PATCH / DELETE | `/api/admin/users/<id>` | 修改角色或密码 / 删除用户（保护配置管理员、guest 与最后一个管理员） |
| GET | `/api/admin/folders` | 全部文件夹 |
| DELETE | `/api/admin/folders/<id>` | 删除文件夹及其图片索引（不移动物理目录）；与 `/api/folders/<id>` 共用清理逻辑，缩略图记录/缓存、收藏、标签、文件夹书签与权限均会清理 |
| GET / POST | `/api/admin/permissions` | 权限列表 / 批量新增权限 |
| DELETE | `/api/admin/permissions/<id>` | 删除权限 |
| GET / POST | `/api/admin/settings` | 读取 / 更新 `config.yaml`（不包含 `.env` 密钥） |

### 4.6 健康检查

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/api/health` | 公开 | 返回 `{"status": "ok"}` |

### 4.7 客户端公开设置

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/api/settings` | 公开 | 只返回 `HOTKEYS` 与 `ENABLE_PRELOAD`；不暴露 `.env` 或管理员配置 |

### 4.8 浏览位置书签（`/api/bookmarks`）

书签保存“锚点图片 + 视图上下文（文件夹/收藏/搜索/排序）”，不保存页码或滚动偏移。

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/api/bookmarks` | 登录 | 当前用户的书签；自动进度排在手动书签前，最多 200 条 |
| POST | `/api/bookmarks` | 登录（非 guest） | 创建手动书签；校验锚点图片读取权限、文件夹与收藏视图一致性；同一用户/视图/锚点已存在时返回已有记录；服务端快照锚点排序键 |
| POST | `/api/bookmarks/auto` | 登录（非 guest） | 按 `(folder_id, is_favorites, search_query)` upsert 自动进度，更新排序与锚点 |
| PATCH | `/api/bookmarks/<id>` | 登录（所有者） | 重命名书签 |
| DELETE | `/api/bookmarks/<id>` | 登录（所有者） | 删除书签 |
| GET | `/api/bookmarks/<id>/restore` | 登录（所有者） | 返回视图上下文、锚点窗口（`before`≤100、`after`≤200）与 `next_cursor`；锚点被删除/移出视图时返回 `anchor.fallback=true` 并定位最近位置 |

## 5. 服务器架构图

```mermaid
graph TD
    A[客户端请求] --> B[Flask路由层]
    B --> C[认证中间件]
    C --> D[业务逻辑层]
    D --> E[数据访问层]
    E --> F[SQLite数据库]
    D --> G[文件系统操作]
    
    subgraph "Flask应用"
        B
        C
        D
        E
    end
```

## 6. 数据模型

### 6.1 数据模型定义

```mermaid
erDiagram
    USERS ||--o{ FOLDERS : owns
    USERS ||--o{ USER_FAVORITES : favorites
    IMAGES ||--o{ USER_FAVORITES : favorited
    FOLDERS ||--o{ IMAGES : contains
    IMAGES ||--o{ IMAGE_TAGS : tagged
    TAGS ||--o{ IMAGE_TAGS : applies
    IMAGES ||--o{ THUMBNAILS : has
    USERS ||--o{ PERMISSIONS : granted
    FOLDERS ||--o{ PERMISSIONS : scoped
    USERS ||--o{ TRASH : deletes
    USERS ||--o{ IMAGE_BOOKMARKS : bookmarks

    USERS {
        integer id PK
        string username UK
        string password_hash
        string role
        datetime created_at
        datetime updated_at
    }

    FOLDERS {
        integer id PK
        string path UK
        string name
        integer user_id FK
        boolean is_public
        string scan_status
        integer scan_total
        integer scan_processed
        string scan_error
        datetime created_at
        datetime updated_at
    }

    IMAGES {
        integer id PK
        string file_path UK
        string file_name
        integer file_size
        datetime modified_time
        integer width
        integer height
        string format
        integer folder_id FK
        datetime created_at
        datetime updated_at
    }

    USER_FAVORITES {
        integer user_id PK
        integer image_id PK
        datetime created_at
    }

    TAGS {
        integer id PK
        string name UK
        datetime created_at
    }

    IMAGE_TAGS {
        integer image_id PK
        integer tag_id PK
        datetime created_at
    }

    THUMBNAILS {
        integer id PK
        integer image_id FK
        string size_type
        string file_path
        datetime created_at
    }

    PERMISSIONS {
        integer id PK
        integer user_id FK
        integer folder_id FK
        string permission_type
        datetime created_at
    }

    TRASH {
        integer id PK
        integer image_id
        string original_path
        string trash_path
        string file_name
        integer user_id FK
        text metadata
        datetime deleted_at
    }

    IMAGE_BOOKMARKS {
        integer id PK
        integer user_id FK
        string kind
        string name
        integer folder_id
        boolean is_favorites
        string search_query
        string sort_by
        string sort_order
        integer anchor_image_id
        string anchor_modified_time
        string anchor_file_name
        integer anchor_file_size
        datetime created_at
        datetime updated_at
    }
```

### 6.2 数据定义语言

> 以下结构与 `server/app/models/schema.sql` 保持一致；实际建表语句使用 `CREATE TABLE IF NOT EXISTS`，并包含对应索引。另由 `db.ensure_fts()` 创建 `images_fts` FTS5 trigram 虚拟表及增删改同步触发器，用于文件名搜索。

#### 用户表 (users)
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'user' CHECK (role IN ('admin', 'user', 'guest')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_username ON users(username);
```

#### 文件夹表 (folders)
```sql
CREATE TABLE folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    user_id INTEGER,
    is_public BOOLEAN DEFAULT FALSE,
    scan_status VARCHAR(20) DEFAULT 'none' CHECK (scan_status IN ('none', 'pending', 'scanning', 'completed', 'failed')),
    scan_total INTEGER DEFAULT 0,
    scan_processed INTEGER DEFAULT 0,
    scan_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_folders_path ON folders(path);
CREATE INDEX idx_folders_user_id ON folders(user_id);
```

#### 图片表 (images)
```sql
CREATE TABLE images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT UNIQUE NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_size INTEGER,
    modified_time TIMESTAMP,
    width INTEGER,
    height INTEGER,
    format VARCHAR(10),
    folder_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (folder_id) REFERENCES folders(id)
);

CREATE INDEX idx_images_file_path ON images(file_path);
CREATE INDEX idx_images_folder_id ON images(folder_id);
CREATE INDEX idx_images_modified_time ON images(modified_time);
```

#### 用户收藏表 (user_favorites)
```sql
CREATE TABLE user_favorites (
    user_id INTEGER NOT NULL,
    image_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, image_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
);

CREATE INDEX idx_user_favorites_user_id ON user_favorites(user_id);
CREATE INDEX idx_user_favorites_image_id ON user_favorites(image_id);
```

#### 标签表 (tags)
```sql
CREATE TABLE tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(50) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 图片标签关联表 (image_tags)
```sql
CREATE TABLE image_tags (
    image_id INTEGER,
    tag_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (image_id, tag_id),
    FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);
```

#### 缩略图表 (thumbnails)
```sql
CREATE TABLE thumbnails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id INTEGER NOT NULL,
    size_type VARCHAR(20) NOT NULL,
    file_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE,
    UNIQUE(image_id, size_type)
);

CREATE INDEX idx_thumbnails_image_id ON thumbnails(image_id);
```

#### 权限表 (permissions)
```sql
CREATE TABLE permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    folder_id INTEGER NOT NULL,
    permission_type VARCHAR(20) NOT NULL CHECK (permission_type IN ('read', 'write', 'delete', 'rename')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE CASCADE,
    UNIQUE(user_id, folder_id, permission_type)
);
```

#### 回收站表 (trash)
```sql
CREATE TABLE trash (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id INTEGER,
    original_path TEXT NOT NULL,
    trash_path TEXT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    user_id INTEGER NOT NULL,
    metadata TEXT,
    deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_trash_user_id ON trash(user_id);
CREATE INDEX idx_trash_deleted_at ON trash(deleted_at);
```

#### 浏览位置书签表 (image_bookmarks)
```sql
CREATE TABLE image_bookmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    kind VARCHAR(10) NOT NULL DEFAULT 'manual' CHECK (kind IN ('manual', 'auto')),
    name VARCHAR(100) NOT NULL,
    folder_id INTEGER NOT NULL DEFAULT 0,       -- 0 = 所有照片
    is_favorites INTEGER NOT NULL DEFAULT 0,
    search_query TEXT NOT NULL DEFAULT '',
    sort_by VARCHAR(20) NOT NULL DEFAULT 'modified_time',
    sort_order VARCHAR(4) NOT NULL DEFAULT 'DESC',
    anchor_image_id INTEGER NOT NULL,
    anchor_modified_time TEXT,
    anchor_file_name TEXT,
    anchor_file_size INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_image_bookmarks_user ON image_bookmarks(user_id, kind, updated_at);
CREATE UNIQUE INDEX idx_image_bookmarks_auto
    ON image_bookmarks(user_id, folder_id, is_favorites, search_query)
    WHERE kind = 'auto';
```

## 7. 前端架构

### 7.1 组件层次结构

```
web/src/
├── api/
│   └── index.ts             # axios 封装、Token 注入、401 凭证清理
├── components/
│   ├── Sidebar.vue          # 侧边栏（文件夹/收藏/回收站/管理/登录）
│   ├── TopBar.vue           # 顶部搜索与主题切换
│   ├── ImageGrid.vue        # 图片网格与批量操作
│   ├── Lightbox.vue         # 图片详情灯箱
│   ├── ImageInfoDialog.vue  # 图片详情弹窗（网格/灯箱共用）
│   ├── BookmarksDrawer.vue  # 浏览位置书签抽屉
│   ├── Empty.vue            # 空状态占位
│   └── common/
│       └── VirtualWaterfall.vue  # 虚拟滚动瀑布流
├── composables/
│   └── useTheme.ts          # 明暗主题
├── lib/
│   └── utils.ts             # class 合并工具
├── pages/
│   ├── HomePage.vue         # 主视图（瀑布流/管理/回收站切换）
│   ├── AdminPage.vue        # 管理面板
│   └── TrashPage.vue        # 回收站
├── router/
│   └── index.ts             # / 与 /about
├── stores/
│   ├── auth.ts              # 登录状态与 401 重置
│   ├── folder.ts            # 文件夹列表与当前选择
│   ├── image.ts             # 图片/回收站/批量操作/书签窗口恢复
│   ├── bookmark.ts          # 浏览位置书签与自动进度
│   ├── hotkey.ts            # 快捷键配置
│   └── ui.ts                # 侧边栏与响应式状态
├── App.vue
├── main.ts
└── style.css
```

### 7.2 状态管理

使用 Pinia 进行状态管理：

- **authStore**：管理用户登录状态、Token 与角色；Token 失效时由 API 层事件触发重置
- **imageStore**：管理图片数据、分页、加载状态、筛选条件、批量操作、回收站与书签锚点窗口恢复
- **bookmarkStore**：管理手动书签与自动浏览进度；负责保存当前视图位置、恢复书签视图与锚点
- **folderStore**：管理文件夹结构、当前选中文件夹
- **hotkeyStore**：从 `/api/admin/settings` 读取快捷键配置
- **uiStore**：管理侧边栏折叠与移动端响应式状态

## 8. 核心逻辑流程

### 8.1 图片扫描流程

```mermaid
graph TD
    A[触发扫描] --> B[获取文件夹路径]
    B --> C[遍历文件系统]
    C --> D{文件是否为图片}
    D -->|是| E[读取图片元数据]
    D -->|否| C
    E --> F[检查数据库是否存在]
    F -->|存在| G[更新元数据]
    F -->|不存在| H[插入新记录]
    G --> I[生成缩略图]
    H --> I
    I --> J[完成扫描]
```

扫描器会记录本次遍历到的文件集合，扫描结束后删除该文件夹下不在集合中的图片索引，并同步清理其收藏、标签、缩略图记录与缓存文件。这样在修改物理路径、切换递归扫描或减少支持格式后，旧索引不会残留。扫描过程中每个批次都会确认文件夹记录仍存在，避免删除文件夹后线程继续写入。

### 8.2 缩略图生成流程

```mermaid
graph TD
    A[请求缩略图] --> B{缓存是否存在}
    B -->|存在| C[返回缓存文件]
    B -->|不存在| D[生成缩略图]
    D --> E[保存到缓存目录]
    E --> F[更新数据库记录]
    F --> C
```

## 9. 目录结构

> 2026-10-24 按仓库现状核对修正：原文档中的 `backend/`、`frontend/` 为规划名，实际目录为 `server/`、`web/`；同日完成目录整理、测试/生产库分离与 `.env` 凭证外置。版本、端口与启动方式的权威记录见 `docs/tech/dev-info.md`。

```
PicGallery/
├── server/                      # Flask 后端
│   ├── app/
│   │   ├── __init__.py          # create_app、.env/config 加载、蓝图注册、web/dist 静态托管
│   │   ├── models/schema.sql    # 建表语句
│   │   ├── routes/              # auth.py / folder.py / image.py / bookmarks.py / admin.py / settings.py
│   │   ├── services/            # scanner.py（扫描）/ thumbnail.py（缩略图与预生成）
│   │   └── utils/db.py          # 连接、建表、轻量迁移、FTS5 索引、管理员/访客初始化
│   ├── venv/                    # Python 3.12.7 虚拟环境（git 忽略）
│   ├── requirements.txt         # Python 依赖
│   └── run.py                   # 开发入口（Flask dev server）
├── web/                         # Vue3 + Vite 前端
│   ├── src/
│   │   ├── api/                 # axios 封装与 401 清理
│   │   ├── components/          # Sidebar/TopBar/ImageGrid/Lightbox/ImageInfoDialog/BookmarksDrawer/common
│   │   ├── composables/         # useTheme
│   │   ├── pages/               # HomePage/AdminPage/TrashPage
│   │   ├── router/              # 路由
│   │   ├── stores/              # Pinia：auth/folder/image/bookmark/hotkey/ui
│   │   ├── lib/                 # 工具函数
│   │   ├── App.vue
│   │   ├── main.ts
│   │   └── style.css
│   ├── public/                  # favicon、MiSans 字体
│   ├── dist/                    # 构建产物（git 忽略，生产静态资源）
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts           # 别名 @ 与 /api 代理
├── docs/                        # prd/tech/plan/deploy/rules/prototype
├── scripts/
│   ├── deploy-script/           # Windows 部署脚本
│   └── sql-script/              # init_db.py / normalize_db.py / prebuild_thumbnails.py
├── data/                        # 本地运行数据（git 忽略）
│   ├── db/database.db           # 开发/测试数据库
│   ├── cache/                   # 缩略图缓存
│   ├── trash/                   # 应用内回收站
│   └── app_logs/                # 本地日志
├── config.yaml                  # 非敏感运行配置（开发/测试）
├── config.example.yaml          # 配置示例
├── .env.example                 # 密钥与管理员初始账号示例（真实 .env 不入库）
├── prod_run.py                  # 生产入口（Waitress）
└── README.md
```

## 10. 性能优化策略

### 10.1 数据库优化

- 已为 `images(file_path)`、`images(folder_id)`、`images(modified_time)` 建立索引，并新增 `images(folder_id, modified_time)`、`images(file_name)`、`images(file_size)`、`folders(is_public)`。
- SQLite 连接启用 `journal_mode=WAL`、`synchronous=NORMAL`、`cache_size=-20000`、`temp_store=MEMORY`，降低浏览读取与扫描写入的相互阻塞。
- `GET /api/images` 的 `page` 最小为 1、`per_page` 限制在 1–200，避免异常大分页。
- 图片响应启用条件请求与缓存头：缩略图 `max-age=86400`，原图/下载 `max-age=3600`。
- 文件名搜索使用 FTS5 trigram 虚拟表 `images_fts`，查询词 ≥3 字符走 `MATCH`，短词或 FTS5 不可用时回退 `LIKE`；索引与 `images` 通过触发器同步，可用 `init_db.py --rebuild-search-index` 重建。
- 书签恢复与定位使用 `/api/images/window` 的 keyset 前后窗口查询，不按页码或深 `OFFSET` 加载；窗口默认前 40、后 80，上限 100/200。
- 列表分页支持 keyset 游标：`cursor`/`next_cursor` 绑定排序与最后一条记录，避免深层 `OFFSET`；首次请求仍返回完整 `total`。
- 后续：窗口化数据源/元数据级虚拟化；定期 `ANALYZE`/`VACUUM`。

### 10.2 前端优化

- 虚拟瀑布流使用二分查找定位可见区间，滚动复杂度 O(log n + 可见项)，不再逐帧过滤全部已加载项。
- 分页追加使用原地 `push` + `triggerRef` + `itemsVersion`，避免每页 O(n) 数组复制。
- 搜索 300ms 防抖；请求使用 `AbortController` 取消并通过序号丢弃乱序响应；按图片 ID 去重。
- 图片网格与灯箱使用 `loading="lazy"`、`decoding="async"`；大网格使用 `medium` 缩略图。
- 灯箱原图预加载增加 6MB 体积门槛与 120 条 URL 上限，切换时清理定时器；滚轮缩放按帧合并。
- 动效仅使用 `transform/opacity`，虚拟列表不使用 `transition-group` 与全量 `will-change`，并支持 `prefers-reduced-motion`。
- 列表分页使用服务端 `next_cursor` 游标；前端保留 `nextCursor`，服务端返回 null 时停止加载。
- 后续：窗口化数据源、响应式 `srcset` 多档缩略图；Element Plus 已按需引入，管理页/回收站/灯箱已按需加载。

### 10.3 后端与图片处理优化

- 缩略图按需生成并落盘缓存；缩略图记录写入 `thumbnails` 表。
- 默认输出 WebP（`THUMBNAIL_FORMAT`），读取兼容存量 jpg；格式迁移使用 `prebuild_thumbnails.py --rebuild`，成功后删除旧格式文件。
- 回收站缩略图由 `generate_thumbnail_from_path` 缓存到 `cache/trash/<size>/`，恢复/永久删除时同步清理。
- 扫描完成且状态置为 `completed` 后，后台线程按 id 分批预生成缺失的 `small` 缩略图；`THUMBNAIL_PREGENERATE` 控制开关，全局锁避免并发预生成。
- 历史库可用 `scripts/sql-script/prebuild_thumbnails.py --limit/--folder` 分批补齐。
- 扫描任务使用后台线程，进度每 10 个文件更新一次；100k 规模可进一步改为批量提交。
- 10 万张规模的后续重点：窗口化数据源、AVIF/多档响应式缩略图、受限并发与失败占位缓存、真实数据压测。