# 02 前端单题练习代码审查

日期：2026-11-09。审查范围：`git diff main...HEAD`，提交 `3778eb0` 及随后的审查修复。规格来源：工单 [02](../../.scratch/agent-principles-demo/issues/02-frontend-single-question-practice.md) 与 [spec.md](../../.scratch/agent-principles-demo/spec.md)。

两个审查面独立列出，不合并、不跨面排序。标准来源：`AGENTS.md`、`docs/agents/*`、`backend/README.md`、`backend/pyproject.toml`、`fronted/eslint.config.js`、`fronted/tsconfig*.json`、`UI.md`，另加 Fowler 代码异味基线（始终为判断项，仓库文档优先，工具已覆盖的项不再重复）。

## Standards

硬性违规 0 项。判断项与处理：

1. **未使用依赖抑制（已修复）**：`QuestionPractice` 挂载 effect 原先用 `eslint-disable react-hooks/exhaustive-deps` 掩盖 `load` 依赖。现改为 `useCallback` + `[load]`，仅对「异步取数 effect 内 setState」一条规则做带理由的窄抑制。
2. **可滥用命名（已修复）**：`restart` 实际「重试同一评价任务」，与「重新抽题」语义冲突，改为 `retryEvaluation`。
3. **重复逻辑（保留）**：`load`、`reopen`、`send` 兜底路径都执行「恢复会话并视 phase 继续轮询」。三处上下文不同（挂载恢复、历史打开、响应丢失对账），抽成一个 hook 会引入更多依赖与测试噪声；当前规模下保留，后续草稿恢复（16）若加入第四处再抽取。
4. **跨边界重复常量（保留）**：`QuestionFeedback` 以文案列出 35/25/15/15/10 权重。权重权威在服务端 `contracts.WEIGHTS`；前端只作说明性文案，不回算分数，故不引入第二份计算逻辑。
5. **N+1 查询（保留）**：`_view` 每会话多查一次 `role_packs` 取标题。当前每页最多 20 条，SQLite 本地读取；如发布校验加入更多关联列，再改为 JOIN。
6. **测试内重复（保留）**：空白与跳过用例各自内联完整会话对象。两例断言不同结果，合并助手会降低可读性。

## Spec

缺失或部分：

1. **`available_actions` 未被使用（已修复）**：工单要求页面从服务端读取「可用动作」；原实现只按 `phase` 推导界面。现回答框、跳过与重试按 `session.available_actions` 显示，并新增「服务端不给动作时不渲染作答区」测试。
2. **轮询没有终止条件（已修复）**：后台任务停留在 queued/running 时会永久轮询。现限制 150 秒后停止轮询，保留已保存回答，提示稍后重新打开。进程中断后的任务接管仍属 15，本项不声称已实现。

超出本项但良性：展示可用题数并说明无题原因（04 的核心项之一，此处仅为入口可用的最小信息，未做完整可用性与缺口页）；渲染 `independent_references` 链接（13/14 的完整引用与报错入口未做）；评价失败后的「重试评价」按钮（与 16 重叠，但为满足「失败保留答案并重试」的最小必需项）。

未发现「规格要求已实现但行为错误」的项。浏览器验收额外发现并已修复：刷新恢复后返回入口时开始按钮保持禁用（补回归测试）。

## 结论

标准面：0 硬性违规，6 判断项（2 已修复、4 保留并说明）。规格面：0 缺陷，2 项缺失已修复，列出 3 处良性相邻范围。
