CREATE TABLE IF NOT EXISTS verified_evidence (
 id TEXT PRIMARY KEY, question_code TEXT NOT NULL, answer_version INTEGER NOT NULL,
 payload TEXT NOT NULL,
 FOREIGN KEY(question_code, answer_version) REFERENCES questions(code, version)
);
CREATE TABLE IF NOT EXISTS user_reports (
 id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
 question_code TEXT NOT NULL, answer_version INTEGER NOT NULL, payload TEXT NOT NULL
);
PRAGMA user_version=7;
