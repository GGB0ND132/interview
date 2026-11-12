# 08 独立代码审查

固定点 `2ba2cff`（07 前置依赖）；首轮实现 `4edf9d8`。分别以全新上下文启动 Standards 与 Spec 审查，使用 `git diff 2ba2cff...HEAD`，没有让审查 Agent 修改代码。

## Standards

依据 `AGENTS.md`、`docs/agents/*`、`UI.md` 与 `docs/ui-design/页面设计稿_V3.md`。仓库没有单独的 CODING_STANDARDS、CONTRIBUTING、GLOSSARY 或 ADR 文件。

首轮五类规范问题：上翻阅读时自动滚动；报告正文和移动元信息字号偏小；阶段播报与提交 busy 状态不全；统计使用元信息间隔点；装饰图标未隐藏。另有一项判断性建议：两处 disposition 文案映射重复。

修正至 `cdb9f8f`：只在跟随底部时滚动内部问答区，否则显示跳转提示；尊重 reduced-motion；报告正文 16px、元信息 13px；独立 polite 状态区与 busy 属性；统计分列；装饰图标隐藏；统一 disposition 文案。复查发现辅助提交按钮和 setup form 仍缺 busy 属性，收尾补齐。移动截图发现经历/情境后端主题名相同，前端改用不同的自然环节名称。

最终 Standards Agent 复查结论：“Confirmed: the remaining busy-state Standards item is resolved. Stage-first competency labels introduce no Standards concern. No unresolved findings from my review.”

## Spec

依据 `.scratch/agent-principles-demo/issues/08-frontend-mock-interview.md` 和阶段规格，并核对 07 实际 API。

审查结论：无可执行的规格缺陷或越界。页面按服务端环节、题目、追问、状态和可用操作运行；revision、同步锁及错误后重新读取防止状态分叉；详细反馈仅在结束后渲染；完整与部分报告保留缺口；模式历史隔离。草稿刷新持久化和引用报错属于明确后续工单。

最终计数：Standards 0 项未解决，Spec 0 项。浏览器真实模型验证由主 Agent 单独完成，见 [08 验收](08-frontend-mock-interview.md)。
