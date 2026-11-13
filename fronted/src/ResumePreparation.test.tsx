import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { createPracticeApi } from './api'
import MockInterview from './MockInterview'
import ResumePreparation from './ResumePreparation'

const projects = [{ id: 'p1', text: '检索助手：我负责工具调用与错误恢复。', source: { paragraph: 3 } }, { id: 'p2', text: '不希望使用的课程项目', source: { paragraph: 4 } }]
const preview = { resume_id: 'r1', revision: 0, status: 'needs_confirmation', source_type: 'docx', blocks: projects, project_fragments: projects, confirmed: null, error: null, notice: '项目仅为候选人陈述，未经外部核实。', warnings: [] }
const opening = { id: 't1', question_code: 'INTRO', kind: 'main', stage: 'introduction', text: '请介绍你的学习经历。' }
const active = { session_id: 's1', mode: 'mock_interview', pack_id: 'agent', created_at: '2026-11-13', status: 'active', phase: 'awaiting_answer', revision: 1, current_turn: opening, turns: [opening], submissions: [], available_actions: ['answer', 'finish'] }
function server(route: (path: string, body: Record<string, unknown> | FormData) => unknown | Promise<unknown>) {
  const calls: { path: string; body: Record<string, unknown> | FormData }[] = []
  const api = createPracticeApi({ fetchImpl: vi.fn(async (input, init) => {
    const path = String(input).replace('/api/v1', '')
    const body = init?.body instanceof FormData ? init.body : init?.body ? JSON.parse(String(init.body)) : {}
    calls.push({ path, body })
    let data
    if (path === '/role-packs') data = { items: [{ id: 'agent', title: 'Agent 基础档', status: 'published', version: 1 }] }
    else if (path.endsWith('/availability')) data = { can_start: true, available_count: 57, topics: [], stages: [] }
    else if (path.startsWith('/sessions?')) data = { items: [] }
    else if (path === '/sessions') data = { ...active, phase: 'draft', revision: 0 }
    else if (path.endsWith('/start')) data = active
    else data = await route(path, body)
    return data instanceof Response ? data : new Response(JSON.stringify({ data, error: null }))
  }) as typeof fetch })
  return { api, calls }
}
afterEach(() => { localStorage.clear(); vi.restoreAllMocks() })

it('uploads, traces original fragments and uses only explicitly confirmed selections', async () => {
  const user = userEvent.setup()
  const { api, calls } = server((path, body) => {
    if (path === '/resumes') return preview
    if (path === '/resumes/r1/confirm') return { ...preview, status: 'confirmed', revision: 1, confirmed: { resume_id: 'r1', projects: projects.filter(p => (body as { fragment_ids: string[] }).fragment_ids.includes(p.id)), no_project_experience: false, notice: preview.notice } }
    throw new Error(path)
  })
  render(<MockInterview api={api} />)
  await user.upload(await screen.findByLabelText('上传简历（可选）'), new File(['docx'], 'resume.docx'))
  expect((await screen.findAllByText('第 3 段')).length).toBeGreaterThan(0)
  expect(screen.getByText('提取结果尚未确认，本场不使用项目片段。')).toBeTruthy()
  await user.click(screen.getByRole('checkbox', { name: projects[1].text }))
  await user.click(screen.getByRole('button', { name: '确认所选项目' }))
  await screen.findByText('已确认，本场使用所选项目陈述。')
  expect((screen.getByRole('checkbox', { name: projects[1].text }) as HTMLInputElement).checked).toBe(false)
  expect(calls.find(c => c.path.endsWith('/confirm'))?.body).toEqual({ expected_revision: 0, fragment_ids: ['p1'], no_project_experience: false })
  await user.click(screen.getByRole('button', { name: '开始模拟面试' }))
  await screen.findByRole('textbox', { name: '你的回答' })
  expect((calls.find(c => c.path === '/sessions')?.body as { config: unknown }).config).toMatchObject({ resume_id: 'r1', experience_mode: 'experience' })
})

it('discards confirmation when project text is corrected and never attaches the old resume', async () => {
  const user = userEvent.setup()
  const { api, calls } = server(path => {
    if (path === '/resumes/text') return { ...preview, source_type: 'pasted_text' }
    if (path.endsWith('/confirm')) return { ...preview, status: 'confirmed', confirmed: { projects, no_project_experience: false } }
    throw new Error(path)
  })
  render(<MockInterview api={api} />)
  await user.type(await screen.findByLabelText('粘贴或修正项目文本'), projects[0].text)
  await user.click(screen.getByRole('button', { name: '预览项目文本' }))
  await user.click(await screen.findByRole('button', { name: '确认所选项目' }))
  await screen.findByText('已确认，本场使用所选项目陈述。')
  await user.click(screen.getByRole('button', { name: '修正所选项目文本' }))
  await user.type(screen.getByLabelText('粘贴或修正项目文本'), '我只负责前端。')
  await user.click(screen.getByRole('button', { name: '开始模拟面试' }))
  await screen.findByRole('textbox', { name: '你的回答' })
  expect((calls.find(c => c.path === '/sessions')?.body as { config: { resume_id?: string } }).config.resume_id).toBeUndefined()
})

