# Agent 原理与系统基础档：双模式阶段演示规格

Status: ready-for-agent  
Target date: 2026-11-18  
Scope: Agent 原理与系统基础档；模拟面试与试题练习

## Problem Statement

现有前端仍以固定演示题、预设追问和组件状态展示练习。工单 01 已完成真实单题后端闭环，但题库批量发布、前端接入、模拟面试和个性化流程仍待实现。用户需要在 2026-11-18 前，用自己的联网电脑演示两种连接真实题库与服务的练习模式，同时如实说明可用题数和未覆盖能力。

## Solution

两种模式共用版本化 Agent 基础题库。试题练习随机抽一道合格题、保存回答并立即给出反馈。模拟面试按开场、经历或假设情境、技术、行为和候选人反问推进，从合格主题随机规划技术题，按回答生成聚焦追问，并以证据覆盖决定完整或部分报告。JD 文本经确认后影响可覆盖主题的选题权重；文字版 PDF/DOCX 简历的项目片段须先由用户确认，再用于经历切入和追问。无上传资料也能完成两种模式。

## User Stories

1. As a learner, I want separate mock interview and question practice entrances, so that I can choose a full conversation or one question.
2. As a learner, I want to start either mode without uploading documents, so that preparation does not block practice.
3. As a learner, I want to see the actual available question count and coverage gaps, so that I know what the published pack can assess.
4. As a learner, I want practice mode to draw an eligible question and provide immediate feedback, so that I can train a specific ability quickly.
5. As a learner, I want a mock interview to cover introduction, experience or a stated scenario, technical abilities, behavior and candidate questions, so that the flow resembles an interview.
6. As a learner, I want follow-ups tied to my actual answer and the current main question, so that I can clarify gaps without receiving unrelated questions.
7. As a learner, I want a complete report only when required stages and priority abilities have enough evidence, so that an early or thin conversation is reported as partial.
8. As a learner, I want a blank submission to count as zero and a deliberate skip to have no score, so that the report reflects what I did.
9. As a learner, I want to paste and confirm a JD, so that relevant published abilities receive more weight and unsupported requirements remain visible.
10. As a learner, I want to upload and confirm résumé project text before it is used, so that parsing mistakes do not become interview facts.
11. As a learner, I want refresh to restore the current question, saved answers and my unsent draft in the same browser, so that an interruption does not erase my work.
12. As a learner, I want a failed model or retrieval step to preserve my answer and offer retry, so that the system does not substitute canned feedback.
13. As a learner, I want to inspect genuine supporting citations and report a wrong question or score, so that I can challenge uncertain feedback.
14. As a maintainer, I want every source question checked before publishing and failures reported, so that the 115 source candidates are not mistaken for 115 usable questions.
15. As a maintainer, I want two sampled reviews in each Agent topic, so that obvious answer or rubric errors are caught before release.

## Implementation Decisions

- 工单 01 的 FastAPI、SQLite、模型调用、单题评分和幂等提交已完成并保留；后续工单在现有接口和题目快照上扩展，不重复实现该闭环。
- 首批仅开放 Agent 原理与系统基础档。固定 MianStack 取材提交 `b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77`，目标处理 115 道基础题；其中 30 道原仓库标记已有答案，85 道待补。只用标准题目，第三方题集和面经不进入本批。
- 缺答案题可由 Agent 补写，但须记录来源状态和版本。每题自动检查题面、ID、分类与难度、完整答案、评分点和原题定位；只让通过项进入可评分题池。12 个主题各在发布前人工抽查两题，发现错题先停用并扩大抽查，重复错误暂停主题评分。
- 两种模式只从已发布题库选主问题。模拟面试从题量足够且适合面试的主题中随机选 3～4 个，通常约 7～8 道主问题，上限 12 道；开场、经历或情境、行为与反问的通用题可跨场次复用。JD 对可映射主题加权但仍随机；没有合格题的 JD 要求留作未覆盖项。
- 模型可针对当前主问题和用户实际回答、已确认 JD/简历生成追问，不得临时生成未经发布的主问题。简历项目是候选人陈述，不是外部核实的成果；JD 与简历都不能证明技术答案正确。
- 非空回答先保存再评价。空白提交由后端直接记 0 分、计入均分并单列，不调用模型；明确跳过为无分数且不计均分。模拟面试在结束后展示详细评分，试题练习在单题结束后立即反馈。
- 原题定位与独立技术资料分开保存；没有核对过的独立资料时不展示伪造引用。题目或评分报错记录应包含题目 ID、答案版本和用户说明。
- 服务端持久化正式问答、任务与报告；同一浏览器按会话和轮次保存未提交草稿。失败保留答案并重试，不用预设结果冒充实时生成。
- 11 月 18 日先验收双模式真实闭环、JD 文本、简历上传确认、历史与恢复。试题练习的关联重答与下一题、JD 文件上传、个人学习资料入库及其他方向不作为当天必做。

## Testing Decisions

- 使用两个外部行为验收入口：发布题包后的可用题数和拒绝原因；浏览器连接真实后端完成双模式及个性化、恢复和失败路径。测试观察用户与维护者能看到的结果，不复刻内部实现。
- 发布验证覆盖缺字段、重复 ID、无效来源定位、停用与版本变更；接受数须与可抽题数一致。保留 12 个主题各两题的人工抽查记录。
- 单题练习验证随机抽题、非空回答、空白 0 分、跳过无分数、即时反馈和幂等提交。工单 01 的已通过检查是后续回归基线。
- 模拟面试验证五类环节、3～4 个技术主题的选择快照、追问上限、完整与部分报告，以及含糊、答错、不会和无项目经历的分支。
- JD 验证无输入、可映射和无法覆盖三种情况；简历验证上传确认、解析失败回退和无简历练习。未确认资料不得影响会话。
- 两种模式分别验证刷新恢复、后端重启读取、任务中断接管和失败重试。真实引用应解析到保存的支持片段；仅有原题来源时不得伪造技术资料引用。

## Out of Scope

- 11 月 18 日前开放 Python 后端、React、Vue 或更高难度的 Agent 题包。
- 为演示强行发布未通过校验的全部 115 道题，或宣称抽查证明了所有答案正确。
- 从 JD、简历或实时检索生成新的正式主问题。
- 试题练习的重答与下一题、JD 文件上传、个人学习资料入库、语音、公开多用户服务和多 Agent 运行架构。

## Further Notes

- 2026-11-10 用户指定的 05 批次执行例外：先由独立子 Agent 审核，只有未解决的问题交给人工；无未解决问题后工单回到 `ready-for-agent`。05 保留单独的 Agent 审核身份、版本与材料记录，不冒充人工抽查。该授权不更改 06 或其他批次的审核要求。

- 阶段验收目标与长期 V1 功能范围以项目需求 V1.5 和题库运行流程为准。01 已完成真实单题后端验收；其他工单仍未完成。
- 抽查不能保证未抽中题目的技术答案正确。发布结果必须保留答案来源状态和实际可评分数量，用户可报告题目或评分问题。
