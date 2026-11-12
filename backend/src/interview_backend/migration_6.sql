-- Tickets 09 and 11 independently used schema 5 for JD and resume tables.
-- Preserve either layout and its records while adding the missing feature.
CREATE TABLE IF NOT EXISTS jd_mappings (
 id TEXT PRIMARY KEY, payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS session_jd (
 session_id TEXT PRIMARY KEY REFERENCES sessions(id), payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS resumes (
 id TEXT PRIMARY KEY, payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS session_resumes (
 session_id TEXT PRIMARY KEY REFERENCES sessions(id), snapshot_json TEXT NOT NULL
);
PRAGMA user_version=6;
