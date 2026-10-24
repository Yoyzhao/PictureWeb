# 项目规则（PicGallery / PictureWeb）

> 定位：只在本项目生效的编码、命名、技术栈、运行与协作约束。硬约束与授权边界仍按 `fullstack-general` 的 `SKILL.md` 执行。
>
> 加载时机：冷启动回顾时必读；热推进确认可跳过。

## 1. 项目特有编码规范

- 数据库中的图片路径统一存**正斜杠**：写入时 `path.replace('\\', '/')`，访问磁盘前 `os.path.normpath()` 还原；新增文件操作不得绕过该约定。
- 所有 SQL 使用参数绑定；动态字段（排序等）必须先走白名单校验（参考 `server/app/routes/image.py` 的 `allowed_sort_fields`），禁止拼接用户输入。
- 前端所有 HTTP 请求必须经 `web/src/api/index.ts` 的 axios 实例，Token 由请求拦截器统一注入；页面与组件不得直接 `new axios` 或写死后端地址。
- 删除图片统一进入应用内回收站（`TRASH_DIR` + `trash` 表），并在 `metadata` 中保存收藏、标签、尺寸等可恢复信息；禁止新增物理删除路径，除非有 CHG 决策。
- 权限必须在服务端校验（`g.user['role']` 或 `permissions` 表），前端隐藏按钮只作为体验优化，不能作为权限依据。
- 时间字段新增时先确认口径；当前 `created_at/updated_at/deleted_at` 为 SQLite UTC、`modified_time` 为本地时间，不得在未统一前混用于同一排序或统计。

## 2. 命名约定

- Vue 组件文件 PascalCase（`ImageGrid.vue`）；页面放 `web/src/pages/`，命名 `<名称>Page.vue`。
- Pinia store 文件名小写、导出 `useXxxStore`（`useImageStore`）。
- 后端每个模块一个 Blueprint 文件，`url_prefix` 为 `/api/<模块名>`。
- API 字段使用 snake_case（`file_name`、`is_favorite`、`scan_status`）；前端类型接口与之对齐。
- 数据库表名小写下划线；时间字段统一 `created_at` / `updated_at` / `deleted_at`。
- 文档编号沿用 Skill 规范：Bug `Bug-XXX`、任务 `T-XXX`、变更 `CHG-YYYYMMDD-NN`、测试用例 `TC-<模块>-XXX`。

## 3. 技术栈与安全约束

- 后端保持 Flask + 标准库 `sqlite3` + Pillow + Waitress；不引入 ORM、迁移框架或第二个 Web 框架（如需变更，先走 CHG 并评估数据兼容）。
- 前端保持 Vue 3 Composition API + `<script setup>` + Pinia + Element Plus + Tailwind CSS；不引入 Vuex/Redux。
- 路径别名 `@` 固定指向 `web/src`（`vite.config.ts` 与 `tsconfig.json` 一致）。
- 全局主题变量集中在 `web/src/style.css` 的 `:root` 与 `dark` class；新增颜色/间距优先复用变量，不散落硬编码。
- 前端 TypeScript 当前 `strict: false`，新增代码不依赖该放宽项，避免引入新的类型错误。
- **密钥与凭证禁止硬编码**：`SECRET_KEY`、管理员初始账号/密码、Token 有效期只从 `.env` 或平台密钥服务读取；源码、`config.yaml`、文档、日志和提交历史中不得出现真实值。
- **登录 Token 使用签名机制**：由 `itsdangerous` + `SECRET_KEY` 签发，默认 7 天有效期；不得恢复 `token-{id}`、`admin-token`、`guest-token` 等可伪造格式。
- `.env` 必须保持未跟踪；只有 `.env.example` 可入库，且示例中不得填真实值。

## 4. 运行与配置约定

- 沿用现有目录结构 `server/` + `web/`，禁止为套用 Skill 模板重排、重命名或迁移目录与入口。
- 端口约定：生产 5000（Waitress）、开发后端 5001（Flask dev server）、前端 5173（Vite，`/api` 代理到 5001）；不得自动换端口或终止非目标进程。
- 配置分工：`config.yaml` 只放非敏感运行配置（端口、DB、缓存、回收站、缩略图、快捷键）；`.env` 放密钥与管理员初始账号。生产副本必须使用自己的 `config.yaml` 与 `.env`。
- 测试库与生产库物理分离：仓库开发配置固定指向 `data/db/database.db`、`data/cache`、`data/trash`；生产库位于部署副本，禁止把仓库配置改回生产路径。
- 生产入口 `prod_run.py`（Waitress）；开发入口 `server/run.py`；前端必须先 `npm run build` 才能由 Flask 托管。
- 不跟踪 `server/venv/`、`web/node_modules/`、`web/dist/`、`data/`、`logs/`、`.env`；新增依赖必须同步 `requirements.txt` 或 `package.json` + lock 文件。

