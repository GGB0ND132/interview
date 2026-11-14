# Ticket 17 local main merge verification

Date: 2026-11-14 (Asia/Shanghai).

## Inputs and preservation

- Original main: `6e2605746e7ad87304702670b8d8a9787c9675fd`.
- Source `GGB0ND132/17`: `8c82f142ab6d09bc622dfbc45ba51852a0e05862`.
- Backup: `backup/main-before-17-20261114`, pointing to original main.
- Existing completed ticket 17 record matched the latest source branch and was saved unchanged in `ad81ee7c86a4aa63b4a7327e05c1cf90dd8cfe45` before merging.
- Local two-parent merge only; no push, branch deletion or worktree deletion.

The merge completed without conflicts. Before adding this record, the index matched the latest source branch exactly. All 275 tracked paths from original main and all 300 source paths remain present: zero missing paths and zero deletions. There are no unresolved index entries. Frontend code and existing backend application behavior, schema and migrations are unchanged; additions cover acceptance tooling/evidence and recovery test stabilization.

The preexisting untracked `docs/verification/05-main-merge-http.json` remains excluded from commits, with SHA256 `0784FF4073E91F5A041AFFC7FAA416B0E94E9E53833B3F7B24E2B90D761C14DF`. Source worktree changes were not modified.

## Verification on the latest merged tree

- Frontend `npm test -- --reporter=dot`: 61 passed across 5 files, 31.93 seconds.
- Frontend `npm run lint`: passed.
- Frontend `npm run build`: passed, including TypeScript and Vite production build.
- Backend `uv run --locked pytest -q`: 206 passed in 98.10 seconds. One existing Starlette/httpx dependency deprecation warning.
- Backend `uv run --locked mypy`: passed, 19 source files.
- Backend `uv run --locked ruff check .`: passed.
- Backend `uv run --locked ruff format --check .`: passed, 58 files.
- Inventory and review artifact check: 115 unique inventory entries; 23 unique passed sample records; all sample digests match their published snapshots. Live availability consistency fields agree within the saved inventory. This checks saved evidence, not the current persistent database.
- `git diff --cached --check`: passed; `git ls-files -u`: empty.

## Interrupted attempt and latest updates

The earlier source `b7f9057` produced 204 passing backend tests and one failure in the existing killed-process recovery test: attempts was 3 rather than 2, while the job succeeded and only one answer was saved. The isolated test and all 19 recovery-module tests subsequently passed. The interrupted complete rerun had no retrievable final result and is not counted as a pass.

The source then advanced through `a1a25bc` and `8c82f14`. These include a deterministic recovery regression using a simulated scheduling delay, a normal lease for successful takeover, scorable inventory filtering for quarantine/topic pause, release records and final user confirmation. The fresh 206-test result above includes these updates; no production lease or fencing policy was changed by ticket 17.

An independent read-only merge review of the earlier `b7f9057` delta found no new actionable defects. Later source changes were inspected directly here, and the source's separate Standards/Spec follow-up and confirmation reviews are retained in `17-code-review.md`; these are distinct review scopes.

The latest completed issue record and user confirmation are preserved, including 23 passed samples, the sole-source GUI exception and intentionally empty remaining reviewer fields. Known scoring, follow-up factual-premise and JD mapping limitations remain documented. Future November 16/18 checks are not represented as already performed.

No new browser acceptance, paid model calls, publication or persistent database changes were performed during this merge. Source evidence and screenshots were retained; Git does not copy ignored SQLite databases between worktrees.
