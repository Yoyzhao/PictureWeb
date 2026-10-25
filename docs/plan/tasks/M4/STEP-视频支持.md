# M4 / 视频支持 — 阶段任务文档

- **里程碑**：M4 视频支持
- **阶段**：需求确认 + 轻量 5B 交互设计 + 5C/5D 垂直切片 + 6/7 联调
- **文档状态**：方案已落盘（执行状态见 `docs/plan/project-progress.md`）
- **关联 CHG**：`CHG-20261025-04`（`docs/tech/功能变更.md`）
- **关联 ADR**：`ADR-001`（`docs/tech/arch/ADR-001-视频支持与媒体模型.md`）
- **本轮基线**：M3 完成后的工作区（未提交 commit）；生产副本为 2026-10-25 02:00 版本，本轮暂不同步
- **更新日期**：2026-10-25

## 任务索引

| 任务 ID | 一句话范围 | 详情 |
|---|---|---|
| T-029 | 媒体模型迁移、视频配置、扫描与 ffprobe 元数据 | 本文 T-029 |
| T-030 | 视频封面生成、占位图、临时文件与缓存清理 | 本文 T-030 |
| T-031 | 媒体类型筛选、书签上下文、Range/MIME、回收站字段 | 本文 T-031 |
| T-032 | 混合列表、类型筛选、视频灯箱、信息与回收站展示 | 本文 T-032 |
| T-033 | 桌面 M3U/复制地址、Android VLC intent、iOS VLC x-callback | 本文 T-033 |
| T-034 | 联调、真机验证、构建与文档同步 | 本文 T-034 |
| T-035 | 视频播放交互增强（P0）：点击语义、键盘、续播、视频工具栏与底部控制条 | 本文 T-035 |
| T-036 | 视频播放体验增强（P1）：比例占位、缓冲提示、倍速、画中画、错误重试 | 本文 T-036 |
| T-037 | 离线无损转封装脚本：FLV/MKV 等容器 → MP4（`-c copy`） | 本文 T-037 |

> 状态、负责人、优先级、依赖、阻塞与验收结论只写在 `docs/plan/project-progress.md`，本文档只维护执行细节。

## 方案要点

### 1. 范围与边界

**范围内**

- 图片与视频统一索引、浏览、筛选与管理。
- 视频封面、时长/分辨率/编码等元数据。
- 视频在网格、灯箱、信息弹窗、回收站中的展示。
- 收藏、移动、删除/回收站、恢复、重命名、搜索、多选、书签完整复用。
- 跨平台外部播放器联动与客户端缓存防护。
- 服务端封面缓存、临时文件与孤儿缓存清理。

**范围外**

- 不引入 HLS/DASH、转码或转封装服务。
- 不做网页上传视频；视频仍通过“添加文件夹 + 扫描”入库。
- 不修改媒体读取接口的服务端权限校验；权限整改另立项。
- 不做视频剪辑、字幕管理、播放列表管理与转码缓存。
- 不改变现有图片处理、图片 UI 与生产部署路径。

### 2. 数据模型

`images` 表新增字段（存量行迁移为 `image`）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `media_type` | VARCHAR(10) | `image` / `video`，默认 `image` |
| `duration` | REAL | 视频时长（秒），图片为 NULL |
| `video_codec` | VARCHAR(20) | 如 `h264`、`hevc`、`vp9`、`av1`；图片为 NULL |
| `audio_codec` | VARCHAR(20) | 如 `aac`、`opus`、`mp3`；无音轨或图片为 NULL |

`image_bookmarks` 新增：

| 字段 | 类型 | 说明 |
|------|------|------|
| `media_filter` | VARCHAR(10) | `all` / `image` / `video`，默认 `all` |

迁移约束：

- `server/app/models/schema.sql` 与 `server/app/utils/db.py::migrate_db()` 同步修改。
- 使用 `ALTER TABLE ... ADD COLUMN` 增量迁移，不改写存量数据。
- 自动书签部分唯一索引 `idx_image_bookmarks_auto` 需按 `(user_id, folder_id, is_favorites, search_query, media_filter)` 重建；先删除旧索引再创建。
- 新增 `idx_images_media_type(media_type)` 或在现有组合索引上补充媒体类型，具体以实际查询计划为准。
- 迁移前备份开发库到 `data/backups/`；不触碰生产库。

### 3. 扫描与元数据

- `config.yaml` / `config.example.yaml` 新增：
  - `SCAN_VIDEO_EXTENSIONS: .mp4,.m4v,.webm,.mov,.mkv,.avi,.wmv,.flv`
  - `FFMPEG_PATH: ffmpeg`（Windows 服务环境建议绝对路径，如 `D:/FFmpeg/ffmpeg.exe`）
  - `FFPROBE_PATH: ffprobe`
  - `VIDEO_THUMBNAIL_PREGENERATE: true`
  - `VIDEO_THUMBNAIL_TIMEOUT: 20`
- 扫描器按扩展名区分图片/视频；图片沿用 `SCAN_EXTENSIONS`，视频使用 `SCAN_VIDEO_EXTENSIONS`。
- 视频元数据通过 `ffprobe` JSON 读取：`width`、`height`、`duration`、`format_name`、`codec_name`；容器写入 `format` 时取短名。
- 旋转处理：读取 `side_data_list.rotation`，90°/270° 时交换宽高，避免封面和网格比例错位。
- 已存在行文件修改时更新元数据、`file_size`、`modified_time`，并删除旧封面缓存；下次请求重新生成。
- FFmpeg/ffprobe 缺失时：视频仍可入库（宽高/时长为 0/NULL），封面返回共享占位图；启动日志记录警告。
- 扫描进度与对账逻辑沿用现有 `scanned_keys` 集合；视频与图片一起计入 `scan_total`。

### 4. 封面与缓存生命周期

- 新增 `server/app/services/video.py`（或等价服务模块）：
  - `probe_video(path)`：调用 ffprobe，返回元数据；超时返回空值。
  - `extract_poster(path, duration)`：FFmpeg 抽帧到临时文件/管道，时间点取 10% 时长、上限 10 秒；失败回退到 1 秒/0 秒。
  - `generate_video_poster(source_path, cache_key, size_type)`：抽帧后交给 Pillow 缩放并输出 WebP，复用现有 `_save_thumbnail` 的格式/质量配置。
