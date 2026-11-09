# 02 前端单题练习接入验证

日期：2026-11-09。工单：[02](../../.scratch/agent-principles-demo/issues/02-frontend-single-question-practice.md)。接口说明：[backend/README.md](../../backend/README.md)。

## 已检查

- 真实浏览器（Chrome，Playwright 驱动）经 Vite 开发代理连接本机 FastAPI 服务和实际百炼 `qwen-plus`，路由 `/question-practice`：
  - 页面显示服务端可用题数「2 道可抽」，开始按钮可用性随服务端 `can_start` 变化；页面不再使用 `data.ts` 的固定演示题。
  - 抽到 `Q-AGENT-SAMPLE-02`（版本 1），题面、题目编号与版本均来自服务端会话快照。
  - 输入非空回答并提交后，页面显示「回答已保存，正在生成反馈」，原回答保持可见；评价完成后立即在原题下显示服务端总分 80、五个维度、值得保留、需要补充和参考答案，未使用任何预设分数。
  - 刷新浏览器后从已保存会话恢复同一回答与 80 分反馈，页面只有一份回答记录，没有重新提交（`localStorage` 仅保存会话 ID）。
  - 空白提交显示 0 分和「空白提交记为 0 分，计入均分；本次未调用模型评价」，跳过一次抽题显示「未评分」和「跳过不计分，也不进入均分」。
  - 「最近练习」列表读取服务端 `GET /sessions`，每条记录一条提交，没有重复行。
  - 打开 `/history`、`/practice` 时可见明确标注的演示数据说明，并指向「试题练习」的真实入口。
- 浏览器验收过程中发现并修复一处缺陷：刷新恢复后返回练习入口时，可用题数未读取，开始按钮保持禁用。已补充回归测试 `can draw a new question after returning from a refreshed session`。
- 前端自动检查：`npm test`（`vitest run`）15 项通过（API 客户端 4 项、单题练习页 11 项，覆盖可用数来自服务端、可用动作按服务端渲染、处理中状态、即时反馈、空白 0 分、跳过无分、刷新恢复、失败保留与重试、响应丢失后的服务端对账、重复点击只提交一次、轮询超时停止）；`npx tsc -b`、`npm run lint`、`npm run build` 通过。
- 后端回归：`uv run pytest -q` 23 项通过；`mypy`、`ruff check`、`ruff format --check` 通过。新增检查覆盖会话视图的 `created_at`、`difficulty`、`pack_title` 与历史列表。
- [代码审查记录](02-code-review.md)：标准面 0 硬性违规、6 项判断（2 已修复、4 保留并说明）；规格面 0 缺陷，2 项缺失已修复。
- 真实调用证据：[02-live-model.json](02-live-model.json)，保存题号/版本、回答、原话引文、五维反馈、服务端总分、参考答案、来源和报告，不含密钥。

## 复现

```powershell
# 终端 1
cd backend
uv sync --locked --extra dev
uv run --locked pytest -q
uv run --locked mypy
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked uvicorn interview_backend.api:create_app --factory --host 127.0.0.1 --port 8000

# 终端 2
cd fronted
npm install
npx vitest run
npx tsc -b
npm run lint
npm run build
npm run dev
```

浏览器打开 <http://127.0.0.1:5173/question-practice>。`vite.config.ts` 把 `/api` 代理到 `127.0.0.1:8000`，无需修改后端 CORS。真实提交会调用模型并产生费用；自动测试使用替身，不调用远端模型。

## 范围

本项只把试题练习页面接到已有单题服务：随机抽一题、非空回答即时反馈、空白 0 分、跳过无分、刷新后读取已保存记录、失败重试与重复提交防护。仍未完成：115 道正式题库与发布校验（03/05/06）、前端可用性与缺口页（04）、模拟面试（07/08）、JD 与简历（09–12）、引用与报错入口（13/14）、未提交草稿与进程中断后的任务接管（15/16）。演示题仍只有两道自编样题，页面如实显示「演示样题」与可用题数；「最近练习」不显示完整面试结论。
