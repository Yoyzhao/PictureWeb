# M3 / 浏览位置书签 — 阶段任务文档

- **里程碑**：M3 浏览位置书签
- **阶段**：需求确认 + 轻量 5B 交互设计 + 5C/5D 垂直切片
- **状态**：已完成，待用户验收
- **关联 CHG**：`CHG-20261025-01`（`docs/tech/功能变更.md`）
- **更新日期**：2026-10-25

## 任务索引

| 任务ID | 名称 | 状态 | 负责人 | 主要产出 |
|--------|------|------|--------|----------|
| T-025 | 浏览位置书签（自动进度 + 手动书签） | 已完成 | main | `image_bookmarks` 表、书签 CRUD/自动进度/锚点窗口接口、书签 store、书签抽屉、网格/灯箱保存入口、锚点滚动与恢复视图 |

## 方案要点

- **锚点而非序号**：书签保存锚点图片 ID、当时的排序键（修改时间/文件名/大小）与视图上下文（文件夹、收藏夹、搜索词、排序），不保存页码、滚动偏移或加载数量；排序变化、新增图片、删除图片都不会让位置整体错位。
- **恢复时还原书签视图**：恢复保存的文件夹/收藏/搜索/排序，再通过 `/api/bookmarks/<id>/restore` 返回锚点前后窗口（默认前 40、后 80），前端以窗口初始化列表并滚动到锚点。
- **锚点缺失兜底**：锚点被删除、移动出当前视图或无权限时，用保存的排序键查找最近的下一张/上一张；前端提示“原图片已删除或移出当前视图，已定位到附近位置”。
- **自动进度 + 手动书签**：自动进度按 `(folder_id, is_favorites, search_query)` 每视图一条，随浏览更新排序与锚点；手动书签可保存多个命名位置，均存服务端、按用户隔离。
- **入口切换态**：网格“记住这里”和灯箱“书签”根据当前图片是否已有手动书签显示激活态（“已书签/取消书签”），再次点击取消；同一用户、同一视图、同一锚点由接口去重。
- **权限**：书签接口要求登录，guest 禁止写入；创建/自动保存时校验锚点图片读取权限与视图一致性；恢复仍走图片列表的权限过滤。

## 实施记录

### 数据库

- `server/app/models/schema.sql` 新增 `image_bookmarks` 表与索引；`server/app/utils/db.py` 的 `migrate_db()` 同步创建表/索引，已有库启动时自动补齐。
- `folder_id=0` 表示“所有照片”，避免 SQLite 唯一索引对 NULL 的处理差异；自动进度使用部分唯一索引 `idx_image_bookmarks_auto(user_id, folder_id, is_favorites, search_query) WHERE kind='auto'`。
- 锚点快照字段：`anchor_image_id`、`anchor_modified_time`、`anchor_file_name`、`anchor_file_size`。

### 后端接口

- `routes/bookmarks.py`：列表、创建、自动 upsert、重命名、删除、恢复；恢复时按 `sort_by` 选择对应兜底键值。
- `routes/image.py`：抽取 `image_select`/`image_filters`/`serialize_image` 供列表与窗口共用；新增 `GET /api/images/window`，按锚点取前后窗口（keyset，无深 OFFSET），支持 `fallback_value` 兜底。
- `server/app/__init__.py` 注册书签 Blueprint。

### 前端

