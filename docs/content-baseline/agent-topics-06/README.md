# 06 题包与人工复核入口

当前状态：**内容和发布机制已准备，正式发布等待人工核查**。固定 MianStack 提交 `b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77` 的后六主题共 58 题，21 题保留原文答案，37 题补答；58 题均有本项目独立编写的评分点。115 是全部基础题取材数，不能标作当前可评分数。

## 12 主题盘点

下表为本分支、空验收数据库中的实际结果。前六主题的 57 题仅保存固定来源快照，05 的候选题包尚未合入本分支；未整理与拒绝分开计数。后六主题的自动通过不代表技术正确性已获人工确认。

| 主题 | 取材 | 原仓库有答案 | 本分支已整理 | 自动通过 | 拒绝 | 人工抽查完成 | 正式可抽 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Agent 基础与运行循环 | 17 | 3 | 0 | 0 | 0 | 0 | 0 |
| Agent 应用架构与场景设计 | 18 | 4 | 0 | 0 | 0 | 0 | 0 |
| 规划、推理与任务执行 | 8 | 1 | 0 | 0 | 0 | 0 | 0 |
| 上下文工程 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| 记忆系统 | 6 | 1 | 0 | 0 | 0 | 0 | 0 |
| 工具调用与 Function Calling | 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| MCP、A2A 与工具协议 | 15 | 3 | 15 | 15 | 0 | 0 | 0 |
| Skills 能力系统 | 13 | 7 | 13 | 13 | 0 | 0 | 0 |
| 工作流、状态与执行恢复 | 5 | 4 | 5 | 5 | 0 | 0 | 0 |
| 多 Agent 编排与协作 | 8 | 4 | 8 | 8 | 0 | 0 | 0 |
| Agent 框架与 Harness | 16 | 3 | 16 | 16 | 0 | 0 | 0 |
| GUI、Computer Use 与多模态 Agent | 1 | 0 | 1 | 1 | 0 | 0 | 0 |
| 合计 | 115 | 30 | 58 | 58 | 0 | 0 | 0 |

重新连接自己的服务后，可用数以实时 availability 为准，不以上表覆盖已有数据库。盘点命令自动读取 05 的 `agent_topics_first_half.json`（存在时）和本题包，始终列出全部 12 个主题。主题名称含 A2A 不代表固定版本有独立 A2A 基础题或已经覆盖其全部规范。

## 文件与版本

- [review-cards.md](review-cards.md)：11 张待人工核查卡片，包含完整答案、评分点、原题定位与完整内容 SHA-256。
- [human-reviews.json](human-reviews.json)：真实审核记录入口，目前审核人、时间、材料与发现均空白，结论为 `pending`。
- [逐题编辑稿](../../../backend/content/agent-topics-second-half.md)：每道题的评分点及缺答案题的完整补答，不复用万能答案。
- [补答依据与版本](../../../backend/content/agent-answer-sources.json)：编辑阅读清单；动态文档按记录日期定位，不能当已独立核对的引用。
- [逐题来源记录](../../../backend/content/agent-topics-second-half-provenance.json)：原文件 SHA-256、答案/评分点来源和依据键。
- [可导入候选题包](../../../backend/src/interview_backend/agent_topics_second_half.json)：原题 ID、题面与分类不改，状态为 candidate，独立 `answer_refs` 为空。
- [固定来源快照](../../../backend/src/interview_backend/mianstack_snapshot.json)：完整 115 道标准基础题；没有导入第三方题集或面经。

补答作者记录为 Codex，运行时模型标识没有独立留档，因此没有编造具体模型版本。生成日期采用日精度 `2026-11-10`，编辑版本 `06-editorial-v1`，题目内容版本 `agent-basics-06-v1`。参考经历题不要求伪造使用经验；代码或项目实操题不标为适合模拟面试主问题，但仍保留在单题练习候选中。

## 人工核查与发布

按 [卡片](review-cards.md) 打开原题和独立资料，核对技术结论、限定版本与评分点，填写 `human-reviews.json` 对应记录：

1. `reviewer` 为实际人工审核人，`reviewed_at` 为带时区的 ISO 时间。
2. `materials` 的每项填 `locator`、`version`、实际核对的 `checked_excerpt`；不能直接复制阅读清单冒充已经核对。
3. `findings` 记录发现和理由，结论改为 `approved` 或 `changes_required`。未审核保留 `pending`。
4. 同主题至少两道不同题，有补答时至少包含一题补答。默认选题优先补答；可自行换成其他题并填写其完整内容哈希。

