# M2 / 性能与 UI 优化 — 阶段任务文档

- **里程碑**：M2 前端性能与 UI 优化
- **阶段**：前端渲染性能 + 后端配套 + UI 重构（5C/5D 垂直切片）
- **状态**：已完成，待用户验收
- **关联 CHG**：`CHG-20261024-02`、`CHG-20261024-04`、`CHG-20261024-05`、`CHG-20261024-06`（`docs/tech/功能变更.md`）
- **更新日期**：2026-10-24

## 任务索引

| 任务ID | 名称 | 状态 | 负责人 | 主要产出 |
|--------|------|------|--------|----------|
| T-008 | 虚拟瀑布流滚动性能优化 | 已完成 | main | `VirtualWaterfall.vue` 二分查找、rAF 合并、原地追加、`itemsVersion` |
| T-009 | 图片数据层与搜索性能优化 | 已完成 | main | `stores/image.ts` 防抖、取消、去重、原地 push；`api/index.ts` signal |
| T-010 | UI 重构与性能优先动画 | 已完成 | main | 全局 token、侧边栏/顶栏/卡片/灯箱/回收站/管理页 |
| T-011 | 后端 10 万级配套优化 | 已完成 | main | 索引、WAL、`per_page` 上限、图片缓存头、公开 settings 接口 |
| T-012 | 验证与文档同步 | 已完成 | main | 类型检查、构建、浏览器冒烟、性能文档与进度 |
| T-017 | 首屏指标与构建体积优化（第二轮） | 已完成 | main | aspect-ratio 消除 CLS、首屏图片优先级、Element Plus 按需引入、字体精简、滚动防抖与 buffer 调整 |
| T-018 | 按需加载与缩略图 WebP 化（第三轮） | 已完成 | main | Admin/Trash/Lightbox 异步加载、WebP 缩略图、存量迁移开关、回收站缩略图修复 |
| T-019 | 图片卡片悬停与选中态修复 | 已完成 | main | 移除 item paint containment、hover 抬升+阴影+微放大、选中 2px 外环 |
| T-020 | 缩略图预生成覆盖修复与解码优化 | 已完成 | main | 以当前缓存文件判断缺失、修正旧路径记录、JPEG draft 降采样 |
| T-021 | 触屏与移动端适配 | 已完成 | main | 无 hover 操作可达、抽屉侧边栏、16px 输入、响应式弹窗、dvh、灯箱手势 |
| T-022 | 回收站、移动与收藏逻辑修复 | 已完成 | main | 权限校验、移动/删除成功 ID、恢复校验、显式清理孤儿记录 |

## 性能分析结论

详见 `docs/tech/features/frontend-performance-前端渲染性能与UI优化.md`。核心结论：

1. 优化前虚拟列表滚动为 O(n) 全量过滤；分页追加为 O(n) 数组复制，累计 O(n²)；这是 10 万级最先放大的两个瓶颈。
2. 搜索逐字符请求、无取消/乱序保护，会造成请求风暴与结果错乱。
3. 灯箱原图预加载无体积上限，大图预加载浪费带宽与解码内存。
4. 后端缺少排序索引与 WAL，`per_page` 无上限，图片无缓存头。
5. 剩余主要瓶颈：`LIKE '%q%'` 搜索、无限滚动最终累积全部已加载项、缩略图同步按需生成。

## 实施记录

### T-008 虚拟瀑布流

- `visibleItems` 使用 `lowerBoundByTop`/`upperBoundByTop` 二分查找，再补齐与视口起始位置重叠的前序项。
- 布局追加原地 `push` + `triggerRef`；新增 `itemsVersion` prop 解决同数组原地追加的 prop 感知问题。
- 滚动监听 `passive` + `requestAnimationFrame` 合并；内容不足一屏时自动触发 `load-more`。
- 移除 `transition-group` 与全量 `will-change`，使用 `contain: layout paint style`。
- 新增 `metaHeight` 参数；0×0 尺寸回退 4:3。

### T-009 数据层

