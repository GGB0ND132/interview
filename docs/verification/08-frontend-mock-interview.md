# 08 前端模拟面试验收

2026-11-12；工作区 `C:/Users/ctrlz/orca/workspaces/interview agent/08`，分支 `GGB0ND132/08`。

## 实现与启动

当前分支从 `1888bae` 快进接入已完成的前置分支 `GGB0ND132/07`（`2ba2cff`）；未修改 main。08 实现提交 `4edf9d8`，阅读位置与无障碍修正 `cdb9f8f`，后续收尾提交记录最终属性和验收材料。

`/practice` 替换原固定题目与定时推进的演示入口。前端通过现有会话 API 创建、开始、提交、轮询、重试、切换题组和结束；服务端 `available_actions` 与 revision 决定操作权限。非空回答使用唯一提交 ID；响应不确定时先读取服务端，同步失败则锁定操作，保留草稿等待重新同步。页面不渲染进行中的 score、feedback 或参考答案。暂停仅暂停当前页面的输入和推进，不声称中断模型任务。

验收数据库为 `backend/data/08-acceptance.sqlite3`，从 07 验收库复制，后续测试仅写入此副本。题库有 57 道已发布技术题，其中 48 道适合模拟面试，覆盖 6 个题量充足的主题；已发布五道通用环节题。复制库包含 07 的旧合成会话，08 新增会话以本文 ID 为准。数据库和密钥不提交 Git。

在两个 PowerShell 终端分别启动（本机环境已配置模型密钥，勿写入前端）：

```powershell
cd backend
$env:DATABASE_PATH='data/08-acceptance.sqlite3'
uv run uvicorn interview_backend.api:create_app --factory --host 127.0.0.1 --port 8008
```

```powershell
cd fronted
$env:INTERVIEW_BACKEND_URL='http://127.0.0.1:8008'
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5178 --strictPort
```

访问 `http://127.0.0.1:5178/practice`。日常默认后端地址仍由 Vite 配置指向 8000；新建数据库须先按 05/07 的发布流程准备技术题和通用题。

## 自动检查

测试边界沿用阶段规格指定的浏览器交互与 HTTP API。组件检查使用真实 API 客户端，仅在 fetch 边界提供可控响应；断言可见问题、操作和报告，不依赖组件内部状态。新增测试先失败后实现。

- `npm test`：25/25（既有单题/API 20，模拟面试 5）。覆盖真实服务端追问形状、隐藏评分、暂停保留草稿、结束确认、部分/完整报告、处理锁、版本冲突、失败重试及响应丢失后的同步。审查修正后重跑模拟面试 5/5。
- `npm run build`：通过，包含 TypeScript 检查；`npm run lint`：通过，无警告。
- `uv run --locked pytest -q`：113/113；`mypy`、`ruff check .`、`ruff format --check .`：通过。后端代码没有为 08 修改。保留既有 Starlette/httpx 弃用提示。
- 两路独立审查分别检查仓库规范和规格，结果及修正见 [08-code-review.md](08-code-review.md)。

## Playwright 与真实模型

按用户最终指定使用 Playwright 的独立 Chrome 会话，前端 5178 代理至真实后端 8008，真实模型 `qwen-plus`，未 mock 网络或评价结果。默认浏览器控制未完成，以下成果均来自 Playwright。所有候选人文本为明确合成的验收样例，分数仅证明实际连接与报告计算，不代表评分准确性或真实候选人水平。

| 浏览器路径 | 会话 | 观察结果 |
| --- | --- | --- |
| 完整面试 | `3411ae8f-800b-4dd8-aeea-ead2a62934b5` | 开场、假设情境、技术、行为、反问；4 个技术主题，8 道主问题；`completed / complete / coverage_satisfied`，整体 96、技术 95，报告 gaps 为空 |
| 提前结束 | `fad15500-67cd-41c2-83aa-6f4df68d9764` | 暂停/继续保留未提交草稿；跳过开场；没有项目经历转入明示假设；含糊回答触发引用“调用一下”的真实追问；用户结束后 `ended_early / partial / user_ended`，技术等未问项与信息缺口保留；无计分组显示“未评价” |

完整路径行为题两次返回 `MODEL_OUTPUT_INVALID`，页面显示失败并保留同一回答，经两次 `/retry` 后恢复并最终完成。没有替换成预置反馈，也没有修改后端校验来通过本次验收。

部分路径收到的新追问为：“你提到‘调用一下’，能以‘用户输入‘查我昨天的订单’’为例，说说这句话里模型、工具和程序各自要做什么吗？”在等待时用鼠标上翻阅读旧回答，新追问到达后保持阅读位置并显示跳转入口，点击可回到最新交流。

完整报告在 1440×900 浅色截图检查；部分报告在 390×844 深色截图检查，无横向溢出，中文说明、空分和覆盖行可读。刷新后仍从服务端读取同一部分报告。通过侧栏进入试题练习、切换模拟面试模式并进入独立入口后，可恢复该报告；试题最近记录未混入模拟会话。浏览器最终 console error 为 0。

- [完整报告响应](08-complete-report.json)、[桌面截图](08-complete-desktop.png)
- [部分报告响应](08-partial-report.json)、[移动端截图](08-partial-mobile.png)
- `.scratch/agent-principles-demo/08-browser-step.js` 记录本次已抽中题目的合成回答；随机重开可能选到其他题，需要补充对应样例。`08-browser-partial.js` 记录第二条浏览器交互路径。两者通过 `playwright-cli run-code --filename` 执行。

## 边界

服务端持久化会话和报告，当前浏览器保存模拟会话 ID；暂停后的草稿仅保留在当前页面，未实现 16 的未提交草稿刷新持久化。模型任务崩溃接管属于 15，JD/简历确认属于 10/12，引用增强与报错属于 14。资料管理和独立历史页继续明确标注为演示；真实模拟面试记录在模拟面试入口回看。
