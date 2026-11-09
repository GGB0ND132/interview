export type PracticeConfig = { role: string; difficulty: string; count: number; followups: number; focus: string; kb: string }
export type Session = { id: string; title: string; role: string; date: string; score: number | null; count: number; status: '已完成' | '提前结束'; topic: string; answers?: { question: string; answer: string }[] }
export const defaultConfig: PracticeConfig = { role: '后端开发工程师', difficulty: '进阶', count: 5, followups: 1, focus: '综合能力', kb: '后端面试知识库' }
export const questions = [
  { topic: '缓存与一致性', title: '如何设计一个可靠的缓存更新策略？', text: '在一个读多写少的业务中，你会如何保证 Redis 缓存与 MySQL 数据的一致性？请说明你的更新顺序，以及出现并发请求时可能遇到的问题。', followup: '你提到了缓存更新流程。如果删除缓存失败，你会如何发现并补偿？请结合一个具体的实现方案说明。', points: ['说明先更新数据库、再删除缓存的基本流程', '识别并发与删除失败带来的一致性窗口', '给出重试、消息补偿或过期时间等工程方案'], reference: 'Cache Aside 模式中，应用先从缓存读取；未命中时访问数据库并回填。写入时更新数据库，再使对应缓存失效。缓存删除仍可能失败，需要结合重试机制、过期策略和业务允许的一致性窗口设计补偿。', file: 'Redis 核心知识与实践.md' },
  { topic: '数据库与事务', title: '事务隔离级别解决了什么问题？', text: '请解释 MySQL 的可重复读隔离级别。它如何处理一致性读取？在实际业务中，你会如何选择普通快照读和加锁读取？', followup: '如果两个事务同时读取库存并扣减，你会怎样避免超卖？请说明 SQL 或事务层面的处理方式。', points: ['区分快照读与当前读', '解释事务可见性和并发问题', '结合业务选择锁或条件更新'], reference: 'InnoDB 的一致性非锁定读使用多版本机制提供快照。在可重复读级别，同一事务的普通读取共享一致性视图；加锁读取读取当前可用的数据并获取对应锁。', file: 'MySQL 事务与索引.pdf' },
  { topic: '接口与可靠性', title: '如何避免接口重复提交？', text: '一个订单创建接口在网络超时后被客户端重试。你会如何设计幂等机制，避免生成重复订单？', followup: '如果业务已经成功，但幂等结果还没有写入，服务就重启了，你会如何缩小这个窗口并恢复结果？', points: ['区分幂等键与业务唯一约束', '说明并发请求的处理方式', '考虑超时与中间状态恢复'], reference: '幂等请求可以通过唯一请求标识识别。数据库唯一约束提供最终的防重复边界；请求状态、业务写入和结果记录应尽可能在可控事务中保持一致。', file: '后端系统设计笔记.docx' },
  { topic: '项目与权衡', title: '如何定位接口响应变慢的问题？', text: '假设你负责的列表接口响应时间明显上升，你会按什么顺序排查？请结合监控、日志和数据库执行计划给出思路。', followup: '如果确认慢在数据库，但短期不能改变表结构，你会优先采取什么措施？为什么？', points: ['先确定影响范围并分解耗时', '使用证据定位瓶颈', '说明短期缓解和长期改进的权衡'], reference: '接口诊断应结合请求耗时、调用链、依赖服务和数据库查询证据。先定位主要耗时段，再使用查询计划、索引情况和数据规模验证假设。', file: '后端系统设计笔记.docx' },
  { topic: '表达与边界', title: '如何解释你做过的一次技术选型？', text: '请选择一个你真实参与的项目，说明一次技术选型：当时的目标是什么、有哪些备选方案、你如何做出权衡，以及最后怎样验证效果？', followup: '如果业务规模扩大十倍，你原来的选择还成立吗？请说明需要重新评估的条件。', points: ['交代真实背景与个人责任', '比较方案与约束条件', '明确验证方式和适用边界'], reference: '项目类问题应根据用户实际经历展开，区分个人贡献与团队成果。缺少真实数据时应说明测量计划，不能编造收益数字。', file: '后端系统设计笔记.docx' },
]
export const initialSessions: Session[] = [
  { id: 'demo-1', title: '从原理到实践，补齐缓存设计', role: '后端开发工程师', date: '2026-10-26 19:30', score: 82, count: 5, status: '已完成', topic: '缓存与一致性' },
  { id: 'demo-2', title: '数据库事务与索引专项', role: '后端开发工程师', date: '2026-10-25 14:20', score: 76, count: 3, status: '已完成', topic: '数据库与事务' },
  { id: 'demo-3', title: '把项目经历讲得更具体', role: '后端开发工程师', date: '2026-10-23 20:10', score: 85, count: 5, status: '已完成', topic: '项目与表达' },
  { id: 'demo-4', title: '接口可靠性与异常恢复', role: '后端开发工程师', date: '2026-10-21 18:45', score: 71, count: 3, status: '已完成', topic: '接口与可靠性' },
]
export const dimensions = [ { name: '准确性', score: 85 }, { name: '覆盖程度', score: 76 }, { name: '相关性', score: 90 }, { name: '回答结构', score: 82 }, { name: '具体程度', score: 74 } ]
