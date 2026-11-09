# 02: 前端单题练习接入真实服务

**What to build:** 用户从独立的试题练习入口选择 Agent 基础档，在页面上抽题、输入或空白提交答案，并立即看到真实反馈和历史记录。

**Blocked by:** 01 后端单题练习真实闭环。

**Status:** ready-for-agent

- [x] 页面从服务端读取题目、可用动作、评价和历史，当前流程不再使用固定演示题或预设分数。
- [x] 回答处理中显示状态；正常回答、空白提交和明确跳过分别呈现正确结果与计分说明。
- [x] 用户刷新后可从已保存的会话读取已提交答案与反馈；失败或重复点击不会显示重复记录。
- [x] 浏览器验收能完成一次真实随机单题、非空回答和即时反馈；模拟内容若仍可见，明确标为演示数据。

## Comments

- 原始工单位于 `C:/Users/ctrlz/Desktop/study/interview agent/.scratch/agent-principles-demo/issues/02-frontend-single-question-practice.md`；此副本随实施分支保存，完成说明同步回原始工单，业务代码仅写入当前实施分支。
- 2026-11-09：Implementation completed，分支 `GGB0ND132/02`。新增 `/question-practice` 入口与 `fronted/src/api.ts` 客户端，经 Vite `/api` 代理连接后端；题目、可用动作、评价和历史全部来自服务端，`localStorage` 只保存会话 ID。空白提交 0 分与跳过无分的计分说明、处理中状态、刷新恢复、失败重试与重复点击防护均已由自动测试覆盖；真实浏览器经百炼 `qwen-plus` 完成一次抽题、非空回答和即时反馈验收。会话视图补充 `created_at`、`difficulty`、`pack_title` 供历史列表使用。验证记录见 `docs/verification/02-frontend-single-question.md` 和 `docs/verification/02-live-model.json`。
- 浏览器验收发现并修复：刷新恢复后返回入口时未重新读取可用题数，开始按钮保持禁用；已补回归测试。
- 不在本项范围：重答与下一题、草稿恢复、模拟面试、可用性与缺口页，分别属于 16、08、04 等后续工单。
