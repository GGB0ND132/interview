import { useEffect, useRef, useState } from 'react'
import { ArrowRight, BookOpenText, ExternalLink, FileText, LoaderCircle, Play, SkipForward } from 'lucide-react'
import { ApiError, createPracticeApi } from './api'
import type {
  Availability,
  Dimension,
  Difficulty,
  Feedback,
  Pack,
  PracticeApi,
  SessionView,
  Submission,
} from './api'

const STORAGE_KEY = 'ia-qp-session'
const DIFFICULTIES: { value: Difficulty; label: string }[] = [
  { value: 'easy', label: '基础' },
  { value: 'medium', label: '进阶' },
  { value: 'hard', label: '挑战' },
]
const DIMENSION_LABELS: Record<Dimension['name'], string> = {
  accuracy: '准确性',
  completeness: '完整性',
  relevance: '相关性',
  structure: '表达结构',
  specificity: '具体性',
}

function readStored(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

function storeSession(sessionId: string | null) {
  try {
    if (sessionId) localStorage.setItem(STORAGE_KEY, sessionId)
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    // Storage can be unavailable; the server remains the source of truth.
  }
}

function sleep(ms: number) {
  return new Promise(resolve => window.setTimeout(resolve, ms))
}

function message(error: unknown) {
  return error instanceof ApiError ? error.message : '练习服务暂时不可用'
}

export default function QuestionPractice({ api = createPracticeApi() }: { api?: PracticeApi }) {
  const [booting, setBooting] = useState(true)
  const [packs, setPacks] = useState<Pack[]>([])
  const [packId, setPackId] = useState('')
  const [difficulty, setDifficulty] = useState<Difficulty>('easy')
  const [availability, setAvailability] = useState<Availability | null>(null)
  const [session, setSession] = useState<SessionView | null>(null)
  const [answer, setAnswer] = useState('')
  const [busy, setBusy] = useState(false)
  const [watching, setWatching] = useState(false)
  const [error, setError] = useState('')
  const [history, setHistory] = useState<SessionView[]>([])
  const submitKey = useRef<string | null>(null)
  const submitLock = useRef<TurnKey | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' })
  }, [session?.phase, session?.revision])

  async function load() {
    setBooting(true)
    setError('')
    try {
      const [list, recent] = await Promise.all([api.packs(), api.history(1, 10)])
      const published = list.items.filter(item => item.status === 'published')
      const first = published[0]
      setPacks(published)
      setHistory(recent.items)
      const stored = readStored()
      let restored: SessionView | null = null
      if (stored) {
        try {
          restored = await api.session(stored)
        } catch {
          storeSession(null)
        }
      }
      const activePack = restored?.pack_id ?? first?.id
      const activeDifficulty = restored?.difficulty ?? difficulty
      if (restored) {
        setPackId(restored.pack_id)
        setDifficulty(restored.difficulty)
        setSession(restored)
        if (restored.phase === 'evaluating') void watchJob(restored, restored.submissions[0]?.job_id ?? null)
      } else if (first) {
        setPackId(first.id)
      }
      if (activePack) {
        setAvailability(await api.availability(activePack, { mode: 'question_practice', difficulty: activeDifficulty }))
      }
    } catch (failure) {
      setError(message(failure))
    } finally {
      setBooting(false)
    }
  }

  async function chooseDifficulty(next: Difficulty) {
    setDifficulty(next)
    if (!packId) return
    setAvailability(null)
    try {
      setAvailability(await api.availability(packId, { mode: 'question_practice', difficulty: next }))
    } catch (failure) {
      setError(message(failure))
    }
  }

  async function draw() {
    if (!packId || busy) return
    setBusy(true)
    setError('')
    try {
      const draft = await api.create(packId, { mode: 'question_practice', difficulty })
      const started = await api.start(draft.session_id, draft.revision)
      storeSession(started.session_id)
      submitKey.current = null
      setAnswer('')
      setSession(started)
    } catch (failure) {
      setError(message(failure))
    } finally {
      setBusy(false)
    }
  }

  async function send(disposition: Submission['disposition'], text = '') {
    if (!session?.current_turn || busy || watching) return
    if (submitLock.current?.turn === session.current_turn.id && submitLock.current.disposition === disposition && submitLock.current.text === text) return
    submitLock.current = { turn: session.current_turn.id, disposition, text }
    setBusy(true)
    setError('')
    submitKey.current ??= `submission-${crypto.randomUUID()}`
    try {
      const result = await api.submit(session.session_id, {
        turn_id: session.current_turn.id,
        expected_revision: session.revision,
        client_submission_id: submitKey.current,
        disposition,
        answer_text: disposition === 'answered' ? text : '',
      })
      setSession(result.session)
      setAnswer('')
      if (result.session.phase === 'evaluating') void watchJob(result.session, result.submission.job_id)
      else {
        submitLock.current = null
        submitKey.current = null
      }
    } catch (failure) {
      submitLock.current = null
      setError(message(failure))
      // The request may have been stored before the connection dropped; the
      // server is the source of truth, so reconcile instead of leaving a stale view.
      try {
        const stored = await api.session(session.session_id)
        if (stored.phase !== 'awaiting_answer') {
          setError('')
          setAnswer('')
          setSession(stored)
          if (stored.phase === 'evaluating') void watchJob(stored, stored.submissions[0]?.job_id ?? null)
        }
      } catch {
        // Keep the local error; the user can retry or reopen the session later.
      }
    } finally {
      setBusy(false)
    }
  }

  async function watchJob(current: SessionView, jobId: string | null) {
    setWatching(true)
    try {
      if (jobId) {
        for (;;) {
          const job = await api.job(jobId)
          if (job.status === 'succeeded' || job.status === 'failed') break
          await sleep(700)
        }
      }
      const updated = await api.session(current.session_id)
      setSession(updated)
      if (updated.phase !== 'evaluating') {
        submitLock.current = null
        submitKey.current = null
        void refreshHistory()
      }
    } catch (failure) {
      setError(message(failure))
    } finally {
      setWatching(false)
    }
  }

  async function restart() {
    if (!session || busy || watching) return
    setBusy(true)
    setError('')
    try {
      await api.retry(session.session_id, session.revision)
      await watchJob(session, session.submissions[0]?.job_id ?? null)
    } catch (failure) {
      setError(message(failure))
    } finally {
      setBusy(false)
    }
  }

  async function refreshHistory() {
    try {
      const recent = await api.history(1, 10)
      setHistory(recent.items)
    } catch {
      // History is a convenience; the current session stays usable.
    }
  }

  function leave() {
    storeSession(null)
    submitKey.current = null
    submitLock.current = null
    setSession(null)
    setAnswer('')
    setError('')
    void refreshHistory()
  }

  async function reopen(id: string) {
    setBusy(true)
    setError('')
    try {
      const restored = await api.session(id)
      storeSession(restored.session_id)
      setPackId(restored.pack_id)
      setDifficulty(restored.difficulty)
      setSession(restored)
      if (restored.phase === 'evaluating') void watchJob(restored, restored.submissions[0]?.job_id ?? null)
    } catch (failure) {
      setError(message(failure))
    } finally {
      setBusy(false)
    }
  }

  if (session) return <PracticeRun session={session} answer={answer} setAnswer={setAnswer} busy={busy} watching={watching} error={error} onSend={send} onRetry={restart} onLeave={leave} bottomRef={bottomRef} />

  return <main className="page-content qp-setup">
    <div className="page-header"><h1>试题练习</h1><p>从已发布的 Agent 原理与系统基础档随机抽一道题，提交后立即看到按本题答案与评分点生成的反馈。</p></div>
    {booting ? <div className="processing" role="status"><LoaderCircle size={16} className="spin" />正在读取练习服务</div> : error && !packs.length ? <div className="qp-error" role="alert"><p>{error}</p><button className="button secondary" onClick={() => void load()}>重新连接</button></div> : <form className="setup-form" onSubmit={event => { event.preventDefault(); void draw() }}>
      <div className="form-field"><label htmlFor="qp-pack">岗位包</label><select id="qp-pack" className="field" value={packId} onChange={e => setPackId(e.target.value)}>{packs.map(pack => <option key={pack.id} value={pack.id}>{pack.title}</option>)}</select><p className="field-help">首批开放 Agent 原理与系统基础档，题目与答案带来源版本。</p></div>
      <fieldset className="choice-field"><legend>难度</legend><div className="choice-row">{DIFFICULTIES.map(level => <label className={`choice ${difficulty === level.value ? 'selected' : ''}`} key={level.value}><input type="radio" name="qp-difficulty" checked={difficulty === level.value} onChange={() => void chooseDifficulty(level.value)} /><span>{level.label}</span></label>)}</div></fieldset>
      <p className="qp-availability" role="status">{availability === null ? '正在查询可用题目' : availability.can_start ? <><b>{availability.available_count}</b> 道可抽</> : '当前筛选没有可评分的已发布题目'}</p>
      {availability && !availability.can_start && <p className="field-error" role="alert">没有满足条件的题：发布校验未通过的题不会进入抽题池。可以更换难度或稍后重试。</p>}
      {error && <p className="field-error" role="alert">{error}</p>}
      <button className="button primary setup-submit" type="submit" disabled={!availability?.can_start || busy}><Play size={17} />{busy ? '正在抽题' : '随机抽一题'}</button>
    </form>}
    {history.length > 0 && <section className="qp-history"><h2>最近练习</h2><div className="history-list">{history.map(item => <button className="history-row qp-history-row" key={item.session_id} onClick={() => void reopen(item.session_id)}><div><strong>{item.current_turn?.topic ?? '抽题中'}</strong><div className="history-sub"><span>{item.pack_title ?? item.pack_id}</span><span>{new Intl.DateTimeFormat('zh-CN', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(item.created_at))}</span><span>{PHASES[item.phase]}</span></div></div><span className="history-score">{item.submissions[0]?.score ?? '—'}</span></button>)}</div></section>}
    <p className="page-footnote">所有题目、评分和历史来自本机练习服务；模拟面试与资料管理页面仍是浏览器内演示数据。</p>
  </main>
}

