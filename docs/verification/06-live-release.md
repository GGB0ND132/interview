# 06 本地持久化演示发布验收

2026-11-10：06 全部工单项已完成。后六主题 58 题经独立 Agent 全量内容审核后，已通过显式 `agent_full` 发布流程写入实际演示数据库。发布 ID：`55d425b3-4066-4c94-8157-286437d8f64e`；新增 58、拒绝 0，当前全部 12 主题实际可抽 **115** 题。

这里的正式发布指本机持久化 06 演示实例，不表示远程生产部署。05 的 8000/5173 服务继续保留。06 从运行中的 05 数据库执行只读 SQLite 一致性备份，保留原 57 题和 7 个会话，然后由 06 服务迁移到 schema 3 并发布后六主题。未将 05 候选源码合入本分支，也未将 05 内容冒充本轮重新审核。

- 06 试题练习：http://127.0.0.1:5174/question-practice
- 06 API：http://127.0.0.1:8001
- 数据库：`C:/Users/ctrlz/orca/workspaces/interview agent/06/backend/data/practice.sqlite3`（运行数据不入 Git）。
- 本轮审核：Agent 58、人工 0；人工模板仍为空白。默认 `human_sample` 保留，质量更正/恢复的既有人工作业入口不变。

| 主题 | 固定来源 | 本轮预检通过 | 本轮拒绝 | 本轮 Agent 审核 | 实际可抽 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Agent 基础与运行循环 | 17 | — | — | — | 17 |
| Agent 应用架构与场景设计 | 18 | — | — | — | 18 |
| 规划、推理与任务执行 | 8 | — | — | — | 8 |
| 上下文工程 | 2 | — | — | — | 2 |
| 记忆系统 | 6 | — | — | — | 6 |
| 工具调用与 Function Calling | 6 | — | — | — | 6 |
| MCP、A2A 与工具协议 | 15 | 15 | 0 | 15 | 15 |
| Skills 能力系统 | 13 | 13 | 0 | 13 | 13 |
| 工作流、状态与执行恢复 | 5 | 5 | 0 | 5 | 5 |
| 多 Agent 编排与协作 | 8 | 8 | 0 | 8 | 8 |
| Agent 框架与 Harness | 16 | 16 | 0 | 16 | 16 |
| GUI、Computer Use 与多模态 Agent | 1 | 1 | 0 | 1 | 1 |
| 合计 | 115 | 58 | 0 | 58 | 115 |

前六行“—”表示继承 05 已发布数据，本轮未重新预检/审核。发布 JSON 中 `source_count/available_count` 是 12 主题全局数量，`prepared_count/validation_passed_count/reviewed_count` 仅计 `scope_competency_ids` 选中的后六主题；前六主题的 `unprepared_count/blockers` 表示本分支未提供候选稿，不表示实际题库缺少可用题。

## 真实验收证据

- [发布报告](06-live-release.json)：显式 `agent_full`、完整 58 条内容哈希/材料审批、逐题预检与发布结果、服务端回读 115 题。
- [幂等重放](06-live-idempotency.json)：新增 0、58 unchanged，可抽仍为 115。
- [首次在线验收](06-live-verification.json)：58 个当前内容版本逐字段匹配；57 个继承题的全部版本与 05 API 一致；后六主题分别创建、开始并明确跳过，保存 6 份真实报告，平均分为 null，不调用模型。
- [重启后验收](06-live-after-restart.json)：仅重启 06 的服务进程，115 题与原发布报告仍可读取；58 当前版本、57 继承题全部版本、7 个原会话和 6 份跳过报告逐项一致。05 仍为原 57 题。
- 页面入口 HTTP 200，前端 `/api` 代理与 8001 的 availability 全等（115）。Tabbit 诊断退出 1 且无输出，Computer Use 返回 browser access host unavailable，因此没有浏览器视觉验收或真实模型评分验收的成功声明。

规范/规格双轴独立代码审查无剩余问题。备份脚本显式关闭连接，失败仅清理本次创建的目标，附成功/失败/禁止覆盖回归。验收脚本按审核意见补充原会话逐项比较，预期数据库路径与 HTTP 实测事实分开记录。

最终检查：后端 **71 passed**，mypy 10 个源文件、Ruff 检查及 27 文件格式通过；前端 **20 passed**，TypeScript/Vite 构建与 ESLint 通过。现有 Starlette 依赖弃用提示不影响结果。

## 再次启动与核验

从 `backend/` 启动：`uv run uvicorn interview_backend.api:create_app --factory --host 127.0.0.1 --port 8001`。从 `fronted/` 执行：

```powershell
$env:INTERVIEW_BACKEND_URL='http://127.0.0.1:8001'
npm run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

从 `backend/` 可重复发布并只读核验（05 服务需在线用于继承比对；`--previous` 不创建新会话）：

```powershell
uv run python -X utf8 scripts/release_agent_topics.py --base-url http://127.0.0.1:8001 --review-policy agent_full --scope second-half --reviews ../docs/verification/06-content-protocols-workflow-review.json ../docs/verification/06-content-skills-multiagent-review.json ../docs/verification/06-content-frameworks-gui-review.json --publish --output ../docs/verification/06-current-release.json
uv run python -X utf8 scripts/verify_live_agent_topics.py --release ../docs/verification/06-live-release.json --previous ../docs/verification/06-live-verification.json --output ../docs/verification/06-current-live-check.json
```

`verify_live_agent_topics.py --draw` 会额外创建六条演示跳过会话，日常检查不要加此参数。若需要建立新演示库，`seed_demo_database.py --source <已有数据库> --target <不存在的新目标>` 使用 SQLite 只读一致性备份，拒绝覆盖已有目标；不要再次覆盖当前运行数据库。
