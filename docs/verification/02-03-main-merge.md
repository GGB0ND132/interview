# 02、03 分别合并至 main 的核对记录

日期：2026-11-09。

## 合并来源与顺序

- 原 main：`2622c53f635d563813505103c238519d9ff89827`。保留备份分支 `backup/main-before-02-03-20261109`。
- main 原有的两份未提交工单完成记录先保存为 `80bab67`，合并后两份工单与该提交逐字一致。
- 先将 `GGB0ND132/02`（`b50f6b011cc335620afed8482148baa44b5bf40f`）以独立 merge commit `e0b14f1` 合并至 main。
- 再将 `GGB0ND132/03`（`ddaeef3c8001552a31b129ae7bc3cdb282dfb7e2`）以独立 merge commit 合并至 main，本记录随该次合并保存。
- 两个实施工作区均无未提交改动，未删除实施分支或工作区。本次仅合并本地 main，未推送远端。

## 冲突处理与文件完整性

- 预演发现 `backend/README.md` 内容冲突：保留 02 的真实前端接入说明，以及 03 的发布服务、迁移、接口与运行说明。
- 正式合并 03 时，工单 03 的完成记录也与 main 原有补充发生冲突；保留 main 中包含实施工作区和分支信息的完整记录。
- `backend/src/interview_backend/practice.py` 自动合并，并核对两个方向的差异：02 的历史字段 `pack_title/created_at/difficulty` 和 03 的候选池、主题计数、题包版本及可选生成元数据处理均保留。
- 按 Git 路径集合核对：原 main 的 107 个、02 的 116 个、03 的 117 个受版本控制文件，均存在于合并结果中，各自缺失 0 个；合并文件并集为 126 个，另新增本记录。没有删除或重命名文件。
- 两个分支新增的全部文件保持原 blob；两个工单保持 main 合并前保存的内容。原 main 的改动路径均属于 02/03 的已知改动范围。
- `git diff --cached --check` 通过，无未解决的合并条目；冲突文件中无残留冲突标记。

## 组合结果验证

在 main 合并后的实际文件上执行：

- 后端：`uv sync --locked --extra dev`；`uv run --locked pytest -q`，55 项通过；`uv run --locked mypy`、`uv run --locked ruff check .`、`uv run --locked ruff format --check .` 均通过。
- 前端：`npm ci --no-audit --no-fund`；`npm test`，15 项通过；`npm run lint`、`npm run build` 均通过，构建包含 TypeScript 检查。
- 后端测试有一条现有 TestClient/httpx 弃用提示，未导致失败。

本次未重新调用付费模型或执行浏览器验收；两个事项原有验收证据完整保留，以上是本次对组合代码的实际检查。
