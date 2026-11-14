import json
from importlib.resources import files
from pathlib import Path

from fastapi.testclient import TestClient
from test_topic_quality import incident, sample

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
        assert not any(row["available_for_scoring"] for row in report["questions"])
        assert all(row["exclusion_reasons"] == ["UNPUBLISHED"] for row in report["questions"])
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
        assert not row["available_for_scoring"]
        assert "QUESTION_DISABLED" in row["exclusion_reasons"]
        assert row["validation"]["reasons"][0]["code"] == "QUESTION_DISABLED"


def test_quality_quarantine_and_topic_pause_are_excluded_from_scorable_inventory(tmp_path: Path):
    with TestClient(create_app(database_path=tmp_path / "quality.sqlite3")) as client:
        for name in ("first_half_candidates.json", "agent_topics_second_half.json"):
            batch = json.loads(files("interview_backend").joinpath(name).read_text("utf-8"))
            client.post("/api/v1/maintenance/question-publications", json=batch).raise_for_status()
        incident(client, "Q-0322")
        original = next(q for q in batch["questions"] if q["code"] == "Q-0322")
        correction = {**original, "content_version": "inventory-corrected-v2"}
        client.post(
            "/api/v1/maintenance/topic-quality/agent_protocols/corrections",
            json={"expected_version": 1, "candidate": correction, "review": sample(correction)},
        ).raise_for_status()
        report = inspect_release(client)
        row = next(row for row in report["questions"] if row["code"] == "Q-0322")
        assert row["status"] == "published"
        assert not row["available_for_scoring"]
        assert row["exclusion_reasons"] == ["QUESTION_QUARANTINED"]
        assert report["scorable_source_count"] == report["available_count"] == 114
        assert report["counts_match_availability"]
        incident(client, "Q-0416")
        report = inspect_release(client)
        protocols = [r for r in report["questions"] if r["topic"] == original["topic"]]
        assert len(protocols) == 15
        assert all(not r["available_for_scoring"] for r in protocols)
        assert all("TOPIC_SCORING_PAUSED" in r["exclusion_reasons"] for r in protocols)
        assert report["scorable_source_count"] == report["available_count"] == 100
        assert report["counts_match_availability"]
        assert not report["release_matches_candidates"]
