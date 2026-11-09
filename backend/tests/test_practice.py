import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import httpx
import pytest
from fastapi.testclient import TestClient

from interview_backend.api import create_app
from interview_backend.contracts import Dimension, ModelEvaluation
from interview_backend.model import ModelError, ModelSettings

CONFIG = {"mode": "question_practice", "difficulty": "easy"}
PACK = "pack_agent_basics_sample"


def data(response):
    assert response.is_success, response.text
    return response.json()["data"]


def test_published_sample_can_be_drawn_and_read_after_restart(tmp_path: Path):
    database = tmp_path / "practice.sqlite3"
    with TestClient(create_app(database_path=database)) as client:
        available = data(client.post(f"/api/v1/role-packs/{PACK}/availability", json=CONFIG))
        assert available["available_count"] == 2
        assert available["can_start"] is True
        draft = data(client.post("/api/v1/sessions", json={"pack_id": PACK, "config": CONFIG}))
        session = data(
            client.post(
                f"/api/v1/sessions/{draft['session_id']}/start",
                json={"expected_revision": draft["revision"]},
            )
        )
        assert session["current_turn"]["question_code"] in {
            "Q-AGENT-SAMPLE-01",
            "Q-AGENT-SAMPLE-02",
        }
        assert session["phase"] == "awaiting_answer"
        assert "rubric" not in session["current_turn"]
        assert "answer" not in session["current_turn"]
    with TestClient(create_app(database_path=database)) as client:
        restored = data(client.get(f"/api/v1/sessions/{session['session_id']}"))
        assert restored == session


class Evaluator:
    def __init__(self, *, fail: bool = False):
        self.calls = 0
        self.fail = fail

    def evaluate(self, *, question, answer):
        self.calls += 1
        if self.fail:
            raise ModelError("provider unavailable")
        return ModelEvaluation(
            dimensions=[
                Dimension(
                    name="accuracy", score=80, reason="covers the boundary", answer_quote="校验参数"
                ),
                Dimension(
                    name="completeness",
                    score=65,
                    reason="one recovery detail is brief",
                    answer_quote="限制权限",
                ),
                Dimension(
                    name="relevance",
                    score=90,
                    reason="answers the tool question",
                    answer_quote="执行次数",
                ),
                Dimension(
                    name="structure",
                    score=70,
                    reason="uses a clear sequence",
                    answer_quote="并记录失败",
                ),
                Dimension(
                    name="specificity",
                    score=60,
                    reason="needs a concrete example",
                    answer_quote="安全重试",
                ),
            ],
            strengths=["回答与问题相关"],
            improvements=["补充一个真实边界案例"],
        )


def start(client):
    draft = data(client.post("/api/v1/sessions", json={"pack_id": PACK, "config": CONFIG}))
    return data(
        client.post(f"/api/v1/sessions/{draft['session_id']}/start", json={"expected_revision": 0})
    )


def submit(client, session, submission_id, disposition, answer=""):
    return client.post(
        f"/api/v1/sessions/{session['session_id']}/answers",
        json={
            "turn_id": session["current_turn"]["id"],
            "expected_revision": session["revision"],
            "client_submission_id": submission_id,
            "disposition": disposition,
            "answer_text": answer,
        },
    )


def test_nonempty_answer_is_saved_then_scored_and_idempotent(tmp_path: Path):
    evaluator = Evaluator()
    with TestClient(
        create_app(database_path=tmp_path / "normal.sqlite3", evaluator=evaluator)
    ) as client:
        session = start(client)
        response = submit(
            client,
            session,
            "sub-1",
            "answered",
            "我会校验参数，限制权限和执行次数，并记录失败以便安全重试。",
        )
        assert response.status_code == 202
        result = data(client.get(f"/api/v1/sessions/{session['session_id']}"))["submissions"][0]
        assert result["score"] == 74
        assert result["feedback"]["dimensions"][0]["answer_quote"] == "校验参数"
        assert evaluator.calls == 1
        replay = data(
            submit(
                client,
                session,
                "sub-1",
                "answered",
                "我会校验参数，限制权限和执行次数，并记录失败以便安全重试。",
            )
        )
        assert replay["idempotent_replay"] is True
        assert replay["submission"]["score"] == 74
        assert evaluator.calls == 1
        report_result = data(client.get(f"/api/v1/sessions/{session['session_id']}/report"))
        assert report_result["average_score"] == 74
        assert report_result["answered_count"] == 1
        assert report_result["blank_count"] == report_result["skipped_count"] == 0