## 5. 目录与文档归属

- 文档统一放 `docs/`：需求 `prd/`、技术与环境 `tech/`、计划与进度 `plan/`、部署 `deploy/`、规则 `rules/`、原型 `prototype/`；调试与测试目录首次需要时创建。
- 部署与运维脚本放 `scripts/deploy-script/`；数据库脚本放 `scripts/sql-script/`。
- 历史原型放 `docs/prototype/`，仅作参考，不作为当前实现依据。
- 本地运行数据统一放 `data/`：`db/`、`cache/`、`trash/`、`app_logs/`。
- 不在根目录散落临时脚本；一次性排查脚本用完清理或归入 `scripts/`。

## 5.1 前端性能约定

- 虚拟列表的可见项计算必须使用索引/二分查找，禁止在滚动回调中过滤全部已加载项。
- 分页追加必须原地修改并使用版本信号/`triggerRef` 通知，禁止每页复制完整图片或布局数组。
- 搜索输入必须防抖（当前 300ms）；列表请求必须支持取消并防止乱序响应覆盖新结果。
- 高亮/选中判断使用 `Set`，禁止在每张卡片渲染时对大数组做 `includes`。
- 动画只使用 `transform`/`opacity`；虚拟列表项不使用逐项入场动画或全量 `will-change`；必须支持 `prefers-reduced-motion`。
- 大图网格使用 `medium` 缩略图，原图预加载需设置体积/数量上限；新增图片接口应返回缓存头。
- 面向 10 万级数据的新功能，先评估是否会累积全部数据到前端内存；优先窗口化/游标分页方案。
- 图片元素必须提供 `width`/`height` 或 `aspect-ratio` 预留尺寸；首屏前 15 张使用 `eager` + `fetchpriority="high"`，其余 `lazy` + `decoding="async"`。
- Element Plus 组件必须按需引入（`unplugin-vue-components` + `ElementPlusResolver`，CSS 由解析器注入），禁止恢复 `app.use(ElementPlus)`、全量样式或全量图标注册；新增指令时单独引入对应样式（参考 `main.ts` 的 `ElLoading`）。
- 字体只保留实际使用的字重（当前 MiSans Regular 400 + Semibold 600）；新增字重或字体文件前必须评估首屏传输体积。
- 虚拟列表 `buffer` 保持 600 左右，新增滚动相关样式不得使用 `backdrop-filter` 等昂贵合成效果。

## 5.2 后端性能约定

- 文件名搜索优先使用 `images_fts`（FTS5 trigram）；查询词 <3 字符或 FTS5 不可用时才回退 `LIKE`。
- 列表分页后续请求必须使用 `cursor`/`next_cursor`，禁止新增深层 `OFFSET`；游标必须绑定排序并在不匹配时返回 400。
- 新增排序字段时必须同时提供对应索引与 keyset 比较逻辑，并用 `id` 作为 tie-breaker。
- 缩略图预生成受 `THUMBNAIL_PREGENERATE` 控制；全库补齐使用 `scripts/sql-script/prebuild_thumbnails.py` 分批执行，禁止在请求线程内全库同步生成。
- 修改 `images.file_name` 或删除图片时必须保证 FTS 触发器同步；批量导入绕过触发器时执行 `--rebuild-search-index`。

## 6. 特殊流程与禁忌

- 未经明确授权，禁止写入生产部署目录、生产数据库或执行扫描/删除等会改动生产数据的操作；只读验证优先使用 `/api/health` 与匿名可见列表接口。
- 禁止在未确认的情况下修改权限模型、`permissions` 语义或替换 Token 存储方式（如 localStorage -> Cookie）；这些属于高风险变更，需先形成 CHG 并获确认。
- 修改管理员凭据时只更新 `.env`，再执行 `scripts/sql-script/init_db.py --reset-admin-password`；禁止把密码写回源码或文档。
- 生产环境对外暴露前必须修改默认管理员密码、收紧 CORS，并补齐图片读取接口的服务端权限校验。
- 修改 `server/app/models/schema.sql` 时，必须同时提供已有库的增量迁移逻辑（`migrate_db`），禁止只改建表语句导致存量库不可用。