# 16：前端草稿恢复与重试验收

日期：2026-11-13。分支：`GGB0ND132/16`。审查基线：`ae6b49f7ec6809e20477be91d7d45908b4bc30f6`。

## 实现

两个练习页面共用 `useAnswerDraft`，按服务端的会话 ID 和当前轮次 ID 保存文字及待确认提交身份。输入同步写入同一浏览器的 localStorage；只有读取服务端后才选择可恢复的草稿。服务端确认提交后删除对应草稿，追问或其他会话不会继承旧题文字。浏览器存储不可用时允许继续输入和提交，但无法承诺刷新后保留未提交文字。

正式题目、已提交答案、评价状态与反馈均由原有会话/任务/报告接口读取。单题页只在 404 或模式不匹配时移除会话入口，临时连接失败会保留入口并显示重新连接；最近历史读取失败不阻断当前会话恢复。请求结果不确定且同步失败时禁用再次提交，提供重新同步会话。相同提交跨刷新重试沿用提交 ID，修改内容时生成新身份；界面同步锁防止连续点击重复发送。

单题评价重试使用 retry 接口返回的 job ID；双方界面都按服务端动作控制重试。单题页离开或卸载后使旧轮询失效，避免迟到响应把已离开的会话重新打开。模拟面试结束前仍不展示详细分数和参考答案。

## 自动检查

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

前端 4 个文件、36 项通过，其中草稿恢复专项 11 项；TypeScript/Vite 构建与 ESLint 通过。后端 133 项通过（59.65 秒），mypy、Ruff 与格式检查通过。有一条已有 Starlette TestClient 依赖弃用提示。

专项覆盖双模式草稿刷新、题目/会话隔离、服务端答案覆盖本地草稿、提交清理、连接不确定时锁定、跨刷新沿用提交身份、存储失败降级，以及单题临时恢复失败和迟到轮询。工作区原有未提交的恢复测试保留并扩展。首次运行原测试因刷新后文字为空失败；临时恢复入口及离开后迟到轮询的新增测试也分别先失败，修复后通过。

## 浏览器与真实 HTTP 验收

使用 Playwright CLI 驱动 Chromium，前端 `127.0.0.1:5176` 代理到独立后端 `127.0.0.1:8016`。数据库为本工作区忽略的 `backend/data/acceptance-16.sqlite3`，只发布验收库的题目；未使用其他工作区数据库。评价器是明确的受控适配器，不调用收费模型，不作为模型评分质量验证。

可复现的验收服务（在 backend 目录执行）：

```powershell
uv run --extra dev python -X utf8 scripts/acceptance_frontend_recovery.py --database data/acceptance-16.sqlite3 --port 8016 --outcome failure
# 完成双模式提交后，停止上述进程，以同一个库重启：
uv run --extra dev python -X utf8 scripts/acceptance_frontend_recovery.py --database data/acceptance-16.sqlite3 --port 8016 --outcome success
```

前端启动：

```powershell
$env:INTERVIEW_BACKEND_URL='http://127.0.0.1:8016'
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5176 --strictPort
```

| 验收项 | 单题练习 | 模拟面试 |
| --- | --- | --- |
| 输入后刷新 | Q-2536 原题及 35 字草稿恢复 | 开场原题及 43 字草稿恢复 |
| 连续点击提交后刷新 | 一份已提交答案、超时原因和重试按钮 | 一份已提交答案、超时原因和重试按钮，未公开评分 |
| 浏览器草稿清理 | localStorage 仅剩会话入口 | localStorage 仅剩两个模式的会话入口 |
| 强制结束后端并用同库重启 | 原答案及 evaluation_failed 保持 | 原答案及 evaluation_failed 保持 |
| 连续点击重试 | feedback_ready，revision 5，反馈 75 分 | stage_transition，revision 6，可继续下一组，详细反馈仍隐藏 |
| HTTP 核对重复记录 | submissions=1，原 job attempts=2，succeeded | submissions=1，原 job attempts=2，succeeded |
| 成功结果刷新 | 一份答案及本题反馈 | 结束生成部分报告后刷新，恢复原答案、题组分数与覆盖缺口 |

实际会话：单题 `4ff7f243-b14c-4aff-8a06-8a7962474ad0`，原任务 `167adcb5-c65b-422e-a4fc-cf070e9f7bd8`；模拟面试 `1df34185-c9f7-4dda-93b0-c31f8d4807d7`，原任务 `11f34d86-5392-429a-86b3-2a2dea06e4e6`。原后端进程 57160 被强制停止，新进程 30188 从同库启动后完成读取及重试。

本地截图保存在忽略目录 `output/playwright/16-question-retry.png`、`16-mock-retry.png`、`16-mock-report-restored.png`；已检查单题反馈截图。CLI 快照在 `.playwright-cli/`。控制台仅观察到初次请求 favicon 的 404，没有应用异常。

本项验证同一浏览器、同源、浏览器存储可用时的草稿恢复；不提供跨浏览器同步或跨标签编辑冲突合并。模型调用期间强杀后自动接管由 15 的真实进程/TCP 测试覆盖，本项的浏览器重启场景在失败答案已持久化后进行。没有把受控评价器结果声称为真实模型质量验收。

独立审查记录见 [16-code-review.md](16-code-review.md)。
