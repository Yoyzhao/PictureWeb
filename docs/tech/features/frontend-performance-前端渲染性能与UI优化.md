# 前端渲染性能与 UI 优化

- **状态**：活跃
- **关联 CHG/任务**：`CHG-20261024-02`、`CHG-20261024-04`、`CHG-20261024-05` / T-008 ~ T-012、T-017、T-018
- **所属里程碑**：M2 前端性能与 UI 优化
- **最后更新**：2026-10-24

## 需求摘要

在现有 PicGallery 前端（Vue 3 + 虚拟瀑布流 + Lightbox）上完成两件事：

1. 分析 10 万张图片规模下的渲染瓶颈，并落地高收益、可回退的优化；
2. 对侧边栏、顶栏、图片卡片、灯箱、回收站与管理页做一致性 UI 重构，并加入性能优先的动画。

不改页面主骨架、路由和核心交互路径；不引入新的 UI 框架或动画库。

## 性能分析（优化前）

### 前端

| 瓶颈 | 位置 | 影响 |
|------|------|------|
| 每次滚动过滤全部已加载项 | `VirtualWaterfall.vue` 的 `visibleItems` | O(n) / 滚动帧；加载到数万项后滚动明显卡顿 |
| 每次分页复制整个图片数组 | `stores/image.ts` 的 `images.value = [...images.value, ...data]` | 每页 O(n)，累计 O(n²)；10 万张时内存与主线程压力大 |
| 搜索每输入一个字符就请求 | `watch(searchQuery)` | 一次搜索触发多次列表 + count 查询 |
| 无请求取消/乱序保护 | `fetchImages` | 慢请求可能覆盖新筛选结果，造成重复项与抖动 |
| 卡片选中判断为数组线性查找 | `ImageGrid.vue` 的 `isSelected` | 选中数量大时每张可见卡片都做 O(n) 查找 |
| 虚拟列表项使用 `transition-group` + 全局 `will-change` | `VirtualWaterfall.vue` | 滚动时频繁进入/离开动画与图层提升，增加合成与布局开销 |
| 灯箱原图预加载无体积上限 | `Lightbox.vue` | 大图（10MB+）预加载占用带宽与解码内存；定时器不清理会预加载过期图片 |
| 缩略图/原图无 HTTP 缓存头 | 后端 `image.py` | 重复浏览时重复传输与解码 |
| 大网格仍用 300px 小图 | `ImageGrid.vue` | 大图网格模糊，或被迫加载原图 |

### 后端

| 瓶颈 | 位置 | 影响 |
|------|------|------|
| 缺少 `file_name` / `file_size` / `folder_id+modified_time` 索引 | `schema.sql` | 按文件名/大小排序或按文件夹筛选时全表扫描 + 排序 |
| SQLite 默认 journal 模式 | `utils/db.py` | 扫描写入与浏览读取并发时容易互相阻塞 |
| `per_page` 无上限 | `routes/image.py` | 恶意/误用大分页会一次性读取大量行 |
| 搜索使用 `LIKE '%q%'` | `routes/image.py` | 10 万级时无法命中索引，仍是主要剩余瓶颈 |

## 已实施优化

### 虚拟瀑布流（`VirtualWaterfall.vue`）

- 可见项改为**二分查找**定位区间，再向两侧补齐重叠项；滚动复杂度从 O(n) 降为 O(log n + 可见项)。
- 布局追加改为**原地 push + `triggerRef`**，不再每页复制完整布局数组。
- 新增 `itemsVersion` 信号，解决“同数组原地追加时子组件 prop 引用不变、无法感知长度变化”的问题。
- 滚动监听改为 `passive` + `requestAnimationFrame` 合并，每个渲染帧最多更新一次。
- 移除 `transition-group` 和全量 `will-change`，改用 `contain: layout paint style` 隔离布局。
- 新增 `metaHeight` 参数，让瀑布流预留高度与卡片实际标题区一致；宽高为 0 的图片回退到 4:3 比例。
- 列宽变化、容器 resize 时重排；内容不足一屏时自动请求下一页。

### 图片数据层（`stores/image.ts`）