- `server/app/services/thumbnail.py`：
  - `generate_thumbnail` 根据 `media_type` 分支；视频走 FFmpeg + Pillow。
  - `generate_thumbnail_from_path` 按扩展名识别视频，供回收站使用。
  - 视频抽帧失败时返回共享占位图 `data/cache/placeholder/video.webp`，不写 `thumbnails` 记录。
  - FFmpeg 并发用 `Semaphore(1)` 或 `Semaphore(2)` 限制；失败结果用短 TTL 内存缓存，避免同一视频反复抽帧。
  - 增加 `cleanup_video_temp()`：应用启动时清理 `data/cache/tmp` 下遗留的抽帧文件；每次抽帧在 `finally` 中删除。
  - **按需生成锁超时（防线程耗尽）**：`/thumbnail` 同步路由获取信号量时设置短超时（约 500ms）：
    - 超时未获锁 → **立即返回共享占位图**（HTTP 200，不 404、不 500），同时把该任务投递到后台队列（复用预生成队列或等价线程池）补生成；下次请求命中已生成封面。
    - 获锁 → 正常抽帧生成并返回真实封面。
    - 失败结果进 TTL 缓存后，后续请求直接返回占位图，不重复进入队列；队列对同一 `(image_id, size_type)` 去重。
    - 背景：生产 Waitress `threads=8`，若多个封面请求在信号量上串行阻塞（FFmpeg 抽帧秒级），会耗尽全部服务线程导致所有 API（含非媒体接口）无响应；本机制保证锁等待不占用请求线程。
    - 启动清理与预生成路径不受锁超时影响，仍按信号量排队执行。
- 后台预生成：
  - 扫描完成后沿用 `start_folder_thumbnail_prebuild`，由 `VIDEO_THUMBNAIL_PREGENERATE` 控制视频部分。
  - 视频封面低优先级、单 worker；图片封面仍按现有逻辑。
  - `scripts/sql-script/prebuild_thumbnails.py` 增加媒体类型参数（如 `--media image|video|all`），支持分批补齐。
- 清理：
  - 删除/移动/重命名/文件夹移除/扫描对账沿用 `clear_image_thumbnails`、`_remove_thumbnail_files`。
  - 回收站恢复/永久删除沿用 `clear_trash_thumbnails`。
  - 新增 `scripts/sql-script/prune_cache.py --dry-run`：清理 `cache/small`、`cache/medium` 中数据库已不存在的图片/视频封面，以及 `cache/trash/{small,medium}` 中已不存在的回收站记录封面；支持 `--apply` 实际删除。
  - 共享占位图只保留一份，不按视频复制。
  - 不生成任何视频副本；原始视频始终从源路径读取。

### 5. 服务端接口

- `GET /api/images` 新增 `media_type=image|video`（缺省/`all` 返回全部）；`image_filters` 同步支持，列表计数与 keyset 分页保持一致。
- `GET /api/images/window` 与书签恢复接口同样接受 `media_filter`；书签保存/自动进度/恢复均带该字段。
- `serialize_image` 通过 `SELECT i.*` 自动带出 `media_type`、`duration`、`video_codec`、`audio_codec`；必要时对 `duration` 做浮点归一化。
- `GET /api/images/<id>/raw`：
  - 按扩展名显式映射 MIME：`.mp4/.m4v` → `video/mp4`，`.webm` → `video/webm`，`.mov` → `video/quicktime`，`.mkv` → `video/x-matroska`，`.avi` → `video/x-msvideo`，`.wmv` → `video/x-ms-wmv`，`.flv` → `video/x-flv`，其余回退 `application/octet-stream`。
  - 保留 `send_file(conditional=True)` 与 Range；视频额外设置 `Cache-Control: no-store`、`max_age=0`，避免浏览器把视频正文写入磁盘缓存；图片保持现有缓存头。
- `GET /api/images/<id>/download`：保持附件下载；视频同样使用正确 MIME 和文件名。
- `GET /api/images/<id>/thumbnail`：视频返回封面；失败返回共享占位图，不返回原视频。
- 回收站：
  - 删除时 `metadata` 增加 `media_type`、`duration`、`video_codec`、`audio_codec`。
  - 回收站列表解析并返回这些字段。
  - 恢复插入 `images` 时写回媒体字段，避免恢复后变回图片。
  - `GET /api/images/trash/<id>/thumbnail` 对视频失败时返回占位图或 404，**不得回退为原视频文件**（当前实现会回退原文件，视频场景会传输整个视频）。
- 权限：本轮保持现状；`raw`/`thumbnail`/`download` 不新增鉴权逻辑，风险记录在 `project-progress.md`。
- 不新增播放列表接口；M3U 由前端生成，URL 使用 `location.origin + /api/images/<id>/raw`。

### 6. 前端

- `web/src/stores/image.ts`：
  - `Image` 接口增加 `media_type`、`duration`、`video_codec`、`audio_codec`。
  - 新增 `mediaFilter: 'all' | 'image' | 'video'`，持久化到 localStorage；请求带 `media_type`。
  - 切换筛选时重置列表、清空选择、退出多选、更新自动进度上下文。
- `web/src/api/index.ts`：`getImages` 参数增加 `media_type`。
- `web/src/stores/bookmark.ts`：书签上下文增加 `media_filter`；创建/自动进度/恢复均透传。
- 网格 `ImageGrid.vue`：
  - 顶部排序区增加“全部/图片/视频”筛选控件；筛选变化触发重新加载。
  - 视频卡片增加播放角标与时长徽标；封面继续走 `/thumbnail`。
  - `imageAspectRatio` 对未知尺寸视频回退 16:9；卡片 `width/height` 与 `aspect-ratio` 保持显式设置，避免 CLS。
  - “图片数量/没有更多图片/没有照片”等文案改为媒体中性表述。
  - 多选、收藏、移动、删除、重命名、详情、下载对视频复用。
- 灯箱 `Lightbox.vue`：
  - `media_type==='video'` 时渲染 `<video controls playsinline preload="metadata" :poster>`；不自动播放。
  - 视频隐藏旋转/缩放/裁剪等图片专用控件；保留上一张/下一张、重命名、移动、收藏、信息、书签、删除。
  - `<video>` 触发 `error` 时显示“该格式无法在浏览器中直接播放”，并展示外部播放器入口。
  - 键盘：左右仍切换媒体；空格播放/暂停，避免与原生控件冲突；输入框/视频控件聚焦时不拦截。
  - `ENABLE_PRELOAD` 只预加载下一张图片，不预加载视频原文件。
  - 视频工具栏/菜单增加“用本地播放器打开”“复制播放地址”“下载原文件”；平台不支持时降级。
- 信息弹窗 `ImageInfoDialog.vue`：增加类型、时长、视频编码、音频编码；图片保持原字段。
- 回收站 `TrashPage.vue`：视频卡片增加播放角标与时长；封面走回收站缩略图；恢复/永久删除不变。
- 书签抽屉 `BookmarksDrawer.vue`：继续使用 `/thumbnail`；视频显示角标或时长；书签恢复带 `media_filter`。
- 移动端：触屏热区 ≥44px；视频使用原生控件与 `playsinline`；桌面 M3U 入口在移动端隐藏，保留复制地址/VLC 深链。

### 7. 跨平台外部播放器联动

