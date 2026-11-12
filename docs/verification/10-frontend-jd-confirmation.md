# 10 前端 JD 确认与覆盖缺口验收

2026-11-12；工作区 `C:/Users/ctrlz/orca/workspaces/interview agent/10`，分支 `GGB0ND132/10`。

## 实现

工作区从 `1888bae` 快进接入已合并 08/09 的本地 main `fb130fd`，没有修改 main。10 实现 `37c413f`，规范复查修正 `541c973`。

模拟面试入口提供可选 JD 文本（20～20000 字），提取结果按可覆盖与不能覆盖分组，显示原文行号、相关主题及实际合格主问题数量。用户逐项核对勾选后确认；存在缺口时确认按钮明确接受覆盖缺口。无 JD、只有原文、仅有预览、修改原文或勾选后未重新确认，都不会向新会话发送 JD 引用。处理中禁止重复请求与开始；切换题包重置准备项并忽略旧响应。确认失败保留原文，可重新提取或不使用 JD 继续。

进行中与报告可展开本场抽选记录：从服务端 plan 读取全部候选主题的真实权重、题量和入选情况。JD 相关候选权重为 4，其他为 1；页面明确仍随机、不保证入选，权重不是概率。报告使用服务端确认快照及 jd_gaps，区分无法映射、题量不足、本场未抽中和回答依据不足。历史完成项称“面试已结束”，避免五类环节完成但 JD 仍有缺口时误标“完整报告”。

沿用 UI.md 的字体、色彩、字段及报告布局；frontend-design 用于保持现有视觉，ui-ux-pro-max 的表单错误与无障碍建议用于就地错误、显式标签、焦点与处理状态。没有新增文件上传或主问题生成。

## 自动检查与独立审查

测试边界沿用阶段 spec 的浏览器用户交互与 HTTP API。组件测试使用真实 API 客户端，仅在 fetch 边界提供可控响应，检查可见内容与发出的会话配置。

- 前端 `npm test`：33/33（模拟面试 13，既有单题 16、API 4）。新增 8 项包含未确认排除、确认缺口与报告、修改原文/选择失效、确认锁、失败保留与重试、切包迟到响应及短 JD blur 校验。关键新行为均先失败后实现。
- `npm run build`（含 TypeScript）与 `npm run lint`：通过。
- 后端未改代码；`uv run --locked pytest -q`：130/130，`mypy`、`ruff check .`、`ruff format --check .` 通过。保留既有一条 Starlette/httpx 弃用提示。
- 两路独立审查：规范初审 4 项已修复并复查；规格无发现。详见 [10-code-review.md](10-code-review.md)。

## 真实浏览器与后端

Playwright 独立 Chrome 会话 `issue10`，页面 `http://127.0.0.1:5180/practice` 通过 Vite 代理至后端 8010，无网络 mock。后端读取当前环境的模型配置，实际模型 `qwen-plus`。所有候选人回答均为合成验收文本；技术题明确不会用于验证覆盖和缺口，不将分数解释为评分质量或候选人能力结论。

独立数据库 `backend/data/10-acceptance.sqlite3` 通过 SQLite backup 从 09 验收库复制。57 道已发布技术题中 48 道适合面试，6 个合格主题，通用环节题已发布。包含复制来的历史记录，10 新会话以本记录的 ID 为准；本次不改其他工作区数据库，不提交密钥与 SQLite 文件。

启动方式：

```powershell
# backend 目录
$env:DATABASE_PATH='data/10-acceptance.sqlite3'
uv run --locked uvicorn interview_backend.api:create_app --factory --host 127.0.0.1 --port 8010
```

```powershell
# fronted 目录
$env:INTERVIEW_BACKEND_URL='http://127.0.0.1:8010'
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5180 --strictPort
```

## 浏览器结果

| 路径 | 会话 | 真实观察 |
| --- | --- | --- |
| 最终代码无 JD | `fe21b053-d2a5-4083-93c3-15f22c09e1cc` | 不填 JD 直接开始，六个候选主题权重均为 1，四个随机主题；提前结束可查看报告 |
| 最终代码可覆盖 JD | `e26a43c3-738f-4044-a731-496c6e79b17f` | 原文“熟悉工具调用与 Function Calling”，提取、核对确认后开始；工具调用权重 4，其他为 1，三个主题；提前结束报告如实列出该能力回答依据不足 |
| 最终代码接受未覆盖要求并完成整场 | `fe72e5c3-9ca9-439b-a081-2fc2ed23932c` | 原文“熟悉工具调用；掌握 Kubernetes；熟悉 MCP”，可覆盖与两个缺口分组；确认接受后完成开场、假设情境、技术、行为与反问，3 个技术主题、7 主问题，实际模型 qwen-plus；`status=completed`、`interview_completeness=complete`、`completeness=partial`，Kubernetes 的 unmapped_requirement 和 MCP 的 topic_not_eligible 保留 |

最终代码两条开始路径不调用模型；完整含缺口路径的每条回答均连接真实模型，未用预置反馈。另有早期验收会话 `ff0062f1-7735-4e01-84fc-cacb9c4c1d61`（无 JD）、`6f07214d-5bef-4af6-b1e2-556ef7588607`（短 JD），均经真实 qwen-plus 开场评价后提前结束；短 JD 后由审查改为至少 20 字，因此最终验收使用上表的新会话。

完整路径的技术主问题均属于保存的已发布候选池。明说不会被记录为 knowledge_gap；本次模型对剩余可评估维度仍给出高分，不代表技术掌握，本工单没有评估或更改既有评分逻辑。

[10-live-jd-summary.json](10-live-jd-summary.json) 保存三条最终代码路径的服务端摘要、实际候选权重、阶段序列、来源池核对、JD 缺口及完整报告 SHA-256。`.scratch/agent-principles-demo/10-browser-step.js` 逐题驱动真实模型交流；`10-browser-start-cases.js` 核对两个开始路径，全程通过页面操作创建/确认/开始/结束，HTTP 只用于读取核对。

在 1440×1000 浅色与 390×844 深色检查 JD 预览和报告。移动端 viewport 为 390，预览 document.scrollWidth 为 390、报告为 375，均无横向溢出；刷新后同一确认快照与缺口可恢复。浏览器有一条既有 favicon.ico 404，无应用 JS 异常。

截图保存在本机 `output/playwright/10-jd-preview-desktop.png`、`10-jd-preview-mobile.png`、`10-jd-gap-report-mobile-top.png`、`10-jd-gap-report-desktop.png`，遵循浏览器技能的输出目录约定，默认不进入 Git。

## 实现边界

本项不含 JD 文件上传、简历、未提交 JD 准备页刷新持久化；已开始会话与报告中的确认快照由服务端持久化。确认成功的响应丢失后，旧版本重试可能冲突，页面保留文本并提示重新提取。题库与明示词表仍有语义边界，必须由用户核对，不能因界面显示“可覆盖”推断岗位能力已掌握。