GUI 只有 Q-0897 一题，**不重复计算、不自造第二题、不自动降低门槛**。当前流程会阻塞 GUI。需由需求方明确是否允许“固定来源全部一题人工核查”的例外，或另行批准扩展题源；这不妨碍其他五个完成核查的主题发布。

从 `backend/` 执行（服务先按 backend README 启动）：

```powershell
# 只预检和读取实时数量，默认不写题库
uv run python -X utf8 scripts/release_agent_topics.py --reviews ../docs/content-baseline/agent-topics-06/human-reviews.json --output ../docs/verification/06-current-inventory.json
# 完成人工核查后，才通过此命令导入符合门槛的主题
uv run python -X utf8 scripts/release_agent_topics.py --reviews ../docs/content-baseline/agent-topics-06/human-reviews.json --publish --output ../docs/verification/06-current-release.json
```

审批绑定完整候选内容（包括题面、来源、答案、评分点和版本）的规范 JSON SHA-256；内容有改动须更新内容版本、重新核查。空白或无材料的审批不生效；无效、重复或过期的非 pending 审批会阻止本次写入。报告保留人工记录副本、逐题预检/发布原因、12 主题数量及当前服务的真实可抽数。

`--publish` 可以发布已审核主题而保留未审核主题；若整套 12 主题尚不齐备，保存结果后退出码为 2，必须读 `publication` 和 `published_now_count` 判断是否已有部分主题写入。幂等重放不会复制题目。03 的通用维护发布 API 仍是受信任维护入口，**人工门槛由此发布流程执行，不是鉴权边界**；不要用通用接口绕过正式审核。

## 错题、扩大抽查与恢复

维护接口均位于 `/api/v1/maintenance/topic-quality/{competency_id}`，状态和复查记录保存在 schema 3 SQLite，服务重启不丢失。

| 操作 | 方法/后缀 | 请求/效果 |
| --- | --- | --- |
| 查质量状态 | GET，无后缀 | 错误记录、暂停状态、需抽查数、恢复历史、当前完整候选内容及哈希 |
| 发现已知错题 | POST `/incidents` | `{code, expected_version, error_kind, reason}`；原子停用该版本、隔离题号，扩大到同主题 4 道不同题；不足 4 道则检查全部 |
| 重复主题错误 | 同上 | 同一未解决周期内第二条错误记录触发主题暂停，错误类别可以不同；同一版本重复报同一错误不累计 |
| 修正题目 | POST `/corrections` | `{expected_version, candidate, review}`；须先为该停用版本登记 active incident，新 `content_version`、逐题自动校验和真实人工批准缺一不可，批准结构与前文相同；更正记录保存在 publication |
| 复查后恢复 | POST `/resume` | `{samples:[...]}`；达到扩大抽查数且包含全部更正错题，按当前内容哈希复核后才能解除暂停与隔离；记录完整材料、发现、结论和时间 |

单道错题更正后仍隔离，直到扩大抽查完成。暂停主题和隔离题同时从 availability 与真实抽题候选池剔除；评价开始前及模型返回后都会检查状态，避免执行中的任务落下已失效评分。回答保留并返回明确错误，历史题目快照不改写；已停用旧版本不会因发布新版本而重新评分。空白 0 分和明确跳过的既有规则保留。

`error_kind` 应统一使用具体错误类别，例如 `mcp_transport_vs_result_streaming`，以便识别同类错误。`reason` 保存发现及材料定位。维护入口沿用当前项目本机、无认证的部署边界；填写 `actor_type=human` 是受信任维护者的人工声明，不是系统自动证明有人审核过。

## 重新生成与验证

```powershell
uv run python -X utf8 scripts/prepare_agent_sources.py
uv run python -X utf8 scripts/build_agent_topic_pack.py
uv run python -X utf8 scripts/build_agent_review_cards.py
uv run python -X utf8 scripts/acceptance_agent_topics.py --output ../docs/verification/06-topics-http.json
```

来源脚本只读取固定 commit 的标准题。卡片脚本不会覆盖已有人工 JSON；候选内容修改后需显式复核旧记录中的哈希。验收脚本只在临时数据库中用通用维护接口验证 58 题可导入、六主题可实际抽取并保存跳过报告；它不生成真实审批、不调用模型、不修改正式数据库。实际正式发布仍为 0，不能将机制验收题数作为已人工审核题数。
