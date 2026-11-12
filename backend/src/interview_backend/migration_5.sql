CREATE TABLE jd_mappings (
 id TEXT PRIMARY KEY, payload TEXT NOT NULL
);
CREATE TABLE session_jd (
 session_id TEXT PRIMARY KEY REFERENCES sessions(id), payload TEXT NOT NULL
);
PRAGMA user_version=5;
