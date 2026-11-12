from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path
from typing import Any


def active_incidents(state: dict[str, Any]) -> list[dict[str, Any]]:
    return list(state["incidents"][state.get("resolved_incident_count", 0) :])


class Store:
    """One connection per transaction; no database lock spans a model call."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            # Serialize inspection and the entire upgrade, including concurrent startups.
            db.execute("BEGIN IMMEDIATE")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in range(9):
                raise RuntimeError(f"Unsupported database schema version: {version}")
            if version == 0:
                self._execute_migration(db, "schema.sql")
                pack = json.loads(
                    files("interview_backend").joinpath("samples.json").read_text(encoding="utf-8")
                )
                db.execute(
                    "INSERT OR IGNORE INTO role_packs VALUES (?, ?, ?, ?)",
                    (pack["pack_id"], pack["title"], pack["status"], pack["version"]),
                )
                for question in pack["questions"]:
                    question.setdefault("version", 1)
                    question["generation"] = pack["generation"]
                    db.execute(
                        "INSERT OR IGNORE INTO questions VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            question["code"],
                            question["version"],
                            pack["pack_id"],
                            question["difficulty"],
                            question["status"],
                            json.dumps(question, ensure_ascii=False),
                        ),
                    )
                db.execute("PRAGMA user_version=1")
                version = 1
            if version == 1:
                self._execute_migration(db, "migration_2.sql")
                version = 2
            if version == 2:
                self._execute_migration(db, "migration_3.sql")
                version = 3
            if version < 8:
                # Independent branches reused versions 4 and 5 for different features.
                # Add missing tables, never replay conflicting CREATE/ALTER statements.
                db.execute(
                    "CREATE TABLE IF NOT EXISTS mock_interviews (session_id TEXT PRIMARY KEY REFERENCES sessions(id), state_json TEXT NOT NULL)"
                )
                self._execute_migration(db, "migration_6.sql")
                has_provenance = any(
                    column[1] == "provenance_json"
                    for column in db.execute("PRAGMA table_info(submissions)")
                )
                if not has_provenance:
                    db.execute("ALTER TABLE submissions ADD COLUMN provenance_json TEXT")
                self._execute_migration(db, "migration_7.sql")
                self._backfill_provenance(db)
                has_recovery = any(
                    column[1] == "claim_token" for column in db.execute("PRAGMA table_info(jobs)")
                )
                if not has_recovery:
                    self._execute_migration(db, "migration_8.sql")
                else:
                    # Ticket 15's schema 5 already contains the lease columns and index.
                    db.execute("PRAGMA user_version=8")

    @staticmethod
    def _execute_migration(db: sqlite3.Connection, name: str) -> None:
        # executescript implicitly commits, which would release the upgrade lock.
        statement = ""
        for line in files("interview_backend").joinpath(name).read_text("utf-8").splitlines(True):
            statement += line
            if sqlite3.complete_statement(statement):
                db.execute(statement)
                statement = ""
        if statement.strip():
            raise RuntimeError(f"Incomplete SQL migration: {name}")

    @staticmethod
    def _backfill_provenance(db: sqlite3.Connection) -> None:
        from .provenance import snapshot

        for row in db.execute(
            "SELECT a.id,a.turn_id,s.question_json,m.state_json FROM submissions a "
            "JOIN sessions s ON s.id=a.session_id LEFT JOIN mock_interviews m ON m.session_id=s.id "
            "WHERE a.provenance_json IS NULL"
        ).fetchall():
            question = json.loads(row["question_json"]) if row["question_json"] else None
            if row["state_json"]:
                state = json.loads(row["state_json"])
                turn = next((t for t in state["turns"] if t["id"] == row["turn_id"]), None)
                question = next(
                    (
                        g["question"]
                        for g in state["groups"]
                        if turn and g["id"] == turn["group_id"]
                    ),
                    None,
                )
            if question:
                provenance = snapshot(question)
                provenance["provenance_status"] = "legacy_without_evidence_snapshot"
                db.execute(
                    "UPDATE submissions SET provenance_json=? WHERE id=?",
                    (json.dumps(provenance, ensure_ascii=False), row["id"]),
                )

    @contextmanager
    def connect(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def published_questions(db: sqlite3.Connection, pack_id: str) -> list[dict[str, Any]]:
        rows = db.execute(
            "SELECT payload FROM questions WHERE pack_id=? AND status='published' "
            "AND version=(SELECT MAX(q.version) FROM questions q WHERE q.code=questions.code)",
            (pack_id,),
        ).fetchall()
        return Store.filter_quality(db, pack_id, (json.loads(row["payload"]) for row in rows))

    @staticmethod
    def filter_quality(
        db: sqlite3.Connection, pack_id: str, questions: Iterable[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        states = [
            state
            for row in db.execute("SELECT payload FROM topic_quality")
            if (state := json.loads(row["payload"]))["pack_id"] == pack_id
        ]
        held = {state["topic"] for state in states if state["paused"]}
        quarantined = {incident["code"] for state in states for incident in active_incidents(state)}
        return [q for q in questions if q["topic"] not in held and q["code"] not in quarantined]

    @staticmethod
    def scoring_block(db: sqlite3.Connection, question: dict[str, Any]) -> str | None:
        version = db.execute(
            "SELECT status,pack_id FROM questions WHERE code=? AND version=?",
            (question["code"], question["version"]),
        ).fetchone()
        if version is not None and version["status"] == "disabled":
            return "QUESTION_DISABLED"
        hold = db.execute(
            "SELECT payload FROM topic_quality WHERE topic=?", (question["topic"],)
        ).fetchone()
        if (
            hold is not None
            and version is not None
            and json.loads(hold["payload"])["paused"]
            and json.loads(hold["payload"])["pack_id"] == version["pack_id"]
        ):
            return "TOPIC_SCORING_PAUSED"
        if hold is not None and version is not None:
            state = json.loads(hold["payload"])
            if state["pack_id"] == version["pack_id"] and question["code"] in {
                incident["code"] for incident in active_incidents(state)
            }:
                return "QUESTION_QUARANTINED"
        return None