- `fetchImages` 使用 `AbortController` + 请求序号，取消旧请求并忽略乱序响应。
- `watchDebounced(searchQuery, 300)`；文件夹/排序/收藏即时响应。
- 分页 `push + triggerRef + imagesVersion`；按 ID 去重；`total` 达到后不再请求。
- 选中判断改 `Set`；重置清空选中；收藏/重命名原地更新。

### T-010 UI

- 全局：新增圆角/阴影/动效/focus/reduced-motion token；修复 `--bg-body`、`--bg-secondary`。
- 侧边栏：按钮语义、圆角导航、active 态、文件夹操作图标组、登录 loading/回车、用户卡与头像。
- 顶栏：搜索清空/Esc/焦点环、按钮 36px 点击区。
- 图片网格：骨架屏、卡片统一视觉、状态栏跟随侧边栏宽度、玻璃背景、`decoding=async`、大网格 medium 缩略图。
- 灯箱：预加载体积/数量限制、定时器清理、图片淡入、rAF 滚轮缩放、条件 `will-change`、玻璃工具栏。
- 回收站/管理页：统一卡片、头部、标签页与表格样式；角色/权限中文标签。

### T-011 后端

- `schema.sql` + `migrate_db()` 新增 4 个索引。
- SQLite WAL / synchronous / cache_size / temp_store。
- `per_page` 限制 1–200，`page` 最小 1。
- 缩略图 `max-age=86400`，原图/下载 `max-age=3600`，启用条件请求。
- 新增 `GET /api/settings`（公开，仅返回 HOTKEYS + ENABLE_PRELOAD），修复匿名 401 控制台错误。

### T-017 首屏指标与构建体积优化（第二轮）

- `ImageGrid.vue` / `TrashPage.vue` 的 `<img>` 补齐 `width`/`height`/`aspect-ratio`，消除缩略图未预留尺寸导致的 CLS（0.184 → 0.00）。
- `VirtualWaterfall.vue` 透传 `index`；首屏前 15 张 `eager` + `fetchpriority=high`，LCPDiscovery 通过，LCP 生产预览 449 ms。
- `vite.config.ts` 接入 `unplugin-vue-components` + `ElementPlusResolver`；`main.ts` 移除全量 Element Plus/样式/图标注册，仅保留 `ElLoading` 指令；JS 1,268.86 → 619.27 KB（gzip 212.8 KB），CSS 392.26 → 234.44 KB（gzip 34.7 KB）。
- MiSans 由 4 字重（约 19.5MB）精简为 Regular(400) + Semibold(600)（约 9.7MB），首屏总传输 20.15 → 10.26 MB。
- 容器 resize 120ms、列宽/layout 80ms 防抖；`buffer` 1000 → 600；状态栏移除 `backdrop-filter`；预览模式增加 4173 `/api` 代理。
- 生产预览实测：滚动 111.2 fps、0 长任务；LCP 449 ms、CLS 0.00。

### T-018 按需加载与缩略图 WebP 化（第三轮）

- `HomePage.vue` 使用 `defineAsyncComponent` 加载 `AdminPage` / `TrashPage` / `Lightbox`；首屏 JS 619.27 → 467.54 KB（gzip 164.85 KB），首屏 CSS 234.44 → 128.16 KB（gzip 20.67 KB）；管理页、表格、灯箱、回收站均生成独立 chunk。
- 浏览器验证：初始加载无 `Lightbox-*.js`，点击图片后按需请求且状态 200；CLS 0.00，灯箱可正常打开/关闭。
- 缩略图服务新增 `THUMBNAIL_FORMAT`（默认 `webp`），读取优先当前格式、回退存量 jpg；写入使用 WebP `method=4`，DB 记录改为 upsert。
- `generate_thumbnail(..., force=True)` 与 `prebuild_thumbnails.py --rebuild` 支持存量格式迁移，迁移后删除旧 jpg，避免双份缓存；本地迁移 200 张验证通过（jpg 422→235、webp 2→202）。
- 同图对比（quality=90）：300px WebP 比 JPEG 小 22.7%，800px 小 31.2%。
- 回收站缩略图改用 `generate_thumbnail_from_path` 缓存到 `cache/trash/<size>/<id>.webp`，修复此前把文件路径当作 image_id 导致回退原图的问题；回收站网格按列宽请求 small/medium，恢复/永久删除时清理缓存。
- 缩略图 `size` 参数收敛为 `small`/`medium` 白名单，避免任意值拼接缓存路径。

