import { useEffect, useRef, useState } from 'react'
import { ApiError } from './api'
import type { PracticeApi, ResumePreview } from './api'
import { ResumeLocation } from './ResumeContext'

export type ResumeChoice = { resumeId?: string; pending: boolean; mode?: 'experience' | 'scenario' }

export default function ResumePreparation({ api, disabled, onChange }: {
  api: PracticeApi; disabled: boolean; onChange: (choice: ResumeChoice) => void
}) {
  const [text, setText] = useState('')
  const [preview, setPreview] = useState<ResumePreview | null>(null)
  const [original, setOriginal] = useState<ResumePreview | null>(null)
  const [selected, setSelected] = useState<string[]>([])
  const [operation, setOperation] = useState<'upload' | 'paste' | 'confirm' | 'scenario' | null>(null)
  const [error, setError] = useState('')
  const lock = useRef(false)
  const mounted = useRef(true)
  const input = useRef<HTMLTextAreaElement>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const errorSummary = useRef<HTMLDivElement>(null)
  const pending = operation !== null
  const confirmed = preview?.status === 'confirmed'
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  useEffect(() => { if (error && !pending) errorSummary.current?.focus() }, [error, pending])

  function invalidate() { onChange({ pending: false }); setError('') }

  async function perform(action: NonNullable<typeof operation>, file?: File) {
    if (lock.current || disabled) return
    invalidate()
    if (action === 'upload' && file && (!/\.(pdf|docx)$/i.test(file.name) || file.size > 5 * 1024 * 1024)) {
      setPreview(null); setOriginal(null)
      setError('仅支持不超过 5 MiB 的文字版 PDF 或 DOCX。请改为粘贴项目文本。')
      return
    }
    if (action === 'paste' && !text.trim()) { setError('请先粘贴非空项目文本。'); return }
    if (action === 'confirm' && (!preview || !selected.length || selected.length > 20)) return
    lock.current = true
    setOperation(action)
    onChange({ pending: true })
    if (action !== 'confirm') setPreview(null)
    let choice: ResumeChoice = { pending: false }
    try {
      let result: ResumePreview
      if (action === 'upload' && file) {
        setOriginal(null)
        result = await api.uploadResume(file)
        if (mounted.current) { setOriginal(result); setText('') }
      } else if (action === 'scenario') {
        const declaration = await api.pasteResume('用户声明没有相关项目经历。')
        result = await api.confirmResume(declaration.resume_id, declaration.revision, [], true)
      } else if (action === 'confirm' && preview) {
        result = await api.confirmResume(preview.resume_id, preview.revision, selected, false)
      } else result = await api.pasteResume(text)
      if (!mounted.current) return
      setPreview(result)
      setSelected((result.confirmed?.projects ?? result.project_fragments).map(item => item.id))
      if (result.error) setError(result.error.message)
      if (result.confirmed) choice = { pending: false, resumeId: result.resume_id, mode: result.confirmed.no_project_experience ? 'scenario' : 'experience' }
    } catch (failure) {
      if (mounted.current) setError(failure instanceof ApiError ? failure.message : '项目内容处理失败，请重试或粘贴文本。')
    } finally {
      lock.current = false
      if (mounted.current) { setOperation(null); onChange(choice) }
    }
  }

  function clear() {
    setText(''); setPreview(null); setOriginal(null); setSelected([]); invalidate()
    if (fileInput.current) fileInput.current.value = ''
  }

  return <section className="resume-preparation" aria-label="简历与项目准备" aria-busy={pending}>
    <h2>简历与项目（可选）</h2>
    <p className="field-help" id="mi-resume-help">支持文字版 PDF、DOCX，最大 5 MiB；扫描件不支持识别。先预览并确认项目，也可不上传直接练习。</p>
    {error && <div className="qp-error" role="alert" tabIndex={-1} ref={errorSummary}><p id="mi-resume-error">{error}</p><a href="#mi-resume-text">粘贴项目文本重新预览</a></div>}
    <div className="form-field"><label htmlFor="mi-resume-file">上传简历（可选）</label>
      <input ref={fileInput} id="mi-resume-file" type="file" className="field" accept=".pdf,.docx" disabled={disabled || pending} aria-describedby="mi-resume-help" onChange={event => { const file = event.target.files?.[0]; if (file) void perform('upload', file); event.target.value = '' }} />
    </div>
    <div className="form-field"><label htmlFor="mi-resume-text">粘贴或修正项目文本</label>
      <textarea ref={input} id="mi-resume-text" className="field" rows={5} maxLength={50000} value={text} disabled={disabled || pending} aria-describedby="mi-resume-text-help" onChange={event => { setText(event.target.value); setPreview(null); invalidate() }} />
      <p className="field-help" id="mi-resume-text-help">仅填写愿意用于面试的项目内容，最多 50000 字。修正后的文本需重新预览和确认，来源标记为用户粘贴或修正文本。</p>
    </div>
    <div className="practice-actions"><button type="button" className="button secondary" disabled={disabled || pending || !text.trim()} onClick={() => void perform('paste')}>预览项目文本</button>
      <button type="button" className="button ghost" disabled={disabled || pending} onClick={() => void perform('scenario')}>确认没有相关项目经历</button>
      {(preview || text || original) && <button type="button" className="button ghost" disabled={disabled || pending} onClick={clear}>清除项目内容</button>}
    </div>
    {pending && <p role="status">{operation === 'upload' ? '正在上传并解析简历，请稍候。' : operation === 'paste' ? '正在提取项目片段，请稍候。' : '正在保存项目确认，请稍候。'}</p>}
    {original && original.blocks.length > 0 && <details className="resume-original"><summary>回查上传简历原文</summary>{original.blocks.map(block => <div key={block.id}><p className="meta-note"><ResumeLocation fragment={block} /></p><p>{block.text}</p></div>)}</details>}
    {preview && <div className="resume-preview">
      {preview.warnings.map(warning => <p className="field-help" key={warning}>{warning}</p>)}
      {preview.project_fragments.length > 0 && !preview.confirmed?.no_project_experience && <>
        <h3>选择本场使用的项目片段</h3>
        <ul className="mi-gap-list">{preview.project_fragments.map(project => <li key={project.id}>
          <label className="jd-choice"><input type="checkbox" disabled={disabled || pending || confirmed} checked={selected.includes(project.id)} onChange={event => { setSelected(ids => event.target.checked ? [...ids, project.id] : ids.filter(id => id !== project.id)); invalidate() }} /><span>{project.text}</span></label>
          <p className="meta-note">{preview.source_type === 'pasted_text' ? '用户粘贴或修正文本，' : ''}<ResumeLocation fragment={project} /></p>
        </li>)}</ul>
        <p className="field-help">最多选择 20 个片段，总计不超过 12000 字。</p>
        <div className="practice-actions"><button type="button" className="button secondary" disabled={disabled || pending || confirmed || !selected.length || selected.length > 20} onClick={() => void perform('confirm')}>确认所选项目</button>
          <button type="button" className="button ghost" disabled={disabled || pending || !selected.length} onClick={() => { setText(preview.project_fragments.filter(item => selected.includes(item.id)).map(item => item.text).join('\n')); setPreview(null); invalidate(); input.current?.focus() }}>修正所选项目文本</button>
        </div>
      </>}
      <p className="meta-note">{preview.notice}</p>
      <p role="status" className="field-help">{confirmed ? preview.confirmed?.no_project_experience ? '已确认没有相关项目经历，本场使用假设情境题。' : '已确认，本场使用所选项目陈述。' : '提取结果尚未确认，本场不使用项目片段。'}</p>
    </div>}
  </section>
}
