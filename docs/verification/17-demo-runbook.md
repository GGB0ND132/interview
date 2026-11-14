# 17：阶段演示操作手册

检查日期：2026-11-14（Asia/Shanghai）。目标：11 月 16 日预检、11 月 18 日演示。代码基线 `6e26057` 已包含 01–16。本手册对应本机单用户实例，不表示部署到公网。

## 演示前准备

从本工作区打开两个 PowerShell 终端。题库和会话在本工作区忽略的 SQLite 中，Git 合并不会复制数据库。模型密钥仅由后端进程环境读取 `DASHSCOPE_API_KEY` 或 `LLM_API_KEY`，不要填入页面或提交仓库。

终端 A（仓库根目录）：

```powershell
cd backend
uv sync --locked --extra dev
$env:DATABASE_PATH='data/demo-17.sqlite3'
uv run --locked uvicorn interview_backend.api:create_app --factory --host 127.0.0.1 --port 8017
```

终端 B，先准备指定演示库。该命令写入题库，沿用 05 的独立 Agent 审核门槛和 06 显式全量 Agent 审核门槛；只发布通过项，不调用模型。通过保存的发布 ID 回读确认 HTTP 服务使用同一个目标库。重复运行不新增题目版本，不删除原会话。

```powershell
cd backend
uv run --locked python -X utf8 scripts/prepare_demo.py --database data/demo-17.sqlite3 --output ../docs/verification/17-prepare-current.json --resume-output ../output/playwright/17-resume.docx
cd ../fronted
npm ci
$env:INTERVIEW_BACKEND_URL='http://127.0.0.1:8017'
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5177 --strictPort
```

打开 <http://127.0.0.1:5177/question-practice>。必须以当前 HTTP 可用性为准，不照读本文的历史计数。当前快照为 115 道可抽技术题、98 道适合模拟面试、11 个题量充足的技术主题和另行发布的 5 道通用题。GUI 有 1 道来源题，不能成为要求至少两题的随机面试主题。

若端口被占用，先识别占用实例或另选一组端口，同步修改代理与验收命令。不要终止不明进程。后端不可达时展示连接失败与重新连接，模型失败时保留回答并重试，不能用静态反馈代替。

## 现场演示顺序

1. 展示题库可用数及 12 主题覆盖。说明固定来源是 `didilili/mianstack@b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77`，115 是本次全部来源候选数，只有通过校验且未停用的当前版本进入抽题池。当前 115 全部通过，不代表所有答案或模型评分都准确。
2. 随机抽一道，现场作答，输入一部分后刷新，核对原题及草稿。提交后说明正在调用真实后端模型，等待即时反馈；刷新核对保存的回答和反馈。没有核验资料时展示无引用说明，原题链接只供追溯。查看评分维度及不确定项，必要时通过页面报告问题。
3. 分别另抽题执行“空白提交”和“跳过本题”。空白为 0 分并计入均分；跳过为 null、不计均分。两者均不调用评分模型。
4. 打开模拟面试准备页。无资料可直接开始，默认使用明确的假设情境。个性化演示粘贴“熟悉工具调用和 Agent 运行循环，能够处理失败重试；熟悉 Kubernetes 集群运维。”，提取并确认。说明匹配主题提高权重仍随机，无法映射的要求保留为缺口，不生成新主问题。
5. 上传 `output/playwright/17-resume.docx`，回查第 2 段，确认项目。文件是合成课程案例，不是用户真实简历。只有确认后的项目进入会话；修正后须重新预览确认。解析失败可粘贴，扫描件识别不在本次范围。
6. 开始模拟面试，依次完成开场、经历或情境、随机技术主题、行为、候选人反问。经历回答先说明自己负责的工作，含糊时查看与实际回答相关的追问；不要承诺每次一定生成追问。进行中只展示交流，结束后才公开评分和参考答案。
7. 展示报告。完整或部分以服务端实际证据与 JD 覆盖为准。报告有“已了解”只表示材料足以评价，不表示答对；明确不会也可形成已观察到的知识缺口。缺少证据、提前结束、JD 未覆盖均应保留说明。刷新后再查看报告、JD 选题记录和项目来源。
8. 说明边界：资料管理与独立历史页仍为演示数据，真实记录在两个练习入口查看；个人学习资料入库、JD 文件上传、其他岗位/难度、语音和公开多用户不作为本次交付。

## 可重复检查

只读核对当前发布池，不抽题、不调用模型；输出逐题版本、来源状态、校验/拒绝原因、停用状态和实际数量。未发布、停用、内容版本不匹配或总数不一致时保存记录并退出 2。该退出码只判断发布池，不代表整份工单或人工抽查通过。

```powershell
# backend 目录
uv run --locked python -X utf8 -m interview_backend.demo_acceptance --base-url http://127.0.0.1:8017 --output ../docs/verification/17-release-current.json
# 生成逐题可读发布表、23 题待审材料和人工结论空表。使用新目录，避免覆盖人工已填结果。
uv run --locked python -X utf8 scripts/record_demo_release.py --inventory ../docs/verification/17-release-current.json --output-dir ../output/17-review-current
```

