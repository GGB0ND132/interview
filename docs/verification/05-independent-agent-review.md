# 05 独立子 Agent 内容审核

用户于 2026-11-10 明确指定：先由独立子 Agent 审核，仅把未解决问题交给人工；通过后转为 `ready-for-agent`。本记录按该指示替代 05 原来的常规人工抽查要求，不影响其他工单。

本轮覆盖 57/57 题的完整答案、考察点、必须点、可选点、误区与可接受变体。初审发现 2 处内容问题，修正和扩大复查后全部通过；需人工裁决的未解问题为 0。题包摘要：`95f13360681b8ca166ec49d47e4bb6f78de168215f459eabda1792e0917cb459`。

独立子 Agent 审核不等于人工审核，也不证明评分模型已校准。`human_review` 保持为空，实际子 Agent 结论写入单独的 `agent_review`；逐题机器记录见 [first_half_agent_audit.json](../../backend/src/interview_backend/first_half_agent_audit.json)，12 道样本和两次扩大复查记录见 [first_half_review.json](../../backend/src/interview_backend/first_half_review.json)。

## 已修正的问题

- Q-4839：`05.1` 把主动性窄化为定期观察，并把独立调度器设为必须。`05.2` 改为围绕目标主动发起或推进任务，允许事件、持续循环和定时机制；答案、考察点、必须点和误区同步修正。原审查者据 Wooldridge & Jennings 的主动性定义复核，并对运行循环主题 17 题逐题扩大复查，17/17 通过。
- Q-2995：`05.1` 的必须点无条件要求异步状态，会误伤正确的短任务同步执行。`05.2` 将异步查询或等效非阻塞限定于长耗时任务。原审查者据 Python subprocess 文档复核，并对工具主题 6 题扩大复查，6/6 通过。
- 发布检查：扩大抽查曾允许同题的通过记录掩盖失败记录。已改为任意不完整通过记录都阻断；独立复核确认，`expanded_veto` 回归验证拒绝且数据库题量为 0。

以上问题均有明确依据，可代理修正，无需用户裁决。未将这些实际发现删除，历史问题和复查结论保存在 incidents 中。

## 逐题审核与依据

下表“通过”覆盖完整候选答案及全部评分点，不是只看题面。来源组列出子 Agent 实际读取的资料；队列、预算、隔离、澄清及架构划分等属于工程判断，不冒充文档逐字规定。

### loop

审查者：`/root/content_review_loop`；首次审查/复核时间见逐题记录。范围：Agent 基础与运行循环。

