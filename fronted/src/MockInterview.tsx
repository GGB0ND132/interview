import { useCallback, useEffect, useRef, useState } from 'react'
import { LoaderCircle, Pause, Play } from 'lucide-react'
import { ApiError, createPracticeApi } from './api'
import type { Disposition, InterviewReport, Pack, PracticeApi, SessionView } from './api'
import { useQuestionAvailability } from './useQuestionAvailability'
import { useAnswerDraft } from './useAnswerDraft'
import { competencyLabel, COVERAGE, DISPOSITIONS, STAGES } from './interview-labels'
import { Modal } from './components'
import MockInterviewReport from './MockInterviewReport'
import './question-availability.css'
import './mock-interview.css'

const defaultApi = createPracticeApi()
const errorMessage = (error: unknown) => error instanceof ApiError ? error.message : '模拟面试服务暂时不可用，请重新同步会话'
const isEnded = (session: SessionView) => session.status === 'completed' || session.status === 'ended_early'
const SESSION_KEY = 'ia-mi-session'
function storedSession(): string | null { try { return localStorage.getItem(SESSION_KEY) } catch { return null } }
function remember(id: string | null) {
  try { if (id) localStorage.setItem(SESSION_KEY, id); else localStorage.removeItem(SESSION_KEY) }
  catch { /* The server retains the session even if browser storage is unavailable. */ }
}

