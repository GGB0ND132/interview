export type Disposition = 'answered' | 'blank_answer' | 'skipped' | 'no_experience' | 'no_questions'
export type Phase = 'draft' | 'awaiting_answer' | 'evaluating' | 'feedback_ready' | 'evaluation_failed' | 'stage_transition'
export type Difficulty = 'easy' | 'medium' | 'hard'

export type PracticeConfig = {
  mode: 'question_practice'
  difficulty: Difficulty
  language?: 'zh-CN'
  question_types?: ['technical']
  focus_competency_ids?: string[]
}

export type InterviewConfig = {
  mode: 'mock_interview'
  difficulty: 'easy'
  feedback_timing: 'after_session'
  experience_mode: 'experience' | 'scenario'
  max_followups_per_question: number
}
export type InterviewStage = 'introduction' | 'experience' | 'scenario' | 'technical' | 'behavioral' | 'candidate_questions'
export type Coverage = {
  competency_id: string
  status: 'unobserved' | 'insufficient' | 'observed' | 'not_applicable'
  reason?: string
  unresolved: string[]
  group_ids: string[]
  answer_quotes: { group_id: string; quote: string }[]
}
export type PlannedQuestion = { code: string; version: number; stage: InterviewStage; topic: string; competency_id: string; prompt: string }

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
  kind: 'main' | 'followup'
  question_type: InterviewStage
  stage: InterviewStage
  group_id?: string
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
  status: 'draft' | 'active' | 'completed' | 'ended_early'
  phase: Phase
  current_turn: Turn | null
  submissions: Submission[]
  available_actions: string[]
  mode?: PracticeMode
  turns?: Turn[]
  coverage?: Coverage[]
  plan?: { selected_topics: string[]; max_main_questions: number; max_turns: number; questions: PlannedQuestion[] }
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
export type InterviewReport = Report & {
  completeness: 'complete' | 'partial'
  stop_reason: string
  stop_reason_detail: string
  technical_average_score: number | null
  coverage: Coverage[]
  gaps: Coverage[]
  groups: { id: string; question: PlannedQuestion; status: string; score: number | null; feedback: Feedback | null; submissions: Submission[] }[]
  turns: Turn[]
  limitations: string[]
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
    create: (packId: string, config: PracticeConfig | InterviewConfig) =>
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
    interviewReport: (sessionId: string) =>
      request<InterviewReport>(`/sessions/${encodeURIComponent(sessionId)}/report`),
    next: (sessionId: string, expectedRevision: number) =>
      request<SessionView>(`/sessions/${encodeURIComponent(sessionId)}/next`, {
        method: 'POST', body: JSON.stringify({ expected_revision: expectedRevision }),
      }),
    finish: (sessionId: string, expectedRevision: number) =>
      request<SessionView>(`/sessions/${encodeURIComponent(sessionId)}/finish`, {
        method: 'POST', body: JSON.stringify({ expected_revision: expectedRevision }),
      }),
    history: (page = 1, pageSize = 20) =>
      request<HistoryPage>(`/sessions?page=${page}&page_size=${pageSize}`),
  }
}

export type PracticeApi = ReturnType<typeof createPracticeApi>