| 平台/浏览器 | 主入口 | 兜底 | 客户端文件 |
|-------------|--------|------|------------|
| Windows / macOS / Linux 桌面 | 复制播放地址；可选下载 M3U | 下载原文件 | M3U 仅数百字节；默认复制地址不产生文件 |
| Android + Chrome/Edge | `intent://` 打开 VLC（`package=org.videolan.vlc`、`action=VIEW`、`type=video/*`） | 复制播放地址；通用 intent 让系统选择播放器 | 无文件 |
| Android + Firefox/其他 | 复制播放地址，粘贴到 VLC“网络串流” | 下载原文件 | 无文件 |
| iOS / iPadOS + Safari | `vlc-x-callback://x-callback-url/stream?url=<encoded>`（仅 stream，不 download） | 复制播放地址到 VLC“网络串流”；`vlc://` 视版本兜底 | 无文件 |
| iOS / iPadOS 其他浏览器 | 复制播放地址；系统分享面板 | 下载原文件 | 无文件 |

实现要点：

- 新增 `web/src/utils/externalPlayer.ts`：
  - `buildRawUrl(imageId)`：`${location.origin}/api/images/${imageId}/raw`。
  - `copyPlayUrl(imageId)`：Clipboard API，失败时回退到输入框选择。
  - `downloadM3U(image)`：Blob + `URL.createObjectURL`，下载后立即/短延时 `revokeObjectURL`；文件名清洗；仅桌面端显示。
  - `buildAndroidVlcIntent(url)`：把 `http://host/path` 转成 `intent://host/path#Intent;scheme=http;type=video/*;package=org.videolan.vlc;end`；可附加 `S.title`；不使用 `download` 动作。
  - `buildIosVlcStream(url)`：`vlc-x-callback://x-callback-url/stream?url=${encodeURIComponent(url)}`；不附加 `download`。
  - `detectPlatform()`：Android/iOS/桌面；只用于决定默认入口，不阻止其他入口。
- 外部播放器入口在所有视频上可用，不只在播放失败时出现；播放失败时额外高亮提示。
- iOS 深链必须在用户点击的同步调用栈中触发（如 `window.location.href`），不要等异步请求后再跳转，否则 Safari 可能拦截。
- 未安装 VLC 或深链失败时，提示“未检测到 VLC，已复制播放地址”，并保留手动粘贴说明。
- `vlc://` 支持随 VLC iOS 版本变化（2.3 部分支持、2.4 起支持），仅作兜底；`vlc-x-callback://` 是文档化主路径。
- Android `intent://` 仅 Chromium 内核浏览器稳定支持；Firefox 等直接显示复制地址。
- 不引入浏览器扩展、本地助手或自定义协议注册；后续如需要真正一键，可另立项评估。

### 8. 客户端缓存与磁盘占用防护

- **不自动下载视频**：任何入口都必须由用户点击；不提供“打开即下载整个视频”的默认行为。
- **浏览器播放**：`<video preload="metadata" playsinline>`，不设 `autoplay`；不预加载下一段视频原文件；视频 raw 响应 `Cache-Control: no-store`。
- **M3U**：仅桌面端可选；Blob 生成后 `revokeObjectURL`；文件本身是数百字节文本；浏览器无法自动删除已下载文件，需用户自行清理或一次性设置“始终打开此类文件”。
- **移动端深链**：Android intent 与 iOS x-callback 只把 URL 交给 VLC，不生成文件；使用 `stream`，不使用 `download`。
- **播放器缓存**：VLC 的缓冲/缓存由 VLC 自身管理（通常为内存缓冲），本项目无法清理；本项目保证不生成视频副本，也不主动要求 VLC 下载。
- **服务端**：不生成视频副本；只缓存封面；临时抽帧文件即时清理；提供孤儿缓存清理脚本。
- **禁止项**：不要用 `data:` URI 承载 M3U（Safari 有长度限制）；不要在列表/灯箱预加载视频原文件；不要把视频写入 `cache/`。

### 9. 权限与安全

- 本轮沿用现状：`raw`、`thumbnail`、`download` 不校验登录与文件夹权限；视频 URL 可被同网段按 ID 访问。
- 外部播放器入口使用同一 raw URL，不放宽权限。
- 若后续引入签名媒体 URL，M3U/深链/复制地址必须使用签名后的 URL，且签名有效期覆盖播放时长。
- CV/扫描路径继续使用数据库中的路径，不接受客户端传入路径；避免路径遍历。

### 10. 平台兼容性与 HEVC

- iOS Safari 通常支持 HEVC 硬件解码，优先使用原生 `<video>`；不因 UA 预设为不可播。
- Android Chrome 通常不支持 HEVC，桌面 Chrome 也不支持或依赖系统解码；由 `<video>` 的 `error` 事件触发外部播放器提示。
- 不为编码组合维护静态黑名单；以实际播放失败为准，避免误判。
- H.264/AAC MP4 与 VP9/WebM 作为可播基线；MKV/AVI/WMV/FLV 通常需要外部播放器。

## T-029 媒体模型迁移、视频配置、扫描与元数据

### 目标与边界

#### 目标

现有图片库无数据丢失地扩展为媒体库；视频文件可被扫描、入库并带出时长/分辨率/编码。

#### 范围内

- `images`、`image_bookmarks` 迁移与索引。
- 视频后缀配置、FFmpeg/ffprobe 路径配置。
- 扫描器媒体类型判定、ffprobe 元数据、旋转处理、修改失效。
- 启动时 FFmpeg 可用性检查与警告日志。

#### 范围外

- 封面生成与缓存清理（T-030）。
- 接口与前端（T-031/T-032）。

### 技术方案

#### 影响位置

- 数据模型/迁移：`server/app/models/schema.sql`、`server/app/utils/db.py`
- 服务端扫描：`server/app/services/scanner.py`、新增 `server/app/services/video.py`
- 配置：`config.yaml`、`config.example.yaml`
- 应用启动：`server/app/__init__.py`（FFmpeg 检查/日志）

#### 实现说明

- `migrate_db()` 使用 `PRAGMA table_info` 判断字段是否存在，分别添加 `media_type`、`duration`、`video_codec`、`audio_codec`、`media_filter`。
- `schema.sql` 同步新增字段，保证新库与旧库结构一致。
- 自动书签索引重建：`DROP INDEX IF EXISTS idx_image_bookmarks_auto` 后创建包含 `media_filter` 的新索引。
- 迁移前备份开发库；迁移脚本幂等，允许多次启动。
- 扫描器 `is_media_file` 返回 `(is_media, media_type)`；图片分支保持 Pillow 逻辑，视频分支调用 ffprobe。
- ffprobe 命令使用参数列表、`timeout`、`capture_output=True`；Windows 中文路径按 UTF-8 处理。
- 视频 `format` 取容器短名（如 `mp4`、`matroska`、`webm`），避免 `format_name` 逗号串写入。
- 旋转：`side_data_list.rotation` 为 ±90/±270 时交换宽高；封面由 FFmpeg 自动旋转。
- 文件修改时删除旧封面记录与缓存文件；文件删除由现有扫描对账处理。

### 实施步骤

