import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { createPracticeApi } from './api'
import type { PracticeMode, SessionView } from './api'
import QuestionPractice from './QuestionPractice'
import MockInterview from './MockInterview'

afterEach(() => { localStorage.clear(); vi.restoreAllMocks() })

function recoveryServer(mode: PracticeMode) {
  const turn = { id: 'turn-1', question_code: 'Q1', question_version: 1, kind: 'main' as const, question_type: 'technical' as const, stage: 'technical' as const, topic: '工具调用', competency_id: 'tools', text: '如何处理工具调用失败？' }
  let view: SessionView = { session_id: 's1', mode, pack_id: 'agent', pack_version: 1, pack_title: 'Agent 基础档', created_at: '2026-11-13T00:00:00Z', difficulty: 'easy', revision: 1, status: 'active', phase: 'awaiting_answer', current_turn: turn, turns: [turn], submissions: [], available_actions: ['answer', 'skip', 'finish'] }
  let offline = false
  let sessionOffline = false
  let operation: ((path: string, body: Record<string, unknown>) => unknown | Promise<unknown>) | null = null
  const calls: string[] = []
  const requests: Record<string, unknown>[] = []
  const api = createPracticeApi({ fetchImpl: vi.fn(async (input, init) => {
    const path = String(input).replace('/api/v1', '')
    calls.push(path)
    if (offline) throw new TypeError('offline')
    if (sessionOffline && path === '/sessions/s1') throw new TypeError('session offline')
    const body = init?.body ? JSON.parse(String(init.body)) : {}
    if (path.endsWith('/answers')) requests.push(body)
    const data = operation && (path.endsWith('/answers') || path.endsWith('/retry') || path.startsWith('/jobs/')) ? await operation(path, body)
      : path === '/role-packs' ? { items: [{ id: 'agent', title: 'Agent 基础档', version: 1, status: 'published' }] }
      : path.endsWith('/availability') ? { can_start: true, available_count: 12, topics: [], stages: [], missing: [] }
      : path.startsWith('/sessions?') ? { items: [view], page: 1, page_size: 20, total: 1 }
      : view
    return new Response(JSON.stringify({ schema_version: '1.0', request_id: 'r', data, error: null }))
  }) as typeof fetch })
  const Component = mode === 'question_practice' ? QuestionPractice : MockInterview
  localStorage.setItem(mode === 'question_practice' ? 'ia-qp-session' : 'ia-mi-session', 's1')
  return { page: <Component api={api} />, calls, requests, get view() { return view }, set view(next: SessionView) { view = next }, set offline(next: boolean) { offline = next }, set sessionOffline(next: boolean) { sessionOffline = next }, set operation(next: typeof operation) { operation = next } }
}

it('restores the unsubmitted question-practice draft after remounting from the saved server turn', async () => {
  const server = recoveryServer('question_practice')
  const user = userEvent.setup()
  const first = render(server.page)
  await user.type(await screen.findByRole('textbox', { name: '你的回答' }), '先保留错误原因，再决定是否重试。')
  first.unmount()
  render(server.page)
  await waitFor(() => expect((screen.getByRole('textbox', { name: '你的回答' }) as HTMLTextAreaElement).value).toBe('先保留错误原因，再决定是否重试。'))
  expect(server.calls.some(path => path.endsWith('/answers'))).toBe(false)
})

