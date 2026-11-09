CREATE TABLE IF NOT EXISTS question_publications (
 id TEXT PRIMARY KEY, report TEXT NOT NULL
);
INSERT OR IGNORE INTO role_packs VALUES (
 'pack_agent_basics_mianstack', 'Agent 原理与系统基础档（MianStack）', 'published', 0
);
PRAGMA user_version=2;