1. 备份开发库，修改 `schema.sql` 与 `migrate_db()`，启动验证字段与索引。
2. 增加配置键与默认值，更新 `config.example.yaml`。
3. 新增 `video.py` 元数据探测函数，接入扫描器。
4. 扩展扫描器媒体类型判定与修改失效逻辑。
5. 启动检查 FFmpeg/ffprobe，记录可用性但不阻塞图片功能。
6. 用临时目录构造图片+视频混合库，验证扫描结果。

### 验证与验收

- `PRAGMA table_info(images)` 含 4 个新字段；存量行 `media_type='image'`。
- `PRAGMA index_list(image_bookmarks)` 自动索引包含 `media_filter`。
- 混合目录扫描后：视频 `media_type='video'`，时长/宽高/编码非空；图片行为不变。
- 修改视频文件后重扫：元数据更新，旧封面缓存被删除。
- `py_compile` 通过；现有图片列表 total 与扫描数量不回归。
- FFmpeg 不可用时：视频仍入库，日志有警告，接口不报 500。

### 风险与恢复

- 迁移失败：使用数据库备份恢复；迁移保持幂等。
- ffprobe 超时/异常：单文件记录失败日志，不影响其他文件；字段留空。
- 兼容性：旧库启动自动迁移；旧客户端新增字段可忽略。

## T-030 视频封面、占位图与缓存清理

### 目标与边界

#### 目标

视频在网格/书签/回收站有稳定封面；失败有占位图；服务端不产生视频副本与孤儿临时文件。

#### 范围内

- FFmpeg 抽帧 + Pillow 输出 WebP。
- 共享占位图。
- 临时文件清理、失败重试抑制。
- 后台预生成与 `prune_cache` 脚本。

#### 范围外

- 视频转码/转封装。
- 前端封面展示（T-032）。

### 技术方案

#### 影响位置

- `server/app/services/thumbnail.py`
- 新增 `server/app/services/video.py`
- `scripts/sql-script/prebuild_thumbnails.py`
- 新增 `scripts/sql-script/prune_cache.py`
- `server/app/routes/admin.py`（缓存清理范围，如适用）

#### 实现说明

- 抽帧时间：`min(max(duration * 0.1, 0.5), 10)` 秒；短视频用 0 秒；失败重试 1 秒。
- FFmpeg 输出到 `data/cache/tmp/<uuid>.jpg`，Pillow 读取后按现有 `_save_thumbnail` 输出 WebP；`finally` 删除临时文件。
- 占位图：`data/cache/placeholder/video.webp`，单文件；首次需要时用 Pillow 生成（深色背景 + 播放三角）。
- 失败 TTL 缓存：进程内 `dict[(image_id,size_type)] = (timestamp, error)`，10 分钟内直接返回占位图，避免反复启动 FFmpeg。
- `thumbnails` 表只记录成功生成的封面；失败不写记录。
- `prebuild_thumbnails.py` 增加 `--media` 参数；视频默认单 worker、低优先级，可配置关闭。
- `prune_cache.py`：
  - 读取 `images.id` 集合与 `trash.id` 集合；
  - 扫描 `cache/small`、`cache/medium`、`cache/trash/small`、`cache/trash/medium`；
  - 删除不在集合中的 `<id>.webp`/`.jpg`；
  - `--dry-run` 只打印数量与路径样例；`--apply` 实际删除；
  - 不清理 `cache/tmp` 之外的其他目录。
- 应用启动调用 `cleanup_video_temp()` 清理 `cache/tmp` 中超过一定时间的遗留文件。
- 管理页“清理缓存”如覆盖 cache 目录，需保留/重建共享占位图，并清理 `cache/tmp`。

### 实施步骤

1. 实现抽帧、元数据探测与占位图。
2. 修改 `generate_thumbnail`/`generate_thumbnail_from_path` 分支。
3. 接入扫描后预生成与失败抑制。
4. 新增 `prune_cache.py` 与启动临时目录清理。
5. 用测试视频验证封面与回收站封面。

### 验证与验收

- H.264 MP4、VP9 WebM 均生成 small/medium WebP 封面。
- FFmpeg 缺失/损坏文件返回共享占位图，接口不 404、不传输原视频。
- 视频删除/移动/重命名/文件夹移除后，封面文件与 `thumbnails` 记录无残留。
- 回收站恢复/永久删除后，`cache/trash` 无残留。
- `prune_cache.py --dry-run` 无数据库引用文件计数正确；`--apply` 后缓存目录无孤儿。
- `data/cache/tmp` 在任务结束后为空；启动清理可处理遗留文件。
- 锁超时生效：冷启动并发请求多个未生成视频封面时，路由在约 500ms 内返回占位图而非阻塞；期间其他 API（列表/健康检查）仍可正常响应；稍后重取同一封面返回真实封面（后台补生成命中）。

### 风险与恢复

- FFmpeg 抽帧失败：占位图 + 日志；不影响列表。
- 大量视频预生成占用 CPU：可关闭 `VIDEO_THUMBNAIL_PREGENERATE`，改为手动分批。
- 清理脚本误删：默认 dry-run，`--apply` 前需确认；只删除缓存目录内符合命名规则的文件。

## T-031 服务端媒体筛选、Range/MIME 与回收站字段

### 目标与边界

#### 目标

服务端按媒体类型筛选；视频以正确 MIME 与 Range 提供；书签恢复保持筛选；回收站完整保留视频类型。

#### 范围内

- `image_filters`/`get_images`/`window` 的 `media_type`。
- 书签 `media_filter` 上下文。
- raw/download MIME、视频 `no-store`。
- 回收站 metadata、列表、恢复、缩略图兜底。

#### 范围外

- 前端筛选 UI（T-032）。
- 权限整改。

### 技术方案

#### 影响位置

- `server/app/routes/image.py`
- `server/app/routes/bookmarks.py`
- `server/app/routes/admin.py`（如缓存统计需要）

#### 实现说明

- `image_filters(user, folder_id, is_favorite, q, media_type=None)`；白名单 `image`/`video`，其他值返回 400 或按不筛选处理（实现时统一）。
- `get_images` 与 `get_images_window` 读取 `media_type` 参数；cursor 不包含媒体类型，过滤条件单独绑定。
- `fetch_image_window` 增加参数并传给 `image_filters`。
- 书签：
  - `image_bookmarks` 读/写/自动 upsert/恢复窗口全部带 `media_filter`。
  - 自动书签唯一键包含 `media_filter`；旧书签默认 `all`。
  - 书签列表返回该字段，前端恢复视图时使用。
- raw/download：
  - 显式 MIME 映射；`send_file(..., mimetype=..., conditional=True, max_age=0)`。
  - 视频响应覆盖 `Cache-Control: no-store`；图片保持 `max_age`。
  - 下载接口 `as_attachment=True`，视频使用原始文件名。
- 回收站：
  - 删除 metadata 写入媒体字段。
  - `get_trash_items` 解析并返回媒体字段、时长、编码；前端用于角标/信息。
  - 恢复插入 `images` 时写回媒体字段；字段缺失时按扩展名推断 `media_type`。
  - 回收站缩略图：视频失败返回占位图/404；禁止回退原视频。
