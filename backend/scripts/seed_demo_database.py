"""Make a consistent SQLite backup for a separate persistent demo, never overwrite."""

import argparse
import json
import sqlite3
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    target = args.target.resolve()
    if target.exists() or source == target:
        parser.error("Target must be a new database; existing data is never overwritten")
    target.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive file creation protects against accidentally replacing a concurrent seed.
    with target.open("xb"):
        pass
    with (
        sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as original,
        sqlite3.connect(target) as copy,
    ):
        original.backup(copy)
        if copy.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Copied database failed integrity check")
        print(
            json.dumps(
                {
                    "source": str(source),
                    "target": str(target),
                    "schema_version": copy.execute("PRAGMA user_version").fetchone()[0],
                    "question_versions": copy.execute("SELECT COUNT(*) FROM questions").fetchone()[
                        0
                    ],
                    "preserved_sessions": copy.execute("SELECT COUNT(*) FROM sessions").fetchone()[
                        0
                    ],
                    "backup_method": "sqlite3.Connection.backup; source opened read-only",
                }
            )
        )


if __name__ == "__main__":
    main()
