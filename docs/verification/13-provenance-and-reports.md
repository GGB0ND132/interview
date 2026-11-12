# 13 后端答案来源与错题反馈

## 行为与契约

范围为当前分支的单题后端（依赖 01、03）。未接入 07 模拟面试或 14 前端。普通反馈不再返回 `answer_origin / answer_generation`；维护入口和服务端题目快照保留这些内部字段。

题目开始时冻结 `verified_references`，作答时持久化 `provenance_json`。非空、空白、跳过和失败均有题目 code、question/answer version、content_version、原题定位和原文答案状态。评价成功后只保存模型实际使用的独立资料及运行时核查实际使用的资料；无证据使用时为空数组。`GET /sessions/{id}/report` 增加 `provenance`；反馈保留 `reference_answer` 与既有分数契约。

旧 schema 1–3 自动升级至 4，不重算历史分数。迁移从原会话快照恢复题目与答案来源，标记 `legacy_without_evidence_snapshot`。旧的链接/关键词元数据不追认为完整证据，普通读取过滤它们，原始内部记录保留。

以下路径均带 `/api/v1` 前缀。

| 接口 | 契约 |
| --- | --- |
| `POST /maintenance/questions/{code}/evidence` | 维护者核对支持关系后提交 `expected_version,title,url,excerpt,claim,reviewer`。`reviewer` 是实际核查者，提交表示已经检查片段支持 claim；不是由普通用户声明即放行。服务端再次抓取并逐字校验片段，保存时间、文档正文 SHA-256 和证据 ID。登记前后检查当前答案版本，冲突 409；未找到片段 400。 |
| `GET /maintenance/questions/{code}/evidence?answer_version=1` | 读取指定答案版本的已登记证据。 |
| `GET /maintenance/submissions/{id}/provenance` | 读取评分内部来源快照，包括 Agent 补答状态与生成元数据。 |
| `POST /sessions/{id}/reports` | `turn_id,category=question\|score,explanation`；题目 code、答案版本及 submission ID 均由会话快照推导，不能由用户指定。评分类报错须已有完成的评分记录。返回 201、报错 ID、`status=open`。 |
| `GET /sessions/{id}/reports/{report_id}` | 读取该会话的报错记录；其他会话访问 404。 |
| `GET /maintenance/reports?status=open&page=1&page_size=20` | 按状态筛选并分页列出报错，可省略状态。 |
| `GET /maintenance/reports/{id}` | 读取报错及处理历史。 |
| `POST /maintenance/reports/{id}` | `expected_status,status,note`，支持 `open/in_review/resolved/dismissed`，并发处理状态不符 409。追加处理记录，不覆写用户说明。 |

报错是疑问，不自动认定题目错误。维护者确认后通过已有 `POST /maintenance/questions/{code}/disable` 停用当前版本；报错仍绑定用户当时看到的历史版本。停用后新 draft/start 使用现有统一候选池，不会回退抽取旧版。06 的隔离与主题暂停机制保持有效。

## 证据边界

原题 `question_source` 与独立技术资料 `independent_references` 分开。独立资料包含真实保存的 `excerpt,claim,url,title,checked_at,reviewer,document_sha256,id`，不生成文档页码。维护登记需要人工或实际 Agent 核查；自动逐字校验只证明片段存在，不单独证明语义正确。

只允许服务端 `EVIDENCE_ALLOWED_HOSTS` 列表内的 HTTPS 文档 URL；禁止凭据、其他端口、重定向，限制正文 2 MB，脚本/样式内容不算可见正文。维护者应使用最终规范 URL。例如 Anthropic 旧 `/engineering/building-effective-agents` 已重定向，实际资料入口为 `/research/building-effective-agents`。

模型将超出答案范围或有版本争议的结论列入 `technical_checks`，含 `claim,query,reason,affected_dimensions`。服务端按查询词检索**同题同答案版本的维护证据库**，最多五条；这是有意限定的资料检索，不是开放互联网搜索，不使用 JD/简历作技术依据，也不从网页生成主问题。

检索候选须重新读取来源且保存片段仍在正文；模型再次判断是否直接支持具体结论，服务端核查所选 ID 和支持引文的精确子串。关键词重合不足以支持结论。只将 `verified` 结果作为 `technical_explanations`，并保存支持片段与证据 ID。没有直接证据为 `insufficient_evidence`；网络、文档变化或模型核查失败为 `retrieval_failed`，保存 `attempt_id,query,candidate_ids,source_failures,error_code`，不回显提供商错误正文。

未能核实的争议至少使 accuracy/completeness 及声明受影响维度成为 null；重算分数和覆盖率，替换可能含确定结论的建议文案。实际回答不变，用户可报错等待维护。新增资料后可用于后续会话或正在评价的按需检索；已保存结果不会被后台资料更新改写。本项不新增已完成评分的重评入口。

该后端沿用本机单用户、维护接口无认证的现有运行边界。

## 验证入口

```powershell
cd backend
uv run pytest tests/test_provenance.py -q
uv run mypy
uv run ruff check .
uv run ruff format --check .
# 使用进程环境中的真实模型密钥，自动启动并重启临时 TCP 服务；数据库必须尚不存在。
uv run python -X utf8 scripts/acceptance_provenance.py --database data/13-live-new.sqlite3 --output ../docs/verification/13-live-provenance.json
```

定向 HTTP 测试覆盖完整片段与实际引用、仅原题来源、无证据争议、支持/不支持/网络失败/伪造引文的检索、用户报错/改版/处理/停用/重启、空白与跳过、旧库迁移、伪造资料 ID。仅替换外部模型与文档 HTTP 边界。

真实验收结果、完整回归及独立双轴审查将在完成后记录于此。