def test_blank_and_skip_are_distinct_and_do_not_call_model(tmp_path: Path):
    evaluator = Evaluator()
    with TestClient(
        create_app(database_path=tmp_path / "blank.sqlite3", evaluator=evaluator)
    ) as client:
        blank_session = start(client)
        blank = data(submit(client, blank_session, "blank-1", "blank_answer"))
        assert blank["submission"]["score"] == 0
        assert evaluator.calls == 0
        blank_report = data(client.get(f"/api/v1/sessions/{blank_session['session_id']}/report"))
        assert blank_report["average_score"] == 0 and blank_report["blank_count"] == 1

        skip_session = start(client)
        skipped = data(submit(client, skip_session, "skip-1", "skipped"))
        assert skipped["submission"]["score"] is None
        assert evaluator.calls == 0
        skip_report = data(client.get(f"/api/v1/sessions/{skip_session['session_id']}/report"))
        assert skip_report["average_score"] is None and skip_report["skipped_count"] == 1


def test_model_failure_keeps_answer_and_retry_reuses_submission(tmp_path: Path):
    failing = Evaluator(fail=True)
    with TestClient(
        create_app(database_path=tmp_path / "failure.sqlite3", evaluator=failing)
    ) as client:
        session = start(client)
        data(
            submit(
                client,
                session,
                "failed-1",
                "answered",
                "我会校验参数，限制权限和执行次数，并记录失败以便安全重试。",
            )
        )
        failed = data(client.get(f"/api/v1/sessions/{session['session_id']}"))
        assert failed["submissions"][0]["status"] == "failed"
        assert (
            failed["submissions"][0]["answer_text"]
            == "我会校验参数，限制权限和执行次数，并记录失败以便安全重试。"
        )
        assert failing.calls == 1

    succeeding = Evaluator()
    with TestClient(
        create_app(database_path=tmp_path / "failure.sqlite3", evaluator=succeeding)
    ) as client:
        data(
            client.post(
                f"/api/v1/sessions/{session['session_id']}/retry",
                json={"expected_revision": failed["revision"]},
            )
        )
        retried = data(client.get(f"/api/v1/sessions/{session['session_id']}"))["submissions"][0]
        assert retried["status"] == "completed"
        assert retried["score"] == 74
        assert succeeding.calls == 1


def test_idempotency_key_cannot_be_reused_with_different_input(tmp_path: Path):
    with TestClient(
        create_app(database_path=tmp_path / "conflict.sqlite3", evaluator=Evaluator())
    ) as client:
        session = start(client)
        data(submit(client, session, "one-key", "blank_answer"))
        response = submit(client, session, "one-key", "skipped")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "STATE_CONFLICT"


def test_answer_is_visible_while_model_is_running(tmp_path: Path):
    class ObservingEvaluator(Evaluator):
        def evaluate(self, *, question, answer):
            stored = data(client.get(f"/api/v1/sessions/{session['session_id']}"))
            assert stored["phase"] == "evaluating"
            assert stored["submissions"][0]["answer_text"] == answer
            assert "feedback" not in stored["submissions"][0]
            return super().evaluate(question=question, answer=answer)

    with TestClient(
        create_app(database_path=tmp_path / "saved.sqlite3", evaluator=ObservingEvaluator())
    ) as client:
        session = start(client)
        response = submit(
            client,
            session,
            "saved-first",
            "answered",
            "我会校验参数，限制权限和执行次数，并记录失败以便安全重试。",
        )
        assert response.status_code == 202
        finished = data(client.get(f"/api/v1/sessions/{session['session_id']}"))
        assert finished["status"] == "completed"


