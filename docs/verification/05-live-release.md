# 05 持久化发布与页面验收

2026-11-10，用户要求继续剩余任务。目标为本工作区 README 约定的 `backend/data/practice.sqlite3`：真实持久化本地练习库，非临时验收数据库；没有远程部署。

初始未运行前后端、目标库不存在。按既有命令初始化，确认发布前 MianStack 可用数为 0；通过审核门槛命令正式导入 57 题。发布 ID 为 `a82ce858-d104-4ba7-a5c8-c44cab0bc862`，题包摘要保持 `95f13360681b8ca166ec49d47e4bb6f78de168215f459eabda1792e0917cb459`。

## 真实服务与页面结果

- 发布接受 57、拒绝 0，当前可用 57；六主题数量为 17、18、8、2、6、6，其余六主题为 0。
- 从运行服务读取上述 publication_id，与命令保存报告一致，确认验收服务连接同一数据库。
- 六主题逐一按能力筛选、创建单题会话并开始，实际抽到该主题已发布题；记录保存 session_id、题号及版本。
- 重复走审核门槛发布：新增 0、未变 57，可用数仍为 57。
- 用户指定默认浏览器后，使用 Orca 内置浏览器访问 `http://127.0.0.1:5173/question-practice`。MianStack 基础档显示“57 道可抽”，主题目录与服务端数量一致，随机抽题按钮可用。
- 点击“随机抽一题”打开记忆系统 Q-3642（版本 1），题面为“记忆系统中的意图识别承担什么职责？”，可输入答案。未提交答案，返回入口后仍显示 57 道。
- 页面刷新及后端重启后保留题库与练习记录。验证生成六个 API 会话和一个页面会话，均为未作答状态，模型调用 0。

完整机器证据见 [05-live-release.json](05-live-release.json)。页面状态与重启后只读检查记录见 [05-live-ui-restart.json](05-live-ui-restart.json)，SQLite 完整性检查为 ok、会话 7、提交与任务均为 0。页面截图见 [题库数量](05-live-availability.png) 与 [实际抽题](05-live-question.png)。本轮未提交评分请求，只验证发布与抽题，不声称非空答案的在线评分已验收。

## 复现与完成状态

前后端分别使用 `backend/README.md` 中的 Uvicorn 命令及前端 `node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173 --strictPort`。实际数据库与日志保存在忽略目录 `backend/data/`，不提交个人练习数据库。克隆代码不会自动获得本机发布数据。

持久化发布与六主题 HTTP 验收脚本为 `backend/scripts/release_first_half.py`，它调用既有 `first_half_release` 发布入口，不绕过审核。重跑会重复校验和创建六个未作答会话，已有题目不重复新增；若后续 06 已发布，不适用此限定 57 题的验收脚本。

工单全部 **5/5** 勾选；仓库五个 triage 状态没有 closed，按既有已完成工单惯例保留 `ready-for-agent`，完成情况以清单及证据为准。

最终后端 **73 passed**，mypy、ruff check、ruff format --check 通过；前端 TypeScript 与 Vite build 通过。只有既有 Starlette/httpx 弃用提示。

最终增量相对 `18b5402` 由全新上下文两个子 Agent 独立复核：Standards 0 项、Spec 0 项。审查者额外只读确认发布报告和六个保存会话，重启过程由主 Agent 记录，不冒充审查者亲历。
