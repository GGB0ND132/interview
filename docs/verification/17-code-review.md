# 17：独立规范与规格审查

日期：2026-11-14。技能：`mattpocock-skills:code-review`。固定基线 `6e2605746e7ad87304702670b8d8a9787c9675fd`。审查在提交前对 `git diff --cached 6e26057` 进行，另核对两处后续工作树修正；当时没有新增提交。两个审查者使用独立新上下文，不修改实现。

规范来源为 `AGENTS.md`、`docs/agents/{issue-tracker,triage-labels,domain}.md`、`backend/pyproject.toml` 以及技能的完整代码异味基线。本库没有 `CODING_STANDARDS.md`、`CONTRIBUTING.md`、根 glossary 或 ADR。规格来源为本功能 spec 与 17 号工单，结合 05/06 的已记录发布例外。

## Standards

审查者：`/root/standards_review`。

硬性规范违反 0 项，可行动的代码异味判断 0 项。工单目录、Comments 与 `needs-info` 遵循仓库约定。发布核对通过公开 HTTP 边界，发布检查、准备和证据捕获职责清楚。

核对机器证据与叙述一致：115 可用、单题 91、空白 0、跳过 null、模拟 9 份提交并形成部分报告。人工审核未完成，受控恢复与真实模型证据分开。未提出修正要求。

## Spec

审查者：`/root/spec_review`。

本次工具未发现新增的可行动规格缺陷或越界实现。保留两项 P2 既存验收/质量问题：

1. 工单要求“12 个主题各两题的人工抽查结论”，实际仅有 Agent 审核；GUI 仅一题。报告如实披露，第一项未勾选、`needs-info` 防止宣称全部通过。
2. 规格要求追问基于当前问题与实际回答/确认资料；本次真实模型追问出现未被候选人明确提供的“不自动重试”前提。证据中保留原文，报告列为后续质量修正，未将其冒充已解决。

真实反馈为 `qwen-plus`，受控恢复为 `external_adapter`；面试环节完整与 JD 缺口造成的部分报告并存，记录一致。空白/跳过、发布数量与重启比较符合所记事实。高表达分与 JD 重试词未映射也已披露，没有声称解决。

审查者独立运行 `uv run --locked pytest tests/test_demo_acceptance.py -q`，2 passed。未要求修改本次工具。

## 修正与复核

审查前自动检查发现新测试 import 排序，已修正并通过 Ruff check/format 与专项测试；浏览器 prepare 输出改用实际存在的 `selection_algorithm/topic_candidates/topic_draws`；操作手册补充 `--verify-existing`。两个审查者都检查了这两处工作树补充。

Standards：0 项，最严重问题无。Spec：2 项已披露的既存 P2 问题，分别是人工抽查缺口与追问事实边界；本次新增缺陷 0 项。

## 用户回归跟进审查

固定基线 `b7f905742fabb98a1bca439141b9ab56bdc7c7e5`，提交前以 `git diff --cached b7f9057` 检查新增修正；提交列表当时为空。两个独立新上下文审查者不修改代码，规范和规格来源沿用上文。

### Standards

审查者 `/root/followup_standards_review`：0 项硬性违规，0 项值得提出的代码异味。工单状态与 Comments 符合约定；人工身份与结论为空/pending，生成器拒绝覆盖已存人工表。HTTP 清单、文档生成与恢复测试职责及现有写法一致，无需修正。

### Spec

审查者 `/root/followup_spec_review`：新增缺陷 0、范围扩张 0。保留 1 项既存 P2：工单第一项要求各主题两题人工结论，实际只有 23 题待审材料、GUI 第二位缺来源，不能认定人工验收完成；不应撤销 05/06 既有 Agent 发布授权。当前实际可评分过滤与服务端最新 published、错题隔离及主题暂停规则一致。

审查者独立运行针对性 5 项测试，覆盖未发布、停用、修正隔离、主题暂停及双模式恢复；全部通过。另验证生成的发布表、抽查包、人工表与清单一致，题号分别为 115/23 个唯一值。本轮完整验证：后端 206 passed、前端 61 passed，mypy、Ruff check/format、TypeScript/Vite build、ESLint 通过。没有新增浏览器或收费模型调用。

本轮 Standards 0 项，最严重问题无；Spec 1 项既存 P2 人工验收缺口，新增问题 0 项。
