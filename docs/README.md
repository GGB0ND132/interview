# 文档导航

启动、模型配置、数据库和页面操作从[根 README](../README.md)开始。

| 文档 | 用途 |
| --- | --- |
| [项目架构与需求](项目架构与需求_V1.md) | 产品需求基线与后续范围，包含超出当前阶段的规划 |
| [题库建设与运行流程](题库建设与运行流程.md) | 来源、候选、审核、发布、版本与质量维护 |
| [题库整理与审核提示词](题库整理与审核_Agent提示词.md) | 内容整理工作规范 |
| [UI 规范](../UI.md)与[当前页面稿](design/页面设计稿_V3.md) | 当前界面基线 |
| [内容基线](content-baseline/README.md) | 知识资料、能力地图、来源和题包说明 |
| [Agent 工作约定](agents/issue-tracker.md) | 本地工单位置及操作约定 |

## 最终验收

- [最终验收与已知限制](acceptance/17-demo-acceptance.md)
- [演示与重跑手册](acceptance/17-demo-runbook.md)
- [115 题发布处理表](acceptance/17-publication-record.md)
- [抽查材料](acceptance/17-human-review-packet.md)及[用户确认记录](acceptance/17-human-reviews.json)
- [测试材料](../tests/README.md)：发布审核输入、解析样本和最终验收证据

旧工单验收、合并与审查记录、过期调研和旧设计已删除；已提交的历史可从 Git 查阅。本地工单评论保留当时的历史路径，不作为当前文件入口。保留的审核 JSON、用户确认表及最终验收数据不重写。新运行结果写入忽略的 `output/`，不要覆盖已确认的抽查表。
