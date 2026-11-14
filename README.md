# 面试练习智能体

本机运行的 Agent 基础档面试练习项目，提供单题即时反馈和完整模拟面试。前端为 React + TypeScript + Vite，后端为 FastAPI + SQLite，模型密钥仅保存在服务端。

01–17 阶段工单已合入 main。当前开放 Agent 基础档；资料管理与独立历史页仍有演示数据，Python 后端、React/Vue 题包、个人知识库和公开多用户部署不属于本阶段完成范围。

## 能做什么

- 单题练习：从已发布题库随机抽题，提交后查看反馈、参考答案、引用及问题报错入口。
- 模拟面试：开场 → 经历或假设情境 → 技术交流 → 行为问题 → 候选人反问 → 报告。
- 可选确认 JD 后提高匹配主题的抽选权重；覆盖缺口保留到报告，不临时生成主问题填补。
- 可选上传文字版 PDF/DOCX 或粘贴项目文本，预览、修正并确认后用于经历提问。
- 保存会话、回答、任务和报告；同一浏览器同源刷新恢复草稿，模型失败保留原答案并重试。

主问题来自本地已发布题库。模型负责评价和基于实际回答追问；原题链接及简历陈述不自动成为独立技术证据。评分、追问事实前提和 JD 词表仍有[已披露限制](docs/acceptance/17-demo-acceptance.md)。

## 首次运行

需要 Python 3.11+、uv，以及满足 Vite 8 要求的 Node.js（建议 Node 22.12+）和 npm。以下命令从仓库根目录开始，使用 PowerShell。

### 1. 配置并启动后端

