# 搜索分页与缩略图优化

- **状态**：活跃
- **关联 CHG/任务**：`CHG-20261024-03`、`CHG-20261024-07` / T-013 ~ T-016、T-020
- **所属里程碑**：M2 性能与 UI 优化（续）
- **最后更新**：2026-10-24

## 需求摘要

继续推进 10 万张图片规模下的三项基础设施优化：

1. 文件名搜索使用 SQLite FTS5（trigram）替代 `LIKE '%q%'` 全表扫描；
2. 列表分页从 offset 改为 keyset 游标，避免深层 OFFSET；
3. 扫描完成后后台预生成缺失的小尺寸缩略图，降低首次浏览等待。

窗口化数据源尚未实施（见文末限制）。

## 1. FTS5 文件名搜索

### 设计

- 使用外部内容表：
  ```sql
  CREATE VIRTUAL TABLE images_fts USING fts5(
      file_name,
      content='images',
      content_rowid='id',
      tokenize='trigram'
  );
  ```
- 三个触发器保持同步：
  - `images_fts_ai`：新增图片时写入索引；
  - `images_fts_ad`：删除图片时写入 FTS5 delete 指令；
  - `images_fts_au`：重命名时先 delete 再 insert。
- 首次升级/索引为空时执行 `INSERT INTO images_fts(images_fts) VALUES('rebuild')`。
- 外部内容表 `SELECT COUNT(*) FROM images_fts` 返回内容表行数，不能判断索引是否为空；改用 `images_fts_docsize` 判断并触发重建。
- 搜索条件：
  - 查询词 ≥ 3 字符且 FTS5 可用：`i.id IN (SELECT rowid FROM images_fts WHERE images_fts MATCH ?)`，参数使用双引号包裹的短语，内部双引号转义；
  - 查询词 < 3 字符或 FTS5 不可用：回退到 `LIKE '%q%'`。
- 维护命令：
  ```powershell
  .\server\venv\Scripts\python.exe scripts\sql-script\init_db.py --rebuild-search-index
  ```

### 验证

- 索引 docsize = 23,851，与 `images` 行数一致。
- 搜索 `"ANIME-PI"` 命中 7 条；API 返回 200。
- 浏览器搜索 `jpg` 返回 10 条（匿名可见范围），清空后恢复 44 条。

## 2. Keyset 游标分页

### 设计

- `GET /api/images` 新增可选参数 `cursor`；响应新增 `next_cursor`。
- 游标为 base64(JSON)：`{ "s": sort_by, "o": sort_order, "v": last_value, "id": last_id }`。
- 支持三种排序：
  - `modified_time`：`(modified_time, id)` 比较；
  - `file_name`：`(file_name, id)` 比较；
  - `file_size`：`(file_size, id)` 比较。
- 查询条件：
  ```sql
  (i.<sort> < ? OR (i.<sort> = ? AND i.id < ?))  -- DESC
  (i.<sort> > ? OR (i.<sort> = ? AND i.id > ?))  -- ASC
  ```
- `ORDER BY i.<sort> <order>, i.id <order>`，用 id 作为稳定排序的 tie-breaker。
- `total` 在应用 keyset 条件**之前**统计，保证游标页仍返回完整筛选总数；前端保留首次 total。
- 游标与当前 `sort_by`/`sort_order` 不一致或解码失败返回 400。
- 保留 offset 分页作为无游标时的兼容路径；首次请求仍返回 `next_cursor`。
- 前端 `stores/image.ts` 增加 `nextCursor`；首次请求不带 cursor，后续请求带 `cursor`，服务端返回 null 时停止加载。

### 验证

- `modified_time DESC` 第一页 5 条、第二页 5 条，无重复，`total` 均为 23,851。
- 第二页首项时间 ≤ 第一页末项时间。
- `file_name ASC` 游标页首项 ≥ 上一页末项。
- 非法游标与排序不匹配均返回 400。
- 浏览器滚动到底部出现“没有更多图片了”，无异常请求。

