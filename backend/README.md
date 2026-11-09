# 单题练习与题库发布服务（工单 01、03）

Python 3.11+、FastAPI、SQLite。提供两道自编 Agent 基础技术样题的真实单题闭环，以及 MianStack 固定版本题目的逐题发布入口。自编样题与 MianStack 题包独立，后者初始可用数为 0，发布通过项后才可抽取。03 附带两道真实来源题验证发布机制；全部 115 道题的整理与每主题人工抽查属于 05/06。

## 本地运行

从 `backend/` 目录执行：

```powershell
uv sync --extra dev
# 将 .env.example 复制为 .env 并填写 LLM_API_KEY，或在进程环境设置 DASHSCOPE_API_KEY。
uv run uvicorn interview_backend.api:create_app --factory --host 127.0.0.1 --port 8000 --env-file .env
```

已在进程环境设置密钥时可省略 `--env-file .env`。`LLM_BASE_URL` 是兼容聊天协议的 API 根路径，服务追加 `/chat/completions`；默认百炼 `qwen-plus`。密钥只留服务端。`DATABASE_PATH` 默认为当前目录的 `data/practice.sqlite3`。首次启动导入自编样题，随后迁移至 schema 2；现有 schema 1 自动迁移，保留原题与会话。MianStack 示例不会自动发布。

交互文档：<http://127.0.0.1:8000/docs>。第一步 `GET /api/v1/role-packs`，样题包 ID 为 `pack_agent_basics_sample`。

## 调用顺序与契约

所有响应为 `schema_version / request_id / data / error`。业务失败使用非 2xx 和明确错误码；422 格式错误不回显输入。接口前缀 `/api/v1`：

1. `POST /role-packs/{pack_id}/availability`，正文 `{"mode":"question_practice","difficulty":"easy"}`。可选 `focus_competency_ids` 筛选能力；无合格题时 `can_start=false`。
2. `POST /sessions`，正文 `{"pack_id":"pack_agent_basics_sample","config":{"mode":"question_practice","difficulty":"easy"}}`，返回 draft 和 `revision=0`。
3. `POST /sessions/{id}/start`，正文 `{"expected_revision":0}`。随机抽取一题并固定题目/答案/来源版本、候选池与种子，返回 `current_turn.id`、新 revision。作答前不公开答案和评分表。
4. `POST /sessions/{id}/answers`，正文如下：

```json
{
  "turn_id": "从 current_turn.id 取得",
  "expected_revision": 1,
  "client_submission_id": "由客户端生成的唯一提交标识",
  "disposition": "answered",
  "answer_text": "当前实际回答"
}
```

非空回答为去首尾空白后 1–5000 字，原文原样保存；**先事务保存答案和任务，再调用模型**。返回 202 和 `submission.job_id`。客户端轮询 `GET /jobs/{job_id}`，成功后读取 `GET /sessions/{id}` 取得即时反馈。阶段是 `awaiting_answer → evaluating → feedback_ready`，失败为 `evaluation_failed`。生成在本地后台线程执行，不阻塞读取接口。

5. 空白用 `disposition=blank_answer, answer_text=""`：同步返回 200、分数 0，计入均分并单列。明确跳过用 `skipped` 和空文本：分数 null、不计均分。两者均不调用模型，不把空白解释为技术错误。不要把用户真的输入“我不会”的非空回答自动当成跳过。
6. 原提交标识与原 revision、正文完全相同的重试复用同一答案/任务/反馈；同一标识换内容或版本、同一题换标识再次提交均返回 409。进行中的重复提交返回同一 job，不重发模型请求。
7. `GET /sessions/{id}/report` 返回本题服务端均分、计分题数、空白/跳过数；`GET /sessions?page=1&page_size=20` 读取保存记录。单题报告不声称全岗位覆盖。
8. 模型失败后答案仍可读取。`POST /sessions/{id}/retry` 使用当前 `expected_revision`，重试同一任务和答案，不新增记录。

模型只提供五个维度的 0–100 整数或 null、理由、当前回答的精确引文和建议。服务端校验维度唯一、范围、引文子串，再按 `35/25/15/15/10` 权重计算分数，排除 null 后归一化；所有维度都为 null 时无分数。模型提供的总分忽略。超出题库答案的技术结论不确定判断；本项不接入运行时检索，不生成新主问题。

## 验证

```powershell
uv run pytest -q
uv run mypy
uv run ruff check .
uv run ruff format --check .
# 服务已启动且密钥可用时，产生实际调用费用：
uv run python -X utf8 scripts/acceptance.py --output ../docs/verification/01-live-model.json
```

