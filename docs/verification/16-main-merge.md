# Ticket 16 local main merge verification

Date: 2026-11-13

## Inputs and preservation

- Original main: `dab3ebb8de5ea3d615734a811a652b88ecf48b72`.
- Source `GGB0ND132/16`: `d034d68eabc055f07bbd3b225e2d815d94e48e6b`.
- Backup: `backup/main-before-16-20261113` points to original main.
- Existing completed issue record was saved unchanged in `0abec82` before merging; it remains unchanged by the merge.
- Both inputs are integrated through a two-parent merge on local main. No push, branch deletion or worktree deletion was performed.

## Resolution

Two conflict regions in `fronted/src/QuestionPractice.tsx` combined ticket 16 draft synchronization with main's `api` prop required by problem reporting. Both behaviors are retained. The obsolete `TurnKey` type was removed as in ticket 16.

`MockInterview.tsx` merged automatically, preserving JD setup and reporting while adopting the shared draft hook. Backend application code and migrations, schema 8, ticket 15 recovery/lease handling, API types, JD components, citation display and interview report components remain unchanged from original main. The new hook, draft tests and acceptance script match the source branch.

The staged tree retains all 261 original main paths and all 224 source branch paths: zero missing paths and zero deletions. Conflict entries and conflict markers were checked; none remain.

The preexisting untracked `docs/verification/05-main-merge-http.json` is excluded from the merge and retains SHA256 `0784FF4073E91F5A041AFFC7FAA416B0E94E9E53833B3F7B24E2B90D761C14DF`. The source worktree remains clean.

## Fresh checks on the merged tree

- Frontend `npm test`: 53 passed across 4 files (11 draft recovery, 20 question practice, 18 mock interview, 4 API); 29.90 seconds.
- Frontend `npm run lint`: passed.
- Frontend `npm run build`: passed, including TypeScript compilation and production build.
- Backend `uv run --locked pytest -q`: 203 passed in 93.92 seconds. One dependency deprecation warning from Starlette's httpx test client.
- Backend `uv run --locked mypy`: passed, 18 source files.
- Backend `uv run --locked ruff check .`: passed.
- Backend `uv run --locked ruff format --check .`: passed, 53 Python files.
- `git diff --cached --check`: passed; `git ls-files -u`: empty.

No fresh browser acceptance, paid model calls or persistent database changes were performed for this merge. The source branch's browser verification and independent review records are preserved as prior ticket evidence; they were not rerun here.
