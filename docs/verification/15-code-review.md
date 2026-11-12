# 15：独立代码审查

日期：2026-11-12。使用 `mattpocock-skills:code-review` 的两个独立、空白上下文子 Agent，分别审查 Standards 与 Spec；未混合两轴结果。

固定基线：`2ba2cff7400245fce26ee6724444ce8d79f07d07`。初始实现 `25ba67e`，修正 `aed722c`。命令：`git diff 2ba2cff7400245fce26ee6724444ce8d79f07d07...HEAD`；提交列表：`git log 2ba2cff7400245fce26ee6724444ce8d79f07d07..HEAD --oneline`。

规范来源：`AGENTS.md`、`docs/agents/{issue-tracker,triage-labels,domain}.md`、`backend/pyproject.toml`、`backend/README.md` 及技能的 Fowler smell baseline。没有额外 CODING_STANDARDS.md / CONTRIBUTING.md。工单来源为用户指定外部目录的 `15-backend-session-recovery.md`，补充 `.scratch/agent-principles-demo/spec.md`。

## Standards

初审：无发现。未发现违反给定规范或值得报告的可操作代码异味。SQLite 写事务串行化并发检查；令牌和租约在改变状态前隔离过期结果。

观察但不列为缺陷：恢复线程串行执行，正在进行的外部调用会推迟后续扫描；关闭 lifespan 只等待线程一秒，进行中的 daemon 工作可继续执行。当前契约不承诺并行恢复或关闭即取消。

修正复审 `25ba67e..aed722c`：无发现。版本复核位于 `BEGIN IMMEDIATE` 内，逐条执行当前简单迁移 SQL 避免隐式提交，并发启动回归从 HTTP 观察已保存会话。

## Spec

初审一项 P2：`store.py` 的 schema 4→5 升级在拿锁前读取版本。两个实例同时重启可能都选择迁移 5，第二个启动时报 `duplicate column name: claim_token`，影响“重启后可恢复已保存状态”。审查者在临时库独立复现。

修正：新增四个服务并发启动、恢复同一会话的 HTTP 回归，先复现红灯；迁移 5 在写锁中重读版本，仅对版本 4 执行升级，避免 `executescript` 隐式释放保护锁。原有早期迁移未扩展重构。

复审：P2 已解决。审查者独立重跑并发启动回归，1 passed；没有新的 Spec 发现。未发现其他缺项、越界行为或错误实现。

## 检查与边界

最终后端全量 133 passed，mypy、Ruff check/format 通过；前端 20 passed，TypeScript/Vite 构建及 ESLint 通过。双模式真实进程/TCP 中断恢复、重试与报告二次重启验证使用受控外部适配器；未冒称真实收费模型或在线检索验收。细节见 [15-backend-session-recovery.md](15-backend-session-recovery.md)。

两轴汇总：Standards 初审 0、最终 0；Spec 初审 1 项 P2、已修复，最终 0 项未解决发现。