```powershell
cd backend
uv sync --locked --extra dev
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

编辑 `backend/.env`，填写密钥。默认使用百炼兼容接口：

```dotenv
LLM_API_KEY=填写服务商密钥
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-plus
MODEL_TIMEOUT_SECONDS=60
DATABASE_PATH=data/practice.sqlite3
```

```powershell
uv run --locked uvicorn interview_backend.api:create_app --factory --host 127.0.0.1 --port 8017 --env-file .env
```

保持该终端运行。后端会创建数据库和迁移结构；首次启动仅有自编样题，不自动发布完整题库。API 文档：<http://127.0.0.1:8017/docs>。

若进程环境已有同名变量，它们优先于 `.env`，尤其要核对 `DATABASE_PATH`，避免连接另一份数据库。

### 2. 首次发布完整题库

另开终端，在仓库根目录执行：

```powershell
cd backend
uv run --locked python -X utf8 scripts/prepare_demo.py --database data/practice.sqlite3 --base-url http://127.0.0.1:8017 --output ../output/prepare-current.json --resume-output ../output/17-resume.docx
```

脚本名称沿用阶段演示，但也能初始化指定的日常数据库。它沿用 05/06 已记录的审核门槛，发布 115 道技术题和 5 道通用环节题，不调用评分模型；重复运行相同内容不新增题目版本，不删除原会话。必须等后端启动成功，并确保 `--database` 与后端实际使用的路径一致。

输出 JSON 和合成 DOCX 在忽略的 `output/` 中。DOCX 仅为可选演示样例，不代表用户经历。若题目已停用、隔离或发生版本变化，脚本可能拒绝完整匹配，应检查原因，不清空数据库绕过。

### 3. 启动前端

在第二个终端继续执行：

```powershell
cd ../fronted
npm ci
$env:INTERVIEW_BACKEND_URL='http://127.0.0.1:8017'
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5177 --strictPort
```

- 单题练习：<http://127.0.0.1:5177/question-practice>
- 模拟面试：<http://127.0.0.1:5177/practice>

以后通常只需启动后端和前端。依赖未变化时不用重新安装，题库已发布时不用重复初始化。前端端口固定有利于恢复浏览器草稿。

## 页面操作

**单题：**选择题包、难度和可选主题 → 查看服务端实际可用数 → 抽题 → 输入并提交 → 等待评价 → 查看反馈。空白提交记 0 分并计入均分；明确跳过为 null，不计分。题目或评分有误可在反馈页报告。

**模拟面试：**选择题包和经历方式 → 可选粘贴 JD、选择要求并确认 → 可选上传简历、选择项目片段并确认 → 开始面试 → 按服务端动作继续或结束 → 查看报告。未确认的资料不进入会话，修改后需要重新确认。PDF/DOCX 上限 5 MiB，扫描件无 OCR，解析失败可粘贴项目文本。

一场面试通常随机选 3–4 个合格技术主题，不保证覆盖整个题库或所有 JD 要求；完整交流也可能因 JD 缺口显示部分报告。真实历史从两个练习入口的最近会话查看，独立“历史记录”页仍是示例。

模型超时或结构化结果无效时，使用重新同步或重试评价，原回答保留。不要通过新建会话冒充原任务恢复。

## 数据库：日常、演示与测试

| 数据库 | 用途 | 是否必须 |
| --- | --- | --- |
| `backend/data/practice.sqlite3` | 日常题库、会话、回答、JD/简历确认和报告 | 运行需要一份 SQLite；文件名可自行配置 |
| `demo-17.sqlite3` 等演示库 | 隔离合成回答与现场演示历史，使用相同业务代码和真实模型 | 可选，不是额外服务，日常只用 practice 即可 |
| `recovery-17.sqlite3` 等故障库 | 刻意超时、固定评分等受控恢复验收 | 仅故障测试使用，不能作为真实模型评分证明 |
| pytest 临时 SQLite | 自动化测试产生的独立数据 | 自动创建，不应当作日常库 |

数据库不会随 Git 合并复制，提交到仓库的是题库源文件和验收证据。更换 `DATABASE_PATH` 会切换整套数据。备份时先停止后端，再备份整个 `backend/data/`；恢复时使用同一路径。删除演示库会失去其中独有的会话，题库可重建但历史不可凭空恢复。本次目录整理没有删除或创建运行数据库。

## 模型服务与中转站

当前适配器使用 OpenAI Chat Completions 风格协议：`POST {LLM_BASE_URL}/chat/completions`，Bearer 鉴权、`messages`、`temperature=0`、`response_format={"type":"json_object"}`，读取 `choices[0].message.content` 并校验 JSON。

支持这一整套协议和参数的服务商可通过 `.env` 切换，不要把文档网页 URL 填成 API 地址。仅声称“兼容 OpenAI”不足以确认可用：Responses 与 Chat Completions 是不同协议。

2026-11-14 核对 [CodexCN 文档](https://api.codexcn.com/docs)：其示例 API 根地址为 `https://api3.codexcn.com/v1`，明确使用 `wire_api="responses"`。当前项目没有 Responses 适配，未验证该站支持 `/chat/completions` 及 JSON 参数。因此不能保证只修改 `LLM_BASE_URL` 即可使用。若该站仅支持 Responses，需要另行实现并验证协议适配；若提供 Chat Completions，则还需用有效密钥实测模型输出。此次没有配置中转密钥或发起付费验证。

## 目录

```text
backend/                 后端源码、维护命令和 Python 自动化测试
fronted/                 前端源码与组件测试（沿用原目录拼写）
docs/                    当前需求、内容流程、设计和文档导航
  acceptance/            17 最终验收、发布/抽查记录与演示手册
tests/
  fixtures/              发布审核数据、文档解析样本
  evidence/              17 最终验收的 HTTP/模型输出与截图
output/                  本机新生成材料，Git 忽略
.scratch/                本地工单与浏览器验收步骤
```

## 开发验证

```powershell
cd backend
uv run --locked pytest -q
uv run --locked mypy
uv run --locked ruff check .
uv run --locked ruff format --check .

cd ../fronted
npm test
npm run lint
npm run build
```

上述自动测试使用临时数据库和受控外部边界，不需要模型密钥。浏览器与真实模型验收另见[演示手册](docs/acceptance/17-demo-runbook.md)，非空作答及独立证据核验可能产生调用费用。服务目前限本机单用户使用，没有用户认证。

更多入口：[文档导航](docs/README.md)、[后端接口](backend/README.md)、[前端说明](fronted/README.md)、[测试材料说明](tests/README.md)。
