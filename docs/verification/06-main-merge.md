# 06 合并至 main 核对记录

日期：2026-11-11。

## 来源与冲突处理

- 合并前 main：`f87cf192737dd7a5486622ba1333569347ba6264`，已包含 05；备份分支 `backup/main-before-06-20261111` 保留该提交。
- 合并来源：`GGB0ND132/06`，提交 `9b922f59f10f230feb085f0f5363d7f3f5613fb2`。使用独立 merge commit。
- main 原有未提交的 06 工单记录先保存为 `0ee6917`；工单说明冲突保留此版本，内容逐字一致。
- README 保留 05、06 两节，并明确 main 已包含两批候选源码，本地数据库不会随 Git 合并复制或自动发布。
- 来源快照冲突采用 06 的完整版本：固定来源提交相同，main 原有 58 个来源条目全部包含且内容逐字一致，扩为 115 个条目。
- 原 main 的 157 个、05 的 155 个、06 的 166 个受版本控制文件全部保留，无删除或遗漏；02–04 同样核对。仅 README 进行合并说明整理，业务代码沿用分支实现。
- 原有未跟踪文件 `docs/verification/05-main-merge-http.json` 保留且不混入提交。05、06 分支与工作区均保留；未推送远端，未操作日常持久化练习数据库。

## 本次验证

- 后端：`uv run --locked pytest -q`，86 项通过；`uv run --locked mypy`、`uv run --locked ruff check .`、`uv run --locked ruff format --check .` 全部通过。
- 前端：`npm test`，20 项通过；`npm run lint`、`npm run build`（含 TypeScript）通过。
- 06 TCP HTTP 临时库验收：`scripts/acceptance_agent_topics.py`，58 题校验与通用发布、六主题抽题/跳过通过；默认人工审核门槛未授权正式发布，正式发布数 0。机器记录见 [06-main-merge-http.json](06-main-merge-http.json)。
- 05 TCP HTTP 临时库回归：`scripts/acceptance_first_half.py`，57 题经原独立 Agent 审核门槛发布、六主题抽题、重复发布与停用拒绝通过。机器记录见 [06-main-merge-first-half-http.json](06-main-merge-first-half-http.json)。
- 组合验收：在另一个自动清理的临时 SQLite 中，先检查 05 的真实审核记录并发布 57 题，再通过真实维护/会话接口及 06 的三份原审核记录，以显式 `agent_full/second-half` 发布 58 题。确认总数 115、12 主题逐一抽题、06 重发新增 0，05 已开始的会话逐字段不变，重新创建应用后原会话及 115 题仍可读取。该项使用 FastAPI TestClient，无远程模型调用。
- `git diff --cached --check` 通过，无未解决合并条目；后端仅有现有 TestClient/httpx 弃用提示。本轮没有浏览器或真实模型评分验收的成功声明。

组合验收输出：

```json
{"temporary_database": true, "first_half_published": 57, "second_half_published": 58, "available_count": 115, "topics_drawn": 12, "idempotent_added": 0, "existing_session_preserved": true, "restart_preserved": true, "model_calls": 0}
```
