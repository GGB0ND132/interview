CREATE TABLE mock_interviews (
 session_id TEXT PRIMARY KEY REFERENCES sessions(id), state_json TEXT NOT NULL
);
PRAGMA user_version=4;
