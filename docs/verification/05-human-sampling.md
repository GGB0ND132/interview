# 05 发布前审核与人工升级

状态：独立子 Agent 审核及修正复查已通过，无未解决的人工问题。日期：2026-11-10。**本页与关联记录均明确区分 Agent 审核和人工审核。**

按用户 2026-11-10 最新指示，05 先由独立子 Agent 审核，只有未解决疑点才转人工；没有问题后回到 `ready-for-agent`。本轮已覆盖全部 57 题，包括每主题两道补答样本；两道问题题已修正，对其所在主题扩大复查通过。结论与材料见 [独立审核报告](05-independent-agent-review.md)。完整样本题面、答案和评分点仍在 [抽查题册](05-sample-questions.md)，真实记录见 [first_half_review.json](../../backend/src/interview_backend/first_half_review.json)。记录绑定完整题包 SHA-256；内容变化后必须重新核对。

## 核查材料

以下材料在本次实施中实际读取过。网页可能更新，因此记录章节与核查命题；来源链接仅供维护者审核，未写入用户反馈的独立引用字段。

| 编号 | 材料与位置 | 本次核对内容 |
| --- | --- | --- |
| A | [Anthropic，Building effective agents](https://www.anthropic.com/research/building-effective-agents)，What are agents、When (and when not) to use agents | 预定路径与动态决策的区别；从简单方案开始；成本与延迟权衡。 |
| B | [Anthropic，Effective context engineering](https://www.anthropic.com/research/effective-context-engineering-for-ai-agents)，Context engineering vs. prompt engineering 及长期任务部分 | 上下文包含指令、工具、外部资料和历史；窗口有限，需要筛选、压缩或外部笔记。 |
| C | [LangChain，Memory overview](https://docs.langchain.com/oss/python/concepts/memory)，Short-term memory、Long-term memory、Memory types | thread 范围状态与跨 thread 存储；情景、语义、程序性记忆是内容类型；持久化并不改变作用范围。 |
| D | [ReAct 论文 v3](https://arxiv.org/abs/2210.03629v3)，Abstract | 推理与行动交替，动作从外部环境取得信息，再用于更新计划。 |
| E | [阿里云，Function Calling](https://help.aliyun.com/zh/model-studio/qwen-function-calling)，工作原理五步 | 模型返回名称与参数，应用运行工具，将回执加入消息，再次调用模型。 |
| F | [Anthropic，Writing effective tools](https://www.anthropic.com/research/writing-tools-for-agents)，What is a tool、Principles | 工具是执行系统与 Agent 的契约；描述、回传信息与评测会影响使用效果。 |

## 12 题 Agent 自查结果

全选补答题以优先覆盖补答风险。下表结论仅表示 Agent 对所列命题未发现冲突，不能据此填写人工通过。

| 主题 | 题号 | 核查材料 | 发现与 Agent 结论 |
| --- | --- | --- | --- |
| 运行循环 | Q-0419 | A、E | 组件划分非唯一标准；核对模型提议、应用执行、状态回传。未发现所核命题错误。 |
| 运行循环 | Q-1674 | E、F | Runtime 名称依实现而变；候选答案明确不是统一协议。职责分工与调用链一致。 |
| 应用架构 | Q-0898 | A、F | 编码任务需读取、编辑和测试回执，生成代码不等于完成。未宣称测试等于部署。 |
| 应用架构 | Q-2078 | A、E | 固定天气查询优先工作流；调度器而非模型计时。时区、去重是本项目工程设计补充。 |
| 规划 | Q-0883 | A、E | Function Calling 仅提供动作请求，完整循环还有状态与停止。未混淆请求和执行。 |
| 规划 | Q-2506 | D、E | 对照交替动作与环境反馈；单次调用可提出工具意图，但不等于已执行。 |
| 上下文 | Q-7020 | B | RAG 是信息获取方式之一，非全部上下文工程。筛选及不可信输入处理为工程建议。 |
| 上下文 | Q-7196 | B、C | 筛选、分段、摘要与外部存储都可能丢信息；保留关键状态及输出预算。未把大窗口当万能解。 |
| 记忆 | Q-0062 | C | 需保存、召回后参与输入；不是更新模型权重，也不保证事实正确。 |
| 记忆 | Q-4837 | C | 生命周期与内容分类是交叉维度；短期状态也可持久化。未把情景记忆与长期记忆互斥。 |
| 工具调用 | Q-1675 | E、F | 结构参数需校验；错误分类、退避、幂等与未知结果查询是工程设计补充，非声称官方逐条规定。 |
| 工具调用 | Q-4836 | E、F | 核对调用意图与真实执行；结构输出可作数据结果。结构合法不证明语义或权限正确。 |

## 审核记录与后续发布

顶层 `review_policy=independent_agent_first` 明确本批授权，样本的 `agent_review` 单独保存审查者、带时区的审核时间、材料、发现与结论，`review_kind=independent_agent` 标识其类型；原 `human_review` 保持为空。若后续出现需人工裁决的疑点，则暂停并据实际人工核查填写 `human_review`，字段同样包含 `reviewer`、`reviewed_at`、`materials`、`findings`、`conclusion`。不能编造审核人、时间和结论，任一显式失败仍会阻断。

审核通过后，后续 Agent 可在 backend 目录对明确目标数据库发布：

```powershell
uv run --locked python -X utf8 -m interview_backend.first_half_release --database data/practice.sqlite3 --publish
```

默认读取仓库记录，也可用 `--review-file <path>` 指定记录。没有 `--publish` 时仅预览，返回预计接受数及实际已发布数；二者不同。没有明确 Agent 授权策略的记录仍按原人工方式检查。直接调用 03 通用维护 API 不会执行本批审核门槛，因此正式发布必须走此命令。审核完成时先进入 `ready-for-agent`；随后用户要求继续剩余任务，现已对本工作区持久化数据库发布，证据见 [05-live-release.md](05-live-release.md)。

## 错误、扩大抽查与暂停

一旦发现技术错误，记录失败与 `incidents` 的题号、主题、错误类型、发现和材料，停止本批发布并扩大到全主题。修正后另存通过复查结果，并保留原事件。尚未解决或无法依据资料判断的问题才升级人工。本批首次错误即暂停整批发布，同类错误再现时该主题继续暂停，直到修正与全主题复查完成。

尚未发布的错题保持候选；若其他维护流程已发布，立即调用 `POST /api/v1/maintenance/questions/{code}/disable`，携带当前 `expected_version` 和具体 `reason`。同主题重复出现同类错误时，对该主题全部已发布题执行停用，以实际可用数为 0 确认主题评分暂停。停用后原会话保留快照，新练习不可再抽到。03 的接口不支持通过重新导入恢复停用题；重新开放需单独处理，不要删库绕过。

修正正文或评分点时增加 `content_version`，保留原发现，更新绑定摘要，并重新核对 12 道常规样本。每个 incident 的 `expanded_review` 必须包含该主题所有题号及真实审核字段且全部通过，`resolution=corrected_and_rechecked` 才放行；同题的通过记录不能掩盖失败记录。不要移除旧事件跳过复查。自动校验和独立审核不能保证所有技术答案或模型打分都正确。
