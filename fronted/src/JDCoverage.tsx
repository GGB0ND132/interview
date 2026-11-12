import type { InterviewReport, JDRequirement, SessionView } from './api'
import { competencyLabel } from './interview-labels'

const GAP_REASONS = {
  unmapped_requirement: '暂未映射到题库维护的能力',
  topic_not_eligible: '相关主题的合格主问题不足',
  not_selected: '相关主题本场未抽中',
  insufficient_evidence: '本场尚未获得足够的回答依据',
}

export function JDRequirementDetails({ requirement }: { requirement: JDRequirement }) {
  return <div className="jd-requirement-details">
    <p className="meta-note">JD 原文第 {requirement.source_span.line} 行</p>
    {requirement.coverage.map(topic => <p key={topic.competency_id}>{topic.topic}：{topic.eligible_question_count} 道合格主问题，{topic.eligible ? '可参与主题抽选' : topic.reason === 'no_published_questions' ? '暂无已发布题目' : '题量不足，不能参与主题抽选'}</p>)}
    {requirement.gap_reason && <p>{GAP_REASONS[requirement.gap_reason]}</p>}
  </div>
}

export function JDSelection({ session }: { session: Pick<SessionView, 'plan' | 'jd'> }) {
  if (!session.plan?.topic_candidates) return null
  return <details className="mi-coverage jd-selection"><summary>本场主题抽选与 JD</summary>
    <p className="meta-note">{session.jd ? '已确认的 JD 提高相关合格主题的抽选权重。' : '本场未使用 JD，合格主题按基础权重抽选。'}仍随机选择 3～4 个主题，权重不代表入选概率，也不保证每次抽中。</p>
    <ul className="qp-stage-list">{session.plan.topic_candidates.map(item => <li key={item.competency_id}>
      <span>{session.jd?.requirements.flatMap(requirement => requirement.coverage).find(topic => topic.competency_id === item.competency_id)?.topic ?? competencyLabel(item.competency_id, session.plan?.questions ?? [])}</span>
      <span>权重 {item.weight} · {item.eligible_question_count} 道题 · {session.plan?.selected_topics.includes(item.competency_id) ? '本场已抽中' : '本场未抽中'}</span>
    </li>)}</ul>
    {session.jd?.requirements.some(item => item.gap_reason) && <p className="field-help">JD 中题库暂不能覆盖的要求会保留在报告中。</p>}
  </details>
}

export function JDReportCoverage({ report }: { report: InterviewReport }) {
  if (!report.jd) return null
  return <section className="jd-report"><h2>JD 要求覆盖</h2>
    <p className="meta-note">JD 仅用于岗位匹配和追问情境，不作为技术正确性的依据。可抽选不等于本场已覆盖。</p>
    <p>{report.jd_coverage_status === 'covered' ? '本场已获得所确认要求的可评价材料，不代表已掌握。' : '本场仍有 JD 要求未覆盖，详见下列缺口。'}</p>
    <ul className="mi-gap-list">{report.jd_gaps?.map(requirement => <li key={requirement.id}><strong>{requirement.text}</strong><JDRequirementDetails requirement={requirement} /></li>)}</ul>
    <details><summary>回看本场已确认的 JD 原文</summary><p className="meta-note">只列出本场确认的要求；未勾选的要求不参与本场选题或覆盖评价。</p><ul className="mi-gap-list">{report.jd.requirements.map(item => <li key={item.id}>{item.text}<p className="meta-note">原文第 {item.source_span.line} 行</p></li>)}</ul></details>
  </section>
}
