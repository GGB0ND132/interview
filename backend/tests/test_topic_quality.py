from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient
from test_agent_topic_pack import approved_reviews, second_half
from test_publishing import CONFIG, PACK, data

from interview_backend.api import create_app
from interview_backend.contracts import ModelEvaluation
from interview_backend.topic_pack import candidate_digest

BASE = "/api/v1/maintenance/topic-quality/agent_protocols"


def incident(client, code, error_kind="test-transport-confusion"):
    return data(
        client.post(
            f"{BASE}/incidents",
            json={
                "code": code,
                "expected_version": 1,
                "error_kind": error_kind,
                "reason": "Synthetic quality incident for API test",
            },
        )
    )


def sample(question):
    review = deepcopy(approved_reviews()["samples"][0])
    review.update(code=question["code"], candidate_sha256=candidate_digest(question))
    return review


def test_repeat_errors_pause_topic_until_corrections_and_expanded_review(tmp_path: Path):
    database = tmp_path / "quality.sqlite3"
    questions = second_half()["questions"]
    protocol_questions = [q for q in questions if q["competency_id"] == "agent_protocols"]
    with TestClient(create_app(database_path=database)) as client:
        data(
            client.post("/api/v1/maintenance/question-publications", json={"questions": questions})
        )
        first = incident(client, "Q-0322")
        assert first["paused"] is False
        assert first["required_sample_count"] == 4
        second = incident(client, "Q-0416", "test-different-technical-error")
        assert second["paused"] is True
        # Duplicate reports about the same version do not fabricate more errors.
        assert len(incident(client, "Q-0416", "test-different-technical-error")["incidents"]) == 2
        filtered = {**CONFIG, "focus_competency_ids": ["agent_protocols"]}
        assert (
            data(client.post(f"/api/v1/role-packs/{PACK}/availability", json=filtered))[
                "available_count"
            ]
            == 0
        )
        assert client.post(f"{BASE}/resume", json={"samples": []}).status_code == 409
        corrected = []
        for original in protocol_questions[:2]:
            question = deepcopy(original)
            question.update(
                content_version="quality-test-v2",
                answer_origin="maintainer_edited",
                answer=original["answer"] + "\n经合成测试复核后的新版本。",
            )
            corrected.append(question)
            result = data(
                client.post(
                    f"{BASE}/corrections",
                    json={"expected_version": 1, "candidate": question, "review": sample(question)},
                )
            )
            assert result["accepted_count"] == 1
        assert (
            data(client.post(f"/api/v1/role-packs/{PACK}/availability", json=filtered))[
                "available_count"
            ]
            == 0
        )
        reviews = [sample(q) for q in corrected + protocol_questions[2:4]]
        resumed = data(client.post(f"{BASE}/resume", json={"samples": reviews}))
        assert resumed["paused"] is False
        assert (
            data(client.post(f"/api/v1/role-packs/{PACK}/availability", json=filtered))[
                "available_count"
            ]
            == 15
        )
    with TestClient(create_app(database_path=database)) as client:
        assert data(client.get(BASE))["paused"] is False
        assert len(data(client.get(BASE))["resolutions"]) == 1


class UnusedEvaluator:
    def evaluate(self, *, question, answer) -> ModelEvaluation:
        raise AssertionError("A held topic must not call the model")


def test_hold_survives_restart_and_retains_answer_without_scoring(tmp_path: Path):
    database = tmp_path / "held.sqlite3"
    with TestClient(create_app(database_path=database, evaluator=UnusedEvaluator())) as client:
        data(client.post("/api/v1/maintenance/question-publications", json=second_half()))
        config = {**CONFIG, "focus_competency_ids": ["agent_protocols"]}
        session = data(client.post("/api/v1/sessions", json={"pack_id": PACK, "config": config}))
        started = data(
            client.post(
                f"/api/v1/sessions/{session['session_id']}/start", json={"expected_revision": 0}
            )
        )
        incident(client, "Q-0322")
        incident(client, "Q-0416")
    with TestClient(create_app(database_path=database, evaluator=UnusedEvaluator())) as client:
        assert data(client.get(BASE))["paused"] is True
        data(
            client.post(
                f"/api/v1/sessions/{session['session_id']}/answers",
                json={
                    "turn_id": started["current_turn"]["id"],
                    "expected_revision": started["revision"],
                    "client_submission_id": "quality-hold-test",
                    "disposition": "answered",
                    "answer_text": "这是一份已保存但暂时不能评分的实际回答。",
                },
            )
        )
        saved = data(client.get(f"/api/v1/sessions/{session['session_id']}"))
        assert saved["phase"] == "evaluation_failed"
        assert saved["submissions"][0]["answer_text"] == "这是一份已保存但暂时不能评分的实际回答。"
        assert saved["submissions"][0]["error"]["code"] in {
            "TOPIC_SCORING_PAUSED",
            "QUESTION_DISABLED",
        }
        report = data(client.get(f"/api/v1/sessions/{session['session_id']}/report"))
        assert report["average_score"] is None
        assert report["answered_count"] == 0


def test_correction_stays_quarantined_until_expanded_review(tmp_path: Path):
    # Pick a protocol question without depending on the pack's global ordering.
    original = next(q for q in second_half()["questions"] if q["code"] == "Q-0322")
    with TestClient(create_app(database_path=tmp_path / "one-error.sqlite3")) as client:
        data(client.post("/api/v1/maintenance/question-publications", json=second_half()))
        incident(client, original["code"])
        correction = deepcopy(original)
        correction.update(
            content_version="review-correction-v2", answer=original["answer"] + "校验新版本。"
        )
        invalid = client.post(
            f"{BASE}/corrections",
            json={"expected_version": 1, "candidate": correction, "review": {}},
        )
        assert invalid.status_code == 400
        corrected = data(
            client.post(
                f"{BASE}/corrections",
                json={"expected_version": 1, "candidate": correction, "review": sample(correction)},
            )
        )
        assert corrected["accepted_count"] == 1
        assert corrected["topic_counts"]["MCP、A2A 与工具协议"] == 14
        config = {**CONFIG, "focus_competency_ids": ["agent_protocols"]}
        assert (
            data(client.post(f"/api/v1/role-packs/{PACK}/availability", json=config))[
                "available_count"
            ]
            == 14
        )
        assert (
            client.post(f"{BASE}/resume", json={"samples": [sample(correction)]}).status_code == 409
        )


def test_generic_disable_cannot_bypass_quality_recovery(tmp_path: Path):
    original = next(q for q in second_half()["questions"] if q["code"] == "Q-0322")
    with TestClient(create_app(database_path=tmp_path / "generic-disable.sqlite3")) as client:
        data(client.post("/api/v1/maintenance/question-publications", json=second_half()))
        data(
            client.post(
                "/api/v1/maintenance/questions/Q-0322/disable",
                json={"expected_version": 1, "reason": "Synthetic wrong-answer disable"},
            )
        )
        correction = deepcopy(original)
        correction.update(
            content_version="generic-disable-v2", answer=original["answer"] + "校验新版本。"
        )
        response = client.post(
            f"{BASE}/corrections",
            json={"expected_version": 1, "candidate": correction, "review": sample(correction)},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "QUALITY_INCIDENT_REQUIRED"
