import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import QuestionPractice from './QuestionPractice'
import { createPracticeApi } from './api'
import type {
  Availability,
  Feedback,
  HistoryPage,
  Job,
  Pack,
  PracticeApi,
  SessionView,
  Submission,
  Turn,
} from './api'

const PACK: Pack = {
  id: 'pack_agent_basics_sample',
  title: 'Agent 原理与系统基础档（演示样题）',
  status: 'published',
  version: 1,
}

const TURN: Turn = {
  id: 'turn-1',
  question_code: 'Q-AGENT-SAMPLE-01',
  question_version: 1,
  kind: 'main',
  question_type: 'technical',
  stage: 'technical',
  topic: '工具调用',
  competency_id: 'agent_tool_calling',
  text: 'Agent 如何根据工具执行结果继续任务？为什么要有停止条件？',
}

const FEEDBACK: Feedback = {
  dimensions: [
    { name: 'accuracy', score: 80, reason: '说明模型读取真实工具结果', answer_quote: '工具返回的结果' },
    { name: 'completeness', score: 65, reason: '停止条件说明较短', answer_quote: '最大迭代次数' },
    { name: 'relevance', score: 90, reason: '直接回答问题', answer_quote: '根据工具返回的结果' },
    { name: 'structure', score: 70, reason: '顺序清楚', answer_quote: '然后' },
    { name: 'specificity', score: 60, reason: '可补充一个具体例子', answer_quote: '最大迭代次数' },
  ],
  strengths: ['区分了模型决策和程序执行'],
  improvements: ['补充失败后的纠错流程'],
  overall_score: 74,
  assessment_coverage: 1,
  assessment_status: 'complete',
  rubric_version: 'technical_v1',
  limitations: [],
  reference_answer: '模型决定下一步工具，程序执行并返回真实结果；达到完成或失败边界时停止。',
}

const ANSWER = '模型先决定调用哪个工具，程序执行后把工具返回的结果交回模型，然后根据真实结果决定下一步。'

function draft(): SessionView {
  return {
    session_id: 's1',
    pack_id: PACK.id,
    pack_version: 1,
    pack_title: PACK.title,
    created_at: '2026-11-09T10:00:00.000Z',
    difficulty: 'easy',
    revision: 0,
    status: 'draft',
    phase: 'draft',
    current_turn: null,
    submissions: [],
    available_actions: ['start'],
  }
}

function awaiting(): SessionView {
  return {
    ...draft(),
    revision: 1,
    status: 'active',
    phase: 'awaiting_answer',
    current_turn: TURN,
    available_actions: ['answer', 'skip'],
  }
}

function submission(overrides: Partial<Submission> = {}): Submission {
  return {
    id: 'a1',
    turn_id: TURN.id,
    client_submission_id: 'submission-key',
    disposition: 'answered',
    answer_text: ANSWER,
    status: 'saved',
    job_id: 'job-1',
    ...overrides,
  }
}

function evaluating(): SessionView {
  return {
    ...awaiting(),
    revision: 2,
    phase: 'evaluating',
    submissions: [submission()],
    available_actions: [],
  }
}

function ready(overrides: Partial<Submission> = {}): SessionView {
  return {
    ...evaluating(),
    revision: 3,
    status: 'completed',
    phase: 'feedback_ready',
    submissions: [submission({ status: 'completed', score: 74, feedback: FEEDBACK, ...overrides })],
  }
}

function failed(): SessionView {
  return {
    ...evaluating(),
    revision: 3,
    phase: 'evaluation_failed',
    submissions: [
      submission({
        status: 'failed',
        error: { code: 'MODEL_TIMEOUT', message: '模型请求超时，回答已保留', retryable: true },
      }),
    ],
    available_actions: ['retry'],
  }
}

const AVAILABILITY: Availability = {
  pack_id: PACK.id,
  mode: 'question_practice',
  available_count: 2,
  can_start: true,
  missing: [],
  topics: [],
}

const HISTORY: HistoryPage = { items: [awaiting()], page: 1, page_size: 10, total: 1 }

