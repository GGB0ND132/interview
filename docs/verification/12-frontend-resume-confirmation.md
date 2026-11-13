# 12：前端简历上传与项目确认

日期：2026-11-13 至 2026-11-14（Asia/Shanghai）。分支：`GGB0ND132/12`。从 `1888bae` 快进到本地 main `f24d621`，接入已完成的 08/11 及其当前兼容集成；未修改 main。

## 行为

模拟面试准备页支持可选文字版 PDF/DOCX 上传，前端检查扩展名和 5 MiB 限制，服务端继续验证内容。上传与解析、预览、确认分别显示处理状态；操作进行中禁止启动面试和重复修改。

项目片段可逐条选择，显示 PDF 页/行、DOCX 段落或粘贴文本行。上传原文可展开回查。修改所选文本会转入粘贴编辑，清除旧确认引用；重新预览并确认后生成新服务端记录，来源标记为用户粘贴或修正文本。未确认预览与正在编辑的文本不会放入创建会话请求。

仅服务端确认成功后传入 `config.resume_id`，并根据确认结果选择经历或假设情境。用户可以清除项目内容，或明确确认没有项目经历；不上传、不确认也可直接练习。解析失败、格式/大小错误有字段级说明及粘贴回退，失败保留已输入的项目草稿。

进行中的会话及报告读取服务端 `resume_context` 展示已确认片段和来源；刷新报告后仍可查看。项目与成果明确标注为未经外部核实的候选人陈述，不作为独立技术依据。没有项目经历时服务端问题明确带有“假设情境，并非你的真实经历”。

沿用现有 UI.md 的阅读布局、表单、状态和主题 token。Impeccable 项目上下文脚本缺失，未运行其项目初始化或另建视觉方向。

## 自动检查

TDD 边界沿用工单的用户流程与 HTTP 接口。先观察到上传客户端方法缺失、上传字段缺失导致的失败；之后片段确认回归发现未选片段被错误重新勾选，修正后通过。审查阶段增加失败输入保留与可访问错误回归，先失败后修复。

```powershell
# fronted
npm test -- --reporter=dot
npm run build
npm run lint

# backend
uv run --extra dev pytest -q
uv run --extra dev mypy
uv run --extra dev ruff check .
uv run --extra dev ruff format --check .
```

最终：前端 5 文件 61 项通过，其中简历 UI 专项 7 项；TypeScript/Vite 构建和 ESLint 通过。后端 203 项通过，mypy、Ruff 和格式检查通过。后端存在一条原有 Starlette TestClient/httpx 弃用提示。没有新增后端业务实现。

## 真实浏览器与 HTTP

Playwright CLI 驱动 Chromium，前端 `http://127.0.0.1:5172/practice` 代理独立后端 `127.0.0.1:8012`，数据库为忽略路径 `backend/data/acceptance-12.sqlite3`。文件全部为合成简历，未使用个人简历或其他工作区数据库。

可复用现有受控验收服务：

```powershell
# backend
uv run --extra dev python -X utf8 scripts/acceptance_frontend_recovery.py --database data/acceptance-12.sqlite3 --port 8012 --outcome success

# fronted，另一个终端
$env:INTERVIEW_BACKEND_URL='http://127.0.0.1:8012'
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5172 --strictPort
```

浏览器脚本：`.scratch/agent-principles-demo/12-browser-cases.js`。从 `/practice` 准备页或已结束报告运行。所需文件使用 `backend/scripts/acceptance_resumes.py` 的 `document()`、`pdf()`、`pdf(scanned=True)` 生成到 `output/playwright/12-resume.docx`、`12-resume.pdf`、`12-scanned.pdf`。

```powershell
npx --yes --package @playwright/cli playwright-cli -s=issue12 open http://127.0.0.1:5172/practice
npx --yes --package @playwright/cli playwright-cli -s=issue12 run-code --filename=.scratch/agent-principles-demo/12-browser-cases.js
```

最终代码验收结果：

| 路径 | 服务端会话 | 验证结果 |
| --- | --- | --- |
| DOCX 上传确认 | `4059be0e-f765-46ef-b2b0-2d5bc21a1c5e` | 第 2 段项目进入经历问题；结束、刷新后项目来源仍可查 |
| 扫描件失败、粘贴、修正并重新确认 | `922184ea-e7c5-4486-b5a7-d686c968d9ea` | 失败保留原草稿且文件字段标错；新的修正文本进入经历问题，来源为 pasted_text |
| 文字版 PDF 上传确认 | `08ef6d4e-2e61-4dcc-87c5-d6a21829bdb9` | 服务端快照保留第 1 页第 2 行 |
| 无简历直接练习 | `3af701bf-7b16-45a4-861d-cba21ca871c3` | resume_context 为空，进入明确假设情境 |
| 明确确认无项目 | `8c53179c-a34a-4e30-ba60-88decc1bfff0` | no_project_experience=true，进入情境分支 |

所有交互使用真实 HTTP，无网络响应 mock；通过界面跳过开场后进入经历/情境问题，未调用评分模型。此次验证前端集成、来源与分支行为，不声称重新验证真实模型追问或评分质量；相关后端模型验收见 11 号记录。

390×844 移动端已检查失败回退、修正后经历与无项目分支，无横向溢出；检查了桌面及移动截图。截图保存在忽略目录 `output/playwright/12-confirmed-experience.png`、`12-parse-fallback-mobile.png`、`12-corrected-experience-mobile.png`、`12-no-projects-mobile.png`。控制台仅初始 favicon 404，没有应用异常。

独立 Standards/Spec 审查见 `12-code-review.md`。