可重复测试用真实 API 与临时 SQLite，仅替换外部模型边界；真实验收脚本通过 TCP HTTP 调用运行服务，检查模型反馈、引文、服务端分数与幂等重试。保存的验收文件不含密钥。

## 当前边界

仅绑定本机使用，无用户认证，维护入口同样限本机用途。试题练习页面（02）已通过 `/api` 代理接入本服务；模拟面试、资料管理和旧历史页仍为浏览器内演示数据。03 已提供逐题发布与可用性接口，全部主题整理、人工抽查与完整发布属于 05/06；模拟面试属于 07；前端草稿与后台任务的崩溃接管属于 15/16。正常重启可读已保存题目、回答和反馈；进程在模型调用中崩溃时，持久化任务可能停留 queued/running，本项不自动接管，也不保证远端模型计费幂等。

## MianStack 发布（03）

固定来源为 `didilili/mianstack@b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77` 的 `questions/Q-*.md`，仅接受 `category=agent, level=基础`。12 个原始主题及能力 ID 映射见 `publishing.py` 的 `TOPICS`。不读取第三方题集或面经。自有题解 MIT 署名及完整许可见 `third_party/mianstack-LICENSE.txt`。原始正文中的资料链接未由本项目独立核对，不作为独立技术引用展示。03 发布入口只允许空 `answer_refs`，非空逐题拒绝；独立引用的保存与核验留给 13。01 已核对样题的独立引用保持原有行为。

维护接口均有 `/api/v1` 前缀：

| 接口 | 行为 |
| --- | --- |
| `POST /maintenance/question-publications/preview` | 逐题预检，不写题库和发布记录，返回接受/拒绝数、每题原因与预计发布后的 12 主题可用数 |
| `POST /maintenance/question-publications` | 重新校验并仅导入通过项；存储发布报告，返回 `publication_id` |
| `GET /maintenance/question-publications/{id}` | 读取发布时保存的报告，包括拒绝原因；历史报告不代表当前可用数 |
| `GET /maintenance/questions/{code}` | 维护者读取完整题目/答案/来源及全部版本 |
| `POST /maintenance/questions/{code}/disable` | 正文 `{"expected_version":1,"reason":"发现答案错误"}`；停用当前版本，新抽题不回退旧版本 |

请求格式为 `{"questions":[...]}`，单批 1–500 项。完整可调用示例在 `src/interview_backend/mianstack_example.json`，包含 Q-0058、Q-0140 的原文答案与本项目编写的评分点。源文件快照（另含 Q-0597）在 `mianstack_snapshot.json`。示例发布不声称已经完成 05/06 的主题人工抽查。

```powershell
$batch = Get-Content -LiteralPath src/interview_backend/mianstack_example.json -Raw -Encoding utf8
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/maintenance/question-publications/preview -Method Post -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($batch))
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/maintenance/question-publications -Method Post -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($batch))
```

每题需要稳定 `code`、`content_version`、题面、主题/能力、`difficulty=easy`、`stage=technical`、完整答案、非空评分点、答案来源状态、原题定位和是否适合面试。原题定位包含 `original_id/commit/path/url/license/attribution/answer_status`，必须与真实原题相符。内置快照覆盖示例来源；其他题目在发布前从固定提交的 raw GitHub URL 读取核对，网络失败则该题拒绝，不放行。通过题保存原题标题/分类/难度/答案状态、文件 SHA-256、MIT 署名和许可链接。

`answer_origin=source_original` 要求源状态 ready/reviewed 且答案与原文正文一致；补写标 `agent_generated` 并提供 `generation={author,generated_at,model,revision}`（字符串，时间用 ISO 格式）；改写原文标 `maintainer_edited`。空白、过短或含 TODO/待补/占位等标记的答案与评分点拒绝。自动校验只能判断结构与来源，技术正确性仍依靠主题抽查和争议复核。

`version` 由服务端分配。相同内容版本与内容重复导入不新增题；更改题面、答案、评分点或元数据须更换 `content_version`，产生递增题目版本，旧版本不会重新成为候选。已开始会话保留当时完整快照；未开始的 draft 在 start 时按当前题库重新检查并记录题包版本。停用题的重复导入与换内容版本导入均拒绝，本项不提供自动重新启用。

可用性仍使用 `POST /role-packs/pack_agent_basics_mianstack/availability`，返回 `available_count/topic_counts/can_start`，与实际抽题使用相同候选池，支持 `focus_competency_ids`。预览中的 `imported_count` 是预计新增版本数，`committed=false`；实际发布为 true，接受数包含 `unchanged_count`。

在独立的空验收数据库上启动服务后运行（会发布、改版并停用验收题，不调用模型）：

```powershell
uv run python -X utf8 scripts/acceptance_publishing.py --base-url http://127.0.0.1:8000
```
