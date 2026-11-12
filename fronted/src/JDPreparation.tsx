import { useEffect, useRef, useState } from 'react'
import { AlertCircle, LoaderCircle } from 'lucide-react'
import { ApiError } from './api'
import type { JDMapping, JDReference, PracticeApi } from './api'
import { JDRequirementDetails } from './JDCoverage'

export type JDChoice = { packId: string; reference?: JDReference; pending: boolean }

export default function JDPreparation({ api, packId, disabled, onChange }: {
  api: PracticeApi; packId: string; disabled: boolean; onChange: (choice: JDChoice) => void
}) {
  const [text, setText] = useState('')
  const [mapping, setMapping] = useState<JDMapping | null>(null)
  const [operation, setOperation] = useState<'preview' | 'confirm' | null>(null)
  const pending = operation !== null
  const [error, setError] = useState('')
  const [fieldError, setFieldError] = useState('')
  const [showSummary, setShowSummary] = useState(false)
  const [selected, setSelected] = useState<string[]>([])
  const [confirmed, setConfirmed] = useState(false)
  const lock = useRef(false)
  const mounted = useRef(true)
  const input = useRef<HTMLTextAreaElement>(null)
  const errorSummary = useRef<HTMLDivElement>(null)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  useEffect(() => { if (error && !pending) errorSummary.current?.focus() }, [error, pending])

  function invalidate() {
    setConfirmed(false)
    setError('')
    onChange({ packId, pending: false })
  }

  async function perform(action: 'preview' | 'confirm') {
    if (lock.current || disabled || !packId || (action === 'confirm' && !mapping)) return
    if (text.trim().length < 20) {
      setFieldError('岗位描述至少 20 字才能分析')
      setShowSummary(true)
      input.current?.focus()
      return
    }
    lock.current = true
    setOperation(action)
    setError('')
    setConfirmed(false)
    setFieldError('')
    setShowSummary(false)
    if (action === 'preview') setMapping(null)
    onChange({ packId, pending: true })
    let reference: JDReference | undefined
    try {
      const result = action === 'confirm' && mapping
        ? await api.confirmJD({ mapping_id: mapping.id, revision: mapping.revision }, selected)
        : await api.previewJD(packId, text)
      if (!mounted.current) return
      setMapping(result)
      if (action === 'confirm') { reference = { mapping_id: result.id, revision: result.revision }; setConfirmed(true) }
      else setSelected(result.requirements.map(item => item.id))
    }
    catch (failure) { if (mounted.current) setError(failure instanceof ApiError ? failure.message : '岗位要求处理失败，请重试') }
    finally {
      lock.current = false
      if (mounted.current) { setOperation(null); onChange({ packId, reference, pending: false }) }
    }
  }

  return <section className="jd-preparation" aria-label="JD 准备" aria-busy={pending}>
    {(error || showSummary) && <div ref={errorSummary} tabIndex={-1} className="qp-error" role="alert">
      {error ? <p>{error}。JD 文本已保留，可重新提取或直接开始无 JD 面试。</p> : <a href="#mi-jd">请检查岗位 JD 后重新提取</a>}
    </div>}
    <div className="form-field"><label htmlFor="mi-jd">岗位 JD（可选）</label>
      <textarea ref={input} id="mi-jd" className="field" rows={5} maxLength={20000} value={text} disabled={disabled || pending} aria-invalid={Boolean(fieldError)} aria-describedby={fieldError ? 'mi-jd-error' : 'mi-jd-help'} onBlur={() => setFieldError(text.trim() && text.trim().length < 20 ? '岗位描述至少 20 字才能分析' : '')} onChange={event => {
        const value = event.target.value
        setText(value); setMapping(null); invalidate()
        if (!value.trim() || value.trim().length >= 20) { setFieldError(''); setShowSummary(false) }
      }} />
      {fieldError ? <p className="field-error" id="mi-jd-error"><AlertCircle size={14} aria-hidden="true" /><span>{fieldError}</span></p> : <p className="field-help" id="mi-jd-help">粘贴 20～20000 字岗位要求，提取后核对并确认。未确认的内容不参与本场选题；留空也可开始。</p>}
      <p className={`jd-count${text.length >= 18000 ? ' jd-count-warning' : ''}`}>{text.length} / 20000 字</p>
    </div>
    <div className="practice-actions"><button type="button" className="button secondary" aria-busy={operation === 'preview'} disabled={disabled || pending || !text.trim() || !packId} onClick={() => void perform('preview')}>{operation === 'preview' && <LoaderCircle className="spin" size={14} aria-hidden="true" />}提取岗位要求</button>
      {text && <button type="button" className="button ghost" disabled={disabled || pending} onClick={() => { setText(''); setMapping(null); setFieldError(''); setShowSummary(false); invalidate() }}>清除 JD</button>}
    </div>
    {pending && <p role="status">正在处理岗位要求，请稍候。</p>}
    {mapping && <div className="jd-preview">
      {[false, true].map(gap => <section key={String(gap)}><h3>{gap ? '暂不能覆盖的要求' : '可覆盖要求'}</h3>
        <ul className="mi-gap-list">{mapping.requirements.filter(item => Boolean(item.gap_reason) === gap).map(item => <li key={item.id}>
          <label className="jd-choice"><input type="checkbox" checked={selected.includes(item.id)} disabled={disabled || pending} onChange={event => {
            setSelected(ids => event.target.checked ? [...ids, item.id] : ids.filter(id => id !== item.id)); invalidate()
          }} /><strong>{item.text}</strong></label><JDRequirementDetails requirement={item} />
        </li>)}</ul>
        {!mapping.requirements.some(item => Boolean(item.gap_reason) === gap) && <p className="field-help">{gap ? '未发现题库覆盖缺口' : '暂无可覆盖要求，可继续练习题库中的其他能力'}</p>}
      </section>)}
      {mapping.limitations.map(item => <p className="meta-note" key={item}>{item}</p>)}
      <p className="field-help">勾选要用于本场的要求。可覆盖项会提高相关主题的抽选权重，但仍随机；未覆盖项将保留为报告缺口，可继续练习其他能力。JD 不作为技术正确性的依据。</p>
      <button type="button" className="button secondary" aria-busy={operation === 'confirm'} disabled={disabled || pending || confirmed || !selected.length} onClick={() => void perform('confirm')}>{operation === 'confirm' && <LoaderCircle className="spin" size={14} aria-hidden="true" />}{mapping.requirements.some(item => selected.includes(item.id) && item.gap_reason) ? '确认要求并接受覆盖缺口' : '确认所选要求'}</button>
      {!selected.length && <p className="field-help">请勾选至少一项要求以确认，或直接开始无 JD 面试。</p>}
      <p className="field-help" role="status">{confirmed ? '已确认，本场将使用所选 JD 要求。' : '提取结果尚未确认，本场暂不使用 JD。'}</p>
    </div>}
  </section>
}
