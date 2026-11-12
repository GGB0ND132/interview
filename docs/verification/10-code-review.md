# 10 独立代码审查

日期：2026-11-12。分支 `GGB0ND132/10`。

固定基线 `fb130fd3c660d7aadaad8fbee82a3f3642cfbb01`（已合并 08/09 的 main），实现 `37c413f`，规范修正 `541c973`。比较 `git diff fb130fd...HEAD`；规范与规格分别由两个全新上下文的子 Agent 并行审查。

## Standards

依据根 AGENTS.md、docs/agents 三份约定及 UI.md；仓库没有额外 CODING_STANDARDS.md、CONTRIBUTING.md、GLOSSARY.md 或 ADR。另使用 code-review 技能的 Fowler smell baseline，工具可检查的问题不重复计入。

初审 4 项：JD 原文缺少 20～20000 字及 blur 校验/计数；错误字段缺少 aria-invalid、帮助文字替换和焦点管理；异步按钮缺少 aria-busy 与加载图标；抽选元信息使用 UI.md 禁止的间隔点拼接。另有一个非硬性重复代码建议：提取确认失效逻辑。

`541c973` 全部修正：失焦与提取校验、字段错误和链接摘要、无效提取聚焦字段、一般 API 错误聚焦摘要、计数预警、按钮加载语义、独立元数据元素及 invalidate()。新增行为回归先失败后通过。独立复查结论：全部原发现及重复代码建议已解决，无剩余可操作的规范违规。

## Spec

依据 `.scratch/agent-principles-demo/issues/10-frontend-jd-confirmation.md` 及阶段 spec，核对后端 JD 和报告契约。初审及修正复查均无发现：未确认不进入配置；修改原文或勾选即撤销引用；题包切换丢弃迟到响应；确认缺口后可开始；权重及报告使用服务端快照，无新增主问题或保证抽中的文案。

非阻断边界：服务端已提交确认但响应丢失时，旧 revision 重试会冲突，需重新提取；页面保留原文并给出此恢复方式。工单不要求 JD 确认幂等。

最终：Standards 0 项未解决；Spec 0 项发现。审查为静态独立审查，运行结果由主 Agent 的验收记录提供。
