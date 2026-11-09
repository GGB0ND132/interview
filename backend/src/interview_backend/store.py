from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path
from typing import Any


class Store:
    """One connection per transaction; no database lock spans a model call."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version == 0:
                db.executescript(
                    files("interview_backend").joinpath("schema.sql").read_text(encoding="utf-8")
                )
                pack = json.loads(
                    files("interview_backend").joinpath("samples.json").read_text(encoding="utf-8")
                )
                db.execute("BEGIN IMMEDIATE")
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
                db.commit()
                version = 1
            if version == 1:
                db.executescript(
                    "BEGIN IMMEDIATE;\n"
                    + files("interview_backend")
                    .joinpath("migration_2.sql")
                    .read_text(encoding="utf-8")
                    + "\nCOMMIT;"
                )
                version = 2
            if version == 2:
                db.executescript(
                    "BEGIN IMMEDIATE;\n"
                    + files("interview_backend")
                    .joinpath("migration_3.sql")
                    .read_text(encoding="utf-8")
                    + "\nCOMMIT;"
                )
            elif version != 3:
                raise RuntimeError(f"Unsupported database schema version: {version}")

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
        quarantined = {
            incident["code"]
            for state in states
            for incident in state["incidents"][state.get("resolved_incident_count", 0) :]
        }
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
                incident["code"]
                for incident in state["incidents"][state.get("resolved_incident_count", 0) :]
            }:
                return "QUESTION_QUARANTINED"
        return None
