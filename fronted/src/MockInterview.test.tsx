import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { createPracticeApi } from './api'
import MockInterview from './MockInterview'

const opening = { id: 't1', group_id: 'g1', question_code: 'INTRO', question_version: 1, kind: 'main', question_type: 'introduction', stage: 'introduction', topic: '开场', competency_id: 'introduction', text: '请介绍你的学习经历。' }
const followup = { ...opening, id: 't2', kind: 'followup', text: '你提到接口校验，可以举一个具体例子吗？' }
const coverage = [{ competency_id: 'introduction', status: 'unobserved', group_ids: [], answer_quotes: [], unresolved: [] }]
const active = { session_id: 's1', mode: 'mock_interview', pack_id: 'agent', pack_version: 1, pack_title: 'Agent 基础档', created_at: '2026-11-12T00:00:00Z', difficulty: 'easy', revision: 1, status: 'active', phase: 'awaiting_answer', current_turn: opening, turns: [opening], submissions: [], available_actions: ['answer', 'skip', 'finish'], coverage, plan: { selected_topics: ['tools', 'planning', 'memory'], max_main_questions: 12, max_turns: 36, questions: [{ code: 'INTRO', version: 1, stage: 'introduction', topic: '开场', competency_id: 'introduction', prompt: opening.text }] } }
const submission = { id: 'a1', turn_id: 't1', client_submission_id: 'key', disposition: 'answered', answer_text: '我负责接口校验', status: 'completed', job_id: 'j1', score: 91, feedback: { reference_answer: '不能在进行中展示的参考答案', overall_score: 91 } }

function server(routes: (path: string, body: Record<string, unknown>) => unknown | Promise<unknown>) {
  const calls: { path: string; body: Record<string, unknown> }[] = []
  const api = createPracticeApi({ fetchImpl: vi.fn(async (input, init) => {
    const path = String(input).replace('/api/v1', '')
    const body = init?.body ? JSON.parse(String(init.body)) : {}
    calls.push({ path, body })
    let data: unknown
    if (path === '/role-packs') data = { items: [{ id: 'agent', title: 'Agent 基础档', status: 'published', version: 1 }] }
    else if (path.endsWith('/availability')) data = { can_start: true, available_count: 57, eligible_topic_count: 6, minimum_topic_count: 3, topics: [], stages: [], missing: [] }
    else if (path.startsWith('/sessions?')) data = { items: [], total: 0, page: 1, page_size: 20 }
    else data = await routes(path, body)
    return data instanceof Response ? data : new Response(JSON.stringify({ schema_version: '1.0', request_id: 'r1', data, error: null }))
  }) as typeof fetch })
  return { api, calls }
}

afterEach(() => { localStorage.clear(); vi.restoreAllMocks() })

it('starts a server interview, saves one answer and shows the returned follow-up without scores or answers', async () => {
  const user = userEvent.setup()
  const { api, calls } = server(path => {
    if (path === '/sessions') return { ...active, status: 'draft', phase: 'draft', revision: 0, available_actions: ['start'] }
    if (path.endsWith('/start')) return active
    if (path.endsWith('/answers')) return { session: { ...active, phase: 'evaluating', revision: 2, available_actions: [], submissions: [submission] }, submission, idempotent_replay: false }
    if (path === '/sessions/s1') return { ...active, revision: 3, current_turn: followup, turns: [opening, followup], submissions: [submission] }
    throw new Error(`Unexpected request: ${path}`)
  })
  render(<MockInterview api={api} />)
  await user.click(await screen.findByRole('button', { name: '开始模拟面试' }))
  await user.type(await screen.findByRole('textbox', { name: '你的回答' }), '我负责接口校验')
  await user.click(screen.getByRole('button', { name: '提交回答' }))
  expect(await screen.findByText(followup.text, {}, { timeout: 3000 })).toBeTruthy()
  expect(screen.getByText('我负责接口校验')).toBeTruthy()
  expect(screen.queryByText(/91|不能在进行中展示的参考答案/)).toBeNull()
  expect(calls.find(call => call.path === '/sessions')?.body).toMatchObject({ pack_id: 'agent', config: { mode: 'mock_interview', feedback_timing: 'after_session', difficulty: 'easy' } })
  expect(calls.filter(call => call.path.endsWith('/answers'))).toHaveLength(1)
  await waitFor(() => expect((screen.getByRole('button', { name: '提交回答' }) as HTMLButtonElement).disabled).toBe(true))
})

