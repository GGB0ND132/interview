# 单题练习服务（工单 01）

Python 3.11+、FastAPI、SQLite。提供两道自编 Agent 基础技术样题的真实单题闭环；不是 115 道 MianStack 正式题库，也不代表完整岗位包已开放。样题答案标记 `agent_generated`，来源、生成版本和实际核对的独立技术参考随题目快照保存。未发布候选题不会抽到。

## 本地运行

从 `backend/` 目录执行：

```powershell
uv sync --extra dev
# 将 .env.example 复制为 .env 并填写 LLM_API_KEY，或在进程环境设置 DASHSCOPE_API_KEY。
uv run uvicorn interview_backend.api:create_app --factory --host 127.0.0.1 --port 8000 --env-file .env
```

已在进程环境设置密钥时可省略 `--env-file .env`。`LLM_BASE_URL` 是兼容聊天协议的 API 根路径，服务追加 `/chat/completions`；默认百炼 `qwen-plus`。密钥只留服务端。`DATABASE_PATH` 默认为当前目录的 `data/practice.sqlite3`，第一次启动执行版本 1 迁移并导入样题，之后不覆盖内容。

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

仅绑定本机使用，无用户认证。前端仍使用演示数据，未在本项接入。批量导入、主题抽查与完整发布属于 03/05/06；模拟面试属于 07；前端草稿与后台任务的崩溃接管属于 15/16。正常重启可读已保存题目、回答和反馈；进程在模型调用中崩溃时，持久化任务可能停留 queued/running，本项不自动接管，也不保证远端模型计费幂等。无需把这一限制描述成已经实现的完整恢复。
