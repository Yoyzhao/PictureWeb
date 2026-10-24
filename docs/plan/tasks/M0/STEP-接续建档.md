# M0 / 接续建档 — 阶段任务文档

- **里程碑**：M0 历史交付基线
- **阶段**：接续建档（非标准开发阶段，属既有项目首次纳入流程的基线动作）
- **状态**：已完成，待用户追认
- **更新日期**：2026-10-24

## 任务索引

| 任务ID | 名称 | 状态 | 负责人 | 产出 |
|--------|------|------|--------|------|
| T-001 | 既有项目接续建档与目录结构基线整理 | 已完成（待追认） | main | `docs/tech/dev-info.md`、`docs/rules/project-rules.md`、`docs/plan/project-progress.md`；修正架构文档第 9 节与 README |

## 目标与范围

- 目标：让后续开发可以直接依据事实文档接续，不再依赖口头上下文。
- 范围：只读核对代码、配置、运行状态与 Git 历史；补建最小支撑文档；修正与现状不符的目录/端口描述。
- 不做：不改业务代码、不重排目录、不迁移文件、不安装依赖、不操作生产数据。

## 实施记录

1. 读取 PRD、技术架构、开发计划、部署说明与 README。
2. 核对后端 `server/app/`（路由、服务、DB 工具、schema）与前端 `web/src/`（api、stores、pages、components、router）。
3. 核对运行事实：生产副本 `D:\Workspace\_deploy\PicGallery` 监听 5000；仓库配置为 5001；Vite 代理 5001；本地库 23,851 条图片记录。
4. 补建 `docs/tech/dev-info.md`（技术栈、目录与模块、命令、端口、配置键、时区、工具链、风险）。
5. 补建 `docs/rules/project-rules.md`，并将 `.trae/rules/project-rules.md` 改为指向该文件的入口。
6. 补建 `docs/plan/project-progress.md`（基线、阶段映射、任务池、风险、续接点）。
7. 修正 `docs/tech/PictureWeb技术架构文档.md` 第 9 节目录结构与 README 的端口/结构说明。

## 验证计划与结果

| 验证项 | 方法 | 结果 |
|--------|------|------|
| 生产服务可用 | `GET http://127.0.0.1:5000/api/health` | 200，`{"status":"ok"}` |
| 匿名可见范围 | `GET /api/folders`（无 token） | 200，返回 1 个公开文件夹 |
| 前端类型检查 | `cd web; npm run check` | 通过（无输出，退出码 0） |
| 后端语法检查 | `python -m py_compile` 全部后端入口与模块 | 通过 |
| 目录与端口实测 | `Get-ChildItem`、`Get-NetTCPConnection`、读取配置文件 | 与 `dev-info.md` 记录一致 |
| 浏览器交互验收 | 未执行 | 本轮不改代码，不涉及 UI 变化 |

## 结果与遗留

- 已具备后续开发所需的最小事实集：技术栈、目录入口、API 模块、端口、配置键、数据现状、已知风险。
- M0 当时记录的遗留（venv 重建、本地/生产配置分离、mock token 鉴权替换）已在 M1 工程基线整改中处理，详见 `docs/plan/tasks/M1/STEP-工程基线整改.md`。
- 仍未处理：自动化测试、ESLint 配置、图片读取接口鉴权、CORS 收紧、时间字段口径统一。
- 验收：等待用户追认 M0 基线；通过后本阶段标记“已通过”，不追溯历史阶段验收。