function fakeApi() {
  return {
    ...createPracticeApi(),
    packs: vi.fn<PracticeApi['packs']>(async () => ({ items: [PACK] })),
    availability: vi.fn<PracticeApi['availability']>(async () => AVAILABILITY),
    create: vi.fn<PracticeApi['create']>(async () => draft()),
    start: vi.fn<PracticeApi['start']>(async () => awaiting()),
    session: vi.fn<PracticeApi['session']>(async () => ready()),
    submit: vi.fn<PracticeApi['submit']>(async () => ({ session: evaluating(), submission: submission(), idempotent_replay: false })),
    retry: vi.fn<PracticeApi['retry']>(async () => ({ job_id: 'job-1' })),
    job: vi.fn<PracticeApi['job']>(async () => ({ job_id: 'job-1', status: 'succeeded', phase: 'evaluation', result_entity_id: 'a1', error: null })),
    report: vi.fn<PracticeApi['report']>(async () => ({ session_id: 's1', average_score: null, answered_count: 0, blank_count: 0, skipped_count: 0, status: 'active', scoring_scope: 'single_question_training' })),
    history: vi.fn<PracticeApi['history']>(async () => HISTORY),
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

async function startQuestion(user: ReturnType<typeof userEvent.setup>) {
  const draw = await screen.findByRole('button', { name: '随机抽一题' }) as HTMLButtonElement
  await waitFor(() => expect(draw.disabled).toBe(false))
  await user.click(draw)
  await screen.findByText(TURN.text)
}

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('question practice page', () => {
  it('filters by server topics and blocks starting when that topic has no published question', async () => {
    const api = fakeApi()
    api.availability.mockImplementation(async (_pack, config) => ({
      ...AVAILABILITY,
      available_count: config.focus_competency_ids?.length ? 0 : 2,
      can_start: !config.focus_competency_ids?.length,
      missing: config.focus_competency_ids?.length ? ['published_question'] : [],
      topics: [
        { topic: '工具调用', competency_id: 'agent_tool_calling', available_count: 2, interview_count: 2 },
        { topic: '记忆系统', competency_id: 'agent_memory', available_count: 0, interview_count: 0 },
      ],
    }))
    const user = userEvent.setup()
    render(<QuestionPractice api={api} />)
    await screen.findByRole('option', { name: '记忆系统（0 道）' })
    await user.selectOptions(screen.getByLabelText('练习主题'), 'agent_memory')
    await screen.findByText('当前筛选没有可评分的已发布题目')
    expect((screen.getByRole('button', { name: '随机抽一题' }) as HTMLButtonElement).disabled).toBe(true)
    expect(api.create).not.toHaveBeenCalled()
  })

  it('shows missing interview stages from the server and prevents starting the unfinished flow', async () => {
    const api = fakeApi()
    api.availability.mockImplementation(async (_pack, config) => config.mode === 'question_practice' ? AVAILABILITY : {
      ...AVAILABILITY, mode: 'mock_interview', can_start: false,
      eligible_topic_count: 2, minimum_topic_count: 3,
      missing: ['introduction', 'technical_topics', 'mock_interview_flow'],
      stages: [
        { id: 'introduction', label: '开场', available_count: 0, ready: false },
        { id: 'technical_topics', label: '技术', available_count: 2, ready: false },
      ],
    })
    const user = userEvent.setup()
    render(<QuestionPractice api={api} />)
    await screen.findByRole('button', { name: '随机抽一题' })
    await user.click(screen.getByRole('radio', { name: '模拟面试' }))
    await screen.findByText('可覆盖 2 个技术主题，至少需要 3 个。')
    expect(screen.getByText('缺少已发布题（0 道）')).not.toBeNull()
    expect(screen.getByText(/不会临时生成主问题补齐/)).not.toBeNull()
    expect((screen.getByRole('button', { name: '开始模拟面试' }) as HTMLButtonElement).disabled).toBe(true)
    expect(api.create).not.toHaveBeenCalled()
  })

  it('rejects late counts and rechecks a previous filter before enabling start', async () => {
    const api = fakeApi()
    const medium = deferred<Availability>()
    const easyAgain = deferred<Availability>()
    api.availability.mockResolvedValueOnce(AVAILABILITY)
      .mockReturnValueOnce(medium.promise).mockReturnValueOnce(easyAgain.promise)
    const user = userEvent.setup()
    render(<QuestionPractice api={api} />)
    await screen.findByText((_, el) => el?.tagName === 'P' && el.textContent === '2 道可抽')
    await user.click(screen.getByRole('radio', { name: '进阶' }))
    await user.click(screen.getByRole('radio', { name: '基础' }))
    expect((screen.getByRole('button', { name: '随机抽一题' }) as HTMLButtonElement).disabled).toBe(true)
    await act(async () => { medium.resolve({ ...AVAILABILITY, available_count: 99 }) })
    expect(screen.queryByText('99')).toBeNull()
    await act(async () => { easyAgain.resolve({ ...AVAILABILITY, available_count: 0, can_start: false, missing: ['published_question'] }) })
    await screen.findByText('当前筛选没有可评分的已发布题目')
    expect((screen.getByRole('button', { name: '随机抽一题' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('refreshes after a question is disabled and keeps start blocked until a failed refresh recovers', async () => {
    const api = fakeApi()
    api.availability.mockResolvedValueOnce(AVAILABILITY)
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({ ...AVAILABILITY, available_count: 0, can_start: false, missing: ['published_question'] })
    const user = userEvent.setup()
    render(<QuestionPractice api={api} />)
    await screen.findByText((_, el) => el?.tagName === 'P' && el.textContent === '2 道可抽')
    await user.click(screen.getByRole('button', { name: '刷新可用性' }))
    await screen.findByText('题库可用性查询失败')
    expect((screen.getByRole('button', { name: '随机抽一题' }) as HTMLButtonElement).disabled).toBe(true)
    await user.click(screen.getByRole('button', { name: '刷新可用性' }))
    await screen.findByText('当前筛选没有可评分的已发布题目')
    expect(screen.queryByText('题库可用性查询失败')).toBeNull()
    expect((screen.getByRole('button', { name: '随机抽一题' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('rechecks the selected pack instead of showing the previous pack count', async () => {
    const api = fakeApi()
    const next = deferred<Availability>()
    api.packs.mockResolvedValue({ items: [PACK, { ...PACK, id: 'second', title: '第二题包' }] })
    api.availability.mockResolvedValueOnce(AVAILABILITY).mockReturnValueOnce(next.promise)
    const user = userEvent.setup()
    render(<QuestionPractice api={api} />)
    await screen.findByText((_, el) => el?.tagName === 'P' && el.textContent === '2 道可抽')
    await user.selectOptions(screen.getByLabelText('岗位包'), 'second')
    expect((screen.getByRole('button', { name: '随机抽一题' }) as HTMLButtonElement).disabled).toBe(true)
    await act(async () => { next.resolve({ ...AVAILABILITY, pack_id: 'second', available_count: 0, can_start: false }) })
    await screen.findByText('当前筛选没有可评分的已发布题目')
    expect(screen.queryByText((_, el) => el?.tagName === 'P' && el.textContent === '2 道可抽')).toBeNull()
  })

  it('reads the available question count from the server instead of fixed demo content', async () => {
    const api = fakeApi()
    render(<QuestionPractice api={api} />)
    expect(await screen.findByText((_, element) => element?.tagName === 'P' && element.textContent === '2 道可抽')).not.toBeNull()
    expect(screen.queryByText('如何设计一个可靠的缓存更新策略？')).toBeNull()
    expect(api.availability).toHaveBeenCalledWith(
      PACK.id,
      expect.objectContaining({ mode: 'question_practice', difficulty: 'easy' }),
    )
  })

  it('shows a server-drawn question, then processing, then immediate feedback from the server', async () => {
    const api = fakeApi()
    const user = userEvent.setup()
    const jobResult = deferred<Job>()
    let finished = false
    api.job.mockImplementation(() => jobResult.promise)
    api.session.mockImplementation(async () => (finished ? ready() : evaluating()))
    render(<QuestionPractice api={api} />)
    await startQuestion(user)

    await user.type(screen.getByLabelText('你的回答'), ANSWER)
    await user.click(screen.getByRole('button', { name: '提交回答' }))

    expect((await screen.findByRole('status')).textContent).toContain('回答已保存，正在生成反馈')
    expect(api.submit).toHaveBeenCalledWith(
      's1',
      expect.objectContaining({
        turn_id: TURN.id,
        expected_revision: 1,
        disposition: 'answered',
        answer_text: ANSWER,
      }),
    )
    expect(screen.getByText(ANSWER)).not.toBeNull()

    finished = true
    await act(async () => jobResult.resolve({ job_id: 'job-1', status: 'succeeded', phase: 'evaluation', result_entity_id: 'a1', error: null }))

    expect(await screen.findByText('74')).not.toBeNull()
    expect(screen.getByText('准确性')).not.toBeNull()
    expect(screen.getByText('区分了模型决策和程序执行')).not.toBeNull()
    expect(screen.getByText('补充失败后的纠错流程')).not.toBeNull()
    expect(screen.getByText(/准确性 35%/)).not.toBeNull()
  })

  it('records a blank submission as zero with its scoring explanation and never calls the model', async () => {
    const api = fakeApi()
    const user = userEvent.setup()
    api.submit.mockImplementation(async () => ({
      session: {
        ...awaiting(),
        revision: 2,
        status: 'completed',
        phase: 'feedback_ready',
        submissions: [submission({ disposition: 'blank_answer', answer_text: '', status: 'completed', job_id: null, score: 0 })],
        available_actions: [],
      },
      submission: submission({ disposition: 'blank_answer', answer_text: '', status: 'completed', job_id: null, score: 0 }),
      idempotent_replay: false,
    }))
    render(<QuestionPractice api={api} />)
    await startQuestion(user)

    await user.click(screen.getByRole('button', { name: '空白提交' }))

    expect(api.submit).toHaveBeenCalledWith(
      's1',
      expect.objectContaining({ disposition: 'blank_answer', answer_text: '' }),
    )
    expect(await screen.findByText('0')).not.toBeNull()
    expect(screen.getByText(/空白提交记为 0 分，计入均分/)).not.toBeNull()
    expect(api.job).not.toHaveBeenCalled()
  })

  it('records a deliberate skip with no score and explains it is excluded from the average', async () => {
    const api = fakeApi()
    const user = userEvent.setup()
    api.submit.mockImplementation(async () => ({
      session: {
        ...awaiting(),
        revision: 2,
        status: 'completed',
        phase: 'feedback_ready',
        submissions: [submission({ disposition: 'skipped', answer_text: '', status: 'completed', job_id: null, score: undefined })],
        available_actions: [],
      },
      submission: submission({ disposition: 'skipped', answer_text: '', status: 'completed', job_id: null, score: undefined }),
      idempotent_replay: false,
    }))
    render(<QuestionPractice api={api} />)
    await startQuestion(user)

    await user.click(screen.getByRole('button', { name: '跳过本题' }))

    expect(api.submit).toHaveBeenCalledWith('s1', expect.objectContaining({ disposition: 'skipped', answer_text: '' }))
    expect(await screen.findByText('已跳过')).not.toBeNull()
    expect(screen.getByText(/跳过不计分，也不进入均分/)).not.toBeNull()
  })

  it('restores the saved answer and feedback after a refresh without resubmitting', async () => {
    const api = fakeApi()
    localStorage.setItem('ia-qp-session', 's1')
    api.session.mockImplementation(async (id: string) => {
      expect(id).toBe('s1')
      return ready()
    })
    render(<QuestionPractice api={api} />)

    expect(await screen.findByText(ANSWER)).not.toBeNull()
    expect(screen.getByText('74')).not.toBeNull()
    expect(api.submit).not.toHaveBeenCalled()
    expect(api.create).not.toHaveBeenCalled()
  })

  it('keeps a failed answer and retries the same saved submission', async () => {
    const api = fakeApi()
    const user = userEvent.setup()
    let attempt = 0
    api.session.mockImplementation(async () => {
      attempt += 1
      return attempt === 1 ? failed() : ready()
    })
    api.job.mockResolvedValue({ job_id: 'job-1', status: 'failed', phase: 'evaluation', result_entity_id: null, error: { code: 'MODEL_TIMEOUT', message: '模型请求超时，回答已保留', retryable: true } })
    render(<QuestionPractice api={api} />)
    await startQuestion(user)

    await user.type(screen.getByLabelText('你的回答'), ANSWER)
    await user.click(screen.getByRole('button', { name: '提交回答' }))

    expect(await screen.findByText('模型请求超时，回答已保留')).not.toBeNull()
    expect(screen.getByText(ANSWER)).not.toBeNull()
    await user.click(screen.getByRole('button', { name: '重试评价' }))
    expect(api.retry).toHaveBeenCalledWith('s1', 3)
    expect(await screen.findByText('74')).not.toBeNull()
  })

  it('can draw a new question after returning from a refreshed session', async () => {
    const api = fakeApi()
    const user = userEvent.setup()
    localStorage.setItem('ia-qp-session', 's1')
    render(<QuestionPractice api={api} />)
    expect(await screen.findByText('74')).not.toBeNull()

    await user.click(screen.getByRole('button', { name: '返回练习入口' }))
    const draw = await screen.findByRole<HTMLButtonElement>('button', { name: '随机抽一题' })
    await waitFor(() => expect(draw.disabled).toBe(false))
  })

  it('renders actions from the server available actions instead of the phase alone', async () => {
    const api = fakeApi()
    const user = userEvent.setup()
    let calls = 0
    api.session.mockImplementation(async () => {
      calls += 1
      return calls === 1 ? { ...awaiting(), available_actions: [] } : awaiting()
    })
    localStorage.setItem('ia-qp-session', 's1')
    render(<QuestionPractice api={api} />)

    expect(await screen.findByText(TURN.text)).not.toBeNull()
    expect(screen.queryByLabelText('你的回答')).toBeNull()
    expect(screen.queryByRole('button', { name: '跳过本题' })).toBeNull()
    expect(screen.queryByRole('button', { name: '提交回答' })).toBeNull()
    await user.click(screen.getByRole('button', { name: '返回练习入口' }))
    await user.click(await screen.findByRole('button', { name: '随机抽一题' }))
    expect(await screen.findByLabelText('你的回答')).not.toBeNull()
  })

  it('stops polling a job that never finishes and tells the user the answer is saved', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const api = fakeApi()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    api.job.mockResolvedValue({ job_id: 'job-1', status: 'running', phase: 'evaluation', result_entity_id: null, error: null })
    render(<QuestionPractice api={api} />)
    await startQuestion(user)
    await user.type(screen.getByLabelText('你的回答'), ANSWER)
    await user.click(screen.getByRole('button', { name: '提交回答' }))

    await act(async () => {
      await vi.advanceTimersByTimeAsync(151_000)
    })
    expect(api.job.mock.calls.length).toBeLessThan(1000)
    expect(await screen.findByText(/评价仍在排队或运行，回答已经保存/)).not.toBeNull()
    expect(screen.getByText(ANSWER)).not.toBeNull()
  })

  it('shows the saved server record when a submit response is lost after the answer was stored', async () => {
    const api = fakeApi()
    const user = userEvent.setup()
    api.submit.mockRejectedValue(new Error('connection reset'))
    api.session.mockImplementation(async () => ready())
    render(<QuestionPractice api={api} />)
    await startQuestion(user)
    await user.type(screen.getByLabelText('你的回答'), ANSWER)
    await user.click(screen.getByRole('button', { name: '提交回答' }))

    expect(await screen.findByText('74')).not.toBeNull()
    expect(screen.getAllByText(ANSWER)).toHaveLength(1)
  })

  it('sends only one submission when the submit button is clicked repeatedly', async () => {
    const api = fakeApi()
    const user = userEvent.setup()
    const pending = deferred<Awaited<ReturnType<PracticeApi['submit']>>>()
    api.submit.mockImplementation(() => pending.promise)
    render(<QuestionPractice api={api} />)
    await startQuestion(user)
    await user.type(screen.getByLabelText('你的回答'), ANSWER)

    const button = screen.getByRole('button', { name: '提交回答' })
    await user.click(button)
    await user.click(button)

    expect(api.submit).toHaveBeenCalledTimes(1)
    await act(async () => pending.reject(new Error('stop')))
  })
})
