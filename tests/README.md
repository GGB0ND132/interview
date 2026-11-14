# 测试输入与验收证据

可执行测试仍位于 `backend/tests/` 和 `fronted/src/*.test.ts(x)`；本目录集中保存跨前后端材料。

- `fixtures/question-reviews/`：真实发布门槛所需的 06 独立 Agent 审核 JSON，以及未代填的旧人工模板。发布脚本和后端测试会读取，不能随意删除。
- `fixtures/documents/`：隔离文档解析样本和 DOCX 样本生成脚本；不是正式题库或用户简历。
- `evidence/`：仅保留 17 最终验收的 HTTP 响应、真实模型输出、受控恢复结果和截图。不是单元测试，也不代表当前服务状态。

保留的审核 JSON、HTTP/模型 JSON、DOCX 和截图保持原字节。01–14 的阶段输出和重复截图已清理；已提交的历史可从 Git 查阅。新验收输出放入忽略的 `output/`，需要形成正式证据时再有选择地保留。

数据库位于本机 `backend/data/` 或 pytest 临时目录，不保存在这里。不要用合成或受控评分结果冒充真实模型验收。
