import json
from importlib.resources import files
from pathlib import Path

from fastapi.testclient import TestClient

from interview_backend.api import create_app
from interview_backend.demo_acceptance import inspect_release


def test_unpublished_candidates_are_not_reported_as_available(tmp_path: Path) -> None:
    with TestClient(create_app(database_path=tmp_path / "demo.sqlite3")) as client:
        report = inspect_release(client)
        assert report["source_count"] == 115
        assert report["validation_passed_count"] == 115
        assert report["available_count"] == 0
        assert report["published_source_count"] == 0
        assert all(row["status"] == "unpublished" for row in report["questions"])
        assert not report["release_matches_candidates"]


def test_disabled_question_is_excluded_and_blocks_full_release_claim(tmp_path: Path) -> None:
    with TestClient(create_app(database_path=tmp_path / "published.sqlite3")) as client:
        for name in ("first_half_candidates.json", "agent_topics_second_half.json"):
            batch = json.loads(files("interview_backend").joinpath(name).read_text("utf-8"))
            client.post("/api/v1/maintenance/question-publications", json=batch).raise_for_status()
        before = inspect_release(client)
        assert before["release_matches_candidates"]
        client.post(
            "/api/v1/maintenance/questions/Q-0058/disable",
            json={"expected_version": 1, "reason": "验收停用，不可继续计入实际可评分数"},
        ).raise_for_status()
        report = inspect_release(client)
        assert report["available_count"] == 114
        assert report["published_source_count"] == 114
        assert report["rejected_count"] == 1
        assert not report["release_matches_candidates"]
        row = next(row for row in report["questions"] if row["code"] == "Q-0058")
        assert row["status"] == "disabled"
        assert row["validation"]["reasons"][0]["code"] == "QUESTION_DISABLED"
