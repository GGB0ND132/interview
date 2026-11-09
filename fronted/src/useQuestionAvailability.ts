import { useEffect, useMemo, useState } from 'react'
import { ApiError } from './api'
import type { Availability, Difficulty, PracticeApi, PracticeMode } from './api'

export function useQuestionAvailability(api: PracticeApi, packId: string, mode: PracticeMode, difficulty: Difficulty, focus: string) {
  const [revision, setRevision] = useState(0)
  const key = useMemo(() => ({ packId, mode, difficulty, focus, revision }), [packId, mode, difficulty, focus, revision])
  const [result, setResult] = useState<{ key: typeof key; data: Availability | null; error: string } | null>(null)
  useEffect(() => {
    if (!packId) return
    let cancelled = false
    void api.availability(packId, {
      mode, difficulty, ...(focus ? { focus_competency_ids: [focus] } : {}),
    }).then(data => {
      if (!cancelled) setResult({ key, data, error: '' })
    }).catch((failure: unknown) => {
      if (!cancelled) setResult({ key, data: null, error: failure instanceof ApiError ? failure.message : '无法查询题库可用性，请重试' })
    })
    return () => { cancelled = true }
  }, [api, packId, mode, difficulty, focus, key])
  return {
    availability: result?.key === key ? result.data : null,
    availabilityError: result?.key === key ? result.error : '',
    refreshAvailability: () => setRevision(value => value + 1),
  }
}
