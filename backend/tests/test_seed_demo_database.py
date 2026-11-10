"""The persistent-demo copy must preserve data and leave failed seeds retryable."""

import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "seed_demo_database.py"


def seed(source: Path, target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(source), "--target", str(target)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_copy_preserves_source_and_never_overwrites_target(tmp_path: Path) -> None:
    source, target = tmp_path / "source.sqlite3", tmp_path / "copy.sqlite3"
    with closing(sqlite3.connect(source)) as connection:
        connection.executescript(
            "CREATE TABLE questions (id TEXT); INSERT INTO questions VALUES ('Q-1');"
            "CREATE TABLE sessions (id TEXT); INSERT INTO sessions VALUES ('session-1');"
        )
    original = source.read_bytes()
    assert seed(source, target).returncode == 0
    with closing(sqlite3.connect(target)) as connection:
        assert connection.execute("SELECT id FROM sessions").fetchall() == [("session-1",)]
        assert connection.execute("SELECT id FROM questions").fetchall() == [("Q-1",)]
    assert seed(source, target).returncode != 0
    assert source.read_bytes() == original
    # Windows also verifies the script closed the copied database before exiting.
    target.unlink()


def test_failed_copy_removes_only_its_new_target(tmp_path: Path) -> None:
    source, target = tmp_path / "source.sqlite3", tmp_path / "copy.sqlite3"
    source.write_bytes(b"invalid sqlite data")
    assert seed(source, target).returncode != 0
    assert not target.exists()
    assert source.read_bytes() == b"invalid sqlite data"
