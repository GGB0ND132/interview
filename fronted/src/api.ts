export type Disposition = 'answered' | 'blank_answer' | 'skipped'
export type Phase = 'draft' | 'awaiting_answer' | 'evaluating' | 'feedback_ready' | 'evaluation_failed'
export type Difficulty = 'easy' | 'medium' | 'hard'

export type PracticeConfig = {
  mode: 'question_practice'
  difficulty: Difficulty
  language?: 'zh-CN'
  question_types?: ['technical']
  focus_competency_ids?: string[]
}

export type Dimension = {
  name: 'accuracy' | 'completeness' | 'relevance' | 'structure' | 'specificity'
  score: number | null
  reason: string
  answer_quote: string
}

export type Feedback = {
  dimensions: Dimension[]
  strengths: string[]
  improvements: string[]
  overall_score: number | null
  assessment_coverage: number
  assessment_status: 'complete' | 'partial' | 'insufficient'
  rubric_version: string
  limitations: string[]
  reference_answer?: string
  answer_origin?: string
  question_source?: Record<string, unknown>
  independent_references?: { title: string; url: string; publisher?: string; heading?: string }[]
  requested_model?: string
  [key: string]: unknown
}

export type Submission = {
  id: string
  turn_id: string
  client_submission_id: string
  disposition: Disposition
  answer_text: string
  status: 'saved' | 'completed' | 'failed'
  job_id: string | null
  score?: number | null
  feedback?: Feedback
  error?: { code: string; message: string; retryable: boolean }
}

export type Turn = {
  id: string
  question_code: string
  question_version: number
  kind: 'main'
  question_type: 'technical'
  stage: 'technical'
  topic: string
  competency_id: string
  text: string
}

export type SessionView = {
  session_id: string
  pack_id: string
  pack_version: number
  pack_title: string | null
  created_at: string
  difficulty: Difficulty
  revision: number
  status: 'draft' | 'active' | 'completed'
  phase: Phase
  current_turn: Turn | null
  submissions: Submission[]
  available_actions: string[]
}

export type Pack = { id: string; title: string; status: string; version: number }
export type Availability = {
  pack_id: string
  mode: string
  available_count: number
  can_start: boolean
  missing: string[]
  topics: { topic: string; competency_id: string; available_count: number; interview_count: number }[]
  stages?: { id: string; label: string; available_count: number; ready: boolean }[]
  eligible_topic_count?: number
  minimum_topic_count?: number
}
export type PracticeMode = 'question_practice' | 'mock_interview'
export type AvailabilityConfig = Omit<PracticeConfig, 'mode'> & { mode: PracticeMode }
export type HistoryPage = { items: SessionView[]; page: number; page_size: number; total: number }
export type Job = {
  job_id: string
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  phase: string
  result_entity_id: string | null
  error: { code: string; message: string; retryable: boolean } | null
}
export type Report = {
  session_id: string
  average_score: number | null
  answered_count: number
  blank_count: number
  skipped_count: number
  status: SessionView['status']
  scoring_scope: string
}
export type SubmitResult = {
  session: SessionView
  submission: Submission
  idempotent_replay: boolean
}

export class ApiError extends Error {
  code: string
  retryable: boolean
  status: number

  constructor(code: string, message: string, retryable: boolean, status: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.retryable = retryable
    this.status = status
  }
}

type Envelope = { schema_version: string; request_id: string; data: unknown; error: unknown }

export function createPracticeApi(options: { baseUrl?: string; fetchImpl?: typeof fetch } = {}) {
  const baseUrl = (options.baseUrl ?? '/api/v1').replace(/\/$/, '')
  const fetchImpl = options.fetchImpl ?? ((...args) => fetch(...args))

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    let response: Response
    try {
      response = await fetchImpl(`${baseUrl}${path}`, {
        ...init,
        headers: { accept: 'application/json', ...(init.body ? { 'content-type': 'application/json' } : {}), ...init.headers },
      })
    } catch {
      throw new ApiError('NETWORK_ERROR', '无法连接练习服务，请确认后端已启动', true, 0)
    }
    let body: Envelope
    try {
      body = (await response.json()) as Envelope
    } catch {
      throw new ApiError('INVALID_RESPONSE', '练习服务返回了无法识别的响应', true, response.status)
    }
    if (!response.ok || body.error) {
      const error = (body.error ?? {}) as { code?: string; message?: string; retryable?: boolean }
      throw new ApiError(
        error.code ?? 'REQUEST_FAILED',
        error.message ?? '请求失败',
        error.retryable ?? false,
        response.status,
      )
    }
    return body.data as T
  }

  return {
    packs: () => request<{ items: Pack[] }>('/role-packs'),
    availability: (packId: string, config: AvailabilityConfig) =>
      request<Availability>(`/role-packs/${encodeURIComponent(packId)}/availability`, {
        method: 'POST',
        body: JSON.stringify(config),
      }),
    create: (packId: string, config: PracticeConfig) =>
      request<SessionView>('/sessions', {
        method: 'POST',
        body: JSON.stringify({ pack_id: packId, config }),
      }),
    start: (sessionId: string, expectedRevision: number) =>
      request<SessionView>(`/sessions/${encodeURIComponent(sessionId)}/start`, {
        method: 'POST',
        body: JSON.stringify({ expected_revision: expectedRevision }),
      }),
    session: (sessionId: string) =>
      request<SessionView>(`/sessions/${encodeURIComponent(sessionId)}`),
    submit: (
      sessionId: string,
      body: {
        turn_id: string
        expected_revision: number
        client_submission_id: string
        disposition: Disposition
        answer_text: string
      },
    ) =>
      request<SubmitResult>(`/sessions/${encodeURIComponent(sessionId)}/answers`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    retry: (sessionId: string, expectedRevision: number) =>
      request<{ job_id: string }>(`/sessions/${encodeURIComponent(sessionId)}/retry`, {
        method: 'POST',
        body: JSON.stringify({ expected_revision: expectedRevision }),
      }),
    job: (jobId: string) => request<Job>(`/jobs/${encodeURIComponent(jobId)}`),
    report: (sessionId: string) =>
      request<Report>(`/sessions/${encodeURIComponent(sessionId)}/report`),
    history: (page = 1, pageSize = 20) =>
      request<HistoryPage>(`/sessions?page=${page}&page_size=${pageSize}`),
  }
}

export type PracticeApi = ReturnType<typeof createPracticeApi>
