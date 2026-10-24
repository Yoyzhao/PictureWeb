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
