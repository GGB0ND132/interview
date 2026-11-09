# MianStack 题库与真实面经：源码评估

核对日期：2026-11-09。公开仓库 [didilili/mianstack](https://github.com/didilili/mianstack) 固定提交：[`b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77`](https://github.com/didilili/mianstack/tree/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77)。以下是该提交的**公开内容与校验代码**的静态核对，不是在线网站运行结果；未逐一回访 957 个第三方原帖。

## 结论

MianStack 值得借鉴的是稳定题号、一题一文件、分类/专题/题型/难度分离，以及面经的原帖链接和公司岗位情境。公开仓库可提供候选题与真实问法的**人工匹配输入**，但不能直接交付本项目的已审核题库：题目没有岗位能力、环节、评分表、答案依据、本项目审核/发布状态；面经与题目的对应和出现频次由网站另行维护，不在公开数据中。[题目字段](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/schema/content.schema.json#L366-L450)、[公开数据边界](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/USAGE.md#L46-L61)。

## 1. 题库结构与状态含义

- `questions/Q-*.md` 用 JSON frontmatter 保存 `id`、标准题面 `title`、`category`、`topic`、`type`、`level`、`priority`、`focus`、`answerStatus` 等，后接 Markdown 参考答案；分类和专题由 [`categories.json`](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/categories.json) 管理。当前有八个顶层方向：模型、RAG、Agent、AI 工程、训练、软件工程、编程题、项目与综合面试。[字段说明](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/schema/README.md#L28-L51)、[分类实例](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/categories.json#L1-L12)。
- `type` 是 15 种**问法/问题类型**，包括概念解释、原理机制、比较选型、方案设计、项目深挖、代码题、故障排查、行为面和反问等；`level` 只有基础、进阶、深入；`priority` 是备考优先级，和难度不同。可选 `formatTags`、`contextTags` 细化问法与场景。[枚举定义](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/schema/content.schema.json#L63-L126)。`category/topic` 是知识归属，不是岗位、能力或面试环节；题目 schema 无 `role_tracks`、`competency_ids`、`stage`、`rubric`、`source_refs`。[题目 schema](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/schema/content.schema.json#L366-L450)。
- `answerStatus` 是**参考答案内容进度**：`pending` 暂无、`outline` 提纲、`draft` 草稿、`ready` 已有答案、`reviewed` 已校对。只有 `ready/reviewed` 计入 `answered`，校验器仅要求这两种状态有非空正文。它不是本项目的题目技术审核、评分试答或发布状态，也不是某用户“待复习/已掌握”的练习进度。[状态与分组](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/schema/content.schema.json#L101-L116)、[校验代码](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/scripts/lib/content.mjs#L293-L298)。README 称后者保存在当前浏览器；公开仓库没有网站的用户进度实现，不能由此推断账号级持久化。[产品说明](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/README.md#L50)。
- 该快照的实际 `Q-*.md` 为 **8429**（`questions/` 另有 README）；逐文件读取 frontmatter 后，`pending` **7739**、`ready` **690**，其余三种状态在本快照为 0。数字仅描述仓库内容快照，`ready` 不等于通过本项目评分审核。[统计口径](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/USAGE.md#L54-L61)、[状态定义](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/schema/content.schema.json#L101-L116)。
- 题号稳定，合并时在 `aliases.json` 保留旧号指向；`INDEX.md` 和 `indexes/*.md` 是生成目录。可以借鉴这个源数据/衍生索引边界，但导入本项目时仍需另建题目版本与发布记录。[维护规则](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/MAINTAINING.md#L7-L19)、[ID 规则](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/MAINTAINING.md#L50-L55)。

## 2. 面经来源、公司岗位与关联边界

`interviews/MJ-*.md` 在该提交有 **957** 篇：`MJ-NC-*` **910** 篇，`MJ-XHS-*` **47** 篇；相应顶层 `url` 域名分别为 `www.nowcoder.com` 与 `www.xiaohongshu.com`。目录还有一个 `README.md`，不能把所有 Markdown 文件计成面经。内容类型中还允许笔试记录、面经合集、方法分享等，所以“957 篇”也不等于 957 场独立面试。[命名与 ID](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/schema/README.md#L18-L25)、[内容类型](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/schema/content.schema.json#L173-L185)、[统计口径](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/USAGE.md#L54-L58)。

因此，把其**面经**描述成“从很多网站或博客抓取”并不符合该快照：可见面经原帖集中在牛客和小红书。另一个 `collections/` 则是**第三方公开题集**，该快照有 356 个 `COL-*.json`、合计 15901 条原题；顶层 `sourceUrl` 中 335 个指向 GitHub，另有 `xiaolinnote.com`、`javabetter.cn`、`notes.kamacoder.com` 等站点。题集保存原题标题、链接、署名、访问/核验和条目 `reviewStatus`，不等于真实单场面经；例见 [AgentGuide 题集](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/collections/COL-AGENTGUIDE-ALGORITHM.json#L1-L24) 与 [题集字段说明](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/schema/README.md#L177-L213)。题集条目的 `confirmed/new_candidate/needs_review/excluded` 是**原题条目审核**，也不能当作标准题已发布状态。[枚举](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/schema/content.schema.json#L352-L364)。

每篇面经的 `contexts[]` 可保存公司、业务、岗位名/分类、岗位判断方式及置信度、技术方向、实习/全职、校招/社招、轮次和地点；顶层有原帖作者、作者主页、`url`、发布时间、最近回源日期、`sourceStatus` 和 `curationStatus`，正文保留原帖问法。[面经 schema](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/schema/content.schema.json#L452-L645)、[岗位判断方式](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/schema/content.schema.json#L279-L291)。`sourceStatus` 仅表示来源可用性，`curationStatus` 仅表示整理进度；`lastCheckedAt` 代表回源日期，均不证明面试发生过、公司和岗位经过独立核实。[使用说明](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/USAGE.md#L69-L73)、[状态枚举](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/schema/content.schema.json#L187-L209)。

**关键缺口：** 公开仓库没有面经原问法到标准题的 `questionIds`、关系表、出现频次、题族或追问链。README、USAGE 和维护说明均明确这些由另一个网站维护；不能把“公开库无关联字段”解释为“没有面经命中”，也不能据此计算公司题频。[README](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/README.md#L158-L163)、[USAGE](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/USAGE.md#L46-L61)、[维护说明](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/MAINTAINING.md#L58-L68)。

## 3. 两组可核对的候选匹配

下面是**本次依据公开原文与题面做的候选匹配**，不是声称已取得网站的私有关系记录，也不是本项目题库已发布。

| 原问法与面经 | 标准题候选 | 判断与导入处理 |
| --- | --- | --- |
| [MJ-NC-2026-0002 第 18 题](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/interviews/MJ-NC-2026-0002.md#L53-L60)：`B+树和B树的区别？` | [Q-0193](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/questions/Q-0193.md#L1-L20)：`B 树和 B+ 树有什么区别？`，`software / 数据库与 SQL`，比较选型、进阶、`ready` | 题意几乎一致，**匹配高置信**；可作为 Python 后端数据库能力的候选问法，但仍需核答案、评分点、许可和岗位适配。面经中的“字节跳动/飞书”来自归档，其“后端开发工程师（AI / Agent 方向）”明确标为**面试内容推测**，不能写成原帖明示岗位。[面经元数据](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/interviews/MJ-NC-2026-0002.md#L3-L30) |
| [MJ-NC-2026-0716 React 闭包题](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/interviews/MJ-NC-2026-0716.md#L75-L77)：`React useEffect + 定时器计数` 和 `1 秒 count+1` | [Q-7457](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/questions/Q-7457.md#L1-L16)：useEffect 每秒自增，代码题、进阶、`pending` | 子问题重合，**匹配中高置信**；可做 React 方向候选。但原帖未给完整代码，不能补写“原代码”或断定输出值；Q-7457 无参考答案，不能直接进入需即时评分的正式题池。[面经岗位及原帖链接](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/interviews/MJ-NC-2026-0716.md#L3-L37) |

## 4. 与本项目需求的对照和最小匹配流程

| 本项目已写明的目标 | MianStack 公开仓库提供什么 | 本项目仍须补什么 |
| --- | --- | --- |
| [题库建设与运行流程](../题库建设与运行流程.md)要求来源登记、精确定位、多维标注、技术/评分审核和 `candidate → ... → reviewed → published` | 稳定 `Q`/`MJ` ID、题面、知识专题、类型/难度、部分参考答案及面经原帖；`answerStatus` 只是答案进度 | 建本地来源记录与原问法定位；映射 `role_tracks`、`competency_ids`、`content_layer`、`stage`；独立审核答案、评分点与许可，创建本项目 `review_status` 和版本，不能把 `ready` 自动映射为 `published`。[本地流程](../题库建设与运行流程.md#5-审核和发布) |
| [项目架构与需求 V1.4](../项目架构与需求_V1.md)要求 `pack_questions` 保存岗位包、能力、答案/评分/来源版本，正式主问题只选 `published` | 可用作候选素材与来源之一；公开库无岗位包和评分表 | 转换为本地业务结构，保留来源 commit、外部 ID 与答案版本；各岗位/难度/环节通过可用题量和试答门槛后再开放。[本地表契约](../项目架构与需求_V1.md#8-数据存储设计) |
| [.scratch/realistic-interview/spec.md](../../.scratch/realistic-interview/spec.md)要求真实面经只作问法和场景参考，技术主问题与评价来自审核题库 | 有原帖问法及公司/岗位/轮次情境；公开关系数据不全 | 将“面经候选关联”与“已发布主问题”分开；面经不能证明技术答案正确，个人经历和公司真实性也不能由归档自动确认。[本地决定](../../.scratch/realistic-interview/spec.md#决定) |

最小可执行流程（编辑阶段，非运行时联网抽题）：

1. 固定本次仓库 commit，登记面经 `MJ`、原帖 URL/作者、`sourceStatus`、回源日期、原文**条目/行号与短引文**；另登记 `Q` 文件路径、题号和答案状态。第三方原文先核用途与署名；MianStack 对其自写题解采用 MIT，不把这个许可延伸到第三方面经/题集。[版权边界](https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/CONTRIBUTING.md#L64-L81)。
2. 从原帖中只切出**明确可见的问法**，用标准题标题、关键词和 `focus` 召回候选 `Q`，人工比对考察边界。保存 `match_type`（同义/部分重叠/仅相关）、`match_confidence`（高/中/低）、匹配理由、未覆盖的子问及审核人；公司、岗位另保留 `roleMethod` 和其置信度，避免把“题目匹配高”误传成“岗位身份可靠”。
3. 高置信同义问法可作为既有候选题的来源证据；部分重叠保留原问法或拆题，不凭相似度自动合并。`pending/outline/draft` 必须补答案；即使 `ready/reviewed` 也要逐题做技术核对、评分表、来源/权利审核和完整/部分/错误/不会试答，才由本项目发布。
4. 运行时只筛本地 `published` 题库，面经关联可用于“真实问法出处”和岗位情境展示；**不**把未核验的面经提及次数作为选题权重。未来若拿到网站提供的可核验关系数据，先登记其版本和证据口径再考虑频次。

## 5. 建议采纳顺序

| 建议 | 时机 | 原因与边界 |
| --- | --- | --- |
| 借鉴“知识分类 → 专题”，并保留独立的题型、难度、准备优先级 | 首批题库建模时 | 本项目已有 `competency_ids`、`content_layer`、`difficulty`、`stage`、`format_tags`，可给分类/专题建立受控词表并映射能力 ID；不要直接复制面栈全部八大方向或把专题当岗位能力。`priority` 应由目标岗位、JD、能力缺口和审核题量决定，而非照搬来源标签。 |
| 建立面经原问法到本地题目的可审核关联 | 首批内容编辑时，先做 Python 后端与 React/Vue 少量样本 | 保存 `experience_id`、`context_id`、原问法定位和短引文、`question_id`、匹配类型/理由/置信度、审核人及来源版本；一篇面经可对应多题，一题也可有多个来源。只在关联审核后展示“某面经中出现过”，不能从相似文本自动宣称“某公司考过此题”。 |
| 逐题“待复习/已掌握”和最近练习记录 | 最小练习闭环可持久化之后 | 本项目目前只有能力级复习建议和练习尝试。把个人状态另存为题目 ID 对应的用户进度，至少区分“未练”“待复习”“已掌握”，记录用户手动标记与最近一次练习时间；题目版本更新后提醒重新核对。单次模型评分不应自动标为已掌握。先做筛选和回看，再决定是否加入到期时间或间隔复习算法。 |
| 公司/岗位/轮次情境筛选 | 已有足够经回源核对的面经关联后 | 展示原帖声称或整理推断的公司与岗位，并标明推断方式；公司模拟练习仍从本地已发布题库选题。单篇自述不能代表该公司的标准面试流程。 |
| “高频热榜”、大规模导入和自动匹配 | 暂缓 | 公开仓库缺少可重算的面经到题目关系，题目大部分无答案；在关联覆盖率、去重、时间窗及岗位口径确定前，频次容易误导选题。 |

本次数量由固定提交的目录文件及 JSON frontmatter 逐条统计，未把 `README.md` 算入 `Q`/`MJ`，题集条目数按各 `items[]` 求和。外部原帖链接是否仍可访问、归档与原帖是否逐字一致，以及网站私有匹配准确率，本次未验证。
