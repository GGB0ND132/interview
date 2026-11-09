from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path


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
            elif version != 2:
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
