CREATE TABLE resumes (
 id TEXT PRIMARY KEY, payload TEXT NOT NULL
);
CREATE TABLE session_resumes (
 session_id TEXT PRIMARY KEY REFERENCES sessions(id), snapshot_json TEXT NOT NULL
);
PRAGMA user_version=5;
