# 06 题包与审核发布入口

当前状态：**06 全部完成，独立 Agent 全量内容审核及正式本地持久化发布通过，工单 `ready-for-agent`**。固定 MianStack 提交 `b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77` 的后六主题共 58 题：16 题保留原文答案，5 题明确标记维护者修订，37 题补答；58 题均有本项目独立编写的评分点。继承 05 已发布的 57 题后，06 演示库当前实际可抽 115，完整证据与启动方式见 [在线发布验收](../../verification/06-live-release.md)。

按 2026-11-10 用户最新要求，本轮由三个独立子 Agent 全量审核，仅将不能自行解决的问题交人工。58 题均已核查，6 处问题修正后复核通过，没有未决内容问题；不再将原来的人工抽查模板作为本轮工单审核阻塞。当前题目完整哈希与材料记录已独立验证，详见 [审核汇总](../../verification/06-content-review.md)。

## 12 主题盘点

下表为实际 06 演示库结果。本分支整理、预检和 Agent 审核仅计后六主题；前六主题继承 05 已发布的 57 题，候选源码未合入本分支。未整理与拒绝分开计数，未将前六主题计为本轮重新审核。本轮真实人工审核为 0，没有代填身份。

| 主题 | 取材 | 原仓库有答案 | 本分支已整理 | 自动通过 | 拒绝 | Agent 内容审核 | 正式可抽 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Agent 基础与运行循环 | 17 | 3 | 0 | 0 | 0 | 0 | 17 |
| Agent 应用架构与场景设计 | 18 | 4 | 0 | 0 | 0 | 0 | 18 |
| 规划、推理与任务执行 | 8 | 1 | 0 | 0 | 0 | 0 | 8 |
| 上下文工程 | 2 | 0 | 0 | 0 | 0 | 0 | 2 |
| 记忆系统 | 6 | 1 | 0 | 0 | 0 | 0 | 6 |
| 工具调用与 Function Calling | 6 | 0 | 0 | 0 | 0 | 0 | 6 |
| MCP、A2A 与工具协议 | 15 | 3 | 15 | 15 | 0 | 15 | 15 |
| Skills 能力系统 | 13 | 7 | 13 | 13 | 0 | 13 | 13 |
| 工作流、状态与执行恢复 | 5 | 4 | 5 | 5 | 0 | 5 | 5 |
| 多 Agent 编排与协作 | 8 | 4 | 8 | 8 | 0 | 8 | 8 |
| Agent 框架与 Harness | 16 | 3 | 16 | 16 | 0 | 16 | 16 |
| GUI、Computer Use 与多模态 Agent | 1 | 0 | 1 | 1 | 0 | 1 | 1 |
| 合计 | 115 | 30 | 58 | 58 | 0 | 58 | 115 |

重新连接自己的服务后，可用数以实时 availability 为准，不以上表覆盖已有数据库。盘点命令自动读取 05 的 `agent_topics_first_half.json`（存在时）和本题包，始终列出全部 12 个主题。主题名称含 A2A 不代表固定版本有独立 A2A 基础题或已经覆盖其全部规范。

## 文件与版本

- [审核汇总](../../verification/06-content-review.md)：三个独立子 Agent 的 58 题全量审核、修订和复核结论。
- [review-cards.md](review-cards.md)：11 张备用人工核查卡片，包含完整答案、评分点、原题定位与完整内容 SHA-256；本轮无需代填。
- [human-reviews.json](human-reviews.json)：保留原人工记录模板，目前均为真实空白 `pending`，不冒充 Agent 审核结论。
- [逐题编辑稿](../../../backend/content/agent-topics-second-half.md)：每道题的评分点及缺答案题的完整补答，不复用万能答案。
- [补答依据与版本](../../../backend/content/agent-answer-sources.json)：编辑阅读清单；动态文档按记录日期定位，不能当已独立核对的引用。
- [逐题来源记录](../../../backend/content/agent-topics-second-half-provenance.json)：原文件 SHA-256、答案/评分点来源和依据键。
- [可导入候选题包](../../../backend/src/interview_backend/agent_topics_second_half.json)：原题 ID、题面与分类不改，状态为 candidate，独立 `answer_refs` 为空。
- [固定来源快照](../../../backend/src/interview_backend/mianstack_snapshot.json)：完整 115 道标准基础题；没有导入第三方题集或面经。