- 不新增播放接口；外部播放器使用 raw URL。

### 实施步骤

1. 扩展 `image_filters` 与列表/窗口调用点。
2. 书签 schema/路由/上下文字段打通。
3. raw/download MIME 与 no-store。
4. 回收站 metadata/restore/thumbnail 改造。
5. 用 `curl -r` 与不同 `media_type` 验证。

### 验证与验收

- `GET /api/images?media_type=video` 只返回视频；`image` 只返回图片；无参数返回全部。
- 切换筛选后 `total` 正确；keyset 分页无重复、无遗漏。
- 书签保存 `video` 筛选后恢复仍只显示视频；自动进度按筛选隔离。
- `curl -r 0-1023` 返回 206、`Accept-Ranges: bytes`、`Content-Range`；视频响应含 `Cache-Control: no-store`。
- MKV 响应 MIME 为 `video/x-matroska`（或映射值），浏览器/播放器可识别。
- 删除视频进入回收站，列表含 `media_type/duration`；恢复后仍为视频，字段不丢失。
- 视频回收站缩略图失败不返回原视频。
- 图片 raw/thumbnail 缓存头与列表行为无回归。

### 风险与恢复

- 书签索引重建失败：先备份；迁移脚本幂等。
- `no-store` 导致请求增多：局域网可接受；如影响性能可改为短时长 `private, max-age=60` 并记录。
- 回收站旧记录无媒体字段：按扩展名推断，避免恢复失败。

## T-032 前端混合列表、类型筛选与视频灯箱

### 目标与边界

#### 目标

图片与视频在同一网格展示，可筛选；视频可在灯箱播放或触发外部播放器；信息、回收站、多选、书签完整可用。

#### 范围内

- `Image` 类型、`mediaFilter` 状态与请求参数。
- 网格卡片角标/时长/比例/文案。
- 灯箱 `<video>`、错误兜底、工具栏。
- 信息弹窗、回收站角标、书签抽屉展示。
- 移动端交互。

#### 范围外

- 外部播放器深链细节（T-033）。
- 服务端缓存/接口（T-031）。

### 技术方案

#### 影响位置

- `web/src/stores/image.ts`、`web/src/stores/bookmark.ts`、`web/src/api/index.ts`
- `web/src/components/ImageGrid.vue`、`Lightbox.vue`、`ImageInfoDialog.vue`
- `web/src/pages/TrashPage.vue`
- `web/src/components/BookmarksDrawer.vue`
- 可能涉及 `TopBar.vue`/`Sidebar.vue` 文案

#### 实现说明

- `mediaFilter` 默认 `all`，持久化 key 如 `picgallery.mediaFilter`；切换时清空列表、选中、`nextCursor`、多选状态，重新请求。
- 网格顶部增加 segmented control；`small` 网格也保留角标，时长文本不占用信息区。
- 视频卡片：`<img>` 仍用 `/thumbnail`；绝对定位播放图标 + 时长徽标；不要为视频加载 `<video>` 元素。
- `imageAspectRatio`：宽高有效时用原值；视频未知时 `16 / 9`；图片未知保持 `4 / 3`。
- 灯箱：
  - `media_type` 分支渲染 `<video>`；`:poster` 使用 medium 缩略图。
  - `video` 的 `@error` 设置 `videoError=true`，显示错误层与外部播放器入口。
  - 图片专用控件（旋转、重置、裁剪）在视频下隐藏；灯箱工具栏按钮热区保持 ≥44px。
  - 切换上一张/下一张时销毁旧 `<video>`，避免后台继续请求；离开灯箱时暂停并清空 `src`。
  - `imageStyle` 的缩放/旋转只作用于图片；视频使用 `object-fit: contain`。
  - 快捷键：左右切换；空格播放/暂停；输入框或视频控件聚焦时不拦截。
- `ENABLE_PRELOAD` 分支：只预加载下一张图片；视频不预加载 raw，只保留封面。
- 信息弹窗：类型、时长（`mm:ss`）、分辨率、编码、大小、格式、修改时间、路径、收藏状态、所属文件夹。
- 回收站：视频卡片角标/时长；缩略图失败显示占位图；不增加灯箱播放。
- 书签抽屉：视频显示角标/时长；锚点缩略图使用 `/thumbnail`。
- 多选/批量：视频与图片共用；移动、删除、收藏、重命名接口不变。
- 空状态与状态栏文案改为“媒体”。

### 实施步骤

1. 扩展类型、store 与 API 参数。
2. 网格筛选控件与视频卡片。
3. 灯箱视频分支、错误层与工具栏。
4. 信息弹窗、回收站、书签抽屉。
5. 移动端与触屏验证。

### 验证与验收

- 混合列表显示视频角标与时长；筛选“视频/图片/全部”结果正确。
- H.264 MP4/WebM 在灯箱播放、暂停、拖动；关闭灯箱后请求停止。
- MKV 触发错误层，外部播放器入口可见。
- 视频收藏、移动、删除、重命名、信息、书签、多选与图片一致。
- 视频信息显示时长/编码；回收站显示封面与角标；恢复后仍在视频筛选下可见。
- 图片浏览、灯箱、多选、书签无回归。
- 390×844/360×800 无横向溢出；触屏按钮 ≥44px；无控制台 error。
- `npm run check`、`npm run build` 通过。

### 风险与恢复

- 视频元素占用内存：切换时销毁、离开暂停、清空 `src`。
- 自动书签在筛选切换时误写：切换时抑制自动进度，稳定后再更新。
- 视频封面比例导致布局抖动：显式 `aspect-ratio` 与 `width/height`。
- 旧缓存字段缺失：类型/时长显示占位，不阻塞渲染。

## T-033 跨平台外部播放器联动

### 目标与边界

#### 目标

不支持或用户偏好的视频可交给本地播放器；Android/iOS 不产生文件；桌面默认不产生视频副本。

#### 范围内

- `externalPlayer.ts` 工具函数。
- 桌面 M3U/复制地址、Android intent、iOS x-callback、`vlc://` 兜底。
- 入口在灯箱错误层与视频菜单。
- 平台提示与失败兜底。

#### 范围外

- 自定义协议注册、本地助手、浏览器扩展。
- 自动检测已安装播放器（Web 无法可靠枚举）。

### 技术方案

#### 影响位置

- 新增 `web/src/utils/externalPlayer.ts`
- `web/src/components/Lightbox.vue`（工具栏/错误层）
- 可选新增 `web/src/components/ExternalPlayerMenu.vue`

#### 实现说明

- `buildRawUrl` 使用 `location.origin`，保证开发代理/生产同源/LAN 地址一致。
- `copyPlayUrl` 使用 `navigator.clipboard.writeText`，失败回退 `textarea + execCommand`。
- `downloadM3U`：
  - 内容 `#EXTM3U\n#EXTINF:-1,<name>\n<rawUrl>\n`；
  - `Blob` 类型 `audio/x-mpegurl`；`a.download = <safeName>.m3u`；
  - 点击后 `setTimeout(() => URL.revokeObjectURL(url), 1000)`；
  - 仅桌面端显示；移动端不生成文件。
