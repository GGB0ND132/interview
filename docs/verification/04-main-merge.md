# 04 合并至 main 的核对记录

日期：2026-11-09。

## 来源与保留

- 合并前 main：`f855c1844f5472a55225160fabce054be70007db`，已包含 02/03；备份分支为 `backup/main-before-04-20261109`。
- 合并来源：`GGB0ND132/04`，提交 `35c17fe6936ccdd5af3a729be842026284cf829d`；采用独立 merge commit。
- main 原有未提交的 04 完成记录先保存为 `b705624`。合并中仅该工单说明冲突，保留包含工作区与验收说明的 main 版本，与该提交逐字一致。
- 按 Git 路径集合核对：原 main 的 127 个文件、04 分支的 132 个文件均保留，缺失 0 个，无删除或重命名。本次另新增此核对记录。
- 04 业务文件直接保留分支内容，仅使用 Ruff 格式化 `practice.py` 与 `test_availability.py`，修复格式检查失败。
- 保留 04 分支和工作区；本次合并本地 main，未推送远端。

## 本次验证

- 后端：`uv run --locked pytest -q`，58 项通过；`mypy`、`ruff check .`、`ruff format --check .` 均通过。格式化后重新执行上述后端检查。
- 前端：`npm test`，20 项通过；`npm run lint` 与 `npm run build`（含 TypeScript 检查）通过。
- Git：文件集合无遗漏、工单记录保留、`git diff --cached --check` 通过，无未解决合并条目。
- 后端仍有现有 TestClient/httpx 弃用提示，不影响通过。本次未重新运行浏览器验收或调用模型；原有验收与审查文件已随分支保留。