### T-019 图片卡片悬停与选中态修复

- `VirtualWaterfall.vue` 的 `.virtual-waterfall-item` 从 `contain: layout paint style` 改为 `contain: layout style`，避免 hover 抬升与外侧阴影/描边被 paint containment 裁切。
- `ImageGrid.vue`：hover 去掉 1px 主色边框，改为抬升 2px + `--shadow-md` + 图片 `scale(1.02)`；选中态改为 `0 0 0 2px var(--primary), var(--shadow-sm)`，并补充选中+hover 的阴影组合。
- `TrashPage.vue` 同步相同方案，回收站卡片 hover 与选中表现一致。
- 验证：浏览器截图确认 hover 四周完整、无蓝边，选中 2px 环上下左右可见，控制台无 error；滚动 109.5 fps、0 长帧。

### T-020 缩略图预生成覆盖修复与解码优化

- 审计：`images` 21,159，DB `thumbnails` 记录 1,670 small，但当前 `data/cache/small` 仅 424 个文件；1,277 条记录指向旧缓存 `F:\_piccache`，旧预生成按 DB 记录判断缺失，导致当前缓存空缺被跳过。
- `prebuild_thumbnails` 非 force 分支改为遍历 `images` 并按当前 `CACHE_DIR` 文件是否存在判断，生成后 upsert 修正 DB 路径。
- `_save_thumbnail` 对 JPEG 调用 `Image.draft('RGB', size)` 降采样解码；A/B 最大图 189.6→127.4ms。
- 修复项验证：`prebuild_thumbnails(limit=700)` 生成 496 张（70s），当前 small 缓存 424→920，DB 旧路径 1,278→772。
- 当前覆盖率 4.4%（930/21,159），全量约需 1 小时；未在本次自动执行。

### T-021 触屏与移动端适配

- 触屏无 hover：`ImageGrid` / `TrashPage` 在 `@media (hover: none)` 下常显 44px 选择热区与操作按钮；回收站选中后显示还原/删除。
- 移动端侧边栏改为 `position: fixed` 抽屉（220px），主内容不再被压缩；新增 `.sidebar-backdrop`，点击关闭。
- 全局移动端规则：输入框 16px（避免 iOS 聚焦缩放）、Element 弹窗宽度 `calc(100vw - 32px)` 且限高 84dvh。
- 高度改用 `100dvh`：`HomePage`、`Lightbox`、`TrashPage` 增加 `100vh` 回退。
- 灯箱：`touch-action: none`、禁止文本选择、移动端工具栏按钮 44px，左右按钮继续隐藏（手势切换）。
- 滚动容器（图片网格/回收站/管理页）增加 `overscroll-behavior: contain`；TopBar 移动端按钮 40px。
- 验证：390×844 触屏模拟下选择、操作菜单、侧边栏抽屉、弹窗宽度、灯箱工具栏均通过；桌面 hover 行为未回归。

### T-022 回收站、移动与收藏逻辑修复

- 新增 `_folder_access` / `_image_access` / `_path_in_use`：管理员与文件夹所有者全权限；收藏校验读取权限；移动校验源与目标 `write`；删除校验 `delete`；重命名校验 `rename`。
- 移动：目标目录必须存在，同目录跳过，磁盘或 DB 同名自动加后缀，返回 `moved_ids` 与逐项错误。
- 删除：返回 `deleted_ids`、`trashed`、`missing_ids`、`errors`；文件缺失时只删除索引；显式删除收藏与标签，避免 `foreign_keys` 关闭导致孤儿记录。
- 回收站恢复：校验原文件夹存在且可写，metadata 为空时按文件属性重建索引，恢复收藏/标签并返回 `restored_ids`。
- 文件夹删除与用户删除同步清理依赖记录；`PATCH` 禁止修改 `folder_id`，文件名禁止包含路径分隔符。
- 前端批量移动/删除只按成功 ID 移除；移动在“所有照片/收藏夹”视图不再误删本地项；恢复后自动刷新相册。
- 端到端验证：管理员完整流程、无权限用户 403、仅 write 权限用户可见/可收藏/可移动但不可删除、授予 delete 后可删除、同名冲突与回收站恢复收藏保留均通过。

