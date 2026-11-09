# 03: 后端题库发布与可用性

**What to build:** 维护者能从固定版本的 MianStack 标准题整理并发布一批 Agent 基础题，看到每题通过或拒绝的原因；用户只会抽到通过发布校验的题。

**Blocked by:** 01 后端单题练习真实闭环。

**Status:** ready-for-agent

- [x] 固定取材版本，保存原题身份、分类、难度、来源定位、许可信息、答案来源状态和内容版本；第三方题集与面经不进入本批。
- [x] 逐题检查题面、唯一 ID、能力与难度、完整答案、评分点和原题定位；缺项或占位内容不可评分。
- [x] 发布预览列出接受数、拒绝数、每题原因和各主题可用数；只导入通过项，重复导入相同版本不复制题目。
- [x] 对已发布题的答案或评分点修改会生成新版本，旧会话保留原版本；停用题不再进入新练习。
- [x] 通过发布入口和练习可用性接口验证一批真实来源题；缺字段、重复 ID、无效定位和停用题均有可复现的拒绝记录。

## Comments

- 原始工单位于 `C:/Users/ctrlz/Desktop/study/interview agent/.scratch/agent-principles-demo/issues/03-backend-question-publishing.md`；业务代码仅修改当前实施分支，完成说明同步回原始工单。
- 2026-11-09：已实现发布预览、逐题拒绝、幂等发布、版本保留、停用和主题可用数。使用固定来源 Q-0058、Q-0140 完成真实 TCP HTTP 验收；全部 115 题内容整理和主题人工抽查仍属于 05/06。运行与接口见 `backend/README.md`；验收记录见 `docs/verification/03-backend-question-publishing.md`、`docs/verification/03-publishing-http.json`。现有五种 triage 状态没有 closed，完成情况以本工单勾选与记录为准。