const partialReport = { session_id: 's1', status: 'ended_early', scoring_scope: 'mock_interview_training', completeness: 'partial', stop_reason: 'user_ended', stop_reason_detail: '用户提前结束，未完成部分不计分。', average_score: null, technical_average_score: null, answered_count: 0, blank_count: 0, skipped_count: 0, coverage, gaps: [{ ...coverage[0], reason: '尚未完成开场交流' }], groups: [], turns: [opening], limitations: ['本场仅覆盖所选技术主题'] }

it('pauses without losing the draft and requests an early partial report only after confirmation', async () => {
  const user = userEvent.setup()
  const { api, calls } = server(path => {
    if (path === '/sessions') return { ...active, phase: 'draft', revision: 0 }
    if (path.endsWith('/start')) return active
    if (path.endsWith('/finish')) return { ...active, status: 'ended_early', phase: 'feedback_ready', revision: 2, available_actions: [] }
    if (path.endsWith('/report')) return partialReport
    throw new Error(path)
  })
  render(<MockInterview api={api} />)
  await user.click(await screen.findByRole('button', { name: '开始模拟面试' }))
  await user.type(await screen.findByRole('textbox', { name: '你的回答' }), '保留我的草稿')
  await user.click(screen.getByRole('button', { name: '暂停面试' }))
  expect((screen.getByRole('textbox', { name: '你的回答' }) as HTMLTextAreaElement).disabled).toBe(true)
  await user.click(screen.getByRole('button', { name: '继续面试' }))
  expect((screen.getByRole('textbox', { name: '你的回答' }) as HTMLTextAreaElement).value).toBe('保留我的草稿')
  await user.click(screen.getByRole('button', { name: '结束面试' }))
  expect(calls.some(call => call.path.endsWith('/finish'))).toBe(false)
  await user.click(screen.getByRole('button', { name: '结束并生成报告' }))
  expect(await screen.findByRole('heading', { name: '部分面试报告' })).toBeTruthy()
  expect(screen.getByText('尚未完成开场交流')).toBeTruthy()
  expect(screen.getAllByText('未评价').length).toBeGreaterThan(0)
})

it('disables repeated actions while evaluating, reconciles a conflict, then advances using the server revision', async () => {
  const user = userEvent.setup()
  let resolveAnswer!: (value: unknown) => void
  const response = new Promise(resolve => { resolveAnswer = resolve })
  let saved = false
  const { api, calls } = server(path => {
    if (path === '/sessions') return { ...active, phase: 'draft', revision: 0 }
    if (path.endsWith('/start')) return active
    if (path.endsWith('/answers')) return response
    if (path === '/sessions/s1') return { ...active, revision: 4, phase: 'stage_transition', submissions: [submission], available_actions: ['next', 'finish'] }
    if (path.endsWith('/next') && !saved) {
      saved = true
      return new Response(JSON.stringify({ data: null, error: { code: 'STATE_CONFLICT', message: '会话版本已变化', retryable: false } }), { status: 409 })
    }
    if (path.endsWith('/next')) return { ...active, revision: 5, current_turn: { ...opening, id: 't3', stage: 'scenario', text: '在这个假设情境中，你会怎样处理工具超时？' }, turns: [opening, { ...opening, id: 't3', stage: 'scenario', text: '在这个假设情境中，你会怎样处理工具超时？' }], submissions: [submission] }
    throw new Error(path)
  })
  render(<MockInterview api={api} />)
  await user.click(await screen.findByRole('button', { name: '开始模拟面试' }))
  await user.type(await screen.findByRole('textbox', { name: '你的回答' }), '我负责接口校验')
  await user.dblClick(screen.getByRole('button', { name: '提交回答' }))
  expect(calls.filter(call => call.path.endsWith('/answers'))).toHaveLength(1)
  resolveAnswer({ session: { ...active, revision: 2, phase: 'evaluating', submissions: [submission], available_actions: [] }, submission })
  await waitFor(() => expect((screen.getByRole('button', { name: '结束面试' }) as HTMLButtonElement).disabled).toBe(true))
  await user.click(await screen.findByRole('button', { name: '继续下一组' }, { timeout: 3000 }))
  expect(await screen.findByText('会话版本已变化')).toBeTruthy()
  await user.click(screen.getByRole('button', { name: '继续下一组' }))
  expect(await screen.findByText('在这个假设情境中，你会怎样处理工具超时？')).toBeTruthy()
  expect(calls.filter(call => call.path.endsWith('/next')).at(-1)?.body).toEqual({ expected_revision: 4 })
})