const PHASES: Record<SessionView['phase'], string> = {
  draft: '未开始',
  awaiting_answer: '待回答',
  evaluating: '评价中',
  feedback_ready: '已反馈',
  evaluation_failed: '评价失败',
}

type TurnKey = { turn: string; disposition: Submission['disposition']; text: string }

function PracticeRun({ session, answer, setAnswer, busy, watching, error, onSend, onRetry, onLeave, bottomRef }: {
  session: SessionView
  answer: string
  setAnswer: (value: string) => void
  busy: boolean
  watching: boolean
  error: string
  onSend: (disposition: Submission['disposition'], text?: string) => void
  onRetry: () => void
  onLeave: () => void
  bottomRef: React.RefObject<HTMLDivElement | null>
}) {
  const turn = session.current_turn
  const submission = session.submissions[0]
  const processing = session.phase === 'evaluating' || watching
  const awaiting = session.phase === 'awaiting_answer'
  return <main className="practice-active">
    <div className="practice-context"><strong>{session.pack_title ?? session.pack_id}</strong><div><button className="button ghost" onClick={onLeave}>返回练习入口</button></div></div>
    <div className="practice-scroll"><div className="reading-column">
      <div className="progress-meta"><span>试题练习 <b>单题</b></span><span>{DIFFICULTIES.find(item => item.value === session.difficulty)?.label}</span></div>
      {turn && <article className="question-block"><h1>{turn.topic}</h1><p>{turn.text}</p><span className="meta-note mono">题目 {turn.question_code} · 版本 {turn.question_version}</span></article>}
      {submission?.answer_text && <div className="turn"><span className="meta-label">你的回答</span><p className="submitted-answer">{submission.answer_text}</p></div>}
      {session.phase === 'evaluating' && <div className="processing" role="status"><LoaderCircle size={16} className="spin" />回答已保存，正在生成反馈</div>}
      {session.phase === 'evaluation_failed' && <section className="skipped-block"><h2>评价未完成</h2><p>{submission?.error?.message ?? '模型评价暂时失败，你的回答已经保存。'}</p><button className="button primary" disabled={busy || watching} onClick={onRetry}>{watching ? '正在重试' : '重试评价'}</button></section>}
      {session.phase === 'feedback_ready' && submission && <QuestionFeedback submission={submission} />}
      {awaiting && !processing && <p className="meta-note qp-submit-note">提交后立即返回本题反馈；空白提交记 0 分并计入均分，明确跳过不计分。</p>}
      {error && <p className="field-error" role="alert">{error}</p>}
      <div ref={bottomRef} />
    </div></div>
    {awaiting && <div className="composer-area"><div className="composer-inner">
      <label htmlFor="qp-answer" className="composer-label">你的回答</label>
      <textarea id="qp-answer" className="field answer-field" placeholder="输入你的回答……" value={answer} maxLength={5000} onChange={e => setAnswer(e.target.value)} onKeyDown={e => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !e.nativeEvent.isComposing) { e.preventDefault(); if (answer.trim()) onSend('answered', answer.trim()) } }} />
      <div className="composer-toolbar"><span className="keyboard-hint"><kbd>Ctrl</kbd> + <kbd>Enter</kbd> 提交</span><div><span className={`word-count ${answer.length >= 4500 ? 'near-limit' : ''}`}>{answer.length} 字</span><button className="button primary" disabled={!answer.trim() || busy} onClick={() => onSend('answered', answer.trim())}>提交回答</button></div></div>
      <div className="practice-actions"><button className="button ghost" disabled={busy} onClick={() => onSend('blank_answer')}>空白提交</button><button className="button ghost" disabled={busy} onClick={() => onSend('skipped')}><SkipForward size={16} />跳过本题</button>{!answer.trim() && <span className="meta-note">不输入内容直接提交，会按空白提交记 0 分。</span>}</div>
    </div></div>}
  </main>
}