for (const mode of ['question_practice', 'mock_interview'] as const) {
  it(`${mode}: restores only the current turn draft and keeps drafts from different sessions isolated`, async () => {
    const server = recoveryServer(mode)
    const user = userEvent.setup()
    let page = render(server.page)
    await user.type(await screen.findByRole('textbox', { name: '你的回答' }), '旧题草稿')
    page.unmount()
    page = render(server.page)
    expect((await screen.findByRole('textbox', { name: '你的回答' }) as HTMLTextAreaElement).value).toBe('旧题草稿')
    page.unmount()
    const original = server.view
    server.view = { ...original, revision: 2, current_turn: { ...original.current_turn!, id: 'turn-2', text: '新的追问' } }
    page = render(server.page)
    expect((await screen.findByRole('textbox', { name: '你的回答' }) as HTMLTextAreaElement).value).toBe('')
    await user.type(screen.getByRole('textbox', { name: '你的回答' }), '新题草稿')
    page.unmount()
    server.view = { ...server.view, session_id: 's2' }
    render(server.page)
    expect((await screen.findByRole('textbox', { name: '你的回答' }) as HTMLTextAreaElement).value).toBe('')
    expect(server.requests).toHaveLength(0)
  })

  it(`${mode}: restores saved answers and removes their browser draft`, async () => {
    const server = recoveryServer(mode)
    const user = userEvent.setup()
    const page = render(server.page)
    await user.type(await screen.findByRole('textbox', { name: '你的回答' }), '本地未提交版本')
    page.unmount()
    server.view = { ...server.view, revision: 3, phase: 'evaluation_failed', available_actions: ['retry', 'finish'], submissions: [{ id: 'a1', turn_id: 'turn-1', client_submission_id: 'key', disposition: 'answered', answer_text: '服务端已保存版本', status: 'failed', job_id: 'job-1', error: { code: 'MODEL_TIMEOUT', message: '模型超时，回答已保存', retryable: true } }] }
    const restored = render(server.page)
    expect(await screen.findByText('服务端已保存版本')).toBeTruthy()
    expect(screen.queryByText('本地未提交版本')).toBeNull()
    expect(screen.getByRole('button', { name: '重试评价' })).toBeTruthy()
    restored.unmount()
    server.view = { ...server.view, phase: 'awaiting_answer', available_actions: ['answer'], submissions: [] }
    render(server.page)
    expect((await screen.findByRole('textbox', { name: '你的回答' }) as HTMLTextAreaElement).value).toBe('')
    expect(server.requests).toHaveLength(0)
  })

  it(`${mode}: reuses an uncertain submission identity after refresh, then clears its draft on acceptance`, async () => {
    const server = recoveryServer(mode)
    const user = userEvent.setup()
    server.operation = () => { server.sessionOffline = true; throw new TypeError('response lost') }
    const page = render(server.page)
    await user.type(await screen.findByRole('textbox', { name: '你的回答' }), '保留重试身份')
    await user.click(screen.getByRole('button', { name: '提交回答' }))
    await screen.findByRole('button', { name: '重新同步会话' })
    expect((screen.getByRole('button', { name: '提交回答' }) as HTMLButtonElement).disabled).toBe(true)
    page.unmount()
    server.sessionOffline = false
    server.operation = (_path, body) => {
      const submission = { id: 'a1', turn_id: 'turn-1', client_submission_id: String(body.client_submission_id), disposition: 'answered' as const, answer_text: String(body.answer_text), status: 'completed' as const, job_id: null }
      server.view = { ...server.view, revision: 2, phase: mode === 'question_practice' ? 'feedback_ready' : 'stage_transition', submissions: [submission], available_actions: [] }
      return { session: server.view, submission, idempotent_replay: true }
    }
    render(server.page)
    expect((await screen.findByRole('textbox', { name: '你的回答' }) as HTMLTextAreaElement).value).toBe('保留重试身份')
    await user.dblClick(screen.getByRole('button', { name: '提交回答' }))
    expect(await screen.findByText('保留重试身份')).toBeTruthy()
    expect(server.requests).toHaveLength(2)
    expect(server.requests[1]).toEqual(server.requests[0])
    expect(Array.from({ length: localStorage.length }, (_, index) => localStorage.key(index)).filter(key => key?.startsWith('ia-answer-draft:'))).toHaveLength(0)
  })

  it(`${mode}: remains usable when browser storage is unavailable`, async () => {
    const server = recoveryServer(mode)
    const page = render(server.page)
    await screen.findByRole('textbox', { name: '你的回答' })
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked') })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('full') })
    await userEvent.setup().type(screen.getByRole('textbox', { name: '你的回答' }), '仍可输入')
    expect((screen.getByRole('textbox', { name: '你的回答' }) as HTMLTextAreaElement).value).toBe('仍可输入')
    page.unmount()
  })
}

it('keeps the saved session on a temporary restore failure and reconnects to its draft', async () => {
  const server = recoveryServer('question_practice')
  const user = userEvent.setup()
  const first = render(server.page)
  await user.type(await screen.findByRole('textbox', { name: '你的回答' }), '断网也应保留')
  first.unmount()
  server.sessionOffline = true
  render(server.page)
  const reconnect = await screen.findByRole('button', { name: '重新连接' })
  expect(localStorage.getItem('ia-qp-session')).toBe('s1')
  server.sessionOffline = false
  await user.click(reconnect)
  expect((await screen.findByRole('textbox', { name: '你的回答' }) as HTMLTextAreaElement).value).toBe('断网也应保留')
})

it('does not reopen a question session when an old evaluation poll completes after leaving', async () => {
  const server = recoveryServer('question_practice')
  const user = userEvent.setup()
  let complete!: (result: unknown) => void
  const job = new Promise(resolve => { complete = resolve })
  server.operation = () => job
  server.view = { ...server.view, phase: 'evaluating', available_actions: [], submissions: [{ id: 'a1', turn_id: 'turn-1', client_submission_id: 'key', disposition: 'answered', answer_text: '已保存回答', status: 'saved', job_id: 'job-1' }] }
  render(server.page)
  await user.click(await screen.findByRole('button', { name: '返回练习入口' }))
  await act(async () => { complete({ job_id: 'job-1', status: 'succeeded' }) })
  expect(await screen.findByRole('heading', { name: '试题练习' })).toBeTruthy()
  expect(screen.queryByRole('button', { name: '返回练习入口' })).toBeNull()
})