- 分页追加改为原地 `push` + `triggerRef` + `imagesVersion`，避免 O(n²) 复制。
- 搜索使用 `watchDebounced` 300ms，文件夹/排序/收藏切换仍即时响应。
- 新增 `AbortController` 取消旧请求与请求序号保护，避免乱序响应污染列表。
- 按图片 ID 去重，防止分页重叠；加载完 `total` 后不再发起无意义请求。
- 重置时清空选中项与已加载 ID 集合；收藏/重命名改为原地更新。
- 删除/移动后同步清理已加载 ID 集合。

### 图片网格（`ImageGrid.vue`）

- 选中判断改用 `Set`，避免每张卡片线性查找。
- 大网格使用 `medium` 缩略图，中小网格使用 `small`。
- 图片统一 `loading="lazy" decoding="async"`。
- 首屏新增骨架屏；卡片改为统一圆角、边框、轻阴影与 `transform/opacity` 悬停动效。
- 底部状态栏改用 `--current-sidebar-width`，侧边栏折叠/移动端时不再错位；状态栏使用玻璃背景。
- 日期格式化提取为 `formatDate`，避免每张卡片重复创建两个 Date 对象。

### 灯箱（`Lightbox.vue`）

- 原图预加载增加 6MB 体积门槛；预加载 URL 集合上限 120；切换图片时清理全部定时器。
- 当前图使用 `decoding="async"` + `fetchpriority="high"`，加载完成后淡入。
- 滚轮缩放用 `requestAnimationFrame` 合并；`will-change` 只在缩放/平移时启用。
- 切换动画只使用 `transform + opacity`，移除 `transition: all`。
- 工具栏改为玻璃胶囊容器，按钮统一尺寸与状态反馈。

### 侧边栏 / 顶栏 / 回收站 / 管理页

- 全局新增圆角、阴影、动效、焦点环与 `prefers-reduced-motion` 支持；修复 `--bg-body`、`--bg-secondary` 未定义导致的透明背景。
- 侧边栏：导航项改按钮语义、统一圆角与 active 态；文件夹操作按钮改为头部图标组；登录按钮增加 loading、回车提交、自动填充属性；头像与用户卡重做。
- 顶栏：搜索框加清空按钮、Esc 清空、焦点环；操作按钮统一 36px 点击区与 hover 背景。
- 回收站：卡片与图片网格统一视觉；选中判断改 Set；日期异常兜底；头部间距与标题层级统一。
- 管理页：新增副标题；标签页/表格/设置分区统一圆角、边框与表头色；角色与权限类型显示中文。

### 后端配套

- `schema.sql` / `migrate_db()` 新增 `idx_images_folder_modified`、`idx_images_file_name`、`idx_images_file_size`、`idx_folders_public`。
- SQLite 连接启用 `journal_mode=WAL`、`synchronous=NORMAL`、`cache_size` 与 `temp_store=MEMORY`。
- `GET /api/images` 的 `page` 最小为 1，`per_page` 限制在 1–200。
- 缩略图返回 `Cache-Control: public, max-age=86400`，原图/下载 `max-age=3600`，并启用条件请求。
- 新增公开接口 `GET /api/settings`，只返回 `HOTKEYS` 与 `ENABLE_PRELOAD`；修复匿名用户访问 `/api/admin/settings` 产生 401 控制台错误。
- FTS5 搜索、keyset 游标分页与缩略图后台预生成见 `search-pagination-thumbnails-搜索分页与缩略图优化.md`。

### 第二轮：首屏指标与构建体积（2026-10-24 下午）

在首轮基础上按 DevTools 追踪结论继续优化，重点解决 CLS、LCP 发现时机与首屏传输体积：