def test_draft_cannot_be_answered_and_started_session_cannot_start_again(tmp_path: Path):
    with TestClient(create_app(database_path=tmp_path / "state.sqlite3")) as client:
        draft = data(client.post("/api/v1/sessions", json={"pack_id": PACK, "config": CONFIG}))
        response = client.post(
            f"/api/v1/sessions/{draft['session_id']}/answers",
            json={
                "turn_id": f"turn-{draft['session_id']}-main",
                "expected_revision": 0,
                "client_submission_id": "draft-answer",
                "disposition": "blank_answer",
            },
        )
        assert response.status_code == 409
        session = start(client)
        response = client.post(
            f"/api/v1/sessions/{session['session_id']}/start",
            json={"expected_revision": session["revision"]},
        )
        assert response.status_code == 409


def test_unpublished_or_missing_pool_is_never_available(tmp_path: Path):
    with TestClient(create_app(database_path=tmp_path / "unpublished.sqlite3")) as client:
        candidate_config = {**CONFIG, "focus_competency_ids": ["agent_unpublished"]}
        available = data(
            client.post(f"/api/v1/role-packs/{PACK}/availability", json=candidate_config)
        )
        assert available["available_count"] == 0 and available["can_start"] is False
        assert (
            client.post(
                "/api/v1/sessions", json={"pack_id": PACK, "config": candidate_config}
            ).status_code
            == 400
        )
        assert (
            client.post("/api/v1/sessions", json={"pack_id": "missing", "config": CONFIG}).json()[
                "error"
            ]["code"]
            == "PACK_NOT_PUBLISHED"
        )


def test_concurrent_retry_reuses_the_pending_task(tmp_path: Path):
    entered, release = Event(), Event()

    class SlowEvaluator(Evaluator):
        def evaluate(self, *, question, answer):
            entered.set()
            assert release.wait(10), "test did not release the model boundary"
            return super().evaluate(question=question, answer=answer)

    evaluator = SlowEvaluator()
    with TestClient(
        create_app(database_path=tmp_path / "parallel.sqlite3", evaluator=evaluator)
    ) as client:
        session = start(client)
        answer = "我会校验参数，限制权限和执行次数，并记录失败以便安全重试。"
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(submit, client, session, "concurrent-1", "answered", answer)
            try:
                assert entered.wait(5)
                replay = submit(client, session, "concurrent-1", "answered", answer)
                assert replay.status_code == 202
                pending = data(replay)
                assert pending["idempotent_replay"] is True
                assert len(pending["session"]["submissions"]) == 1
                assert submit(client, session, "other-key", "answered", answer).status_code == 409
            finally:
                release.set()
            assert future.result(timeout=5).status_code == 202
        finished = data(client.get(f"/api/v1/sessions/{session['session_id']}"))
        assert len(finished["submissions"]) == evaluator.calls == 1
        assert finished["submissions"][0]["score"] == 74


def model_output():
    return {
        "dimensions": [
            {"name": name, "score": score, "reason": "基于本次回答", "answer_quote": "agent"}
            for name, score in [
                ("accuracy", 80),
                ("completeness", 65),
                ("relevance", 90),
                ("structure", 70),
                ("specificity", 60),
            ]
        ],
        "strengths": ["回答相关"],
        "improvements": ["补充边界"],
        "overall_score": 100,
    }


