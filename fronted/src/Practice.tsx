import { useEffect, useRef, useState } from 'react'
import { ArrowRight, BookOpenText, ChevronDown, FileText, LoaderCircle, Pause, Play, SkipForward } from 'lucide-react'
import { Drawer, Feedback, Modal } from './components'
import { questions } from './data'
import type { PracticeConfig, Session } from './data'

type Turn = { question: string; answer: string }
export default function Practice({ config, active, onStart, onFinish, notify }: { config: PracticeConfig; active: boolean; onStart: (config: PracticeConfig) => void; onFinish: (session: Session) => void; notify: (message: string) => void }) {
  const [draft, setDraft] = useState(config)
  const [types, setTypes] = useState(['技术', '项目'])
  const [moreOpen, setMoreOpen] = useState(false)
  const [index, setIndex] = useState(0)
  const [followup, setFollowup] = useState(0)
  const [answer, setAnswer] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const [allTurns, setAllTurns] = useState<Turn[]>([])
  const [phase, setPhase] = useState<'answer' | 'processing' | 'feedback' | 'complete'>('answer')
  const [paused, setPaused] = useState(false)
  const [skipped, setSkipped] = useState(0)
  const [groupSkipped, setGroupSkipped] = useState(false)
  const [sourceOpen, setSourceOpen] = useState(false)
  const [endOpen, setEndOpen] = useState(false)
  const [configOpen, setConfigOpen] = useState(false)
  const [sessionId] = useState(() => `session-${Date.now()}`)
  const scrollRef = useRef<HTMLDivElement>(null)
  const timerRef = useRef<number | undefined>(undefined)
  useEffect(() => () => window.clearTimeout(timerRef.current), [])
  useEffect(() => { if (active) scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' }) }, [active, phase, followup, turns.length])
  const q = questions[index % questions.length]
  const prompt = followup === 0 ? q.text : followup === 1 ? q.followup : '请进一步说明这个方案的适用边界，以及你会怎样验证它在实际业务中有效。'
  const complete = phase === 'complete'
  function submit() {
    if (!answer.trim() || phase !== 'answer' || paused) return
    const turn = { question: prompt, answer: answer.trim() }
    setTurns(items => [...items, turn]); setAllTurns(items => [...items, turn]); setAnswer(''); setPhase('processing')
    timerRef.current = window.setTimeout(() => { if (followup < config.followups) { setFollowup(n => n + 1); setPhase('answer') } else setPhase('feedback') }, 700)
  }
  function next() { if (index + 1 >= config.count) { setPhase('complete'); return } setIndex(n => n + 1); setFollowup(0); setTurns([]); setGroupSkipped(false); setPhase('answer') }
  function finish(early: boolean) { onFinish({ id: sessionId, title: `${config.role} · ${config.focus}`, role: config.role, date: new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Shanghai', dateStyle: 'short', timeStyle: 'short' }).format(new Date()), score: null, count: Math.min(index + 1, config.count), status: early ? '提前结束' : '已完成', topic: q.topic, answers: allTurns }) }
  if (!active) return <main className="page-content practice-setup"><div className="page-header"><h1>面试练习</h1><p>选择岗位和资料，开始一次有依据的练习。</p></div><form className="setup-form" onSubmit={event => { event.preventDefault(); if (types.length) onStart(draft) }}>
    <div className="form-field"><div className="field-heading"><label htmlFor="practice-role">目标岗位</label><button type="button" className="text-link" onClick={() => notify('岗位要求可在资料管理中查看和编辑')}>查看岗位要求</button></div><select id="practice-role" className="field" value={draft.role} onChange={e => setDraft({ ...draft, role: e.target.value })}><option>后端开发工程师</option><option>全栈开发工程师</option></select></div>
    <div className="form-field"><label htmlFor="practice-kb">知识库</label><select id="practice-kb" className="field" value={draft.kb} onChange={e => setDraft({ ...draft, kb: e.target.value })}><option>后端面试知识库</option></select><p className="field-help">3 份已就绪资料可用于本次练习</p></div>
    <fieldset className="choice-field"><legend>面试类型</legend><div className="choice-row">{['技术', '项目', '行为'].map(type => <label className={`choice ${types.includes(type) ? 'selected' : ''}`} key={type}><input type="checkbox" checked={types.includes(type)} onChange={() => setTypes(items => items.includes(type) ? items.filter(item => item !== type) : [...items, type])} /><span>{types.includes(type) ? '✓ ' : ''}{type}</span></label>)}</div>{types.length === 0 && <p className="field-error">请至少选择一种面试类型。</p>}</fieldset>
    <fieldset className="choice-field"><legend>难度</legend><div className="choice-row">{['基础', '进阶', '挑战'].map(level => <label className={`choice ${draft.difficulty === level ? 'selected' : ''}`} key={level}><input type="radio" name="difficulty" checked={draft.difficulty === level} onChange={() => setDraft({ ...draft, difficulty: level })} /><span>{level}</span></label>)}</div></fieldset>
    <button type="button" className="more-toggle" aria-expanded={moreOpen} onClick={() => setMoreOpen(o => !o)}><ChevronDown size={16} className={moreOpen ? 'rotated' : ''} />更多设置 <span>{draft.count} 道主问题，最多 {draft.followups} 次追问</span></button>
    {moreOpen && <div className="more-fields"><div className="form-field"><label htmlFor="question-count">主问题数</label><select id="question-count" className="field" value={draft.count} onChange={e => setDraft({ ...draft, count: Number(e.target.value) })}>{Array.from({ length: 8 }, (_, i) => i + 3).map(n => <option key={n} value={n}>{n} 道主问题</option>)}</select></div><div className="form-field"><label htmlFor="followup-count">每题追问上限</label><select id="followup-count" className="field" value={draft.followups} onChange={e => setDraft({ ...draft, followups: Number(e.target.value) })}>{[0, 1, 2].map(n => <option key={n} value={n}>{n} 次</option>)}</select></div><div className="form-field"><label htmlFor="practice-focus">练习重点</label><select id="practice-focus" className="field" value={draft.focus} onChange={e => setDraft({ ...draft, focus: e.target.value })}>{['综合能力', '缓存与一致性', '数据库与事务', '项目与表达', '薄弱点再练'].map(value => <option key={value}>{value}</option>)}</select></div></div>}
    <button className="button primary setup-submit" type="submit" disabled={!types.length}><Play size={17} />开始练习</button>
  </form></main>
  return <main className="practice-active"><div className="practice-context"><strong>{config.role}</strong><div><button className="button ghost" onClick={() => setConfigOpen(true)}>查看配置</button><button className="button ghost" onClick={() => setEndOpen(true)}>结束练习</button></div></div><div className="practice-scroll" ref={scrollRef}><div className="reading-column"><div className="progress-meta"><span>主问题 <b>{index + 1}</b> / <b>{config.count}</b></span><span>{config.difficulty}</span></div><div className="progress-track"><span style={{ width: `${((index + (phase === 'feedback' || complete ? 1 : 0)) / config.count) * 100}%` }} /></div><article className="question-block"><h1>{q.title}</h1><p>{q.text}</p><button className="text-link" onClick={() => setSourceOpen(true)}><BookOpenText size={16} />资料来源 <span className="mono">1</span></button></article>
    {turns.map((turn, i) => <div className="turn" key={i}><span className="meta-label">你的回答</span><p className="submitted-answer">{turn.answer}</p>{i + 1 < turns.length && <div className="followup-block"><span className="meta-label">面试官 <span className="mono">追问 {i + 1} / {config.followups}</span></span><h2>{turns[i + 1].question}</h2></div>}</div>)}
    {followup > 0 && phase === 'answer' && <div className="followup-block"><span className="meta-label">面试官 <span className="mono">追问 {followup} / {config.followups}</span></span><h2>{prompt}</h2></div>}
    {phase === 'processing' && <div className="processing" role="status"><LoaderCircle size={16} className="spin" />回答已保存，正在整理{followup < config.followups ? '追问' : '反馈'}</div>}
    {phase === 'feedback' && (groupSkipped ? <div className="skipped-block"><h2>本题组已跳过</h2><p>本题组不生成评价。可以查看资料来源，再进入下一题。</p><button className="button secondary" onClick={() => setSourceOpen(true)}>查看资料</button></div> : <Feedback index={index} onSource={() => setSourceOpen(true)} />)}
    {complete && <div className="complete-block"><h2>本次练习已完成</h2><p>已提交 {allTurns.length} 次回答，跳过 {skipped} 个题组。</p><button className="button primary" onClick={() => finish(false)}>查看练习报告 <ArrowRight size={17} /></button></div>}
  </div></div>
    {!complete && <div className="composer-area"><div className="composer-inner">{phase === 'feedback' ? <div className="next-actions"><span>已完成 {index + 1} / {config.count} 组</span><button className="button primary" onClick={next}>{index + 1 === config.count ? '完成练习' : '下一题'}<ArrowRight size={17} /></button></div> : phase === 'processing' ? <div className="processing-actions">回答已保存，处理完成后可继续。</div> : paused ? <div className="paused-actions"><span>练习已暂停，当前回答会保留。</span><button className="button primary" onClick={() => setPaused(false)}><Play size={17} />继续练习</button></div> : <><label htmlFor="practice-answer" className="composer-label">你的回答</label><textarea id="practice-answer" className="field answer-field" placeholder="输入你的回答……" value={answer} maxLength={5000} onChange={e => setAnswer(e.target.value)} onKeyDown={e => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !e.nativeEvent.isComposing) { e.preventDefault(); submit() } }} /><div className="composer-toolbar"><span className="keyboard-hint"><kbd>Ctrl</kbd> + <kbd>Enter</kbd> 提交</span><div><span className={`word-count ${answer.length >= 4500 ? 'near-limit' : ''}`}>{answer.length} 字</span><button className="button primary" disabled={!answer.trim()} onClick={submit}>提交回答</button></div></div>{!answer.trim() && <p className="disabled-reason">输入回答后可提交。</p>}</>}
    {phase !== 'feedback' && <div className="practice-actions"><button className="button ghost" disabled={phase === 'processing'} onClick={() => setPaused(p => !p)}><Pause size={16} />暂停</button><button className="button ghost" disabled={phase === 'processing' || paused} onClick={() => { setSkipped(n => n + 1); setGroupSkipped(true); setPhase('feedback'); notify('本题组已跳过，不计入评价') }}><SkipForward size={16} />不会，跳过</button>{phase === 'processing' && <span className="meta-note">处理完成后可暂停或跳过。</span>}{paused && <span className="meta-note">继续练习后可跳过。</span>}</div>}</div></div>}
    <Drawer open={sourceOpen} onOpenChange={setSourceOpen} title="资料来源" width="source"><div className="source-detail"><FileText size={20} /><div><strong>{q.file}</strong><span className="mono">版本 1</span></div></div>{phase === 'feedback' || complete ? <blockquote className="source-quote">{q.reference}</blockquote> : <div className="locked-source"><h2>先表达你的理解</h2><p>本题组完成后可查看资料片段。</p></div>}<p className="meta-note">这里展示预置资料示例，尚未连接真实检索服务。</p></Drawer>
    <Modal open={configOpen} onOpenChange={setConfigOpen} title="本次练习配置"><dl className="config-list"><div><dt>岗位</dt><dd>{config.role}</dd></div><div><dt>知识库</dt><dd>{config.kb}</dd></div><div><dt>难度</dt><dd>{config.difficulty}</dd></div><div><dt>主问题</dt><dd>{config.count} 道</dd></div><div><dt>追问上限</dt><dd>{config.followups} 次</dd></div></dl></Modal>
    <Modal open={endOpen} onOpenChange={setEndOpen} title="结束练习"><p className="body-copy">已提交的回答会保留在本次记录中。未提交的草稿不会计入。</p><div className="dialog-actions"><button className="button secondary" onClick={() => setEndOpen(false)}>继续回答</button><button className="button primary" onClick={() => finish(true)}>结束并查看记录</button></div></Modal>
  </main>
}
