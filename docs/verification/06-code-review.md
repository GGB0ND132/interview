# 06 双轴代码审查与最终检查

固定基线 `4a721d9a747a24ab3d8245ee309812ceb1b760cd`，初始实现 `cee2fc079d5f860ad4d6940c37127b9b851384ce`，修正 `efaf00c360c52f844e955f4fa17609ce187040c8`。已确认基线可解析、`git diff 4a721d9...HEAD` 非空。两个独立审查 Agent 使用全新上下文，分别执行规范轴与规格轴；均只读，没有代填人工技术核查。

## Standards

核对 `AGENTS.md`、`docs/agents/issue-tracker.md`、`triage-labels.md`、`domain.md`、`backend/README.md` 与 `backend/pyproject.toml`。没有发现硬性规范违反。工单使用允许的 `needs-info`，评论在 `## Comments`，待审核状态与测试中的合成审批明确分开。

初审有 1 条非阻塞判断：未解决错误列表的切片在候选池、评分、错误登记和恢复路径重复。修正提取 `store.active_incidents()`，复核确认重复已消除，没有新的可行动问题。

复核原结论："Standards follow-up: clean. ... No documented-standard violations or new actionable smells found. Documentation consistently reflects the revised pause and correction rules."

## Spec

依据原始 06 工单和 `agent-principles-demo/spec.md`，初审发现 2 条 P1，均已修复并用先失败后通过的接口测试复现：

1. 原来只有同一 `error_kind` 的错误重复才暂停，未充分满足“重复主题错误导致主题评分暂停”。现改为同一未解决周期内第二条不同题目/版本错误即可暂停，不要求错误类别相同；同一版本重复报错不累计。
2. 先通过旧停用接口停用，再调用新 `/corrections`，原来可绕过扩大抽查。现在更正须匹配 active incident，否则返回 `409 QUALITY_INCIDENT_REQUIRED`；登记错误后，更正版本仍隔离，扩大复查通过后才能恢复。

复核原结论："Both P1 findings are resolved in efaf00c. ... Reviewed the targeted diff and recovery paths; no new issue identified within this scope. Independently ran the two affected integration test files: 8 passed."

人工抽查、正式发布与 GUI 单题例外是明确记录的验收阻塞，不由技术审查 Agent 代替。58 题临时数据库的导入和抽题测试不计为正式内容发布。前六主题缺口在 12 主题盘点中明确保留。

当前规范轴 0 条未解决，规格轴 0 条未解决；两轴均无剩余最高严重度问题。

## 最终验证

实现与审查过程中完成以下检查；全套前后端回归及静态检查运行于修正后的 `efaf00c`，TCP 内容机制证据由基础实现生成并保留：

| 检查 | 结果 |
| --- | --- |
| backend `uv run pytest -q` | 66 passed |
| backend `uv run mypy` | 10 个源文件通过 |
| backend `uv run ruff check .` | 通过 |
| backend `uv run ruff format --check .` | 24 个文件格式通过 |
| frontend `npm test -- --reporter=dot` | 20 passed，2 个测试文件 |
| frontend `npm run build` | TypeScript 与 Vite 生产构建通过 |
| frontend `npm run lint` | 通过 |
| 候选题重建后 `git diff --exit-code` | 候选题与逐题来源记录可重复生成，无变化 |
| TCP HTTP 内容机制验收 | 58 题预检/导入、六主题数量/实际抽题、六份跳过报告通过，正式发布流程保持 0 |

现有 Starlette TestClient 产生 1 条依赖弃用提示，没有失败测试。没有调用真实模型、没有浏览器视觉验收、没有修改正式题库；本次任务没有修改前端代码。

## 后续独立内容审核与修订复查

用户随后明确要求独立子 Agent 审核、仅有未决问题时转人工，并在通过后进入 ready-for-agent。三个内容 Agent 完成 58 题全量核查，修正六题的协议版本/引用一致性或评分范围，当前均复核通过，见 [06-content-review.md](06-content-review.md)。

内容修订提交 `3547749` 相对 `ae7d849` 再由两个独立 Agent 执行 Standards 与 Spec 复查：规范轴无硬违反或可行动 smell；规格轴确认 58 条当前哈希匹配、来源快照未改和修订身份准确，只指出旧 README 与来源清单说明未同步，此问题已更新为 16 原文/5 修订/37 补答、6 题 v2/52 题 v1。

本轮后端完整回归 67 passed，前端完整回归 20 passed，mypy/ruff/格式通过；修订后的 TCP 验收仍为 58 题通过及六主题实际抽题一致。工单状态更新为 ready-for-agent，正式发布单列为未执行；人工模板保留真实空白，不将子 Agent 审核标成人工。
