ALTER TABLE submissions ADD COLUMN provenance_json TEXT;
-- Legacy scores retain their original question snapshot, but link-only metadata
-- cannot be upgraded into independently verified evidence retroactively.
UPDATE submissions SET provenance_json=(
 SELECT json_object(
  'question_code',json_extract(s.question_json,'$.code'),
  'question_version',json_extract(s.question_json,'$.version'),
  'answer_version',json_extract(s.question_json,'$.version'),
  'content_version',json_extract(s.question_json,'$.content_version'),
  'answer_origin',json_extract(s.question_json,'$.answer_origin'),
  'answer_generation',json_extract(s.question_json,'$.generation'),
  'source_answer_status',json_extract(s.question_json,'$.source.answer_status'),
  'question_source',json_extract(s.question_json,'$.source'),
  'independent_references',json('[]'),
  'provenance_status','legacy_without_evidence_snapshot'
 ) FROM sessions s WHERE s.id=submissions.session_id AND s.question_json IS NOT NULL
);
CREATE TABLE verified_evidence (
 id TEXT PRIMARY KEY, question_code TEXT NOT NULL, answer_version INTEGER NOT NULL,
 payload TEXT NOT NULL,
 FOREIGN KEY(question_code, answer_version) REFERENCES questions(code, version)
);
CREATE TABLE user_reports (
 id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
 question_code TEXT NOT NULL, answer_version INTEGER NOT NULL, payload TEXT NOT NULL
);
PRAGMA user_version=4;
