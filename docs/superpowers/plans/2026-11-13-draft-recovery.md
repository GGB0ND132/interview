# Ticket 16 draft recovery implementation plan

> Execute inline using the requested implement workflow; review Standards and Spec independently before the final commit.

**Goal:** Restore browser drafts for the server's current turn in both modes and recover failed operations without duplicate records.

**Architecture:** Keep server sessions authoritative. Share a small browser draft hook between the existing pages. Reconcile every accepted session, discard submitted drafts, and preserve the session pointer on transient failures. Reuse persisted submission identities for uncertain retries.

**Tech stack:** React, TypeScript, localStorage, Vitest, existing FastAPI/SQLite API.

**Spec:** `.scratch/agent-principles-demo/issues/16-frontend-draft-recovery.md` (authoritative copy supplied from the main checkout).

## Constraints and review focus

- Preserve existing layouts and after-session feedback visibility.
- Test through the existing rendered-page/API boundary in `DraftRecovery.test.tsx`.
- Cover changed turns/sessions, accepted submissions with lost responses, temporary restore outages, unavailable/corrupt browser storage, and concurrent clicks.
- Use isolated acceptance databases and a controlled model adapter for restart/failure scenarios.

## Tasks

- [x] Run the existing draft refresh test and observe failure; add shared draft storage and integrate both pages.
- [x] Add and run page regressions incrementally for stale draft isolation, submission cleanup, transient outages, pending submission identity, synchronization and retry.
- [x] Run focused tests and TypeScript checks during implementation; run full frontend/backend suites, lint and build at completion.
- [x] Use Playwright for both modes: refresh drafts, refresh saved answers, restart the backend, retry model failures, and verify one saved answer/result.
- [x] Review changes against initial HEAD `ae6b49f` with independent Standards/Spec agents; fix findings and synchronize both issue copies.
- [x] Commit verified work on the current branch.