function QuestionFeedback({ submission }: { submission: Submission }) {
  const feedback: Feedback | undefined = submission.feedback
  if (submission.disposition === 'skipped') return <section className="feedback"><div className="feedback-heading"><h2>已跳过</h2><strong className="feedback-score">未评分</strong></div><p className="body-copy">跳过不计分，也不进入均分。可以返回练习入口再抽一题。</p></section>
  if (submission.disposition === 'blank_answer') return <section className="feedback"><div className="feedback-heading"><h2>本题反馈</h2><strong className="feedback-score">0</strong></div><p className="body-copy">空白提交记为 0 分，计入均分；本次未调用模型评价，也不把空白解释为技术错误。</p><p className="meta-note">空白提交单独统计，不会覆盖你实际作答的记录。</p></section>
  if (!feedback) return <section className="feedback"><p className="meta-note">评价已完成但缺少反馈内容，请刷新后查看或重试。</p></section>
  return <section className="feedback">
    <div className="feedback-heading"><h2>本题反馈</h2><strong className="feedback-score">{feedback.overall_score ?? '未评价'}</strong></div>
    <p className="body-copy">{feedback.assessment_status === 'complete' ? '五个维度均按本题参考答案与评分点评价，综合分数由服务端加权计算。' : '部分维度未评估，综合分数仅按已评估维度归一化。'}</p>
    {feedback.limitations.length > 0 && <p className="meta-note">{feedback.limitations.join('；')}</p>}
    <h3>维度评价</h3>
    <div className="dimension-list">{feedback.dimensions.map(item => <div className="dimension-row" key={item.name}><span>{DIMENSION_LABELS[item.name]}</span><span className="dimension-rule" /><strong>{item.score ?? '未评价'}</strong></div>)}</div>
    <p className="meta-note">计分权重：准确性 35%，完整性 25%，相关性 15%，表达结构 15%，具体性 10%；不可评价维度排除后归一化。</p>
    <h3>值得保留</h3>{feedback.strengths.map(item => <p className="body-copy" key={item}>{item}</p>)}
    <h3>需要补充</h3>{feedback.improvements.map(item => <p className="body-copy" key={item}>{item}</p>)}
    <details className="answer-details"><summary>参考答案 <ArrowRight size={16} /></summary>{feedback.reference_answer ? <p className="body-copy">{feedback.reference_answer}</p> : <p className="meta-note">本题未保存可展示的参考答案。</p>}</details>
    <h3>来源</h3>
    <p className="meta-note"><FileText size={14} aria-hidden="true" /> 题库答案版本 {String(feedback.answer_version ?? '—')}，来源 {String((feedback.question_source as { source_id?: string } | undefined)?.source_id ?? '—')}，评分表 {feedback.rubric_version}。</p>
    {feedback.independent_references && feedback.independent_references.length > 0 && <ul className="qp-references">{feedback.independent_references.map(item => <li key={item.url}><a className="text-link" href={item.url} target="_blank" rel="noreferrer"><BookOpenText size={16} />{item.title}<ExternalLink size={14} /></a><span className="meta-note">{item.publisher}{item.heading ? ` · ${item.heading}` : ''}</span></li>)}</ul>}
  </section>
}
