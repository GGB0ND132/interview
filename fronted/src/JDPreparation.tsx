import { useEffect, useRef, useState } from 'react'
import { ApiError } from './api'
import type { JDMapping, JDReference, PracticeApi } from './api'
import { JDRequirementDetails } from './JDCoverage'

export type JDChoice = { packId: string; reference?: JDReference; pending: boolean }

export default function JDPreparation({ api, packId, disabled, onChange }: {
  api: PracticeApi; packId: string; disabled: boolean; onChange: (choice: JDChoice) => void
}) {
  const [text, setText] = useState('')
  const [mapping, setMapping] = useState<JDMapping | null>(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<string[]>([])
  const [confirmed, setConfirmed] = useState(false)
  const lock = useRef(false)
  const mounted = useRef(true)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])

  async function perform(confirm: boolean) {
    if (lock.current || disabled || !text.trim() || !packId || (confirm && !mapping)) return
    lock.current = true
    setPending(true)
    setError('')
    setConfirmed(false)
    if (!confirm) setMapping(null)
    onChange({ packId, pending: true })
    let reference: JDReference | undefined
    try {
      const result = confirm && mapping
        ? await api.confirmJD({ mapping_id: mapping.id, revision: mapping.revision }, selected)
        : await api.previewJD(packId, text)
      if (!mounted.current) return
      setMapping(result)
      if (confirm) { reference = { mapping_id: result.id, revision: result.revision }; setConfirmed(true) }
      else setSelected(result.requirements.map(item => item.id))
    }
    catch (failure) { if (mounted.current) setError(failure instanceof ApiError ? failure.message : '岗位要求处理失败，请重试') }
    finally {
      lock.current = false
      if (mounted.current) { setPending(false); onChange({ packId, reference, pending: false }) }
    }
  }

  return <section className="jd-preparation" aria-label="JD 准备" aria-busy={pending}>
    <div className="form-field"><label htmlFor="mi-jd">岗位 JD（可选）</label>
      <textarea id="mi-jd" className="field" rows={5} maxLength={20000} value={text} disabled={disabled || pending} aria-describedby={`mi-jd-help${error ? ' mi-jd-error' : ''}`} onChange={event => {
        setText(event.target.value); setMapping(null); setConfirmed(false); setError(''); onChange({ packId, pending: false })
      }} />
      <p className="field-help" id="mi-jd-help">粘贴岗位要求，提取后核对并确认。未确认的内容不参与本场选题；留空也可开始。</p>
    </div>
    <div className="practice-actions"><button type="button" className="button secondary" disabled={disabled || pending || !text.trim() || !packId} onClick={() => void perform(false)}>提取岗位要求</button>
      {text && <button type="button" className="button ghost" disabled={disabled || pending} onClick={() => { setText(''); setMapping(null); setConfirmed(false); setError(''); onChange({ packId, pending: false }) }}>清除 JD</button>}
    </div>
    {pending && <p role="status">正在处理岗位要求，请稍候。</p>}
    {error && <p id="mi-jd-error" className="field-error" role="alert">{error}。JD 文本已保留，可重新提取或直接开始无 JD 面试。</p>}
    {mapping && <div className="jd-preview">
      {[false, true].map(gap => <section key={String(gap)}><h3>{gap ? '暂不能覆盖的要求' : '可覆盖要求'}</h3>
        <ul className="mi-gap-list">{mapping.requirements.filter(item => Boolean(item.gap_reason) === gap).map(item => <li key={item.id}>
          <label className="jd-choice"><input type="checkbox" checked={selected.includes(item.id)} disabled={disabled || pending} onChange={event => {
            setSelected(ids => event.target.checked ? [...ids, item.id] : ids.filter(id => id !== item.id)); setConfirmed(false); setError(''); onChange({ packId, pending: false })
          }} /><strong>{item.text}</strong></label><JDRequirementDetails requirement={item} />
        </li>)}</ul>
        {!mapping.requirements.some(item => Boolean(item.gap_reason) === gap) && <p className="field-help">{gap ? '未发现题库覆盖缺口' : '暂无可覆盖要求，可继续练习题库中的其他能力'}</p>}
      </section>)}
      {mapping.limitations.map(item => <p className="meta-note" key={item}>{item}</p>)}
      <p className="field-help">勾选要用于本场的要求。可覆盖项会提高相关主题的抽选权重，但仍随机；未覆盖项将保留为报告缺口，可继续练习其他能力。JD 不作为技术正确性的依据。</p>
      <button type="button" className="button secondary" disabled={disabled || pending || confirmed || !selected.length} onClick={() => void perform(true)}>{mapping.requirements.some(item => selected.includes(item.id) && item.gap_reason) ? '确认要求并接受覆盖缺口' : '确认所选要求'}</button>
      <p className="field-help" role="status">{confirmed ? '已确认，本场将使用所选 JD 要求。' : '提取结果尚未确认，本场暂不使用 JD。'}</p>
    </div>}
  </section>
}
