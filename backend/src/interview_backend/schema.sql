CREATE TABLE IF NOT EXISTS role_packs (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, status TEXT NOT NULL, version INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS questions (
 code TEXT NOT NULL, version INTEGER NOT NULL, pack_id TEXT NOT NULL REFERENCES role_packs(id),
 difficulty TEXT NOT NULL, status TEXT NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(code, version)
);
CREATE TABLE IF NOT EXISTS sessions (
 id TEXT PRIMARY KEY, pack_id TEXT NOT NULL REFERENCES role_packs(id),
 pack_version INTEGER NOT NULL, config_json TEXT NOT NULL, status TEXT NOT NULL,
 phase TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0, turn_id TEXT,
 question_json TEXT, selection_json TEXT,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE TABLE IF NOT EXISTS submissions (
 id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id), turn_id TEXT NOT NULL,
 client_submission_id TEXT NOT NULL, request_json TEXT NOT NULL, disposition TEXT NOT NULL,
 answer_text TEXT NOT NULL, status TEXT NOT NULL, score INTEGER, evaluation_json TEXT,
 error_json TEXT, job_id TEXT,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
 UNIQUE(session_id, client_submission_id), UNIQUE(session_id, turn_id)
);
CREATE TABLE IF NOT EXISTS jobs (
 id TEXT PRIMARY KEY, submission_id TEXT NOT NULL UNIQUE REFERENCES submissions(id),
 status TEXT NOT NULL, phase TEXT NOT NULL, error_json TEXT
);