export default function MockInterview({ api = defaultApi }: { api?: PracticeApi }) {
  const [packs, setPacks] = useState<Pack[]>([])
  const [packId, setPackId] = useState('')
  const [booting, setBooting] = useState(true)
  const [connectionAttempt, setConnectionAttempt] = useState(0)
  const [restoreFailed, setRestoreFailed] = useState(false)
  const [history, setHistory] = useState<SessionView[]>([])
  const [historyError, setHistoryError] = useState('')
  const [historyAttempt, setHistoryAttempt] = useState(0)
  const [experience, setExperience] = useState<'experience' | 'scenario'>('scenario')
  const [followups, setFollowups] = useState(2)
  const { availability, availabilityError, refreshAvailability } = useQuestionAvailability(api, packId, 'mock_interview', 'easy', '')
  const [session, setSession] = useState<SessionView | null>(null)
  const current = useRef<SessionView | null>(null)
  const { answer, setAnswer, restoreDraft, answerRequest, detachDraft } = useAnswerDraft()
  const [busy, setBusy] = useState(false)
  const lock = useRef(false)
  const [error, setError] = useState('')
  const [syncRequired, setSyncRequired] = useState(false)
  const [paused, setPaused] = useState(false)
  const [endOpen, setEndOpen] = useState(false)
  const [report, setReport] = useState<InterviewReport | null>(null)
  const [reportError, setReportError] = useState('')
  const [reportAttempt, setReportAttempt] = useState(0)
  const scrollArea = useRef<HTMLDivElement>(null)
  const following = useRef(true)
  const [unread, setUnread] = useState(false)

  const accept = useCallback((view: SessionView) => {
    const previous = current.current
    if (previous?.session_id === view.session_id && previous.revision > view.revision) return
    const oldTurn = previous?.current_turn?.id
    if (oldTurn !== view.current_turn?.id && !following.current) setUnread(true)
    current.current = view
    restoreDraft(view)
    remember(view.session_id)
    setSession(view)
    setSyncRequired(false)
  }, [restoreDraft])

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const result = await api.packs()
        if (cancelled) return
        const published = result.items.filter(pack => pack.status === 'published')
        setPacks(published)
        setPackId(published.find(pack => pack.id === 'pack_agent_basics_mianstack')?.id ?? published[0]?.id ?? '')
        const id = storedSession()
        if (id) {
          try {
            const restored = await api.session(id)
            if (cancelled) return
            if (restored.mode === 'mock_interview') accept(restored)
            else remember(null)
          } catch (failure) {
            if (cancelled) return
            if (failure instanceof ApiError && failure.status === 404) remember(null)
            else { setRestoreFailed(true); throw failure }
          }
        }
        setRestoreFailed(false)
        setError('')
      } catch (failure) { if (!cancelled) setError(errorMessage(failure)) }
      finally { if (!cancelled) setBooting(false) }
    }
    void load()
    return () => { cancelled = true }
  }, [api, connectionAttempt, accept])

  useEffect(() => {
    let cancelled = false
    void api.history(1, 20).then(result => {
      if (!cancelled) { setHistory(result.items.filter(item => item.mode === 'mock_interview')); setHistoryError('') }
    }).catch((failure: unknown) => { if (!cancelled) setHistoryError(errorMessage(failure)) })
    return () => { cancelled = true }
  }, [api, historyAttempt])

  // This timer only reads persisted state; progression always comes from the server.
  const sessionId = session?.session_id
  const phase = session?.phase
  useEffect(() => {
    if (!sessionId || phase !== 'evaluating' || syncRequired) return
    let cancelled = false
    let timer: number
    const id = sessionId
    async function poll() {
      try {
        const view = await api.session(id)
        if (cancelled) return
        accept(view)
        if (view.phase === 'evaluating') timer = window.setTimeout(() => void poll(), 800)
      } catch (failure) {
        if (!cancelled) { setError(errorMessage(failure)); setSyncRequired(true) }
      }
    }
    timer = window.setTimeout(() => void poll(), 800)
    return () => { cancelled = true; window.clearTimeout(timer) }
  }, [api, sessionId, phase, syncRequired, accept])

  const ended = session ? isEnded(session) : false
  useEffect(() => {
    if (!sessionId || !ended) return
    let cancelled = false
    void api.interviewReport(sessionId).then(result => {
      if (!cancelled) { setReport(result); setReportError('') }
    }).catch((failure: unknown) => { if (!cancelled) setReportError(errorMessage(failure)) })
    return () => { cancelled = true }
  }, [api, sessionId, ended, reportAttempt])

  function jumpToLatest() {
    following.current = true
    setUnread(false)
    const scroll = scrollArea.current
    scroll?.scrollTo({ top: scroll.scrollHeight, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' })
  }

  useEffect(() => {
    const scroll = scrollArea.current
    if (scroll && scroll.clientHeight > 0 && following.current) {
      scroll.scrollTo({ top: scroll.scrollHeight, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' })
    }
  }, [session?.revision])

  async function run(operation: () => Promise<void>) {
    if (lock.current) return
    lock.current = true
    setBusy(true)
    setError('')
    try { await operation() } catch (failure) {
      setError(errorMessage(failure))
      if (current.current) {
        try { accept(await api.session(current.current.session_id)) }
        catch { setSyncRequired(true) }
      } else refreshAvailability()
    } finally { lock.current = false; setBusy(false) }
  }

  async function start() {
    if (!availability?.can_start || session || restoreFailed) return
    await run(async () => {
      const draft = await api.create(packId, { mode: 'mock_interview', difficulty: 'easy', feedback_timing: 'after_session', experience_mode: experience, max_followups_per_question: followups })
      accept(draft)
      accept(await api.start(draft.session_id, draft.revision))
    })
  }

  async function send(disposition: Disposition) {
    const view = current.current
    if (!view?.current_turn || syncRequired || paused || !view.available_actions.includes(disposition === 'skipped' ? 'skip' : 'answer')) return
    const text = disposition === 'answered' ? answer.trim() : ''
    if (disposition === 'answered' && !text) return
    await run(async () => {
      const body = answerRequest(view, disposition, text)
      accept((await api.submit(view.session_id, body)).session)
    })
  }

  async function advance(action: 'start' | 'next' | 'finish' | 'retry') {
    const view = current.current
    if (!view || syncRequired || !view.available_actions.includes(action) || (paused && action !== 'finish')) return
    await run(async () => {
      if (action === 'retry') {
        await api.retry(view.session_id, view.revision)
        accept(await api.session(view.session_id))
      } else accept(await api[action](view.session_id, view.revision))
      setEndOpen(false)
    })
  }

  function leave() {
    remember(null)
    current.current = null
    setSession(null)
    setReport(null)
    setReportError('')
    detachDraft()
    setError('')
    setPaused(false)
    following.current = true
    setUnread(false)
    setSyncRequired(false)
    setHistoryAttempt(value => value + 1)
    refreshAvailability()
  }

  if (!session) return <main className="page-content qp-setup">
    <div className="page-header"><h1>模拟面试</h1><p>从开场到候选人反问，完成一次 Agent 基础档交流。</p></div>
    {booting ? <p role="status">正在连接面试服务</p> : <form className="setup-form" aria-busy={busy} onSubmit={event => { event.preventDefault(); void start() }}>
      <div className="form-field"><label htmlFor="mi-pack">岗位包</label><select id="mi-pack" className="field" value={packId} onChange={event => setPackId(event.target.value)}>{packs.map(pack => <option key={pack.id} value={pack.id}>{pack.title}</option>)}</select><p className="field-help">Agent 基础档；无需上传资料即可开始。</p></div>
      <div className="form-field"><label htmlFor="mi-experience">经历环节</label><select id="mi-experience" className="field" value={experience} onChange={event => setExperience(event.target.value as typeof experience)}><option value="scenario">没有项目经历，回答假设情境</option><option value="experience">分享我的项目经历</option></select></div>
      <div className="form-field"><label htmlFor="mi-followups">每组追问上限</label><select id="mi-followups" className="field" value={followups} onChange={event => setFollowups(Number(event.target.value))}>{[0, 1, 2].map(value => <option key={value} value={value}>{value} 次</option>)}</select></div>
      <section className="qp-coverage" aria-label="面试可用性"><div className="field-heading"><h2>环节与能力覆盖</h2><button type="button" className="text-link" onClick={refreshAvailability}>刷新可用性</button></div>
        <p className="field-help">基础难度；开场、经历或情境、技术、行为与反问。技术交流随机选择 3～4 个题量充足的主题。</p>
        <p role="status">{availability ? `${availability.available_count} 道适合面试的技术题，${availability.eligible_topic_count ?? 0} 个可用主题` : availabilityError || '正在查询题库'}</p>
        <ul className="qp-stage-list">{availability?.stages?.map(stage => <li key={stage.id}><span>{stage.label}</span><span>{stage.ready ? '可覆盖' : '缺少合格题目'}</span></li>)}</ul>
        {availability && !availability.can_start && <p className="field-error">必需环节或技术主题不足，请发布合格题目后刷新。</p>}
      </section>
      <p className="meta-note">面试过程中展示交流进度，详细评分和参考答案在结束后公开。</p>
      <button className="button primary setup-submit" aria-busy={busy} disabled={!availability?.can_start || busy || restoreFailed}>{busy ? '正在开始' : '开始模拟面试'}<Play size={16} aria-hidden="true" /></button>
    </form>}
    {error && <div className="qp-error" role="alert"><p>{error}</p>{(!packs.length || restoreFailed) && <button className="button secondary" onClick={() => { setBooting(true); setConnectionAttempt(value => value + 1) }}>重新连接</button>}</div>}
    <section className="qp-history"><div className="field-heading"><h2>最近模拟面试</h2><button className="text-link" disabled={busy} onClick={() => setHistoryAttempt(value => value + 1)}>刷新最近会话</button></div><p className="meta-note">显示服务端最近 20 条会话中的模拟面试，可继续交流或回看报告。</p>{historyError && <p role="alert" className="field-error">{historyError}</p>}{history.map(item => <button className="history-row qp-history-row" key={item.session_id} disabled={busy} onClick={() => void run(async () => { setReport(null); setReportError(''); setPaused(false); accept(await api.session(item.session_id)) })}><div><strong>{item.pack_title ?? 'Agent 基础档'}</strong><div className="history-sub"><span>{new Date(item.created_at).toLocaleString('zh-CN')}</span><span>{item.status === 'completed' ? '完整报告' : item.status === 'ended_early' ? '部分报告' : item.status === 'draft' ? '待开始' : '进行中'}</span></div></div><span>{isEnded(item) ? '查看报告' : '继续面试'}</span></button>)}</section>
  </main>

  if (ended) return report ? <MockInterviewReport report={report} questions={session.plan?.questions ?? []} onBack={leave} /> : <main className="page-content"><h1>面试已结束</h1>{reportError ? <div className="qp-error" role="alert"><p>{reportError}</p><button className="button primary" onClick={() => { setReportError(''); setReportAttempt(value => value + 1) }}>重新读取报告</button></div> : <p role="status">正在读取服务端报告</p>}</main>

  const turn = session.current_turn
  const processing = session.phase === 'evaluating'
  const blocked = busy || syncRequired || processing || paused
  const canPause = !blocked && ['awaiting_answer', 'stage_transition', 'evaluation_failed'].includes(session.phase)
  return <main className="practice-active mi-active">
    <div className="practice-context"><strong>{session.pack_title ?? 'Agent 基础档'}</strong><div><button className="button ghost" disabled={busy || syncRequired || processing || !session.available_actions.includes('finish')} onClick={() => setEndOpen(true)}>结束面试</button></div></div>
    <div className="practice-scroll" ref={scrollArea} onScroll={event => { const scroll = event.currentTarget; following.current = scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight < 64; if (following.current) setUnread(false) }}><div className="reading-column">
      <h1 className="visually-hidden">模拟面试进行中</h1>
      <p className="visually-hidden" role="status" aria-live="polite" aria-atomic="true">{turn ? STAGES[turn.stage] : '准备开始'}，{processing ? '正在处理回答' : session.phase === 'stage_transition' ? '本组已记录，可以继续下一组' : session.phase === 'evaluation_failed' ? '评价未完成，可以重试' : paused ? '面试已暂停' : '等待你的操作'}</p>
      <div className="progress-meta"><span>{turn ? STAGES[turn.stage] : '准备开始'}</span><span>基础</span></div>
      <details className="mi-coverage"><summary>本场环节与能力覆盖</summary><p className="meta-note">已了解表示已有材料可评价，不等于掌握。</p><ul className="qp-stage-list">{session.coverage?.map(item => <li key={item.competency_id}><span>{competencyLabel(item.competency_id, session.plan?.questions ?? [])}</span><span>{COVERAGE[item.status]}</span></li>)}</ul></details>
      {(session.turns ?? []).map(item => <article className="question-block" key={item.id}>
        <h2>{item.kind === 'followup' ? '面试官追问' : STAGES[item.stage]}</h2><p>{item.text}</p>
        {session.submissions.filter(submitted => submitted.turn_id === item.id).map(submitted => <div className="turn" key={submitted.id}><span className="meta-label">你的回答</span><p className="submitted-answer">{submitted.answer_text || DISPOSITIONS[submitted.disposition]}</p></div>)}
      </article>)}
      {processing && <p className="processing" role="status"><LoaderCircle className="spin" size={16} aria-hidden="true" />回答已保存，正在整理本组交流。处理完成后可继续、暂停或结束。</p>}
      {session.phase === 'evaluation_failed' && <section className="skipped-block"><h2>本组评价未完成</h2><p>{session.submissions.at(-1)?.error?.message ?? '你的回答已保存，可以重试或结束面试。'}</p><button className="button primary" aria-busy={busy} disabled={blocked || !session.available_actions.includes('retry')} onClick={() => void advance('retry')}>重试评价</button></section>}
      {session.phase === 'stage_transition' && <div className="mi-transition"><p>本组交流已记录，继续了解下一项能力。</p><button className="button primary" aria-busy={busy} disabled={blocked || !session.available_actions.includes('next')} onClick={() => void advance('next')}>继续下一组</button></div>}
      {session.phase === 'draft' && <button className="button primary" aria-busy={busy} disabled={blocked || !session.available_actions.includes('start')} onClick={() => void advance('start')}>继续开始面试</button>}
      {error && <div className="qp-error" role="alert"><p>{error}</p><button className="button secondary" disabled={busy} onClick={() => void run(async () => accept(await api.session(session.session_id)))}>重新同步会话</button></div>}
    </div></div>
    <div className="composer-area"><div className="composer-inner">
      {unread && <button className="text-link mi-jump" onClick={jumpToLatest}>有新的交流，跳转到最新位置</button>}
      {busy && <p className="meta-note" role="status">正在同步本次操作，请稍候。</p>}
      {paused && <p role="status">面试已暂停，当前回答会保留。</p>}
      {session.available_actions.includes('answer') && <>
      <label htmlFor="mi-answer" className="composer-label">你的回答</label><textarea id="mi-answer" className="field answer-field" value={answer} maxLength={5000} disabled={blocked} onChange={event => setAnswer(event.target.value)} onKeyDown={event => { if ((event.ctrlKey || event.metaKey) && event.key === 'Enter' && !event.nativeEvent.isComposing) { event.preventDefault(); if (!blocked) void send('answered') } }} />
      <div className="composer-toolbar"><span className="keyboard-hint">Ctrl + Enter 提交</span><div><span className="word-count">{answer.length} 字</span><button className="button primary" aria-busy={busy} disabled={blocked || !answer.trim()} onClick={() => void send('answered')}>提交回答</button></div></div>
      <div className="practice-actions mi-answer-actions"><button className="button ghost" aria-busy={busy} disabled={blocked} onClick={() => void send('blank_answer')}>空白提交</button><button className="button ghost" aria-busy={busy} disabled={blocked || !session.available_actions.includes('skip')} onClick={() => void send('skipped')}>跳过本轮</button>{turn?.stage === 'experience' && <button className="button ghost" aria-busy={busy} disabled={blocked} onClick={() => void send('no_experience')}>没有项目经历</button>}{turn?.stage === 'candidate_questions' && <button className="button ghost" aria-busy={busy} disabled={blocked} onClick={() => void send('no_questions')}>没有问题</button>}</div>
      <p className="meta-note">空白记 0 分；跳过不计分。评分与参考答案在结束后公开。</p>
      </>}
      <div className="practice-actions">{paused ? <button className="button secondary" onClick={() => setPaused(false)}><Play size={16} aria-hidden="true" />继续面试</button> : <button className="button ghost" disabled={!canPause} onClick={() => setPaused(true)}><Pause size={16} aria-hidden="true" />暂停面试</button>}</div>
    </div></div>
    <Modal open={endOpen} onOpenChange={setEndOpen} title="结束本次面试"><p className="body-copy">已提交的回答会保留；未提交的草稿不计入报告。提前结束会生成部分报告，列出未覆盖环节和信息缺口。</p><div className="dialog-actions"><button className="button secondary" onClick={() => setEndOpen(false)}>继续回答</button><button className="button primary" aria-busy={busy} disabled={busy || syncRequired || !session.available_actions.includes('finish')} onClick={() => void advance('finish')}>结束并生成报告</button></div></Modal>
  </main>
}
