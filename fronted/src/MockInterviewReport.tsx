import type { InterviewReport, PlannedQuestion, PracticeApi } from './api'
import { FeedbackSources, ReportProblem } from './FeedbackSources'
import { competencyLabel, COVERAGE, DIMENSIONS, DISPOSITIONS } from './interview-labels'
import { JDReportCoverage, JDSelection } from './JDCoverage'

export default function MockInterviewReport({ api, report, questions, onBack }: { api: PracticeApi; report: InterviewReport; questions: PlannedQuestion[]; onBack: () => void }) {
  return <main className="page-content report-page mi-report">
    <button className="text-link" onClick={onBack}>返回模拟面试入口</button>
    <div className="page-header"><h1>{report.completeness === 'complete' ? '完整面试报告' : '部分面试报告'}</h1><p>{report.stop_reason_detail}</p></div>
    <div className="report-body">
      <JDReportCoverage report={report} />
      <JDSelection session={{ plan: report.plan, jd: report.jd ?? undefined }} />
      <section><h2>本场表现</h2><div className="mi-scores"><p>整体题组均分<strong>{report.average_score ?? '未评价'}</strong></p><p>技术题组均分<strong>{report.technical_average_score ?? '未评价'}</strong></p></div>
        <p className="meta-note">仅计算已完成且有分数的题组，追问不单独计分；空白记 0 分，跳过与未完成题组不计分。</p>
        <div className="report-stats"><span>{report.answered_count} 个计分题组</span><span>{report.blank_count} 个空白</span><span>{report.skipped_count} 个跳过</span></div>
        {report.limitations.map(text => <p className="meta-note" key={text}>{text}</p>)}
      </section>
      <section><h2>环节与能力覆盖</h2><p className="meta-note">已了解表示材料足以评价，不等于回答正确或已掌握。</p><ul className="qp-stage-list">{report.coverage.map(item => <li key={item.competency_id}><span>{competencyLabel(item.competency_id, questions)}</span><span>{COVERAGE[item.status]}</span></li>)}</ul></section>
      <section><h2>未覆盖与信息缺口</h2>{report.gaps.length ? <ul className="mi-gap-list">{report.gaps.map(item => <li key={item.competency_id}><strong>{competencyLabel(item.competency_id, questions)}</strong><p>{item.reason ?? '本场尚未获得可评价材料'}</p>{item.unresolved.filter(text => text !== item.reason).map(text => <p key={text}>{text}</p>)}</li>)}</ul> : <p>本场所选能力均已有可评价材料；其他岗位能力未纳入本次报告。</p>}</section>
      <section><h2>题组回顾与问答</h2>{report.groups.map(group => <article className="answer-record" key={group.id}>
        <h3>{group.question.topic}</h3><p className="report-score">题组分数：{group.status === 'completed' ? group.score ?? '未评价' : '未完成，不计分'}</p>
        {group.feedback?.knowledge_gap === true && <p className="meta-note">已记录知识缺口，不代表掌握。</p>}
        {report.turns.filter(turn => turn.group_id === group.id).map(turn => <div className="mi-report-turn" key={turn.id}><h4>{turn.kind === 'followup' ? '追问' : '主问题'}</h4><p>{turn.text}</p>{group.submissions.filter(item => item.turn_id === turn.id).map(item => <p className="submitted-answer" key={item.id}>{item.answer_text || DISPOSITIONS[item.disposition]}</p>)}</div>)}
        {group.feedback && <div className="mi-group-feedback">
          <h4>值得保留</h4><ul>{group.feedback.strengths.map(text => <li key={text}>{text}</li>)}</ul>
          <h4>需要补充</h4><ul>{group.feedback.improvements.map(text => <li key={text}>{text}</li>)}</ul>
          <details><summary>维度评价与回答依据</summary>{group.feedback.dimensions.map(dimension => <div className="mi-dimension" key={dimension.name}><h4>{DIMENSIONS[dimension.name]}：{dimension.score ?? '未评价'}</h4><p>{dimension.reason}</p>{dimension.answer_quote && <blockquote>{dimension.answer_quote}</blockquote>}</div>)}</details>
          {group.feedback.reference_answer && <details><summary>查看参考答案</summary><p>{group.feedback.reference_answer}</p></details>}
          {group.feedback.limitations.map(text => <p className="meta-note" key={text}>{text}</p>)}
        </div>}
        <FeedbackSources provenance={group.feedback ?? group.submissions.at(-1)?.provenance} />
        {report.turns.filter(turn => turn.group_id === group.id).slice(-1).map(turn => <ReportProblem key={turn.id} api={api} sessionId={report.session_id} turnId={turn.id} canReportScore={group.status === 'completed' && group.submissions.some(item => item.turn_id === turn.id && item.status === 'completed' && item.disposition !== 'skipped')} />)}
      </article>)}</section>
    </div>
  </main>
}
