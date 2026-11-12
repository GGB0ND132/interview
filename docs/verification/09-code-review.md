# 09 独立代码审查

基线为已完成的 07 依赖 `2ba2cff7400245fce26ee6724444ce8d79f07d07`，初审提交为 `0e7fcc6929b0b3eb9b6315d99bf0f071a054539d`，规格修正提交为 `8d81cf94729d5c3f080b998470b76ff68001f6ae`。审查命令：`git diff 2ba2cff7400245fce26ee6724444ce8d79f07d07...HEAD`。

审查对象为用户指定的 09 工单、阶段规格及本次改动；两名独立 Agent 分别处理 Standards 和 Spec，未合并排序。规范来源：`AGENTS.md`、`docs/agents/issue-tracker.md`、`triage-labels.md`、`domain.md`、`backend/README.md`、`backend/pyproject.toml`。仓库无 GLOSSARY、ADR、CODING_STANDARDS 或 CONTRIBUTING；不凭空增加规范。

## Standards

无已记录仓库规范的硬性违规。

一项可选判断建议：`jd.py` 的 requirement/mapping/coverage 结构使用 `dict[str, Any]`，跨提取、持久化、选题和报告通过字符串键读取。可在后续以 `TypedDict` 定义稳定结构，帮助发现字段拼写或形状变化。这沿用当前仓库快照建模方式，不是功能缺陷或已记录规范违规。

审查考虑了全部 smell baseline，没有其他可操作发现。测试与验收中的随机结果重放属于独立检查，不要求与生产抽选实现共用代码。

## Spec

初审一项 P2：“无相关已发布主问题的 JD 要求作为未覆盖项返回……报告仍显示该缺口。”

复现 `熟悉工具调用 + Kubernetes` 经提取、确认、开始和完整问答后，单条要求仅映射工具能力；工具能力被观察后误报 JD 全覆盖。`/` 与括号也有同类问题。该问题是明确未知技术被掩盖，不能仅以词表保守的说明免责。

修正：要求分段支持 `+`、`/`、中英文括号，保留完整主题名、Plan and Execute、C++；未知片段及其原文位置单独保留。三个新增 API 回归在修正前均失败，修正后均通过，完整报告保留 Kubernetes 的 `unmapped_requirement`，综合结果为 `partial`。

原规格审查 Agent 独立复跑三个回归通过，另核对全部 12 个主题名、Plan and Execute、C++ 和 ASCII 括号；确认原 P2 解决，修正中无新增阻断缺陷。确认/revision 门槛、不可变会话映射、带权随机记录和技术证据隔离未发现其他规格缺陷或范围外行为。

Standards：0 硬性违规、1 非阻断建议；Spec：初审 1 项 P2 已修正并复查，剩余 0 项阻断发现。

最终验证：后端 **130 passed**；JD 专项 **17 passed**；mypy、ruff check/format 通过。三场真实 HTTP/模型验收通过，最新代码重启后报告摘要 **3/3 一致**。现存依赖的 TestClient 弃用提示不影响通过结果。
