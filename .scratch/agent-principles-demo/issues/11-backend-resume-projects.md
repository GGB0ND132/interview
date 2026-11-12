# 11: 后端简历项目解析与确认

**What to build:** 用户上传文字版 PDF 或 DOCX 简历，服务端提取可查看的项目片段；用户确认后，模拟面试可把项目作为经历切入和当前主问题的追问情境。

**Blocked by:** 07 后端模拟面试编排与报告。

**Status:** ready-for-agent

- [x] 文字版 PDF/DOCX 上传经过格式和大小检查，保留原文定位与提取出的项目片段；扫描件或解析失败有明确说明和粘贴文本回退。
- [x] 解析结果需要用户确认；未确认片段不能影响面试选题或追问。
- [x] 确认后的内容作为候选人陈述参与经历切入或相关追问，不视为外部核实的经历与成果，也不能充当技术答案依据。
- [x] 用户确认无相关项目经历时，面试转入明确标注的假设情境题，不捏造履历。
- [x] 通过接口验证上传、预览、确认、解析失败与无项目经历路径；个人学习资料知识库入库不在本项范围。

## Comments

- 2026-11-12：在 `GGB0ND132/11` 实现，先从 `1888bae` 快进到已完成的 07 依赖 `2ba2cff`。实现提交 `9a5f2ef`，审查修正 `f3a01e8`。新增 `/api/v1/resumes` 上传/预览、`/resumes/text` 粘贴回退、`/resumes/{id}/confirm` 确认；schema 5 保存原文定位和已确认会话快照，`config.resume_id` 关联模拟面试。
- 已确认片段仅为候选人自述，选择项目进入已发布经历问题，无项目确认进入明确假设情境；技术参考答案和评分引文仍独立。未确认拒绝关联，未选中片段不发送模型，面试中撤回经历后停止使用原片段。仅后端，前端属于 12；未接入知识库。
- 17 个简历 HTTP 测试通过。真实 TCP 验收使用合成简历和临时数据库，完成两次真实模型评价及一次相关追问；重启后 4 条简历记录和报告一致。Standards 独立审查 0 项；Spec 初审的未知 XML 编码失败回退问题已修正并独立复查，剩余 0 项。
- 最终回归：后端全套 130 passed，mypy / Ruff check / format check 通过；前端 20 passed，TypeScript 构建与 lint 通过。
- 接口、限制和验证见 `backend/README.md`、`docs/verification/11-backend-resume-projects.md`、`docs/verification/11-live-model.json`、`docs/verification/11-code-review.md`。保留五种默认 triage 状态中的 `ready-for-agent`，完成情况以本工单勾选和评论为准。