- Android：
  - `intent://<host[:port]><path>#Intent;scheme=http;type=video/*;package=org.videolan.vlc;end`
  - **端口处理**：用 `new URL(rawUrl)` 解析后取 `url.host`（**含端口**，如 `192.168.1.10:5000`）拼入 intent URL，**禁止**只取 `url.hostname`（丢失端口会连到 80 端口静默失败）；`url.port` 为空（默认 80/443）时不写端口。`scheme=http/https` 跟随 `url.protocol`。
  - 验收须覆盖非标端口：局域网 `http://<ip>:5000` 与开发 `:5173` 的深链均能正确带端口。
  - 可选 `S.title=<encoded>`；不使用 download 动作。
  - 点击后 `window.location.href = intentUrl`；无 VLC 时提示复制地址。
- iOS：
  - `vlc-x-callback://x-callback-url/stream?url=<encoded rawUrl>`。
  - 点击后同步跳转；不使用 `download`。
  - 兜底 `vlc://<rawUrl>` 仅在 x-callback 失败/用户选择时使用，并在文档标注版本差异。
- 通用入口顺序：
  - 复制播放地址（所有平台）
  - 用 VLC 打开（Android/iOS，按平台显示）
  - 下载播放列表（桌面）
  - 下载原文件（所有平台，明确提示大小）
- 失败/未安装提示不阻断；保留手动 VLC “网络串流”说明。
- 不在页面加载时生成 M3U；仅在用户点击时生成。

### 实施步骤

1. 实现平台检测与 URL 构造工具。
2. 灯箱视频菜单/错误层接入。
3. 桌面 M3U 下载与 Blob 回收。
4. Android/iOS 深链与兜底提示。
5. 真机验证（用户协助）。

### 验证与验收

- 桌面：复制地址可用；M3U 下载后 VLC 可打开并流式播放；无视频文件下载；M3U 仅文本。
- Android Chrome + VLC：点击“用 VLC 打开”直接进入 VLC 并播放；拖动正常；无文件产生。
- Android 深链端口正确：局域网非标端口地址（如 `http://192.168.x.x:5000`、开发 `:5173`）生成的 intent URL 保留端口；默认端口（80/443）不写多余端口。
- Android Firefox：显示复制地址兜底，不报错。
- iOS Safari + VLC：点击“用 VLC 打开”弹出确认并进入 VLC 播放；使用 stream 不下载；复制地址可用。
- 未安装 VLC：提示并复制地址，不出现死链。
- M3U Blob URL 在下载后被回收；无内存泄漏。
- 不在视频列表加载时产生 M3U 或视频下载。

### 风险与恢复

- VLC 版本/平台差异：以复制地址为最终兜底；文档说明手动“网络串流”。
- Safari 拦截异步跳转：深链必须同步触发。
- Android 非 Chromium：降级复制地址。
- 深链 URL 含未编码字符：统一 `encodeURIComponent`；文件名单独编码。

## T-034 联调、真机验证与文档同步

### 目标与边界

#### 目标

完成端到端验证、跨平台真机验证、质量门控与文档回写；确认无客户端视频缓存残留。

#### 范围内

- API/浏览器/局域网/真机验证。
- 缓存与垃圾清理验证。
- `py_compile`、`npm run check`、`npm run build`。
- 更新 `dev-info.md`、架构文档、CHG/进度/INDEX。

#### 范围外

- 生产副本同步（按既有约定暂缓）。
- 权限整改。

### 实施步骤

1. 生成测试视频（H.264 MP4、VP9 WebM、H.264 MKV、可选 HEVC）。
2. 混合目录扫描、封面、筛选、灯箱、管理操作、书签、回收站。
3. Range/seek、MIME、no-store、blob 回收、临时目录清理。
4. 桌面 + Android + iOS 真机验证；记录设备/浏览器/播放器版本。
5. 静默检查与构建；更新文档与进度。

### 验证与验收

- 全部验收标准见本文“验收标准”节。
- 真机无法自动化的部分由用户协助，记录实际结果；未验证项标注。
- 构建通过；控制台无 error；现有图片功能无回归。
- 生产 5000 不受影响；生产配置/数据库未读写。

### 风险与恢复

- 真机不可用：记录未验证项，不宣称通过；保留复制地址兜底。
- 局域网限制：确认客户端与服务器同网段、5000 端口可达。
- 回滚：代码变更可回退；数据库新增字段为增量，旧版本代码可忽略；封面缓存可删除重建。

## T-035 视频播放交互增强（P0）

### 目标与边界

#### 目标

复用灯箱作为播放舞台，但把视频交互从图片逻辑中分离：点击不被误认为“隐藏界面”、键盘可快进快退、长视频可续播、移动端控件不压住画面。

#### 范围内

- 视频模式点击语义与控件自动隐藏。
- 视频键盘映射（播放/暂停、±5s、音量、静音）。
- localStorage 续播位置与“继续播放”提示。
- 视频工具栏收敛（播放器/收藏/更多/关闭）与底部控制条。

#### 范围外

- 倍速、画中画、缓冲态、错误重试、比例占位（P1）。
- 服务端播放进度、字幕、播放列表、独立视频详情页。

### 技术方案（轻量 5B）

- 点击：根容器在 `video-mode` 下不再隐藏 UI；点击画面仅刷新控件，播放/暂停交给原生控件；图片模式保持原 `toggleUI`。
- 自动隐藏：播放中静止 2.5s 隐藏工具栏、底部条、元数据与左右切换；鼠标移动/触控/按键恢复；暂停与错误层常显。
- 键盘：Space 播放/暂停；←/→ ±5s；Shift+←/→ 切换媒体；↑/↓ 音量；M 静音；焦点在 `<video>` 时让原生控件处理方向键与空格。
- 续播：`picgallery.videoPosition.<id>` 按秒保存；打开时位置 >5s 且 <95% 显示“从 mm:ss 继续播放”，8s 未操作自动消失；播放结束清除。
- 工具栏：视频只保留“本地播放器 / 收藏 / 更多 / 关闭”，更多内含信息、底部信息、重命名、移动、书签、删除；图片工具栏保持原样。
- 布局：视频最大高度预留控件空间；底部条（-10s、播放/暂停、+10s、时间、静音、全屏）居中显示，移动端热区 44px。

### 验证与验收

- 视频工具栏为 4 个入口，底部条 5 个按钮并显示 `当前 / 总时长`。
- 播放 2.5s 后工具栏与底部条自动隐藏（opacity 0），鼠标移动恢复；暂停时常显。
- ←/→ 实测 +5.02s；M 静音；↑ 取消静音；Space 暂停；位置按秒写入 localStorage。
- 关闭后重开同视频显示“从 0:08 继续播放”，点击后从 9s 播放且提示消失。
- 图片灯箱仍显示旋转/重置且无视频控件；503×847 视口无横向溢出，工具栏与底部条均在视口内。
- `npm run check`、`npm run build` 通过；console 无 error/warn。

