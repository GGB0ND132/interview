from pathlib import Path

from fastapi.testclient import TestClient
from test_publishing import CONFIG, PACK, batch, data

from interview_backend.api import create_app


def test_availability_exposes_filterable_topics_and_tracks_publication(tmp_path: Path):
    with TestClient(create_app(database_path=tmp_path / "availability.sqlite3")) as client:
        url = f"/api/v1/role-packs/{PACK}/availability"
        assert data(client.post(url, json=CONFIG))["available_count"] == 0
        data(client.post("/api/v1/maintenance/question-publications", json=batch()))
        available = data(client.post(url, json=CONFIG))
        topic = next(t for t in available["topics"] if t["competency_id"] == "agent_loop")
        assert topic == {
            "topic": "Agent 基础与运行循环",
            "competency_id": "agent_loop",
            "available_count": 1,
            "interview_count": 1,
        }
        filtered = {**CONFIG, "focus_competency_ids": ["agent_loop"]}
        assert data(client.post(url, json=filtered))["available_count"] == 1
        data(
            client.post(
                "/api/v1/maintenance/questions/Q-0058/disable",
                json={
                    "expected_version": 1,
                    "reason": "04 可用性验收停用",
                },
            )
        )
        after = data(client.post(url, json=filtered))
        assert after["available_count"] == 0
        assert after["can_start"] is False
        assert "published_question" in after["missing"]


def test_mock_availability_reports_real_stage_gaps_without_enabling_sessions(tmp_path: Path):
    with TestClient(create_app(database_path=tmp_path / "mock.sqlite3")) as client:
        data(client.post("/api/v1/maintenance/question-publications", json=batch()))
        config = {**CONFIG, "mode": "mock_interview"}
        available = data(client.post(f"/api/v1/role-packs/{PACK}/availability", json=config))
        assert available["available_count"] == 2
        assert available["eligible_topic_count"] == 2
        assert available["minimum_topic_count"] == 3
        assert available["can_start"] is False
        assert available["missing"] == [
            "introduction",
            "experience_or_scenario",
            "technical_topics",
            "behavioral",
            "candidate_questions",
            "mock_interview_flow",
        ]
        assert available["stages"] == [
            {"id": "introduction", "label": "开场", "available_count": 0, "ready": False},
            {
                "id": "experience_or_scenario",
                "label": "经历或假设情境",
                "available_count": 0,
                "ready": False,
            },
            {"id": "technical_topics", "label": "技术", "available_count": 2, "ready": False},
            {"id": "behavioral", "label": "行为", "available_count": 0, "ready": False},
            {
                "id": "candidate_questions",
                "label": "候选人反问",
                "available_count": 0,
                "ready": False,
            },
        ]
        # Availability is read-only; ticket 07 still owns starting the real flow.
        assert (
            client.post("/api/v1/sessions", json={"pack_id": PACK, "config": config}).status_code
            == 422
        )


def test_mock_counts_only_interview_suitable_questions(tmp_path: Path):
    request = batch()
    request["questions"][0]["interview_suitable"] = False
    with TestClient(create_app(database_path=tmp_path / "suitable.sqlite3")) as client:
        data(client.post("/api/v1/maintenance/question-publications", json=request))
        url = f"/api/v1/role-packs/{PACK}/availability"
        assert data(client.post(url, json=CONFIG))["available_count"] == 2
        mock = data(client.post(url, json={**CONFIG, "mode": "mock_interview"}))
        assert mock["available_count"] == 1
        assert mock["eligible_topic_count"] == 1
        loop = next(t for t in mock["topics"] if t["competency_id"] == "agent_loop")
        assert loop["available_count"] == 1
        assert loop["interview_count"] == 0
