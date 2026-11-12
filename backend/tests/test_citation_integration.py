import httpx
import pytest
from fastapi.testclient import TestClient
from test_mock_interview import (
    InterviewEvaluator,
    answer,
    data,
    next_group,
    publish_technical,
    ready,
    refresh,
    start,
)
from test_provenance import EXCERPT, register

from interview_backend.api import create_app


@pytest.mark.parametrize(
    "disposition,stage,text",
    [
        ("no_questions", "candidate_questions", ""),
        ("no_experience", "experience", ""),
        ("skipped", "introduction", ""),
        ("answered", "candidate_questions", "没有问题"),
        ("answered", "experience", "我没有项目经历"),
    ],
)
def test_unscored_dispositions_allow_question_reports_but_reject_score_reports(
    tmp_path, disposition, stage, text
):
    with TestClient(
        create_app(database_path=tmp_path / "unscored.sqlite3", evaluator=InterviewEvaluator())
    ) as client:
        ready(client)
        session = start(client, experience_mode="experience", max_followups_per_question=0)
        while session["current_turn"]["stage"] != stage:
            answer(client, session)
            session = next_group(client, refresh(client, session))
        target_turn = session["current_turn"]["id"]
        answer(client, session, disposition, text=text)
        session = refresh(client, session)
        if session["status"] == "active":
            data(
                client.post(
                    f"/api/v1/sessions/{session['session_id']}/finish",
                    json={"expected_revision": session["revision"]},
                )
            )
        body = {"turn_id": target_turn, "category": "score", "explanation": "本轮未评分"}
        assert (
            client.post(f"/api/v1/sessions/{session['session_id']}/reports", json=body).status_code
            == 409
        )
        body["category"] = "question"
        assert (
            client.post(f"/api/v1/sessions/{session['session_id']}/reports", json=body).status_code
            == 201
        )


class CitingEvaluator(InterviewEvaluator):
    def evaluate(self, *, question, answer):
        evaluation = super().evaluate(question=question, answer=answer)
        evaluation.used_reference_ids = [r["id"] for r in question.get("verified_references", [])]
        return evaluation


def test_report_citations_and_user_reports_bind_to_historical_interview_turn(tmp_path):
    database = tmp_path / "interview.sqlite3"
    transport = httpx.MockTransport(lambda _: httpx.Response(200, text=f"<p>{EXCERPT}</p>"))
    with TestClient(
        create_app(
            database_path=database, evaluator=CitingEvaluator(), evidence_transport=transport
        )
    ) as client:
        publish_technical(client)
        data(client.post("/api/v1/maintenance/mock-interview-questions/publish"))
        evidence = data(register(client, "Q-INTERVIEW-INTRODUCTION"))
        session = start(client, max_followups_per_question=0)
        original_turn = session["current_turn"]
        answer(client, session)
        session = refresh(client, session)
        assert (
            client.post(
                f"/api/v1/sessions/{session['session_id']}/reports",
                json={
                    "turn_id": original_turn["id"],
                    "category": "score",
                    "explanation": "评分尚未公开",
                },
            ).status_code
            == 409
        )
        session = data(
            client.post(
                f"/api/v1/sessions/{session['session_id']}/next",
                json={"expected_revision": session["revision"]},
            )
        )
        session = data(
            client.post(
                f"/api/v1/sessions/{session['session_id']}/finish",
                json={"expected_revision": session["revision"]},
            )
        )
        report = data(client.get(f"/api/v1/sessions/{session['session_id']}/report"))
        assert report["groups"][0]["feedback"]["independent_references"] == [evidence]
        assert "answer_origin" not in str(report)
        saved = data(
            client.post(
                f"/api/v1/sessions/{session['session_id']}/reports",
                json={
                    "turn_id": original_turn["id"],
                    "category": "score",
                    "explanation": "评分维度存在疑问",
                },
            )
        )
        assert saved["question_code"] == original_turn["question_code"]
        assert saved["answer_version"] == 1
        assert saved["status"] == "open"
        assert (
            client.post(
                f"/api/v1/sessions/{session['session_id']}/reports",
                json={"turn_id": "foreign-turn", "category": "question", "explanation": "其他轮次"},
            ).status_code
            == 409
        )
    with TestClient(create_app(database_path=database)) as client:
        assert (
            data(client.get(f"/api/v1/sessions/{session['session_id']}/reports/{saved['id']}"))
            == saved
        )