## T-036 视频播放体验增强（P1）

### 目标与边界

#### 目标

补齐长视频与弱网场景的体验：首帧前不跳变、缓冲有反馈、可调速、可画中画、失败可重试。

#### 范围内

- 视频舞台按数据库宽高设置 `aspect-ratio`，首帧前即占位。
- 缓冲中浮层（`waiting`/`stalled` 显示，`playing`/`canplay`/`seeked` 隐藏）。
- 倍速（0.5×~2×）与当前速率标记。
- 画中画入口（不支持时提示）。
- 错误层“重试”按钮（重新挂载 `<video>`）。

#### 范围外

- 字幕、播放列表、章节、跨设备续播。
- 服务端转码/HLS。

### 技术方案

- `.video-stage` 使用 `--video-ar`（`width/height`，缺省 16:9）设置 `aspect-ratio`，宽度按 `(100dvh - 保留高度) * 比例` 约束，视频 `width/height:100%` + `object-fit:contain`。
- 缓冲状态由 `<video>` 的 `waiting/stalled/canplay/playing/seeked` 事件驱动，浮层用 `role="status"` 与 `aria-live="polite"`。
- 播放设置下拉：6 档倍速、画中画、全屏；切换倍速写入 `video.playbackRate`，非 1× 时在时间旁显示标记。
- 画中画调用 `requestPictureInPicture`/`exitPictureInPicture`，异常与不支持时用消息提示。
- 错误重试：清除 `videoError` 让 `<video>` 重新挂载并 `load()`，配合 `no-store` 重新发起 Range 请求；续播位置仍由 `loadedmetadata` 读取。

### 验证与验收

- 舞台 CSS `aspect-ratio` 为 `1.77778 / 1`，实际宽高比 1.778，首帧前不跳变。
- 播放设置菜单含 `0.5×/0.75×/1×/1.25×/1.5×/2×/画中画/全屏`；选择 1.5× 后 `playbackRate=1.5`、时间旁显示 `1.5×`。
- 派发 `waiting` 显示“缓冲中…”，`canplay` 后消失。
- FLV 错误层含“重试”，点击后重新挂载并再次进入错误层（格式不支持属预期）。
- 503×847 视口无横向溢出，舞台、工具栏、底部条均在视口内；图片灯箱无视频控件。
- `npm run check`、`npm run build` 通过；console 无 error/warn。

## T-037 离线无损转封装脚本

### 目标与边界

#### 目标

为浏览器不支持容器、但编码本身兼容（H.264 + AAC/MP3）的视频提供离线转封装工具，输出 MP4 后重新扫描即可在浏览器播放；不做真转码，不进入 Web 运行时。

#### 范围内

- 新增 `scripts/sql-script/remux_videos.py`。
- 支持按文件夹/数量筛选、输出目录、dry-run、`--replace`（需 `--yes`）。
- 输出前检查编码与音轨兼容性，输出后 ffprobe 校验并清理失败产物。

#### 范围外

- HEVC/AV1 等真转码（耗时数量级更高，仍走外部播放器）。
- Web 端转码接口、任务队列、服务端临时副本。

### 技术方案

- 查询 `images` 中 `media_type='video'` 且容器属于 FLV/MKV/AVI/WMV/MOV 的记录。
- 仅当 `video_codec='h264'` 且 `audio_codec` 为 `aac`/`mp3`/无音轨时处理；其他打印跳过原因。
- `ffmpeg -v error -nostdin -i src -map 0:v:0 -map 0:a? -c copy -movflags +faststart -n out`；超时默认 1800s。
- 输出默认与源同目录同名 `.mp4`，重名自动加 `_1`；`--output-dir` 可集中输出。
- 失败或 ffprobe 校验非 h264 时删除半成品；`--replace --yes` 在校验通过后删除源文件。
- 脚本不写数据库，完成后提示重新扫描受影响文件夹。

### 验证与验收

- 真实库 dry-run：文件夹 28 的 10 个 FLV 全部为候选，预计输出 13.84 GiB，无跳过项。
- 小样本实测：4 秒 FLV 0.1s 完成，输出 MP4 为 h264+aac、时长 4.04s。
- HEVC 样本 dry-run 正确跳过并提示“需真转码”。
- `--replace --yes` 实测：输出校验通过后删除源文件。
- 6.4GB 4K FLV 实测转封装 48.6s，输出 6.41GB；4K 真转码 10s 需 5.6s（x264）/4.41s（nvenc），折算 1 小时约 26~33 分钟。
- `py_compile` 通过；脚本不修改 Web 运行时与生产环境。

## 验收标准（汇总）

1. 开发库迁移成功，存量图片 `media_type='image'`，无数据丢失；生产库未改动。
2. 混合文件夹扫描后，图片与视频均入库；视频时长/宽高/编码正确；旋转视频比例正确。
3. 视频封面生成成功；失败返回共享占位图；回收站视频有封面；封面缓存随删除/移动/修改/对账清理。
4. `GET /api/images?media_type=video` 与书签恢复筛选正确；图片/视频 total 与分页无回归。
5. 视频 raw 返回正确 MIME、206 Range、`Cache-Control: no-store`；浏览器与本地播放器均可拖动。
6. 视频支持收藏、移动、删除/恢复、重命名、搜索、多选、信息、书签；恢复后类型与时长不丢失。
7. 灯箱可播放 H.264 MP4 与 VP9 WebM；不可播格式显示错误层与外部播放器入口。
8. 桌面复制地址/M3U、Android VLC intent、iOS VLC x-callback 均按预期；无自动视频下载与 M3U Blob 残留。
9. 客户端不产生视频副本；浏览器视频缓存被 `no-store` 抑制；服务端无视频副本、临时文件为空、`prune_cache` 可用。
10. `py_compile`、`npm run check`、`npm run build` 通过；控制台无 error；现有图片功能无回归。

## 验证计划

