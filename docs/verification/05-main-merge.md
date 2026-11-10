# 05 合并至 main 核对记录

日期：2026-11-10。

## 合并状态与文件保留

- 合并前 main：`4a721d9a747a24ab3d8245ee309812ceb1b760cd`；已有备份分支 `backup/main-before-05-20261110` 指向该提交。
- 合并来源：`GGB0ND132/05`，提交 `f1c23526a626de359aec661edb096226371a47d8`。
- 本轮开始时已经处于上述来源的未提交合并中，冲突条目为 0，暂存树与 05 分支完全一致；本轮继续验证并完成独立合并提交，没有改写既有暂存内容。
- 原 main 的 133 个、05 的 155 个受版本控制文件全部存在于合并结果；02、03、04 分支的文件也逐一核对，无遗漏，无删除。
- 本轮另新增此核对记录与 `05-main-merge-recheck-http.json`，不修改原分支业务代码。
- 保留未暂存的 06 工单更新，以及本轮开始时已有的未跟踪文件 `05-main-merge-http.json`，二者未混入 05 合并提交。
- 保留 05 分支和工作区，未推送远端，未修改现有持久化练习数据库。

## 本次实际验证

- 后端：`uv run --locked pytest -q`，73 项通过；`uv run --locked mypy`、`uv run --locked ruff check .`、`uv run --locked ruff format --check .` 均通过。
- 前端：`npm test`，20 项通过；`npm run lint`、`npm run build`（包含 TypeScript 检查）均通过。
- 临时库 TCP HTTP 验收：`uv run --locked python -X utf8 scripts/acceptance_first_half.py --output ../docs/verification/05-main-merge-recheck-http.json` 退出 0。审核缺失时拒绝发布且可用数为 0；实际独立 Agent 审核门槛发布接受 57、拒绝 0；六主题抽题、幂等重发和停用拒绝均通过，测试停用一题后可用数为 56。
- 上述 HTTP 验收使用自动清理的临时数据库，不代表本轮在 main 日常数据库发布了题目。原分支持久化发布和浏览器证据随分支保留，本轮未重跑浏览器或调用模型。
- Git 文件集合核对、无未解决合并条目及 `git diff --cached --check` 均通过。后端有一条既有 TestClient/httpx 弃用提示。
