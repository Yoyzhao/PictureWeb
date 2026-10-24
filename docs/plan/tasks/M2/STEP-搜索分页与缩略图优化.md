# M2 / 搜索分页与缩略图优化 — 阶段任务文档

- **里程碑**：M2 前端性能与 UI 优化（续）
- **阶段**：FTS5 搜索 + keyset 分页 + 缩略图预生成（5D + 5C）
- **状态**：已完成，待用户验收
- **关联 CHG**：`CHG-20261024-03`
- **更新日期**：2026-10-24

## 任务索引

| 任务ID | 名称 | 状态 | 负责人 | 主要产出 |
|--------|------|------|--------|----------|
| T-013 | FTS5 文件名搜索 | 已完成 | main | trigram 虚拟表、同步触发器、LIKE 回退、重建命令 |
| T-014 | Keyset 游标分页 | 已完成 | main | cursor/next_cursor、三种排序、前端游标接入 |
| T-015 | 缩略图后台预生成 | 已完成 | main | 扫描后预生成线程、配置项、历史库补齐脚本 |
| T-016 | 验证与文档同步 | 已完成 | main | API 测试、浏览器冒烟、技术说明与 CHG/进度 |

## T-013 FTS5 搜索

- `db.ensure_fts()` 创建 `images_fts`（`content='images'`、`content_rowid='id'`、`tokenize='trigram'`）与增删改三个触发器。
- 通过 `images_fts_docsize` 判断索引是否为空；数量与 `images` 不一致时执行 `rebuild`。
- `FTS5_ENABLED` 写入 app config；不可用时回退 LIKE。
- `get_images`：查询词 ≥3 字符走 `MATCH`，短语用双引号包裹并转义；更短或无 FTS 时用 LIKE。
- `init_db.py --rebuild-search-index` 提供手动重建。
- 验证：docsize 23,851；`ANIME-PI` 命中 7；API 搜索 200。

## T-014 Keyset 分页

- `image.py` 新增游标编码/解码与 `cursor_value`。
- 支持 `modified_time`、`file_name`、`file_size`，以 `id` 为 tie-breaker。
- `total` 在 keyset 条件之前统计，游标页返回完整筛选总数。
- 非法游标、排序不匹配返回 400；保留 offset 兼容路径。
- 前端 `image.ts` 增加 `nextCursor`，首次不带 cursor，后续带 cursor；null 时停止加载。
- 验证：连续两页 5+5、无重复、total 均为 23,851；file_name 排序正确；非法游标 400；浏览器滚动到底部提示“没有更多图片了”。

## T-015 缩略图预生成

- `thumbnail.py` 新增 `prebuild_thumbnails()` 与 `start_folder_thumbnail_prebuild()`：
  - 按 id 分批查询缺失 small 缩略图；
  - 全局锁保证同时只有一个预生成线程；
  - 每批后 sleep 10ms，降低对请求线程的影响。
- `scanner.py` 在扫描完成、状态置为 completed 后触发预生成（受 `THUMBNAIL_PREGENERATE` 控制）。
- `scripts/sql-script/prebuild_thumbnails.py` 支持 `--folder`、`--limit`、`--size`。
- `config.yaml` / `config.example.yaml` 新增 `THUMBNAIL_PREGENERATE: true`。
- 验证：`--limit 5` 后 small 缩略图 1,993 → 1,998。

## T-016 验证与文档

- 后端 `py_compile` 通过；前端 `npm run check` / `npm run build` 通过。
- 浏览器：搜索 `jpg` 命中 10 条并恢复 44 条；滚动到底部提示“没有更多图片了”；Lightbox、侧边栏折叠正常；控制台仅 ResizeObserver 警告。
- 新增 `docs/tech/features/search-pagination-thumbnails-搜索分页与缩略图优化.md`，并登记 `docs/tech/INDEX.md`。
- 生产 5000 健康检查 200，未部署本轮代码；开发服务验证后已停止。

## 限制

1. 窗口化数据源未实施；当前 keyset 无限滚动仍会累积已加载页。
2. 10 万级库首次启动需要重建 FTS 索引，部署前应备份并预留启动时间。
3. 全库缩略图预生成是 CPU 密集型任务，建议分批/低峰执行。
4. 未在 10 万张真实数据上做端到端压测。
