ALTER TABLE jobs ADD COLUMN claim_token TEXT;
ALTER TABLE jobs ADD COLUMN lease_expires_at REAL;
ALTER TABLE jobs ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE jobs ADD COLUMN retry_revision INTEGER;
ALTER TABLE jobs ADD COLUMN recovery_after REAL NOT NULL DEFAULT 0;
CREATE INDEX jobs_pending ON jobs(status, lease_expires_at);
PRAGMA user_version=5;