it('keeps practice blocked while parsing and permits unconfirmed practice after a failed upload', async () => {
  const user = userEvent.setup()
  let finish!: (data: unknown) => void
  const { api, calls } = server(path => {
    if (path === '/resumes') return new Promise(resolve => { finish = resolve })
    throw new Error(path)
  })
  render(<MockInterview api={api} />)
  await user.upload(await screen.findByLabelText('上传简历（可选）'), new File(['broken'], 'scan.pdf'))
  await screen.findByText('正在上传并解析简历，请稍候。')
  expect((screen.getByRole('button', { name: '开始模拟面试' }) as HTMLButtonElement).disabled).toBe(true)
  finish({ ...preview, status: 'parse_failed', blocks: [], project_fragments: [], error: { code: 'RESUME_PARSE_FAILED', message: '扫描件不支持识别，请粘贴项目文本。' } })
  await screen.findByText('扫描件不支持识别，请粘贴项目文本。')
  await user.click(screen.getByRole('button', { name: '开始模拟面试' }))
  await screen.findByRole('textbox', { name: '你的回答' })
  expect((calls.find(c => c.path === '/sessions')?.body as { config: { resume_id?: string } }).config.resume_id).toBeUndefined()
})

it('falls back from parsing failure to corrected pasted text and a fresh confirmation', async () => {
  const user = userEvent.setup()
  const corrected = '修正项目：我实现了 FastAPI 校验。'
  const changes = vi.fn()
  const { api, calls } = server((path, body) => {
    if (path === '/resumes') return { ...preview, status: 'parse_failed', blocks: [], project_fragments: [], error: { code: 'RESUME_PARSE_FAILED', message: '解析失败，请粘贴文本。' } }
    if (path === '/resumes/text') return { ...preview, resume_id: 'new', source_type: 'pasted_text', project_fragments: [{ id: 'edit1', text: (body as { text: string }).text, source: { line: 1 } }] }
    if (path === '/resumes/new/confirm') return { ...preview, resume_id: 'new', status: 'confirmed', confirmed: { projects: [{ id: 'edit1', text: corrected, source: { line: 1 } }], no_project_experience: false } }
    throw new Error(path)
  })
  render(<ResumePreparation api={api} disabled={false} onChange={changes} />)
  await user.upload(screen.getByLabelText('上传简历（可选）'), new File(['broken'], 'scan.pdf'))
  await screen.findByText('解析失败，请粘贴文本。')
  await user.type(screen.getByLabelText('粘贴或修正项目文本'), corrected)
  await user.click(screen.getByRole('button', { name: '预览项目文本' }))
  await user.click(await screen.findByRole('button', { name: '确认所选项目' }))
  await waitFor(() => expect(changes).toHaveBeenLastCalledWith({ pending: false, resumeId: 'new', mode: 'experience' }))
  expect(calls.find(c => c.path === '/resumes/new/confirm')?.body).toMatchObject({ fragment_ids: ['edit1'] })
})

it('explicitly confirms no project experience and switches to the scenario branch', async () => {
  const user = userEvent.setup()
  const { api, calls } = server(path => {
    if (path === '/resumes/text') return preview
    if (path.endsWith('/confirm')) return { ...preview, status: 'confirmed', confirmed: { projects: [], no_project_experience: true } }
    throw new Error(path)
  })
  render(<MockInterview api={api} />)
  await user.selectOptions(await screen.findByLabelText('经历环节'), 'experience')
  await user.click(screen.getByRole('button', { name: '确认没有相关项目经历' }))
  await screen.findByText('已确认没有相关项目经历，本场使用假设情境题。')
  expect((screen.getByLabelText('经历环节') as HTMLSelectElement).value).toBe('scenario')
  await user.click(screen.getByRole('button', { name: '开始模拟面试' }))
  await screen.findByRole('textbox', { name: '你的回答' })
  expect(calls.find(c => c.path.endsWith('/confirm'))?.body).toMatchObject({ fragment_ids: [], no_project_experience: true })
  expect((calls.find(c => c.path === '/sessions')?.body as { config: unknown }).config).toMatchObject({ resume_id: 'r1', experience_mode: 'scenario' })
})

it('rejects unsupported and oversized uploads locally with a paste fallback', async () => {
  const user = userEvent.setup({ applyAccept: false })
  const { api, calls } = server(path => { throw new Error(path) })
  render(<ResumePreparation api={api} disabled={false} onChange={() => {}} />)
  await user.upload(screen.getByLabelText('上传简历（可选）'), new File(['text'], 'resume.txt'))
  expect(await screen.findByRole('alert')).toBeTruthy()
  await user.upload(screen.getByLabelText('上传简历（可选）'), new File([new Uint8Array(5 * 1024 * 1024 + 1)], 'large.pdf'))
  expect(screen.getByText('仅支持不超过 5 MiB 的文字版 PDF 或 DOCX。请改为粘贴项目文本。')).toBeTruthy()
  expect(calls).toHaveLength(0)
})

it('retains a corrected draft after a failed file parse and associates upload errors with the field', async () => {
  const user = userEvent.setup()
  let finish!: (data: unknown) => void
  const { api } = server(() => new Promise(resolve => { finish = resolve }))
  render(<ResumePreparation api={api} disabled={false} onChange={() => {}} />)
  const text = screen.getByLabelText('粘贴或修正项目文本') as HTMLTextAreaElement
  await user.type(text, '项目草稿不能丢失')
  const file = screen.getByLabelText('上传简历（可选）')
  await user.upload(file, new File(['scan'], 'scan.pdf'))
  expect(file.getAttribute('aria-busy')).toBe('true')
  finish({ ...preview, status: 'parse_failed', blocks: [], project_fragments: [], error: { code: 'RESUME_PARSE_FAILED', message: '无法解析扫描件' } })
  await screen.findByText('无法解析扫描件')
  expect(text.value).toBe('项目草稿不能丢失')
  expect(file.getAttribute('aria-invalid')).toBe('true')
  const errorId = file.getAttribute('aria-describedby')?.split(' ').find(id => id.endsWith('-error'))
  expect(document.getElementById(errorId ?? '')?.textContent).toContain('无法解析扫描件')
})
