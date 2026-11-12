# 10、11 分别合并 main 的核验记录

日期：2026-11-12。操作范围为本地 Git 合并；未推送、删除分支或工作区，未启动服务迁移任何现有业务数据库。

## 合并来源与保护

- 合并前 main：`fb130fd3c660d7aadaad8fbee82a3f3642cfbb01`。
- 备份分支：`backup/main-before-10-11-20261112`，指向上述提交。
- 10 来源：`GGB0ND132/10`，`6ced56a00d2629bc3f24bd9b77526b99722743fc`。
- 11 来源：`GGB0ND132/11`，`b87ad68aa5d5febb607e6714c4d517e89808d737`。
- main 原有未提交的 10、11 完成记录先保存为 `82a03bf`；最终内容与该提交一致。
- 10 独立合并提交：`4c2f243`，`Merge ticket 10 JD confirmation frontend into main`。
- 11 在 10 之后单独创建 merge commit，消息为 `Merge ticket 11 confirmed resume projects into main`；本文件随该合并提交保存。

## 冲突处理

10 自动合并成功，保留已保存的工单完成记录。

11 的 `api.py`、`practice.py`、`mock_interview.py`、`model.py` 合并后同时保留 JD 和简历功能：两套接口、创建时的独立确认快照、JD 加权选题、项目经历或假设情境、两类模型上下文及报告字段。报告继续按 JD 缺口计算完整性，简历信息不会覆盖 JD 结果。联合提示版本为 `interview_group_v4_jd_resume`。

两个分支曾独立使用 `migration_5.sql`：main 为 JD 表，11 为简历表。保留 main 原迁移 5，新增迁移 6，以 `CREATE TABLE IF NOT EXISTS` 补齐两套表。兼容 schema 4、JD 版 schema 5 和简历版 schema 5；不重建已有表，不删除记录。新的数据库也经过完整迁移链到 schema 6。

## 验证结果

10 合并后：前端 `npm test` 33 项通过，lint、build（含 TypeScript 检查）通过；当时后端 pytest 130 项、mypy、ruff 检查与格式检查通过。

11 合并结果：

- `uv sync --locked --extra dev` 成功。
- 聚焦 JD、简历和联合回归测试：39 项通过。
- 完整 `uv run --locked pytest -q`：152 项通过，47.30 秒；仅既有 TestClient/httpx 弃用提示。
- `uv run --locked mypy`：15 个源码文件通过。
- `uv run --locked ruff check .` 与 `uv run --locked ruff format --check .`：通过，43 个 Python 文件格式一致。
- 新增 5 项回归：三种旧数据库布局升级和二次启动保留每张既有表的全部行及已开始会话；有项目、无项目两条联合流程保留 JD 权重、模型上下文、原技术参考答案与评分表、JD 缺口报告及重启读取。
- 11 未修改前端，最终前端与 10 合并提交一致。

文件清单核对：合并前 main 的 222 个、10 分支的 229 个、11 分支的 208 个跟踪路径均保留，缺失数均为 0，无删除项。10 的功能改动内容与来源一致；11 除上述共用代码、迁移和 README 的必要整合外，新增简历代码、测试、依赖及既有验收材料与来源一致。迁移 5 的简历建表内容由迁移 6 承接。

`git diff --cached --check` 通过，索引无未解决冲突，源码和测试无冲突标记。

原有未跟踪文件 `docs/verification/05-main-merge-http.json` 未修改、未加入提交，SHA-256 仍为 `0784FF4073E91F5A041AFFC7FAA416B0E94E9E53833B3F7B24E2B90D761C14DF`。

本次未新增浏览器或收费模型验收；分支已有验收材料原样保留。新增验证使用临时 SQLite 和模拟的外部模型响应，实际执行完整 HTTP API、持久化与报告逻辑。