it('restores a failed interview, retries its saved answer and completes candidate questions without inventing a score', async () => {
  localStorage.setItem('ia-mi-session', 's1')
  const user = userEvent.setup()
  const candidate = { ...opening, id: 't3', stage: 'candidate_questions', text: '你有什么问题想了解？' }
  let retried = false
  const { api, calls } = server(path => {
    if (path === '/sessions/s1') return { ...active, revision: retried ? 4 : 3, phase: retried ? 'stage_transition' : 'evaluation_failed', submissions: [{ ...submission, error: { message: '模型暂时不可用', code: 'PROVIDER_UNAVAILABLE', retryable: true } }], available_actions: retried ? ['next', 'finish'] : ['retry', 'finish'] }
    if (path.endsWith('/retry')) { retried = true; return { job_id: 'j2' } }
    if (path.endsWith('/next')) return { ...active, revision: 5, current_turn: candidate, turns: [opening, candidate], submissions: [submission] }
    if (path.endsWith('/answers')) return { session: { ...active, status: 'completed', phase: 'feedback_ready', revision: 6, available_actions: [] } }
    if (path.endsWith('/report')) return { ...partialReport, status: 'completed', completeness: 'complete', stop_reason: 'coverage_satisfied', stop_reason_detail: '本场所需材料均可评价', gaps: [] }
    throw new Error(path)
  })
  render(<MockInterview api={api} />)
  expect(await screen.findByText('模型暂时不可用')).toBeTruthy()
  expect(screen.getByText('我负责接口校验')).toBeTruthy()
  await user.click(screen.getByRole('button', { name: '重试评价' }))
  await user.click(await screen.findByRole('button', { name: '继续下一组' }))
  await user.click(await screen.findByRole('button', { name: '没有问题' }))
  expect(await screen.findByRole('heading', { name: '完整面试报告' })).toBeTruthy()
  expect(calls.find(call => call.path.endsWith('/retry'))?.body).toEqual({ expected_revision: 3 })
  expect(calls.find(call => call.path.endsWith('/answers'))?.body).toMatchObject({ disposition: 'no_questions', answer_text: '', turn_id: 't3', expected_revision: 5 })
})

it('keeps an uncertain submission locked until synchronization reveals the saved follow-up', async () => {
  localStorage.setItem('ia-mi-session', 's1')
  const user = userEvent.setup()
  let reads = 0
  const { api, calls } = server(path => {
    if (path === '/sessions/s1') {
      reads++
      if (reads === 1) return active
      if (reads === 2) throw new TypeError('network down')
      return { ...active, revision: 3, current_turn: followup, turns: [opening, followup], submissions: [submission] }
    }
    if (path.endsWith('/answers')) throw new TypeError('response lost')
    throw new Error(path)
  })
  render(<MockInterview api={api} />)
  await user.type(await screen.findByRole('textbox', { name: '你的回答' }), '我负责接口校验')
  await user.click(screen.getByRole('button', { name: '提交回答' }))
  await waitFor(() => expect((screen.getByRole('button', { name: '提交回答' }) as HTMLButtonElement).disabled).toBe(true))
  await user.click(await screen.findByRole('button', { name: '重新同步会话' }))
  expect(await screen.findByText(followup.text)).toBeTruthy()
  expect((screen.getByRole('textbox', { name: '你的回答' }) as HTMLTextAreaElement).value).toBe('')
  expect(calls.filter(call => call.path.endsWith('/answers'))).toHaveLength(1)
})
