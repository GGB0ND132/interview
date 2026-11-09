# 03 后端题库发布与可用性验收

日期：2026-11-09。实现分支 `GGB0ND132/03`，审查基线 `2622c53f635d563813505103c238519d9ff89827`。

## 已实现

- 维护入口逐题预览和发布，拒绝项不阻塞合格项；记录接受/拒绝原因、预计或实际新增版本数、重复项数、12 主题可用数。
- 固定 MianStack 提交 `b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77`，仅接收标准 Agent 基础题。核验真实源文件身份、分类、难度、主题和答案状态；保留原题标题、路径、URL、文件 SHA-256、MIT 署名及许可定位。
- `source_original` 逐字核对原文答案；Agent 补答保留生成时间、作者、模型、版本，原源题 pending 状态不改写成 ready。题面、答案及评分点有缺失/占位内容时拒绝。
- 同内容版本幂等，改写须增加内容版本并生成新的服务端题目版本；拒绝旧版覆盖。历史会话保留题面、答案、评分点与来源完整快照。
- 停用当前版本后不回退旧版，不允许重复导入或换版本导入偷偷恢复；已经开始的会话保留原快照，未开始的 draft 在 start 时重查候选池。
- 发布与练习可用性使用相同已发布最新版本集合；自编样题包与 MianStack 包隔离。schema 1 自动迁移至 schema 2，不覆盖原会话。

## 外部行为验证

`backend/tests/test_publishing.py` 通过维护 HTTP API、练习 API 与真实临时 SQLite 验证发布、拒绝、并发幂等、版本快照、停用、draft 重查、重启读取和旧数据库迁移。外部 GitHub 错误/待答来源用 HTTP transport 替身，不替换内部题库与数据库。

独立 TCP HTTP 验收：启动本机 Uvicorn 和全新临时 SQLite，运行 `backend/scripts/acceptance_publishing.py`。证据见 [03-publishing-http.json](03-publishing-http.json)。

- Q-0058：Agent 是什么，由哪些核心能力和组件组成？
- Q-0140：Workflow 和 Agent 有什么区别？

两题均取自上述固定提交，使用完整原文答案，评分点由本项目整理；原始文件快照和 MIT 全文随代码保存。初始可用 0，预览不写入，发布后可用 2；重复发布新增 0。按能力筛选后两题分别被抽到。评分点改版得到版本 2，而已有会话仍为版本 1。停用后可用 1。四种拒绝记录（缺字段、重复 ID、无效定位、停用）均可通过 publication ID 重读。

本次没有调用付费模型；旧会话继续按旧答案和旧评分点评价的行为由外部模型边界替身验证，工单 01 的真实模型验收仍是原记录，不将它冒充本次新调用。三份内置原始源文件已重新联网逐字比对固定提交，均一致。

独立双轴审查与修正见 [03-code-review.md](03-code-review.md)：拒绝未经核对的独立引用输入，共享最新已发布版本选择与主题计数，并使用类型化生成元数据。修正后重新运行 TCP HTTP 验收。

## 范围限制

这批两题用于验证 03 的发布机制。未完成全部 115 题内容整理，也未完成 12 主题各两题的人工抽查；这些由 05/06 跟进。自动校验能拦截结构、来源和明显占位问题，不能证明每份答案的技术正确性。未核对的原文资料链接不作为本项目独立技术引用。

维护入口沿用本机单用户服务边界。示例之外的原题需要联网读取固定提交，读取失败时逐题拒绝；已经开始的练习使用服务端持久化快照。

## 复现

最终检查：54 项测试通过（含 32 项发布检查和 22 项原单题回归），mypy、ruff check、ruff format --check 均通过。依赖 TestClient 输出一条现有 httpx 弃用提示，不影响检查结果。

在 `backend/` 执行 `uv sync --locked --extra dev`、`uv run --locked pytest -q`、`uv run --locked mypy`、`uv run --locked ruff check .` 和 `uv run --locked ruff format --check .`。HTTP 验收使用独立空数据库启动服务，随后运行 `uv run --locked python -X utf8 scripts/acceptance_publishing.py --base-url http://127.0.0.1:8000`；该验收会改版和停用验收题。