补答作者记录为 Codex，运行时模型标识没有独立留档，因此没有编造具体模型版本。生成日期采用日精度 `2026-11-10`；52 题保持 `agent-basics-06-v1`，Q-0140、Q-0379、Q-0416、Q-0872、Q-1247、Q-1664 六题为 `agent-basics-06-v2`，修订号 `06-content-review-v2`。参考经历题不要求伪造使用经验；代码或项目实操题不标为适合模拟面试主问题，但仍保留在单题练习候选中。

## 发布策略与备用人工入口

本轮按用户“继续执行后续任务完成06”指令，通过显式 `--review-policy agent_full --scope second-half` 聚合三份真实 Agent 审核记录发布全部 58 题。此策略要求固定来源、全部选中题的身份/内容哈希/材料/结论有效，缺失、过期或无效审批阻止整批写入。默认 `human_sample` 仍要求每主题两道不同题的真实人工样本；质量更正及恢复接口仍使用人工策略。Agent 审核不写入人工模板。两种策略均遵循既有停用、隔离与主题暂停限制。

本次实际发布命令和幂等/重启验收见 [在线发布验收](../../verification/06-live-release.md)。以下保留备用人工流程，未在本轮代填或执行：

按 [卡片](review-cards.md) 打开原题和独立资料，核对技术结论、限定版本与评分点，填写 `human-reviews.json` 对应记录：

1. `reviewer` 为实际人工审核人，`reviewed_at` 为带时区的 ISO 时间。
2. `materials` 的每项填 `locator`、`version`、实际核对的 `checked_excerpt`；不能直接复制阅读清单冒充已经核对。
3. `findings` 记录发现和理由，结论改为 `approved` 或 `changes_required`。未审核保留 `pending`。
4. 同主题至少两道不同题，有补答时至少包含一题补答。默认选题优先补答；可自行换成其他题并填写其完整内容哈希。

GUI 固定来源只有 Q-0897 一题，本轮已通过独立 Agent 全量 1/1 核查并发布，不重复计算、不自造第二题。默认人工策略的“两条人工样本”规则保持原样；显式 Agent 策略要求全部来源题获批，无需伪填第二题或人工身份。

从 `backend/` 执行（服务先按 backend README 启动）：

```powershell
# 只预检和读取实时数量，默认不写题库
uv run python -X utf8 scripts/release_agent_topics.py --reviews ../docs/content-baseline/agent-topics-06/human-reviews.json --output ../docs/verification/06-current-inventory.json
# 完成人工核查后，才通过此命令导入符合门槛的主题
uv run python -X utf8 scripts/release_agent_topics.py --reviews ../docs/content-baseline/agent-topics-06/human-reviews.json --publish --output ../docs/verification/06-current-release.json
```

审批绑定完整候选内容（包括题面、来源、答案、评分点和版本）的规范 JSON SHA-256；内容有改动须更新内容版本、重新核查。空白或无材料的审批不生效；无效、重复或过期的非 pending 审批会阻止本次写入。报告保留人工记录副本、逐题预检/发布原因、12 主题数量及当前服务的真实可抽数。

默认人工策略的 `--publish` 可以发布已审核主题而保留未审核主题；显式 Agent 策略需选中范围全部满足门槛才写入。选中范围不完整或实际发布未达标，保存报告后退出码为 2；须读 `publication` 和 `published_now_count` 判断是否有写入。幂等重放不会复制题目。报告的来源与实时可用数为全局 12 主题口径，整理/审核数量为选中范围，详见 `selected_for_release`。03 通用维护 API 仍是受信任维护入口，审核门槛由此发布流程执行，不是鉴权边界。

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

来源脚本只读取固定 commit 的标准题。卡片脚本不会覆盖已有人工 JSON；候选内容修改后需显式复核旧记录中的哈希。`acceptance_agent_topics.py` 只在临时数据库中验证机制，不生成真实审批、不调用模型、不修改正式数据库。实际持久化发布另见 `06-live-release.json`：本轮 Agent 审核 58、新增发布 58、全库可抽 115。`verify_live_agent_topics.py` 通过实际 HTTP 检查版本、继承数据与前端代理；`--draw` 会创建六个明确跳过的演示会话。