- **CLS 归零**：DevTools 定位到缩略图未预留尺寸导致卡片 `.img-info` 位移（CLS 0.184）。`ImageGrid.vue` / `TrashPage.vue` 的 `<img>` 绑定 `width`/`height` 与 `aspect-ratio`，缺失尺寸时回退 `4 / 3`；虚拟列表把 `index` 透传给卡片。
- **LCP 优先级**：首屏前 15 张图由 `loading="lazy"` 改为 `eager` + `fetchpriority="high"`，其余保持 `lazy` + `decoding="async"`，LCPDiscovery 检查通过。
- **Element Plus 按需引入**：`vite.config.ts` 接入 `unplugin-vue-components` + `ElementPlusResolver`（`importStyle: 'css'`，生成 `src/components.d.ts`）；`main.ts` 移除全量 `ElementPlus` 注册、全量 CSS 与全量图标注册，只保留 `ElLoading` 指令及其样式，避免模板中 `el-*` 组件因未注册而失效。
- **字体精简**：MiSans 从 4 个中文字重（Regular/Medium/Semibold/Bold，约 19.5MB）收敛为实际使用的 Regular(400) + Semibold(600)（约 9.7MB）；CSS 中 `500` 字重回落到 400/600。
- **滚动细节**：`VirtualWaterfall.vue` 容器 resize 防抖 120ms、列宽/layout 防抖 80ms；`buffer` 从 1000 降为 600，减少常驻 DOM 数量；底部状态栏移除 `backdrop-filter`，避免滚动时重复合成。
- **预览代理**：`vite.config.ts` 的 `preview` 增加 4173 端口 `/api` 代理，便于用生产构建做性能测量。

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| 首屏 JS | 1,268.86 KB（gzip 410 KB） | 619.27 KB（gzip 212.8 KB） |
| 首屏 CSS | 392.26 KB（gzip 55.6 KB） | 234.44 KB（gzip 34.7 KB） |
| 字体 | 4 字重 ≈19.5 MB | 2 字重 ≈9.7 MB |
| 首屏总传输（开发服务器） | 20.15 MB | 10.26 MB |
| CLS | 0.184 | 0.00 |
| LCP | 1,063 ms（开发模式） | 449 ms（生产预览：TTFB 4 / 加载延迟 324 / 加载 35 / 渲染 86 ms） |
| 滚动 | 开发模式 34fps、长任务 110–142ms | 生产预览 111.2fps、0 长任务 |

> 滚动数据差异主要来自 Vite 开发服务器与 Vue Inspector 开销；同一份代码在生产预览下无长任务。LCP 剩余主要成本是“加载延迟”（Vue 挂载后才发起缩略图请求），属客户端渲染固有开销。

### 第三轮：按需加载与缩略图 WebP 化（2026-10-24 下午）

- **二级视图按需加载**：`HomePage.vue` 用 `defineAsyncComponent` 加载 `AdminPage`、`TrashPage`、`Lightbox`。首屏 JS 619.27 → **467.54 KB**（gzip 212.8 → 164.85 KB），首屏 CSS 234.44 → **128.16 KB**（gzip 34.7 → 20.67 KB）；管理页 67.01 KB、表格 77.54 KB、灯箱 8.67 KB、回收站 5.81 KB 均拆为独立 chunk。浏览器验证初始加载不含 `Lightbox-*.js`，点击图片后才请求且返回 200。
- **缩略图 WebP**：新增 `THUMBNAIL_FORMAT`（默认 `webp`）。读取时优先当前格式、回退存量 jpg；写入使用 `quality=90, method=4`；DB 记录改为 upsert，迁移后删除旧 jpg 避免双份缓存。同图对比：300px 体积减少 **22.7%**，800px 减少 **31.2%**。
- **存量迁移**：`generate_thumbnail(..., force=True)` 与 `prebuild_thumbnails.py --rebuild` 支持分批迁移；本地迁移 200 张后 jpg 422→235、webp 2→202。
- **回收站缩略图修复**：此前 `generate_thumbnail(trash_path, size)` 把文件路径当作 image_id，查询失败后回退原图。新增 `generate_thumbnail_from_path` 缓存到 `cache/trash/<size>/`，恢复/永久删除时清理；回收站网格按列宽请求 small/medium，不再固定 medium。
- **首屏指标**：分包后生产预览 trace 为 LCP **402 ms**（最佳一次）、CLS 0.00；多次测量在 402–696 ms 间波动，主要受本机缩略图按需生成与后台任务影响。

| 指标 | 第二轮 | 第三轮 |
|------|--------|--------|
| 首屏 JS | 619.27 KB（gzip 212.8 KB） | 467.54 KB（gzip 164.85 KB） |
| 首屏 CSS | 234.44 KB（gzip 34.7 KB） | 128.16 KB（gzip 20.67 KB） |
| 按需 chunk | 无 | AdminPage 67.01 / el-table 77.54 / Lightbox 8.67 / TrashPage 5.81 KB |
| 缩略图格式 | JPEG q90 | WebP q90（300px -22.7%，800px -31.2%） |