- `stores/image.ts`：新增 `restoreBookmarkWindow`，在响应返回后设置视图上下文并加载窗口；恢复期间用短期抑制标记阻止 `folder/favorites/sort/search` watcher 再次重置列表；新增 `scrollAnchorId`/`scrollAnchorVersion` 与 `clearScrollAnchor`。
- `stores/bookmark.ts`：书签列表、创建、自动进度（1.2s 防抖、视图变化时跳过）、恢复、重命名、删除；新增 `bookmarkedImageIds` 与 `toggleAt`——已存在则删除并提示“已取消书签”，不存在则创建；登录/恢复会话时立即拉取书签，创建成功后用接口返回值更新本地列表。
- `routes/bookmarks.py` 创建接口按 `(user, folder_id, is_favorites, search_query, anchor_image_id)` 去重，重复点击返回已有书签。
- `common/VirtualWaterfall.vue`：新增 `view-anchor` 事件（视口顶部首个可见项，排除 buffer）与 `scrollToId`/`scrollRequest` 锚点滚动，滚动完成后发出 `scroll-anchor-done`。
- `ImageGrid.vue`：顶部“记住这里”按钮；接收视口锚点并保存自动进度；传递锚点滚动参数。
- `Lightbox.vue`：工具栏新增“书签”；`HomePage.vue` 在灯箱切图/关闭时更新自动进度。
- `TopBar.vue` + `BookmarksDrawer.vue`：登录非 guest 显示书签入口；抽屉展示自动进度与手动书签，支持恢复、重命名、删除；移动端抽屉宽度与操作热区适配。

## 验证汇总

| 验证项 | 方法 | 结果 |
|--------|------|------|
| 表与索引 | `PRAGMA table_info` / `sqlite_master` | 15 个字段；`idx_image_bookmarks_user`、`idx_image_bookmarks_auto` 存在 |
| 创建/列表/重命名/删除 | 登录 API | 创建返回 201 与锚点快照；列表含文件夹名与锚点存在标记；重命名/删除成功 |
| 锚点窗口 | `/api/bookmarks/<id>/restore` | 中段锚点 `window_index=10`、前 10 后 10、`next_cursor` 存在；锚点位于窗口内 |
| 锚点删除兜底 | 书签锚点改为 999999 后恢复 | `anchor.fallback=true`，按保存的 `modified_time` 定位回原图位置 |
| 排序恢复 | 书签保存“文件名 升序”，切到“修改日期 降序”后恢复 | 排序 UI 恢复为文件名/升序，锚点首屏可见 |
| 搜索恢复 | 搜索 `wallhaven-1k1` 创建书签，清空搜索后恢复 | 搜索框回填，列表恢复为 38 张，锚点定位 |
| 自动进度 | 切换文件夹/排序、滚动、灯箱切图 | 按视图 upsert；滚动后锚点随之更新；重复调用不产生重复行 |
| 列表回归 | `GET /api/images` 两页 keyset | total 一致、无重复、收藏标记正常（抽取公共过滤函数后回归） |
| 书签入口切换 | 网格“记住这里” | 初始“记住这里” → 点击“已书签”+`is-active` → 再次点击“记住这里”+“已取消书签” |
| 书签入口切换 | 灯箱“书签” | 初始“书签” → 点击“取消书签”+`active` → 再次点击恢复“书签” |
| 已书签初始态 | 打开已收藏锚点（31046） | 网格与灯箱均直接显示激活态 |
| 重复创建去重 | 同一视图/锚点连续创建 | 接口返回已有记录，不新增重复行 |
| 前端检查 | `npm run check` / `npm run build` | 通过；BookmarksDrawer 独立 chunk（9.17 KB），初始 JS 478.62 KB（gzip 168.62 KB） |
| 响应式 | 390×844 / 360×800 | 抽屉 359px、无横向溢出；顶栏按钮 44px；书签按钮与“记住这里”可点 |
| 权限 | guest 态 | 顶栏书签、网格“记住这里”、灯箱“书签”均隐藏 |
| 控制台 | DevTools | 无 error/warn |

## 遗留与后续

1. 恢复窗口只加载锚点前后有限数量；窗口上方不继续反向分页，滚到窗口顶部即到头。后续如需完整历史，可增加向上游标分页与前置布局。
2. 自动进度每个视图一条，排序变化会更新该条记录而非保留多份排序位置；手动书签用于固定保存特定排序位置。
3. 未做多用户并发书签写入与真实跨设备验证；生产库与前端的书签表将在下次统一部署时创建。
4. 书签指向的文件夹被删除或权限被收回时，恢复返回空视图并提示；不会自动删除书签。
