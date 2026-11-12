import { useId, useRef, useState } from 'react'
import { ExternalLink, Flag } from 'lucide-react'
import { ApiError } from './api'
import type { AnswerProvenance, PracticeApi, UserReport } from './api'
import './feedback-sources.css'

function webUrl(value?: string): string | undefined {
  if (!value) return undefined
  try {
    const url = new URL(value)
    return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password ? url.href : undefined
  } catch {
    return undefined
  }
}

export function FeedbackSources({ provenance }: { provenance?: AnswerProvenance }) {
  const source = provenance?.question_source
  const originalUrl = webUrl(source?.url)
  const references = (provenance?.independent_references ?? []).filter(reference =>
    reference.id && reference.excerpt?.trim() && reference.claim?.trim() && reference.checked_at && reference.document_sha256 && webUrl(reference.url),
  )
  return <section className="feedback-sources" aria-label="答案来源与资料依据">
    <h3>答案来源与资料依据</h3>
    <p className="meta-note">{provenance?.answer_version ? `题库答案版本 ${provenance.answer_version}` : '本次记录未保存答案版本'}</p>
    <h4>原题位置</h4>
    {source ? <div className="source-location">
      {(source.source_id || source.original_id) && <p>{source.source_id || source.original_id}</p>}
      {(source.locator || source.path) && <p>{source.locator || source.path}</p>}
      {(source.revision || source.commit) && <p>原题修订 {source.revision || source.commit}</p>}
      {source.attribution && <p>{source.attribution}{source.license ? ` (${source.license})` : ''}</p>}
      {originalUrl && <a className="text-link" href={originalUrl} target="_blank" rel="noreferrer">打开原题来源<ExternalLink size={14} aria-hidden="true" /></a>}
      <p className="meta-note">原题位置用于追溯题目，不作为独立技术资料依据。</p>
    </div> : <p className="meta-note">本次记录未保存原题位置。</p>}
    <h4>独立技术资料</h4>
    {references.length ? references.map(reference => <details className="saved-reference" key={reference.id}>
      <summary>查看支持片段：{reference.title}</summary>
      <p className="meta-note">支持的结论</p><p>{reference.claim}</p>
      <p className="meta-note">本次保存的资料片段</p><blockquote>{reference.excerpt}</blockquote>
      <a className="text-link" href={webUrl(reference.url)} target="_blank" rel="noreferrer">打开资料原文<ExternalLink size={14} aria-hidden="true" /></a>
      <p className="source-url">{reference.url}</p>
      <p className="meta-note">核对时间：{reference.checked_at}</p>
    </details>) : <p className="meta-note">本次没有实际使用的已核验独立资料引用。分数依据已发布题库答案与评分点。</p>}
  </section>
}

export function ReportProblem({ api, sessionId, turnId, canReportScore }: {
  api: PracticeApi; sessionId: string; turnId: string; canReportScore: boolean
}) {
  const fieldId = useId()
  const [category, setCategory] = useState<UserReport['category']>('question')
  const [explanation, setExplanation] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [invalid, setInvalid] = useState(false)
  const [receipt, setReceipt] = useState<UserReport | null>(null)
  const lock = useRef(false)
  const input = useRef<HTMLTextAreaElement>(null)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (lock.current || receipt) return
    if (!explanation.trim()) {
      setInvalid(true)
      input.current?.focus()
      return
    }
    lock.current = true
    setPending(true)
    setError('')
    try {
      setReceipt(await api.reportProblem(sessionId, { turn_id: turnId, category, explanation: explanation.trim() }))
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : '提交未能确认，请保留说明并重试。')
    } finally {
      lock.current = false
      setPending(false)
    }
  }

  return <details className="report-problem">
    <summary><Flag size={15} aria-hidden="true" />报告题目或评分问题</summary>
    {receipt ? <div className="report-receipt" role="status"><p>已收到你的反馈，等待复核。</p><p className="meta-note">题目 {receipt.question_code}，答案版本 {receipt.answer_version}</p><p className="meta-note">反馈编号：{receipt.id}</p></div> : <form onSubmit={submit} className="problem-form">
      <p className="meta-note">反馈会关联本题和当时的答案版本，提交后由维护者复核。</p>
      <div className="form-field"><label htmlFor={`${fieldId}-category`}>问题类型</label>
        <select className="field" id={`${fieldId}-category`} value={category} disabled={pending} onChange={event => setCategory(event.target.value as UserReport['category'])}><option value="question">题目或参考答案有疑问</option>{canReportScore && <option value="score">评分有疑问</option>}</select>
      </div>
      <div className="form-field"><label htmlFor={`${fieldId}-explanation`}>问题说明</label>
        <textarea ref={input} id={`${fieldId}-explanation`} className="field textarea-field short" value={explanation} maxLength={5000} required disabled={pending} aria-invalid={invalid || undefined} aria-describedby={`${fieldId}-help${invalid ? ` ${fieldId}-error` : ''}`} onBlur={() => setInvalid(!explanation.trim())} onChange={event => { setExplanation(event.target.value); if (event.target.value.trim()) setInvalid(false) }} />
        <p id={`${fieldId}-help`} className="field-help">请说明具体疑问及理由，最多 5000 字。</p>
        {invalid && <p id={`${fieldId}-error`} className="field-error">请填写具体问题，不能只有空格。</p>}
      </div>
      {error && <p className="field-error" role="alert">{error}</p>}
      <button className="button secondary" type="submit" disabled={pending}>{pending ? '正在提交反馈…' : '提交问题反馈'}</button>
    </form>}
  </details>
}
