# 03 实现审查

基线：`2622c53f635d563813505103c238519d9ff89827`。实现 `91684ea`；审查修正 `c09dc18`。

使用 mattpocock `code-review` 技能，两个独立上下文分别检查 Standards 与 Spec。首轮命令为 `git diff 2622c53f635d563813505103c238519d9ff89827...91684ea`；修正复核为 `git diff 91684ea...c09dc18`。

## Standards

文档标准来源：`AGENTS.md`、三份 `docs/agents/` 约定、`backend/README.md` 与 `backend/pyproject.toml`。无 `CODING_STANDARDS.md`、`CONTRIBUTING.md`、词汇表或 ADR。未发现硬性违规；本地 issue 路径、Comments 和五种 triage 状态使用符合约定。

首轮两项 Fowler 启发式建议（判断项，非硬性违规）：

- Possible Duplicated Code：发布预览与练习分别实现最新已发布版本选择和主题计数。修正为共享 `Store.published_questions` 与 `topic_counts`，避免策略漂移。
- Possible Primitive Obsession：generation 为任意字典，并在业务代码手动按键校验。修正为 `GenerationMetadata`，集中字段类型、非空和 ISO 时间校验。

独立复核结论：两项建议均已处理，修正 diff 未发现新增实质规范问题。

## Spec

首轮发现 1 项 P2：发布入口允许任意非空 `answer_refs`，之后原样出现在反馈 `independent_references`。这不满足父规格“没有核对过的独立资料时不展示伪造引用”和“真实引用应解析到保存的支持片段”。独立审查使用伪造 URL 成功复现。

修正：03 发布模型仅接受空 `answer_refs`，非空内容逐题拒绝，其他合格项仍可发布；增加先失败后通过的维护 HTTP API 回归检查。独立引用保存与核对留给 13，01 已核对样题保持原有行为。原题正文自带的资料目录不标作本项目独立核对引用。

独立复核结论：P2 已解决，针对性回归通过，共享候选查询与生成元数据模型没有引入新的 03 规格问题。固定来源、逐题拒绝、发布预览、部分导入、幂等、版本保留、停用和两道真实来源题验收均符合 03；全部 115 题整理与主题人工抽查正确留给 05/06。

标准：0 硬性违规、2 项建议均已处理；规格：1 项 P2 已修正，复核后 0 未解决缺陷。