## 验证汇总

| 验证项 | 方法 | 结果 |
|--------|------|------|
| 前端类型检查 | `npm run check` | 通过 |
| 前端构建 | `npm run build` | 通过（第二轮 619.27 KB；第三轮分包后见下方） |
| 首屏指标（生产预览） | Chrome DevTools MCP trace | LCP 402–696 ms（多次测量波动）、CLS 0.00 |
| 滚动（生产预览） | DevTools 帧率与长任务 | 111.2 fps、0 长任务 |
| 首屏分包 | `npm run build` | 初始 JS 467.54 KB（gzip 164.85 KB）；Admin/表格/Lightbox/Trash 独立 chunk |
| 按需加载 | 浏览器网络请求 | 初始无 Lightbox chunk；点击图片后加载 200 |
| 缩略图格式 | 同图 JPEG/WebP 对比 | 300px 减少 22.7%，800px 减少 31.2% |
| 回收站缩略图 | `generate_thumbnail_from_path` | webp 生成与清理通过 |
| 缩略图参数 | `?size=../../evil` | 回退 small，未产生越界目录 |
| 卡片 hover/选中 | 浏览器截图 | 无顶部裁切与 1px 蓝边；2px 选中环四周完整 |
| 滚动性能（修复后） | DevTools 滚动采样 | 109.5 fps、0 长帧 |
| FTS5 索引 | DB 审计 | docsize 21,159；3 个触发器；`ANIME-PI` 7 命中 |
| FTS5 接口 | 登录后 API | `ANIME-PI` 7；`PI`（LIKE）58；总列表 21,159 |
| 缩略图预生成修复 | `prebuild_thumbnails(limit=700)` | 生成 496 张/70s；当前缓存 424→920；旧路径 1,278→772 |
| JPEG 解码优化 | `Image.draft()` A/B | 最大图 189.6→127.4ms |
| 触屏选择/操作 | 390×844 模拟 | 选择框 44px、操作按钮可点、选中不开灯箱 |
| 移动端侧边栏 | 390×844 模拟 | 抽屉 220px、主内容 390px、遮罩可关闭 |
| 移动端弹窗 | 登录弹窗 | 358px（16~374），无横向溢出 |
| 灯箱触屏 | 计算样式 | `touch-action: none`、按钮 44px、工具栏可见 |
| 桌面回归 | 恢复桌面视口 | checkbox/overlay 隐藏、侧边栏 relative |
| 收藏/读取权限 | 无权限用户 | 私有列表 0；收藏/详情 403 |
| 移动权限与冲突 | 管理员 / write 用户 | 移动成功、同目录拒绝、同名自动加后缀 |
| 删除与回收站 | 管理员 | `deleted_ids/trashed` 正确；恢复后收藏保留 |
| 孤儿记录清理 | DB 计数 | 删除后 favorites/image_tags 归零；历史孤儿收藏清理 12 条 |
| 浏览器冒烟 | Chrome 浏览器自动化 | 首屏约 16 张卡片/总数 44；搜索、Lightbox、主题切换、滚动加载、侧边栏折叠均通过；控制台无 error |
| 分页上限 | `GET /api/images?per_page=1000` | 返回 `per_page=200` |
| 图片缓存 | thumbnail / raw 响应头 | `public, max-age=86400` / `public, max-age=3600` |
| 排序索引 | 测试库 23,851 行按 file_name 排序 | 约 2.5ms；新增索引存在 |
| SQLite 模式 | `PRAGMA journal_mode` | `wal` |
| 生产隔离 | 生产 5000 `/api/health` | 200，未部署本轮代码 |

## 遗留与后续

1. 未在 10 万张真实数据上做端到端压测；当前结论基于代码复杂度与 23,851 行测试库实测。
2. 后续建议：窗口化数据源、响应式图片/WebP 缩略图、管理页/Lightbox/裁剪器动态导入（Element Plus 已按需引入）、10 万真实数据压测。
3. 图片读取接口仍未做服务端鉴权（历史缺口）。
4. 生产更新按用户要求暂缓至开发完成后统一执行。
