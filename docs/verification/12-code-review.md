# 12：独立代码审查

审查基线：`f24d621156593f03dda149b859e3618305dd6245`（接入已完成依赖后的本地 main）。实现提交：`9aa55e3`；修正：`e6fd0b3`。两名独立子 Agent 使用新上下文并行读取 `git diff f24d621...HEAD`，分别检查 Standards 与 Spec。

## Standards

依据：`AGENTS.md`、`docs/agents/{issue-tracker,triage-labels,domain}.md`、`UI.md` 和现有组件规范；未发现 `CONTRIBUTING.md` 或 `CODING_STANDARDS.md`。同时应用 code-review 的 Fowler smell baseline，作为判断而非硬性标准。

初审发现三项：

- P2：解析失败返回普通预览对象，上传完成分支仍清空用户已输入的项目文本，违反 UI.md 的失败保留输入要求。
- P2：上传/文本校验错误缺少对应字段的 `aria-invalid`、`aria-describedby` 与字段内错误提示。
- P3：提交控件只禁用，没有各自的 `aria-busy`。

修正后独立复查：三项均关闭。失败解析保留草稿，错误映射到字段，上传、预览、无项目确认和项目确认均暴露忙碌状态。独立运行简历专项 7 项通过；未发现新的可操作问题。没有额外代码异味、issue tracker 或领域文档违规项。

## Spec

依据：用户指定外部 `12-frontend-resume-confirmation.md`，并核对现有后端 `resumes.py`、`api.py`、`mock_interview.py`。

独立审查未发现遗漏、范围扩张或错误实现。上传状态、原文回查、片段选择、修正后重新确认、失败回退、仅关联已确认内容及明确的情境分支与工单一致。面试及报告中的项目来源展示支持所要求的可回查能力。

结论：Standards 初审 3 项，修正复查剩余 0 项；Spec 0 项。真实浏览器验收与完整测试由主 Agent 执行，见 `12-frontend-resume-confirmation.md`。
