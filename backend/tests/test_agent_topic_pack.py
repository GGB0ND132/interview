import json
from importlib.resources import files
from pathlib import Path

from fastapi.testclient import TestClient
from test_publishing import CONFIG, PACK, data

from interview_backend.api import create_app
from interview_backend.topic_pack import TopicPack, review_template


def second_half():
    return json.loads(
        files("interview_backend")
        .joinpath("agent_topics_second_half.json")
        .read_text(encoding="utf-8")
    )


def test_complete_second_half_pack_previews_without_publishing(tmp_path: Path):
    with TestClient(create_app(database_path=tmp_path / "topics.sqlite3")) as client:
        preview = data(
            client.post("/api/v1/maintenance/question-publications/preview", json=second_half())
        )
        assert preview["accepted_count"] == 58
        assert preview["rejected_count"] == 0
        assert len(preview["topic_counts"]) == 12
        assert preview["topic_counts"]["MCP、A2A 与工具协议"] == 15
        assert preview["topic_counts"]["Skills 能力系统"] == 13
        assert preview["topic_counts"]["工作流、状态与执行恢复"] == 5
        assert preview["topic_counts"]["多 Agent 编排与协作"] == 8
        assert preview["topic_counts"]["Agent 框架与 Harness"] == 16
        assert preview["topic_counts"]["GUI、Computer Use 与多模态 Agent"] == 1
        assert (
            data(client.post(f"/api/v1/role-packs/{PACK}/availability", json=CONFIG))[
                "available_count"
            ]
            == 0
        )


def test_release_requires_human_review_and_reports_all_twelve_topics(tmp_path: Path):
    with TestClient(create_app(database_path=tmp_path / "release.sqlite3")) as client:
        pack = TopicPack(client)
        report = pack.run(reviews={"samples": []}, publish=True)
        assert report["source_count"] == 115
        assert report["prepared_count"] == 58
        assert report["validation_passed_count"] == 58
        assert report["rejected_count"] == 0
        assert report["published_now_count"] == 0
        assert report["available_count"] == 0
        assert len(report["topics"]) == 12
        gui = next(row for row in report["topics"] if row["competency_id"] == "agent_gui")
        assert gui["source_count"] == 1
        assert gui["reviewed_count"] == 0
        assert "INSUFFICIENT_DISTINCT_SOURCE_QUESTIONS" in gui["blockers"]


def approved_reviews():
    """Synthetic attestations for API tests; never written to the real review artifact."""
    reviews = review_template()
    for sample in reviews["samples"]:
        sample.update(
            reviewer="TEST FIXTURE - not a real human review",
            reviewed_at="2026-11-10T00:00:00+08:00",
            materials=[
                {
                    "locator": "test://review-material",
                    "version": "fixture-v1",
                    "checked_excerpt": "Synthetic review to exercise release orchestration",
                }
            ],
            findings="Synthetic test approval only",
            conclusion="approved",
        )
    return reviews


def test_reviewed_topics_enter_real_practice_and_release_is_idempotent(tmp_path: Path):
    with TestClient(create_app(database_path=tmp_path / "reviewed.sqlite3")) as client:
        report = TopicPack(client).run(approved_reviews(), publish=True)
        # GUI has only one distinct source question, so remains blocked.
        assert report["published_now_count"] == 57
        assert report["available_count"] == 57
        replay = TopicPack(client).run(approved_reviews(), publish=True)
        assert replay["published_now_count"] == 0
        assert replay["publication"]["unchanged_count"] == 57
        for competency in (
            "agent_protocols",
            "agent_skills",
            "agent_workflow_recovery",
            "agent_multi_agent",
            "agent_frameworks_harness",
        ):
            config = {**CONFIG, "focus_competency_ids": [competency]}
            session = data(
                client.post("/api/v1/sessions", json={"pack_id": PACK, "config": config})
            )
            started = data(
                client.post(
                    f"/api/v1/sessions/{session['session_id']}/start", json={"expected_revision": 0}
                )
            )
            assert started["current_turn"]["competency_id"] == competency


def test_changed_or_duplicate_review_cannot_authorize_any_release(tmp_path: Path):
    reviews = approved_reviews()
    reviews["samples"][0]["candidate_sha256"] = "stale answer version"
    reviews["samples"].append(reviews["samples"][1])
    with TestClient(create_app(database_path=tmp_path / "stale.sqlite3")) as client:
        report = TopicPack(client).run(reviews, publish=True)
        assert {error["reason"] for error in report["review_errors"]} == {
            "REVIEW_CONTENT_CHANGED",
            "DUPLICATE_REVIEW_QUESTION",
        }
        assert report["published_now_count"] == 0
        assert report["available_count"] == 0
