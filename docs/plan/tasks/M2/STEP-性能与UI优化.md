# M2 / 性能与 UI 优化 — 阶段任务文档

- **里程碑**：M2 前端性能与 UI 优化
- **阶段**：前端渲染性能 + 后端配套 + UI 重构（5C/5D 垂直切片）
- **状态**：已完成，待用户验收
- **关联 CHG**：`CHG-20261024-02`（`docs/tech/功能变更.md`）
- **更新日期**：2026-10-24

## 任务索引

| 任务ID | 名称 | 状态 | 负责人 | 主要产出 |
|--------|------|------|--------|----------|
| T-008 | 虚拟瀑布流滚动性能优化 | 已完成 | main | `VirtualWaterfall.vue` 二分查找、rAF 合并、原地追加、`itemsVersion` |
| T-009 | 图片数据层与搜索性能优化 | 已完成 | main | `stores/image.ts` 防抖、取消、去重、原地 push；`api/index.ts` signal |
| T-010 | UI 重构与性能优先动画 | 已完成 | main | 全局 token、侧边栏/顶栏/卡片/灯箱/回收站/管理页 |
| T-011 | 后端 10 万级配套优化 | 已完成 | main | 索引、WAL、`per_page` 上限、图片缓存头、公开 settings 接口 |
| T-012 | 验证与文档同步 | 已完成 | main | 类型检查、构建、浏览器冒烟、性能文档与进度 |

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

## 验证汇总

| 验证项 | 方法 | 结果 |
|--------|------|------|
| 前端类型检查 | `npm run check` | 通过 |
| 前端构建 | `npm run build` | 通过（仍有 Element Plus 大 chunk 警告，非本次引入） |
| 浏览器冒烟 | Chrome 浏览器自动化 | 首屏约 16 张卡片/总数 44；搜索、Lightbox、主题切换、滚动加载、侧边栏折叠均通过；控制台无 error |
| 分页上限 | `GET /api/images?per_page=1000` | 返回 `per_page=200` |
| 图片缓存 | thumbnail / raw 响应头 | `public, max-age=86400` / `public, max-age=3600` |
| 排序索引 | 测试库 23,851 行按 file_name 排序 | 约 2.5ms；新增索引存在 |
| SQLite 模式 | `PRAGMA journal_mode` | `wal` |
| 生产隔离 | 生产 5000 `/api/health` | 200，未部署本轮代码 |

## 遗留与后续

1. 未在 10 万张真实数据上做端到端压测；当前结论基于代码复杂度与 23,851 行测试库实测。
2. 后续建议：窗口化数据源/keyset 分页、FTS5 trigram 搜索、缩略图预生成队列、响应式图片、前端代码拆分。
3. 图片读取接口仍未做服务端鉴权（历史缺口）。
4. 生产更新按用户要求暂缓至开发完成后统一执行。
