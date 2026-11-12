# 07 双轴代码审查

基线 `1888bae3693959526403f5471a6496668109065f`，首次实现 `7c464cc`；命令 `git diff 1888bae3693959526403f5471a6496668109065f...HEAD`。按 code-review 技能启用两个独立、只读、无会话历史的审查 Agent，分别检查规范与需求；审查不修改文件、不代替测试。

## Standards

No documented-standard violations found in the committed diff. The changed files do not conflict with the issue-tracker, triage-label, or domain-document rules. Tooling-enforced style/type checks excluded.

Two nonblocking baseline judgments:

- **Duplicated Code**: Both readiness and planning repeat `pool = [q for q in pool if q['interview_suitable']]`, a competency Counter, and the minimum-question eligibility filter. Extract the shared eligible-topic calculation so availability/start gating and actual selection cannot drift when eligibility changes.
- **Primitive Obsession**: `state: dict[str, Any]` defines a persistent aggregate containing nested groups, turns, coverage, limits, and string statuses; subsequent transitions mutate it. A small typed state/group/coverage model would make persistence and transition invariants explicit. This is a maintainability judgment, not a documented requirement or merge blocker.

No concrete correctness defect established during this read-only Standards review. No edits or tests performed.

处理：资格主题计算提取为 `eligible_topics`，可用性和规划共用。持久化聚合的全面类型建模作为非阻断维护建议保留；本次沿用既有 SQLite JSON 快照架构，接口行为由回归检查覆盖。

## Spec

1. **P1 — Observed knowledge gaps can become insufficient and trigger repeated questions.** The implementation overwrites `evidence_status=observed` whenever an applicable score is null. A provider can explicitly identify the candidate’s unknown mechanism while leaving accuracy unassessed; this guard changes coverage to insufficient and schedules another main question. Spec `docs/项目架构与需求_V1.md:280`: “对明确‘不会’的回答记录为已观察到的知识缺口…不再为让用户答对而重复提问。” Completeness must remain separate from dimension scoring.
2. **P2 — Ending during evaluation violates the specified conflict behavior.** The implementation accepts finish while the model job runs and cancels its local job. Spec `docs/项目架构与需求_V1.md:320`: “模型处理期间暂停、结束、重复点击下一题返回明确冲突；V1 不实现任意时刻中断远端请求。”
3. **P2 — Partial terminations have the wrong session status.** The implementation assigns `completed` for every stop reason. Spec `docs/项目架构与需求_V1.md:317`: “模拟面试提前结束或保护上限…completing → ended_early，生成部分报告及终止原因。”
4. **P2 — Fully evaluated expressive stages report partial assessment coverage.** The implementation removes inapplicable dimensions, then divides by 100. Spec `docs/项目架构与需求_V1.md:342`: “可评价权重 / 本题适用权重”. The denominator must exclude inapplicable dimensions.

No concrete scope creep found. No files edited or full suite run. Reviewer could not import dependencies using default Python; the parent agent uses `backend`'s `uv run` environment for reproduction and validation.

处理：四项均先通过 HTTP 回归测试重现失败，再修正。观察状态与数值评分解耦；评价中 finish 返回 409；部分结束为 `ended_early`；反馈支持适用权重分母，同时修正项目与行为题权重。单题默认权重与反馈契约保持兼容。

首次审查：Standards 0 项硬违规、2 项非阻断建议；Spec 4 项，最高 P1。两位审查者对 `7c464cc...d773105` 复核：重复资格计算已修正，无新增规范问题；四项需求问题全部解决，残余 0。字典聚合类型建模保留为一项非阻断维护建议。

随后真实模型调用促使补齐两个边界：不适用维度不要求伪造精确引文（适用维度校验不放宽）；明确未知声明由服务端阻止继续施压。两项均先写失败的 HTTP 回归再修正，补充复核见最终记录。

真实模型诊断又确认未评价维度使用空引文的合法分支。增加三种 HTTP 行为验证：null 与空引文通过、有分数与空引文拒绝、null 与非真实非空引文拒绝；先确认首种失败，再实现未评价空引文例外。该规则不将缺少依据改成已评分结果。

末轮两位审查者分别指出同一项 P2 风险：未知声明的非锚定表达式会把“我不会这样做”或引用别人的“我不会回答”误标为自述知识缺口。新增三个反例先确认失败，再收窄为回答开头的直接声明或“这道题问的…”声明，并排除“不会这样/这么做”的设计意图。有效直接声明仍由原有正例覆盖。

模型提示词更新至 `single_question_v2 / interview_group_v2`，额外提供当前保存回答的真实子串候选供模型原样复制；服务端仍验证最终引文，不因模型使用了候选就跳过校验。

最终复核 `cb9fdfa...3471edc`：两路均确认声明误判已修复，引文校验保留，没有剩余严重问题或规范硬违规；Spec 残余 0。规范仍保留一项非阻断的持久化聚合类型建模建议。最终 113 项后端回归、mypy、ruff check/format 和 5/5 场真实模型 HTTP 验收通过；重启后五份报告逐一一致。
