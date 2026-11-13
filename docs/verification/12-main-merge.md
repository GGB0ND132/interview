# Ticket 12 local main merge verification

Date: 2026-11-14 (Asia/Shanghai).

## Inputs and preservation

- Original main: `f24d621156593f03dda149b859e3618305dd6245`.
- Source `GGB0ND132/12`: `0a27da8b886982e23569b680bb9b0c0c62d1dae7`.
- Backup `backup/main-before-12-20261114` points to original main.
- The existing completed ticket 12 issue record matches the source branch and was saved unchanged in `e3a1749788c6d4c75a21d5b51e523fcf1c9d00b2` before merging.
- Integration uses a two-parent local main merge. No push, branch deletion or worktree deletion was performed.

## Integration result

The source branch was based on original main. The merge completed without conflicts, and its staged tree matched the source branch exactly before this verification record was added.

Ticket 12 adds optional resume upload, project preview and confirmation, text correction and paste fallback, an explicit no-project branch, and server snapshot source display during interviews and reports. Existing JD preparation, citations, problem reporting, draft recovery and retry behavior are retained. Backend code, migrations and dependencies are unchanged.

All 268 tracked paths from original main and all 274 tracked paths from the source branch remain present, with zero missing paths and zero deletions. No unresolved index entries or conflict markers remain. The saved completed issue record remains unchanged. The source worktree is clean.

The preexisting untracked `docs/verification/05-main-merge-http.json` is excluded from commits and retains SHA256 `0784FF4073E91F5A041AFFC7FAA416B0E94E9E53833B3F7B24E2B90D761C14DF`.

## Fresh checks on the merged tree

- Frontend `npm test -- --reporter=dot`: 61 tests passed across 5 files in 33.67 seconds (7 resume preparation, 11 draft recovery, 20 question practice, 18 mock interview and 5 API).
- Frontend `npm run lint`: passed.
- Frontend `npm run build`: passed, including TypeScript compilation and production build.
- Backend `uv run --locked pytest -q`: 203 passed in 97.99 seconds. One existing dependency deprecation warning from Starlette's httpx test client.
- Backend `uv run --locked mypy`: passed, 18 source files.
- Backend `uv run --locked ruff check .`: passed.
- Backend `uv run --locked ruff format --check .`: passed, 53 files.
- `git diff --cached --check`: passed; `git ls-files -u`: empty.

No new browser acceptance, paid model calls or persistent database changes were performed for this merge. Source branch browser and independent review records are preserved in `12-frontend-resume-confirmation.md` and `12-code-review.md` as prior ticket evidence; they were not rerun here.
