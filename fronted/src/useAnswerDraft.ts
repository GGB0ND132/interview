import { useCallback, useRef, useState } from 'react'
import type { PracticeApi, SessionView } from './api'

type AnswerRequest = Parameters<PracticeApi['submit']>[1]
type Draft = { text: string; pending?: AnswerRequest }

function draftKey(sessionId: string, turnId: string) {
  return `ia-answer-draft:${encodeURIComponent(sessionId)}:${encodeURIComponent(turnId)}`
}

function read(key: string): Draft {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(key) ?? 'null')
    if (value && typeof value === 'object' && 'text' in value && typeof value.text === 'string') {
      const draft = value as Draft
      return { text: draft.text.slice(0, 5000), pending: draft.pending }
    }
  } catch { /* Invalid or unavailable storage must not block practice. */ }
  return { text: '' }
}

function write(key: string, draft: Draft | null) {
  try {
    if (draft) localStorage.setItem(key, JSON.stringify(draft))
    else localStorage.removeItem(key)
  } catch { /* The in-memory draft remains usable when browser storage is full. */ }
}

// Only a server-accepted view chooses the draft identity or clears a saved answer.
export function useAnswerDraft() {
  const [answer, setText] = useState('')
  const current = useRef<{ key: string; draft: Draft } | null>(null)

  const restoreDraft = useCallback((view: SessionView) => {
    for (const submission of view.submissions) write(draftKey(view.session_id, submission.turn_id), null)
    const turn = view.current_turn
    const editable = turn && view.phase === 'awaiting_answer' && view.available_actions.includes('answer')
      && !view.submissions.some(item => item.turn_id === turn.id)
    const key = editable ? draftKey(view.session_id, turn.id) : null
    if (!key) {
      if (turn) write(draftKey(view.session_id, turn.id), null)
      current.current = null
      setText('')
    } else if (current.current?.key !== key) {
      const draft = read(key)
      current.current = { key, draft }
      setText(draft.text)
    }
  }, [])

  function setAnswer(text: string) {
    setText(text)
    if (current.current) {
      current.current.draft = { ...current.current.draft, text }
      write(current.current.key, current.current.draft)
    }
  }

  function answerRequest(view: SessionView, disposition: AnswerRequest['disposition'], text: string): AnswerRequest {
    const previous = current.current?.draft.pending
    if (previous && previous.turn_id === view.current_turn?.id && previous.expected_revision === view.revision
      && previous.disposition === disposition && previous.answer_text === text && typeof previous.client_submission_id === 'string') return previous
    const body: AnswerRequest = {
      turn_id: view.current_turn!.id, expected_revision: view.revision,
      client_submission_id: crypto.randomUUID(), disposition, answer_text: text,
    }
    if (current.current) {
      current.current.draft.pending = body
      write(current.current.key, current.current.draft)
    }
    return body
  }

  function detachDraft() {
    current.current = null
    setText('')
  }

  return { answer, setAnswer, restoreDraft, answerRequest, detachDraft }
}