若终端启用了全局 HTTP 代理，访问本机前设置 `$env:NO_PROXY='127.0.0.1,localhost'`。发布清单的 `available_for_scoring` 同时排除错题隔离与主题暂停，不仅检查 published；`counts_match_availability` 为 false 时应重新捕获一致快照。渲染脚本拒绝覆盖已有 `17-human-reviews.json`，不会发布、批准题目或回写人工结论。

当前 [抽查材料](17-human-review-packet.md) 与 [结论表](17-human-reviews.json) 已记录用户确认：23 题均 passed，GUI 接受唯一来源题，其余审核字段省略。重新生成的空表只用于新一轮审核，不能替换已确认记录。结论表不会自动调用发布或恢复 API；发现错题仍须通过既有维护流程隔离与复查。

浏览器回归使用 Playwright CLI。创建独立浏览器会话，先 `snapshot` 检查页面。`17-browser-prepare.js` 从模拟面试准备页执行 JD、DOCX 确认和草稿刷新；`17-browser-step.js` 每次只做一步，可反复执行直到报告。两者使用真实服务和模型，非空回答产生实际模型调用费用。其答案明确为合成验收样例，技术题主要使用明确的知识缺口回答，用于验证流程，不验证评分准确性。

```powershell
# 仓库根目录，前后端均已启动
npx --yes --package @playwright/cli playwright-cli -s=demo17 open http://127.0.0.1:5177/practice
npx --yes --package @playwright/cli playwright-cli -s=demo17 snapshot
npx --yes --package @playwright/cli playwright-cli -s=demo17 run-code --filename=.scratch/agent-principles-demo/17-browser-prepare.js
npx --yes --package @playwright/cli playwright-cli -s=demo17 run-code --filename=.scratch/agent-principles-demo/17-browser-step.js --raw
```

等待模型完成后重复最后一条命令。失败会显示保留的错误并提供重试；持续失败时记录会话 ID，现场如实展示失败，不无限调用。单题现场完成真实反馈后，可从该反馈页运行 `17-practice-checks.js` 保存截图并核对空白/跳过。

## 受控失败与重启

故障演示使用另一个数据库、端口与浏览器会话。以下评价器刻意返回超时或固定 75 分，只检查持久化与重试，不是实时模型评分，不要展示为真实模型结果。

```powershell
# backend 目录，单独终端 C
uv run --locked python -X utf8 scripts/acceptance_frontend_recovery.py --database data/recovery-17.sqlite3 --port 8117 --outcome failure
```

另起前端代理到 8117：在 `fronted` 目录设置 `$env:INTERVIEW_BACKEND_URL='http://127.0.0.1:8117'`，启动 `node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5277 --strictPort`。

```powershell
# 仓库根目录；首次检查用新的浏览器会话和新的 recovery 数据库文件名
npx --yes --package @playwright/cli playwright-cli -s=recovery17 open http://127.0.0.1:5277/question-practice
npx --yes --package @playwright/cli playwright-cli -s=recovery17 snapshot
npx --yes --package @playwright/cli playwright-cli -s=recovery17 run-code --filename=.scratch/agent-principles-demo/17-recovery-fail.js --raw
```

脚本分别验证双模式草稿刷新、失败答案刷新；记录 session/job ID。在终端 C 停止该验收进程，用同一个数据库、同一端口改为 `--outcome success` 重启。不要重新创建数据库。

```powershell
npx --yes --package @playwright/cli playwright-cli -s=recovery17 run-code --filename=.scratch/agent-principles-demo/17-recovery-retry.js --raw
```

重试后应为同一条回答和原 job，attempts=2、succeeded，刷新后结果仍在。模拟面试未结束前不能公开反馈。

保存任意会话证据可在 backend 执行：

```powershell
uv run --locked python -X utf8 scripts/capture_demo_sessions.py --base-url http://127.0.0.1:8017 --session demo=替换成实际会话ID --output ../docs/verification/17-sessions-current.json
# 重启同库后，只读比较已保存的会话、报告和任务；全部相同后记录复核时间
uv run --locked python -X utf8 scripts/capture_demo_sessions.py --base-url http://127.0.0.1:8017 --verify-existing --output ../docs/verification/17-sessions-current.json
```

有据引用的真实模型和文档抓取独立验收使用全新数据库：`uv run --locked python -X utf8 scripts/acceptance_provenance.py --database data/provenance-new.sqlite3 --output ../docs/verification/17-provenance-current.json`。该命令有真实网络及模型调用，拒绝覆盖现有数据库。

## 用户确认与后续现场检查

05/06 已有独立 Agent 审核及显式发布策略。2026-11-14 用户明确将 17 的 23 道抽查题结论统一确认为 passed，接受 GUI 仅一题，并省略其余审核字段；17 全部交付项据此勾选。没有新增 GUI 题或补造审核人、审核时间及资料。

11 月 16 日按本手册重新跑发布池核对与双模式闭环，11 月 18 日演示前再次检查服务、密钥和当前题数。本文是 11 月 14 日预验收，不能代记未来两次检查已经发生。
