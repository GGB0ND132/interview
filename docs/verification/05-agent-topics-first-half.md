# 05 前六主题题包交付与验证

日期：2026-11-10。分支 `GGB0ND132/05`，实施前基线 `4a721d9a747a24ab3d8245ee309812ceb1b760cd`。

当前为**独立子 Agent 审核及修正复查通过、ready-for-agent，尚未正式发布**。按用户 2026-11-10 最新指示，05 先由子 Agent 审核，只有未解决疑点才转人工。本轮 57/57 通过，需人工裁决问题为 0；工单已勾选 4/5，正式目标数据库发布验收仍未完成。实际审核见 [独立内容审核](05-independent-agent-review.md)。

## 内容

从固定 MianStack 提交 `b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77` 的标准 `questions/` 全量盘点 115 道 Agent 基础题，前六主题实际为 57 道。只保存本批 57 题源文件，沿用 MIT 全文与署名；没有引入面经和第三方题集。

| 主题 | 候选数 | 自动校验通过数 | 本次正式新增发布 |
| --- | --- | --- | --- |
| Agent 基础与运行循环 | 17 | 17 | 0 |
| Agent 应用架构与场景设计 | 18 | 18 | 0 |
| 规划、推理与任务执行 | 8 | 8 | 0 |
| 上下文工程 | 2 | 2 | 0 |
| 记忆系统 | 6 | 6 | 0 |
| 工具调用与 Function Calling | 6 | 6 | 0 |

8 题使用原文完整答案，48 题为 Agent 补答，1 题为原文小幅编辑；每题有独立评分点、原题定位和内容版本。Q-4839 与 Q-2995 在内容审核修正后升为 `05.2`，其余为 `05.1`。源题 `pending` 保持不变。生成记录标注本次 Codex、日期 2026-11-10（精度为日期），实际运行时型号不可核验，明确记录 unavailable；生成与独立 Agent 审核均不冒充人工核实。

经历/项目介绍题允许诚实说明未实践并给出假设方案，不拿示例项目当候选人真实经历；这类题中的 9 题标为不适合模拟面试技术规划，但仍可单题练习。独立技术资料只用于维护者抽查准备，`answer_refs` 留空，符合 13 之前的引用边界。

两处整理修正：Q-1909 原题面“工具如何分类？”不足发布要求的八字符，扩为“Agent 的工具可以如何分类？”，原题标题仍从源文件保存。Q-2536 原文“等待补充条件”触发既有“待补”占位检查，改成“等待条件补齐”，标 `maintainer_edited` 并记录生成元数据；没有放宽发布校验。

## 文件与复现

- `backend/src/interview_backend/first_half_candidates.json`：57 题候选，不自动写入数据库。
- `first_half_editorial.json`：本项目补答、评分点、题面/原文编辑，是可维护的编辑输入。
- `first_half_scoring_notes.json`：逐题可选点与常见误区；构建后评分表明确列出考察点、必须点、可选点与可接受变体，可选扩展缺失不扣分。
- `first_half_inventory.json`：取材提交、下载包哈希、每题源文件 SHA-256、题号、分类、原答案状态。
- `mianstack_snapshot.json`：沿用 03 的固定源文件缓存，增加本批真实源题，离线也能核对发布来源。
- [审核与人工升级说明](05-human-sampling.md)、[12 题题册](05-sample-questions.md)、`first_half_review.json`：完整材料、真实 Agent 样本结论和两次扩大复查，人工字段保留为空。
- `first_half_agent_audit.json`：三个独立审查者对全部 57 题的版本、结论、发现及资料组记录。

机械重建：先下载固定提交 zip，再在 backend 运行 `uv run --locked python -X utf8 scripts/prepare_first_half.py <zip-path>`。脚本读取其中全部标准题的元数据再筛选，不下载执行第三方代码。已有人工记录不会被重建覆盖；内容变化后旧摘要会被发布命令拒绝，必须重新复核，不能只更新摘要冒用旧结论。

预览：`uv run --locked python -X utf8 -m interview_backend.first_half_release --database <explicit-sqlite-path>`。显式路径避免误用日常数据库；空数据库会初始化 03 既有 schema 和自编样题，但 MianStack 正式题数仍为 0。正式发布流程见人工抽查说明。

## 实际验证

以公开发布、可用性、会话抽题接口为测试面，使用临时真实 SQLite。回归验证全量内容、六主题抽题、缺失/失败/缺样本/旧摘要拒绝、全主题复查、明确授权的独立 Agent 通过、人审否决，以及扩大抽查同题通过与失败并存仍拒绝。单元测试中的通过记录明确标为合成 fixture，不能当作实际审核证据；实际子 Agent 记录另行保存。

真实 TCP HTTP 验收由 `scripts/acceptance_first_half.py` 启动独立 Uvicorn，在自动清理的临时数据库验证。机器记录见 [05-first-half-http.json](05-first-half-http.json)：先用缺失审核的临时记录验证拒绝且可用数 0，再读取真实独立 Agent 审核记录，经正式发布命令在验收库接受 57、拒绝 0、六主题实际抽题、重复导入新增 0；模拟停用一题后可用 56，重新导入保留拒绝原因。临时库已移除，未正式上线。复现：`uv run --locked python -X utf8 scripts/acceptance_first_half.py --output <report.json>`。

本次未调用付费模型，不声称这批分数经过人工校准。最终重建后后端完整测试 **73 passed**，mypy、ruff check 与格式检查通过；仅有既有 Starlette/httpx 弃用提示。双轴独立审查发现的 2 项 P2 均已修正并复核。详情见 [05-code-review.md](05-code-review.md)。