## 10 万张规模的后续优化空间

当前优化解决了“滚动 O(n)、追加 O(n²)、搜索请求风暴”这三类会随数据量放大的问题；已追加 FTS5 与 keyset 分页，缩略图支持后台预生成。但无限滚动仍会把已浏览页累积在内存中，10 万张全部滚完时内存与布局对象仍会增长。建议下一阶段按优先级推进：

1. **窗口化数据源**：keyset 分页已实现（见 `search-pagination-thumbnails-搜索分页与缩略图优化.md`），但前端仍累积已加载页；真正的窗口化需要元数据级虚拟化或只保留视口附近页面。
2. **响应式图片**：按列宽返回 300/600/1200 多档缩略图或 `srcset`，减少大图网格带宽。
3. **前端代码拆分**：已完成 Element Plus 按需引入与管理页/回收站/灯箱异步加载，首屏 JS 467.54 KB；可继续评估 `vue-cropper` 等未使用依赖清理与路由级分包。
4. **SQLite 维护**：定期 `ANALYZE` / `VACUUM`，并为高频筛选组合补充复合索引。
5. **缩略图格式**：已支持 WebP 与 `--rebuild` 迁移；剩余工作是按批迁移存量 jpg 缓存，并复核 133.6 kB 的缓存浪费来源。
6. **真实数据压测**：在 10 万张库上验证搜索、深度滚动、首屏与缩略图预生成耗时。
7. **图片读取鉴权**：`raw`/`thumbnail`/`download` 仍为公开接口，性能优化不改变该安全缺口。

## 验证

- `npm run check`：通过。
- `npm run build`：通过；第三轮分包后首屏 `index-*.js` 467.54 KB（gzip 164.85 KB）、`index-*.css` 128.16 KB（gzip 20.67 KB），AdminPage/el-table-column/Lightbox/TrashPage 为独立 chunk，无 >500KB 警告。
- 生产预览性能（`vite preview` 4173，Chrome DevTools MCP）：LCP 402–696 ms（多次测量波动）、CLS 0.00；滚动 111.2 fps、无长任务；首屏总传输 10.26 MB（其中字体约 9.7 MB）。
- 按需加载（浏览器网络请求）：初始加载不含 `Lightbox-*.js`，点击图片后请求并返回 200；灯箱打开/关闭正常。
- 浏览器冒烟（http://localhost:5173）：
  - 首屏约 16 张卡片，总数 44；侧边栏/顶栏/瀑布流正常渲染；
  - 搜索 `wall` 结果更新、清空后恢复；
  - Lightbox 打开、右方向键切换、Esc 关闭正常；
  - 深色/浅色切换正常，无闪烁；
  - 滚动加载更多、底部状态栏、侧边栏折叠均无错位；
  - 控制台无 error。
- 后端接口：`GET /api/images?per_page=1000` 返回 `per_page=200`；缩略图 `Cache-Control: public, max-age=86400`；`file_name` 排序在 23,851 行测试库约 2.5ms；WAL 已启用；新增索引存在。
- 未在 10 万张真实数据上做端到端压测；上述瓶颈分析基于代码路径复杂度与当前 23,851 行测试库实测。

## 5B 页面改动回查

- **任务路径**：未新增页面与路由；浏览、搜索、Lightbox、批量操作、回收站、管理页路径保持不变。
- **布局骨架**：侧边栏/顶栏/主区/底部状态栏结构不变；仅视觉 token、间距、卡片与工具栏样式调整。
- **组件一致性**：继续使用 Element Plus 与现有 Pinia/API 封装；新增样式全部复用全局 token，未引入第二套组件体系。
- **关键状态**：加载骨架、空态、选中态、禁用态、错误提示、401 清理均保留。
- **响应式**：沿用 768px 断点；状态栏左偏移改为跟随侧边栏变量。
- **无障碍**：补充 aria-label、按钮语义、焦点环、`prefers-reduced-motion`。
- **性能约束**：动效仅使用 transform/opacity；虚拟列表不使用逐项入场动画；搜索防抖；请求可取消。
