import { describe, expect, it } from 'vitest'
import { ApiError, createPracticeApi } from './api'

function envelope(data: unknown, error: unknown = null, status = 200) {
  return new Response(JSON.stringify({ schema_version: '1.0', request_id: 'request-1', data, error }), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

function recording(response: () => Response) {
  const calls: { url: string; init?: RequestInit }[] = []
  const fetchImpl = (async (url: string | URL | Request, init?: RequestInit) => {
    calls.push({ url: String(url), init })
    return response()
  }) as typeof fetch
  return { calls, fetchImpl }
}

describe('practice API client', () => {
  it('uploads a resume as multipart data and confirms only selected fragment IDs', async () => {
    const { calls, fetchImpl } = recording(() => envelope({ resume_id: 'resume1', status: 'needs_confirmation' }))
    const api = createPracticeApi({ fetchImpl })
    const file = new File(['resume'], 'resume.docx')
    await api.uploadResume(file)
    expect(calls[0].url).toBe('/api/v1/resumes')
    expect((calls[0].init?.body as FormData).get('file')).toBe(file)
    expect(new Headers(calls[0].init?.headers).has('content-type')).toBe(false)
    await api.confirmResume('resume1', 0, ['project-1'], false)
    expect(JSON.parse(String(calls[1].init?.body))).toEqual({ expected_revision: 0, fragment_ids: ['project-1'], no_project_experience: false })
  })
  it('unwraps the server envelope and returns the data payload', async () => {
    const { calls, fetchImpl } = recording(() => envelope([{ id: 'pack_agent', title: '包' }]))
    const api = createPracticeApi({ fetchImpl })
    await expect(api.packs()).resolves.toEqual([{ id: 'pack_agent', title: '包' }])
    expect(calls[0].url).toBe('/api/v1/role-packs')
  })

  it('posts the submission body and returns the server session', async () => {
    const { calls, fetchImpl } = recording(() =>
      envelope({ session: { session_id: 's1' }, submission: { id: 'a1' }, idempotent_replay: false }, null, 202),
    )
    const api = createPracticeApi({ fetchImpl })
    const result = await api.submit('s1', {
      turn_id: 't1',
      expected_revision: 1,
      client_submission_id: 'key-1',
      disposition: 'answered',
      answer_text: '我的回答',
    })
    expect(result.submission).toEqual({ id: 'a1' })
    expect(calls[0].url).toBe('/api/v1/sessions/s1/answers')
    expect(calls[0].init?.method).toBe('POST')
    expect(JSON.parse(String(calls[0].init?.body))).toMatchObject({
      client_submission_id: 'key-1',
      disposition: 'answered',
      answer_text: '我的回答',
    })
  })

  it('surfaces the server error code and retryability', async () => {
    const { fetchImpl } = recording(() =>
      envelope(null, { code: 'STATE_CONFLICT', message: '当前题目、状态或会话版本已变化', retryable: false }, 409),
    )
    const api = createPracticeApi({ fetchImpl })
    const failure = await api.session('s1').catch((error: unknown) => error)
    expect(failure).toBeInstanceOf(ApiError)
    expect(failure).toMatchObject({
      code: 'STATE_CONFLICT',
      retryable: false,
      message: '当前题目、状态或会话版本已变化',
    })
  })

  it('turns a network failure into a retryable error', async () => {
    const fetchImpl = (async () => {
      throw new TypeError('fetch failed')
    }) as unknown as typeof fetch
    const api = createPracticeApi({ fetchImpl })
    const failure = await api.session('s1').catch((error: unknown) => error)
    expect(failure).toBeInstanceOf(ApiError)
    expect(failure).toMatchObject({ code: 'NETWORK_ERROR', retryable: true })
  })
})
