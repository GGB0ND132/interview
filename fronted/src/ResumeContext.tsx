import type { ResumeContext, ResumeFragment } from './api'

export function ResumeLocation({ fragment }: { fragment: ResumeFragment }) {
  const { page, paragraph, line } = fragment.source
  return <span>{[page && `第 ${page} 页`, paragraph && `第 ${paragraph} 段`, line && `第 ${line} 行`].filter(Boolean).join('，') || '用户提供的项目文本'}</span>
}

export default function ConfirmedResume({ context }: { context?: ResumeContext | null }) {
  if (!context) return null
  return <details className="mi-coverage resume-context">
    <summary>本场项目陈述与来源</summary>
    <p className="meta-note">{context.notice}</p>
    {context.no_project_experience ? <p>已声明没有相关项目经历，使用明确标注的假设情境题。</p> : context.projects.map(project => <div key={project.id}><p>{project.text}</p><p className="meta-note">{context.source_type === 'pasted_text' ? '用户粘贴或修正文本，' : ''}<ResumeLocation fragment={project} /></p></div>)}
  </details>
}
