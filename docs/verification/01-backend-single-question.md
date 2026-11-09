# 01 后端单题练习验证

日期：2026-11-09。工单：[01](../../.scratch/agent-principles-demo/issues/01-backend-single-question-practice.md)。使用说明：[backend/README.md](../../backend/README.md)。

## 已检查

- 通过实际 FastAPI 接口和临时 SQLite 运行 22 项检查：只选已发布题、答案/评分表答前隐藏、开始与提交状态校验、服务重建后的题目/失败答案读取、正常评价、独立算例 74 分、模型总分忽略、null 权重归一化、空白 0 分、跳过 null、请求格式、重复及并发提交、错误模型结构/范围/引文、超时和服务失败、任务读取与原答案重试。
- 通过 `uv run --locked mypy` 严格检查 7 个源文件；通过 `ruff check` 与 `ruff format --check`。
- 真实服务运行在本机 TCP HTTP 端口 8011，通过脚本调用实际百炼 `qwen-plus`。得到一条成功单题记录，维度 100/100/100/95/90，服务端计算总分 98；同一提交重试复用原记录，报告均分 98，计分题数 1。
- 原始真实调用结果：[01-live-model.json](01-live-model.json)。文件保存题号/版本、当前回答、原话证据、五维反馈、答案来源、模型配置名、任务和报告，不含密钥。

## 复现

从 `backend/` 运行：

```powershell
uv sync --locked --extra dev
uv run --locked pytest -q
uv run --locked mypy
uv run --locked ruff check .
uv run --locked ruff format --check .
# 密钥在环境中配置，另开终端运行服务
uv run --locked uvicorn interview_backend.api:create_app --factory --host 127.0.0.1 --port 8000
uv run --locked python -X utf8 scripts/acceptance.py --output ../docs/verification/01-live-model.json
```

真实调用会新增练习并使用模型额度；自动测试不调用远端模型。锁文件固定本轮依赖。Starlette 对其 TestClient 使用 httpx 有一条弃用提示，所有检查仍通过。

## 范围

这证明单题业务流程可调用、可保存、可返回针对实际回答的模型反馈，不证明模型分数已完成人工校准。仅有两道本项目自编样题，答案来源为 `agent_generated`；实际核对的 Anthropic 文章作为独立技术参考，与自编题原始定位分别存储。没有导入 MianStack 的 115 道题，没有完成 24 题人工抽查，也没有开放完整岗位包。

前端接入、批量发布、模拟面试和进程崩溃后的任务接管仍在后续工单中。已保存数据可在正常重启后读取；模型调用中断时的 pending 任务不在本次恢复承诺内。初期依赖超时使最初基础服务先于可执行测试落地；未将本次描述为全程严格 TDD。