- [Anthropic Building effective agents](https://www.anthropic.com/research/building-effective-agents)：What are agents; Agents; Appendix1。
- [Alibaba Function Calling](https://help.aliyun.com/zh/model-studio/qwen-function-calling)：工作原理1-5。
- [LangChain Agents](https://docs.langchain.com/oss/python/langchain/agents)：Model/Harness。
- [Wooldridge & Jennings](https://www.cs.ox.ac.uk/people/michael.wooldridge/pubs/ker95/subsubsectionstar3_1_1_1.html)：reactivity/pro-activeness。
- [Gemini Robotics](https://deepmind.google/blog/gemini-robotics-brings-ai-into-the-physical-world/)：Interactivity; controllers; safety。
- [Anthropic Agent Skills](https://www.anthropic.com/research/equipping-agents-for-the-real-world-with-agent-skills)：Anatomy; code execution。
- [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)：State; messages。

| 题号 | 版本 | 最终结果 | 核查发现 |
| --- | --- | --- | --- |
| Q-0058 | 05.1 | passed | 组件划分、状态/上下文和停止/成功边界正确，原答一致。 |
| Q-0419 | 05.1 | passed | 模型提议、宿主执行、回执反馈正确，不强制向量库。 |
| Q-0597 | 05.1 | passed | 模型生成与应用执行分工正确，原答一致。 |
| Q-1555 | 05.1 | passed | 消息状态依赖结构合理，索引按需，不设唯一实现。 |
| Q-1674 | 05.1 | passed | 两类运行时分工正确，明确是工程划分。 |
| Q-1843 | 05.1 | passed | 多环节归因与有限修复合理，预算和缺口边界清楚。 |
| Q-1897 | 05.1 | passed | 任务和反馈说明合理，接受文档了解或假设。 |
| Q-2330 | 05.1 | passed | 技能方法与工具接口分工正确，脚本依赖执行环境。 |
| Q-2466 | 05.1 | passed | 简洁概括闭环与成本可靠性权限挑战。 |
| Q-2612 | 05.1 | passed | 动态任务收益与固定流程边界正确。 |
| Q-2637 | 05.1 | passed | 对话入口和执行方式可重叠，非互斥类别。 |
| Q-3003 | 05.1 | passed | 循环工程明确是工程解释，未冒充标准。 |
| Q-3456 | 05.1 | passed | 模型/应用边界明确，不猜测不可见内部推理。 |
| Q-3946 | 05.1 | passed | 按动态控制与环境反馈判断，不按工具数量。 |
| Q-4839 | 05.2 | passed | 05.2复查：移除独立调度器的强制要求，目标主动性允许事件、持续循环或定时机制。 |
| Q-4896 | 05.1 | passed | 会话与任务是侧重点，允许交互澄清和后台目标交付并存。 |
| Q-5711 | 05.1 | passed | 具身感知行动反馈与高层/低层控制分工正确。 |

### architecture

审查者：`/root/content_review_architecture`；首次审查/复核时间见逐题记录。范围：Agent 应用架构与场景设计。

- [Dify](https://docs.dify.ai/en/quick-start)：Step2/3。
- [Coze](https://docs.coze.cn/)：产品定位与工具扩展。
- [OpenClaw](https://docs.openclaw.ai/)：What is OpenClaw; How it works; Configuration。
- [Anthropic](https://www.anthropic.com/research/building-effective-agents)：What are agents; coding agents。
- [Retrieval](https://docs.langchain.com/oss/python/deepagents/retrieval)：From retrieval to RAG; agentic RAG。
- [OR-Tools](https://developers.google.com/optimization/cp/cp_solver)：Model; return values。
- [KernelBench](https://github.com/ScalingIntelligence/KernelBench)：Evaluation; Multi-Turn。
- [APScheduler](https://apscheduler.readthedocs.io/en/master/userguide.html)：Introduction; Basic concepts。
- [Open-Meteo](https://open-meteo.com/en/docs)：API参数。
- [MCP](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)：Listing/Calling tools; errors; security。
- [Deep Research](https://openai.com/index/introducing-deep-research/)：How it works; Limitations。
- [UiPath RPA](https://www.uipath.com/rpa/robotic-process-automation)：RPA at a glance。

| 题号 | 版本 | 最终结果 | 核查发现 |
| --- | --- | --- | --- |
| Q-0137 | 05.1 | passed | 资料整理、人工核验和假设经历的评分边界公平。 |
| Q-0544 | 05.1 | passed | 产品定位和Dify节点步骤有官方依据，版本限制明确。 |
| Q-0561 | 05.1 | passed | RAG信息供给与Agent控制可组合，不强制向量库。 |
| Q-0898 | 05.1 | passed | 读仓库、编辑、测试和反馈闭环正确，不冒充已部署。 |
| Q-0925 | 05.1 | passed | 知识库和MCP调用链正确，允许仅讲一类或假设。 |
| Q-1009 | 05.1 | passed | 迭代研究、证据缺口和引用核验合理，不强制多Agent。 |
| Q-1434 | 05.1 | passed | 算子调优强调正确性及真实同口径测量，不要求虚构加速比。 |
| Q-2001 | 05.1 | passed | 建模与求解器分工正确，可行不等于证明最优。 |
| Q-2078 | 05.1 | passed | 宿主定时与天气数据职责清楚，允许固定工作流。 |
| Q-2797 | 05.1 | passed | RPA/LLM/Workflow/Agent分工可组合，未混淆分支与动态控制。 |
| Q-2985 | 05.1 | passed | 模型建议与程序执行权限分开。 |
| Q-2993 | 05.1 | passed | 本地推理与远程接口边界合理，不强求统一服务清单。 |
| Q-3382 | 05.1 | passed | OpenClaw网关、通道和会话描述与官方定位一致。 |
| Q-3383 | 05.1 | passed | 搜索与生成可重叠，引用不是正确性保证。 |
| Q-3921 | 05.1 | passed | 目标动作反馈与真实完成证据区分正确。 |
| Q-3939 | 05.1 | passed | 生成嵌入重排分工合理，不要求全部模型类型。 |
| Q-4188 | 05.1 | passed | 按动态需求、成本和可验证性选型。 |
| Q-4303 | 05.1 | passed | 按职责解释Agent与交接，允许单Agent，不虚构经历。 |

### planning_memory_tools

审查者：`/root/content_review_planning_memory_tools`；首次审查/复核时间见逐题记录。范围：规划、推理与任务执行、上下文工程、记忆系统、工具调用与 Function Calling。

- [Context engineering](https://www.anthropic.com/research/effective-context-engineering-for-ai-agents)：Context retrieval; compaction; structured notes。
- [Memory](https://docs.langchain.com/oss/python/concepts/memory)：Short/long term; memory types。
- [ReAct v3](https://arxiv.org/html/2210.03629v3)：Abstract; sections2/3.3/4。
- [Alibaba](https://help.aliyun.com/zh/model-studio/qwen-function-calling)：工作原理。
- [Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview)：Memory; Task planning。
- [subprocess](https://docs.python.org/3/library/subprocess.html)：Using; Security; Popen.communicate。
- [AWS retries](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/)：Timeouts; retries and backoff。
- [Structured output](https://docs.langchain.com/oss/python/langchain/structured-output)：ToolStrategy/ProviderStrategy。
- [topological_sort](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.dag.topological_sort.html)：DAG与拓扑序。

| 题号 | 版本 | 最终结果 | 核查发现 |
| --- | --- | --- | --- |
| Q-0062 | 05.1 | passed | 保存和召回进入上下文才影响回答，不等于权重更新。 |
| Q-0883 | 05.1 | passed | 函数调用请求与完整运行循环区分正确。 |
| Q-1675 | 05.1 | passed | 有限重试、参数修正及幂等边界有官方资料支持。 |
| Q-1909 | 05.1 | passed | 分类维度可交叉，题面扩写保留原ID。 |
| Q-2007 | 05.1 | passed | 记忆作用范围、内容类型与持久化区分正确。 |
| Q-2186 | 05.1 | passed | 待办记录不等于执行和调度，术语依项目。 |
| Q-2506 | 05.1 | passed | ReAct交替动作观察准确，不要求暴露完整思考。 |
| Q-2507 | 05.1 | passed | 错误观察和长轨迹风险合理，预算措施属工程判断。 |
| Q-2536 | 05.1 | passed | 规划反馈与累计预算边界正确，v0.7说明已查官方。 |
| Q-2659 | 05.1 | passed | 工具契约、宿主执行和业务完成分工清楚。 |
| Q-2676 | 05.1 | passed | Memory/RAG按目的生命周期区别，设施可复用。 |
| Q-2995 | 05.2 | passed | 05.2复查：仅长耗时任务要求异步或等效非阻塞，短任务同步方案不再误扣分。 |
| Q-3054 | 05.1 | passed | 按缺口影响决定澄清，区分偏好和外部事实。 |
| Q-3168 | 05.1 | passed | 指令和记忆文件的名称及加载依宿主而变。 |
| Q-3322 | 05.1 | passed | 节点边DAG拓扑含义正确，图表达不自动保证容错。 |
| Q-3323 | 05.1 | passed | DAG与有向环区别准确，允许分支并行和节点内重试。 |
| Q-3642 | 05.1 | passed | 意图是操作路由候选，不替代权限和事实校验。 |
| Q-4836 | 05.1 | passed | 结构合法、调用意图和业务成功不混淆。 |
| Q-4837 | 05.1 | passed | 记忆范围与内容类型交叉，短期状态也可持久化。 |
| Q-5588 | 05.1 | passed | 固定检索与按需工具可组合，不强制Function Calling。 |
| Q-7020 | 05.1 | passed | 上下文工程范围大于RAG，包含整体输入与约束。 |
| Q-7196 | 05.1 | passed | 摘要检索外存和分阶段处理的收益与信息损失均说明。 |

## 来源、范围与后续步骤

原题固定提交、ID、分类、状态与定位已核对，使用完整原文的答案保持原文身份，补答未冒充原答；独立材料没有写入尚未接通的用户反馈引用字段。产品能力依所读版本和部署配置成立，未来变化需重新核对。

未审查个人经历真实性，未逐一穷尽原答中的全部二手教程链接，未实际运行 GPU benchmark、求解器、天气通知或所有产品，也未证明模型对所有等价回答都能公平评分。以上是审核范围，不是未解决的技术疑点。

审核完成时工单转为 `ready-for-agent`，该轮只做独立审核、修正和临时数据库验证。用户随后要求继续剩余任务，本工作区持久化数据库发布和用户界面核验现已完成，工单 5/5，见 [05-live-release.md](05-live-release.md)。