@pytest.mark.parametrize(
    "invalid",
    [
        "fabricated_quote",
        "duplicate_dimension",
        "out_of_range",
        "fractional",
        "missing",
        "non_json",
        "timeout",
        "upstream",
    ],
)
def test_invalid_model_output_or_failure_preserves_answer_without_feedback(
    tmp_path: Path, invalid: str
):
    payload = model_output()
    if invalid == "fabricated_quote":
        payload["dimensions"][0]["answer_quote"] = "invented"
    elif invalid == "duplicate_dimension":
        payload["dimensions"][1]["name"] = "accuracy"
    elif invalid == "out_of_range":
        payload["dimensions"][0]["score"] = 101
    elif invalid == "fractional":
        payload["dimensions"][0]["score"] = 0.5
    elif invalid == "missing":
        del payload["dimensions"]

    def transport(request):
        context = json.loads(json.loads(request.content)["messages"][1]["content"])
        assert context["user_answer"] == "agent uses tools"
        assert context["answer"] and context["rubric"]
        if invalid == "timeout":
            raise httpx.ReadTimeout("secret-provider-detail")
        if invalid == "upstream":
            return httpx.Response(401, text="secret-provider-detail")
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "bad-json" if invalid == "non_json" else json.dumps(payload)
                        }
                    }
                ]
            },
        )

    with TestClient(
        create_app(
            database_path=tmp_path / "invalid.sqlite3",
            model_settings=ModelSettings(api_key="test-secret"),
            model_transport=httpx.MockTransport(transport),
        )
    ) as client:
        session = start(client)
        data(submit(client, session, "invalid-1", "answered", "agent uses tools"))
        failed = data(client.get(f"/api/v1/sessions/{session['session_id']}"))
        submission = failed["submissions"][0]
        assert failed["phase"] == "evaluation_failed"
        assert submission["answer_text"] == "agent uses tools" and submission["status"] == "failed"
        assert "feedback" not in submission and "score" not in submission
        assert "secret" not in json.dumps(failed)
        job = data(client.get(f"/api/v1/jobs/{submission['job_id']}"))
        assert job["status"] == "failed" and job["error"]["retryable"] is True


def test_null_dimensions_use_eligible_weight_and_ignore_model_overall(tmp_path: Path):
    payload = model_output()
    payload["dimensions"][0]["score"] = None
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(payload)}}]}
        )
    )
    with TestClient(
        create_app(
            database_path=tmp_path / "weights.sqlite3",
            model_settings=ModelSettings(api_key="test"),
            model_transport=transport,
        )
    ) as client:
        session = start(client)
        data(submit(client, session, "weights-1", "answered", "agent uses tools"))
        finished = data(client.get(f"/api/v1/sessions/{session['session_id']}"))
        evaluation = finished["submissions"][0]["feedback"]
        assert evaluation["overall_score"] == 71
        assert evaluation["assessment_coverage"] == 0.65
        assert evaluation["assessment_status"] == "partial"


@pytest.mark.parametrize(
    "disposition,text",
    [
        ("answered", "  "),
        ("blank_answer", "  "),
        ("skipped", "not blank"),
        ("answered", "x" * 5001),
    ],
)
def test_invalid_submission_does_not_save_an_answer(tmp_path: Path, disposition: str, text: str):
    with TestClient(create_app(database_path=tmp_path / "input.sqlite3")) as client:
        session = start(client)
        assert submit(client, session, "bad-input", disposition, text).status_code == 422
        assert data(client.get(f"/api/v1/sessions/{session['session_id']}"))["submissions"] == []


def test_session_view_exposes_created_at_and_difficulty_for_history(tmp_path: Path):
    with TestClient(create_app(database_path=tmp_path / "history.sqlite3")) as client:
        session = start(client)
        assert session["created_at"].endswith("Z")
        assert session["difficulty"] == "easy"
        assert session["pack_title"]
        listed = data(client.get("/api/v1/sessions?page=1&page_size=20"))
        assert listed["total"] == 1
        assert listed["items"][0]["session_id"] == session["session_id"]
        assert listed["items"][0]["created_at"] == session["created_at"]