| 验证项 | 方法 | 通过标准 |
|--------|------|----------|
| 数据迁移 | 启动后 `PRAGMA table_info` / `index_list` | 新字段/索引存在；存量行默认 image |
| 混合扫描 | 临时目录含 jpg/mp4/webm/mkv | `media_type`、时长、宽高、编码正确 |
| 封面 | 请求 `/thumbnail?size=small/medium` | WebP 封面；失败占位图；无原视频回退 |
| 筛选 | `media_type=image/video/all` | 结果与 total 正确；分页无重复 |
| Range | `curl -r 0-1023 -D -` | 206、Accept-Ranges、Content-Range |
| 缓存头 | DevTools/响应头 | 视频 `Cache-Control: no-store`；图片保持缓存 |
| 浏览器播放 | MP4/WebM，拖动/暂停/关闭 | 播放正常；关闭后请求停止 |
| 不可播 | MKV/HEVC | 显示错误层；外部入口可用 |
| 管理操作 | 收藏/移动/删除/恢复/重命名/多选/书签 | 与图片一致；恢复后媒体字段保留 |
| 回收站 | 视频删除、缩略图、恢复 | 封面/角标；恢复后仍为视频 |
| 缓存清理 | 删除/移动/修改/对账后检查 cache | 无孤儿封面；`prune_cache --dry-run` 正确 |
| 临时文件 | 抽帧成功/失败后检查 `cache/tmp` | 为空；启动清理有效 |
| 桌面联动 | Windows/macOS + VLC | 复制地址/M3U 可播放；无视频下载 |
| Android | Chrome/Edge + VLC | intent 直接播放；无文件；拖动正常 |
| iOS | Safari + VLC | x-callback stream 播放；无下载；复制地址兜底 |
| 移动端布局 | 390×844 / 360×800 | 无横向溢出；热区 ≥44px |
| 质量门控 | `py_compile`、`npm run check`、`npm run build` | 通过 |

## 风险与回滚

- **编码兼容**：以 `<video>` 实际错误为准；外部播放器兜底；不维护静态编码黑名单。
- **深链差异**：iOS/Android 版本与浏览器差异大；复制地址为最终兜底；真机未验证项如实标注。
- **客户端缓存**：浏览器 no-store 可抑制正文缓存，但外部播放器自身缓存不可控；本项目不生成视频副本。
- **FFmpeg 路径**：Windows 服务环境使用绝对路径；启动检查；失败降级占位图。
- **扫描/预生成 CPU**：视频封面低并发、可关闭；提供分批脚本。
- **权限缺口**：本轮不处理；视频 URL 与图片 URL 同等可被按 ID 读取；另立项。
- **回滚**：代码回退；数据库新增字段与默认值不影响旧代码；删除新增封面缓存即可恢复空间。

## 调研依据

- VideoLAN Wiki, Documentation:iOS（x-callback-url 与 `vlc://` 版本支持表）：https://wiki.videolan.org/Documentation:IOS
- VideoLAN Wiki, Android Player Intents（`ACTION_VIEW`、`org.videolan.vlc`、`video/*`）：https://wiki.videolan.org/Android_Player_Intents/
- VLC for iOS Documentation, Media Synchronization / Open Network Stream：https://docs.videolan.me/vlc-user/ios/3.X/en/gettingstarted/media_synchronization.html
- 本机实测：Flask 3 + Werkzeug 3 `send_file(conditional=True)` Range 返回 206；FFmpeg/ffprobe N-124437 可用（`D:\FFmpeg`）。

> 说明：Android 端采用 `intent://`，iOS 端以 `vlc-x-callback://`（`stream`）为主路径；`vlc://` 因版本差异仅作兜底。该结论以 VideoLAN 文档与本机环境为准，不采用“移动端以 M3U 为主”的方案。

## 阶段完成结果

- **实际产出**：`images` 新增 `media_type`/`duration`/`video_codec`/`audio_codec`，`image_bookmarks` 新增 `media_filter` 并重建自动书签唯一索引；新增 `server/app/services/video.py`；扫描器媒体类型判定、ffprobe 元数据与旋转处理；`thumbnail.py` 视频封面分支、共享占位图、500ms 锁超时与后台队列；`prebuild_thumbnails.py --media`；新增 `scripts/sql-script/prune_cache.py`；接口 `media_type` 筛选、书签 `media_filter`、raw MIME 与 `no-store`、回收站媒体字段与恢复；前端筛选控件、视频角标、灯箱 `<video>` 与错误层、信息/回收站/书签展示；新增 `web/src/utils/externalPlayer.ts` 与灯箱播放器菜单；T-035 视频播放交互（点击语义、自动隐藏、键盘、续播、工具栏收敛与底部控制条）；T-036 视频播放体验（比例占位、缓冲提示、倍速、画中画、错误重试）；T-037 离线无损转封装脚本。
- **方案偏差**：
  1. 未采用“移动端 M3U 主路径”，改为 Android `intent://`、iOS `vlc-x-callback://.../stream`，M3U 仅桌面可选（与 ADR-001 一致）。
  2. 新增配置键 `VIDEO_PROBE_TIMEOUT`（默认 10s），用于限制扫描阶段 ffprobe 超时。
  3. 新索引 `idx_image_bookmarks_auto`、`idx_images_media_type` 由 `migrate_db()` 创建，而非写在 `schema.sql`，否则旧库在补列前执行会报 `no such column`。
  4. 视频封面失败与占位图统一输出 JPEG（`placeholder/video.jpg`），避免在 WebP 编码失败时再引入依赖。
- **外溢发现**：
  1. Chrome 可直接播放 H.264 封装的 MKV（实测无 error），因此未把 MKV 视为必然不可播；错误层以 `<video>` 的 `error` 事件为准（坏文件已实测触发）。
  2. 回收站缩略图原实现会回退原文件，视频场景会传输整个文件；已改为视频返回占位图或 404。
  3. FLV 容器（H.264/AAC）在所有现代浏览器中均不可播，与分辨率无关；用户 4K 素材为 FLV，只能走本地播放器交接。
  4. Bug-006：`acquire_poster_slot()` 阻塞获取后未返回 `True`，预生成线程把已获取误判为失败，泄漏信号量并永久占用 `_prebuild_lock`，导致所有视频封面退化为占位图；已修复并用 `py-spy` 栈与重扫日志验证。
- **遗留项**：
  1. Android/iOS 深链未做真机验证，需用户协助；复制播放地址为兜底。
  2. 媒体读取接口鉴权缺口按用户决定另立项。
  3. 视频重命名改扩展名后 MIME 可能回退 `application/octet-stream`（已知限制）。
  4. 生产副本未同步；同步时需确认部署机存在 `D:/FFmpeg`。
- **验收摘要**：迁移后 21,159 行图片、3 条书签完整；临时混合目录 6 个文件扫描正确（含 90° 旋转宽高交换）；MP4/WebM/MKV 生成 WebP 封面，坏文件返回占位图；API 40 项断言通过（筛选/分页/窗口/书签/Range 206/MIME/no-store/回收站往返）；浏览器筛选、角标、MP4 播放、错误层与图片灯箱回归通过，console 无 error；T-035 播放交互（自动隐藏、±5s、静音、续播、移动端布局）实测通过；T-036 比例占位 1.778、倍速 1.5× 生效、缓冲浮层与重试实测通过；T-037 转封装脚本 dry-run/apply/skip/replace 实测通过（4 秒样本 0.1s，6.4GB 4K 48.6s）；`py_compile`、`npm run check`、`npm run build` 通过；开发库已恢复并通过 `prune_cache.py --dry-run`。
- **关联记录**：`CHG-20261025-04`、`CHG-20261025-05`、`CHG-20261025-06`、`CHG-20261025-07`、`ADR-001`