## 3. 缩略图预生成

### 设计

- 配置项 `THUMBNAIL_PREGENERATE`（默认 true）。
- 扫描完成且状态置为 `completed` 后，启动一个后台线程：
  - 按 id 分批（每批 100）遍历 `images`，以当前 `CACHE_DIR` 中缩略图文件是否存在判断缺失（不依赖 `thumbnails` 表的旧 `file_path`）；
  - 逐张调用 `generate_thumbnail`，生成后 upsert 修正 `thumbnails.file_path`；
  - 每批后短暂 sleep，避免抢占请求线程与扫描线程；
  - 使用全局 `_prebuild_lock`，同一时间只允许一个预生成任务；已有任务时跳过并记录日志。
- JPEG 缩略图先 `Image.draft()` 降采样解码，再 `thumbnail()`，降低大图解码开销。
- 只预生成 `small`；`medium` 仍按 Lightbox 打开时按需生成。
- 手动补齐历史库：
  ```powershell
  .\server\venv\Scripts\python.exe scripts\sql-script\prebuild_thumbnails.py --limit 500
  .\server\venv\Scripts\python.exe scripts\sql-script\prebuild_thumbnails.py --folder 4 --size small
  ```

### 验证

- 本地库缺失小缩略图约 21,859 张。
- 执行 `--limit 5` 后 `thumbnails(size_type='small')` 从 1,993 增加到 1,998，文件写入缓存成功。
- 后台线程未在浏览器冒烟中触发（未重新扫描）；核心函数与脚本已验证。
- 2026-10-24 18:18 复查：`images` 21,159，当前 `data/cache/small` 仅 424 个文件；1,277 条 DB 记录指向旧缓存 `F:\_piccache`，旧逻辑会漏生成。修复后 `--limit 700` 生成 496 张（70s），当前缓存 424→920，旧路径记录 1,278→772，覆盖率 4.4%。
- FTS5 复查：docsize 21,159、3 个同步触发器；登录后 `ANIME-PI` 命中 7、`PI`（LIKE 回退）命中 58、总列表 21,159。
- 全量预生成未执行；按当前吞吐（约 140–190ms/张）预计约 1 小时，建议后台分批运行。

## 验证汇总

| 验证项 | 方法 | 结果 |
|--------|------|------|
| 后端编译 | `py_compile` 相关模块与脚本 | 通过 |
| 前端类型检查 | `npm run check` | 通过 |
| 前端构建 | `npm run build` | 通过 |
| FTS5 搜索 | SQLite MATCH + API | 索引 23,851；`ANIME-PI` 命中 7 |
| 游标分页 | API 连续两页 | 无重复；total 稳定；排序正确；非法游标 400 |
| 缩略图预生成 | `prebuild_thumbnails.py --limit 5/700` | +5 条；修复后 496 张/70s，缓存 424→920 |
| 预生成覆盖 | 当前 CACHE_DIR 文件审计 | 旧 DB 路径 1,277→772；覆盖率 4.4% |
| 浏览器 | 搜索/滚动/Lightbox/侧边栏 | 全部通过；仅 ResizeObserver 警告 |

## 限制与后续

1. **窗口化数据源未实施**：当前仍是 keyset 无限滚动，已加载页会累积在内存；真正窗口化需要元数据级虚拟化，作为后续架构任务。
2. **FTS 首次升级成本**：已有 10 万级库首次启动会重建 FTS 索引，可能耗时较久；部署前应备份并预留启动时间。
3. **缩略图预生成 CPU 成本**：全库补齐 10 万张会持续占用 CPU；建议分批/低峰执行，后续可增加并发限流与 WebP。
4. **未做 10 万张真实数据端到端压测**；当前验证基于 23,851 行测试库。
5. FTS5 依赖 SQLite 编译支持；不可用时自动回退 LIKE。
