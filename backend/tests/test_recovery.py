"""Recovery is observed only through session, job and report HTTP endpoints."""

import json
import multiprocessing
import os
import socket
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import httpx
import pytest
from fastapi.testclient import TestClient
from test_mock_interview import InterviewEvaluator, ready
from test_mock_interview import start as start_mock
from test_practice import data, start

from interview_backend.api import create_app
from interview_backend.model import ModelError

ANSWER = "我说明具体职责和约束，再用成功、失败两类案例验证结果，记录个人行动并总结改进。"


def payload(session):
    return {
        "expected_revision": session["revision"],
        "turn_id": session["current_turn"]["id"],
        "client_submission_id": session["current_turn"]["id"],
        "disposition": "answered",
        "answer_text": ANSWER,
    }


class ExitDuringModel:
    def evaluate(self, *, question, answer):
        os._exit(19)


def crash_process(database, session):
    with TestClient(
        create_app(database_path=database, evaluator=ExitDuringModel(), job_lease_seconds=0.2)
    ) as client:
        client.post(f"/api/v1/sessions/{session['session_id']}/answers", json=payload(session))


def wait_done(client, session):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        current = data(client.get(f"/api/v1/sessions/{session['session_id']}"))
        if current["phase"] != "evaluating":
            return current
        time.sleep(0.03)
    pytest.fail("Saved evaluation was not recovered")


@pytest.mark.parametrize("mode", ["question_practice", "mock_interview"])
def test_killed_process_is_taken_over_without_a_second_answer_or_question(tmp_path, mode):
    database = tmp_path / "crash.sqlite3"
    with TestClient(create_app(database_path=database)) as client:
        if mode == "mock_interview":
            ready(client)
        session = start_mock(client) if mode == "mock_interview" else start(client)
    process = multiprocessing.get_context("spawn").Process(
        target=crash_process, args=(database, session)
    )
    process.start()
    process.join(15)
    try:
        assert process.exitcode == 19
    finally:
        if process.is_alive():
            process.kill()
            process.join(5)
    with TestClient(
        create_app(database_path=database, evaluator=InterviewEvaluator(), job_lease_seconds=0.2)
    ) as client:
        current = wait_done(client, session)
        assert current["phase"] == (
            "stage_transition" if mode == "mock_interview" else "feedback_ready"
        )
        assert current["current_turn"] == session["current_turn"]
        assert len(current["submissions"]) == 1
        saved = current["submissions"][0]
        assert saved["answer_text"] == ANSWER
        job = data(client.get(f"/api/v1/jobs/{saved['job_id']}"))
        assert job["status"] == "succeeded"
        assert job["attempts"] == 2
        replay = data(
            client.post(f"/api/v1/sessions/{session['session_id']}/answers", json=payload(session))
        )
        assert replay["idempotent_replay"]
        assert replay["submission"]["id"] == saved["id"]
        if mode == "mock_interview":
            current = data(
                client.post(
                    f"/api/v1/sessions/{session['session_id']}/finish",
                    json={"expected_revision": current["revision"]},
                )
            )
        report = data(client.get(f"/api/v1/sessions/{session['session_id']}/report"))
        assert data(client.get("/api/v1/sessions"))["total"] == 1
    with TestClient(create_app(database_path=database)) as client:
        assert data(client.get(f"/api/v1/sessions/{session['session_id']}")) == current
        assert data(client.get(f"/api/v1/sessions/{session['session_id']}/report")) == report


@pytest.mark.parametrize("mode", ["question_practice", "mock_interview"])
@pytest.mark.parametrize(
    "failure",
    [
        "MODEL_TIMEOUT",
        "MODEL_OUTPUT_INVALID",
        "MODEL_RATE_LIMITED",
        "RETRIEVAL_FAILED",
        "unexpected",
    ],
)
def test_failure_stage_and_idempotent_retry_survive_restart(tmp_path, mode, failure):
    class FailingEvaluator:
        def evaluate(self, *, question, answer):
            if failure == "unexpected":
                raise RuntimeError("private provider details must not escape")
            if failure == "MODEL_OUTPUT_INVALID":
                raise ValueError("invalid score and quote")
            raise ModelError(
                "temporary failure",
                failure,
                stage="retrieval" if failure == "RETRIEVAL_FAILED" else "evaluation",
            )

    database = tmp_path / "retry.sqlite3"
    with TestClient(create_app(database_path=database, evaluator=FailingEvaluator())) as client:
        if mode == "mock_interview":
            ready(client)
        session = start_mock(client) if mode == "mock_interview" else start(client)
        data(
            client.post(f"/api/v1/sessions/{session['session_id']}/answers", json=payload(session))
        )
        failed = wait_done(client, session)
        saved = failed["submissions"][0]
        assert failed["phase"] == "evaluation_failed"
        assert failed["available_actions"] == ["retry"] or "retry" in failed["available_actions"]
        assert "feedback" not in saved and "score" not in saved
        assert saved["answer_text"] == ANSWER
        error = saved["error"]
        assert error["phase"] == ("retrieval" if failure == "RETRIEVAL_FAILED" else "evaluation")
        assert error["action"] == "retry" and error["retryable"]
        assert "private provider" not in str(error)
        retry_body = {"expected_revision": failed["revision"]}
    with TestClient(create_app(database_path=database, evaluator=InterviewEvaluator())) as client:
        assert data(client.get(f"/api/v1/sessions/{session['session_id']}")) == failed
        url = f"/api/v1/sessions/{session['session_id']}/retry"
        with ThreadPoolExecutor(max_workers=2) as pool:
            replies = list(pool.map(lambda _: data(client.post(url, json=retry_body)), range(2)))
        assert replies[0] == replies[1] == {"job_id": saved["job_id"]}
        current = wait_done(client, session)
        assert len(current["submissions"]) == 1
        assert current["submissions"][0]["status"] == "completed"
        assert current["submissions"][0]["id"] == saved["id"]
        job = data(client.get(f"/api/v1/jobs/{saved['job_id']}"))
        assert job["status"] == "succeeded" and job["attempts"] == 2
        conflict = client.post(
            f"/api/v1/sessions/{session['session_id']}/answers",
            json={**payload(session), "client_submission_id": "different"},
        )
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "STATE_CONFLICT"
        assert conflict.json()["error"]["action"] == "refresh_session"


@pytest.mark.parametrize("mode", ["question_practice", "mock_interview"])
def test_live_lease_is_not_stolen_and_late_result_cannot_overwrite_takeover(tmp_path, mode):
    entered, release = Event(), Event()

    class OldEvaluator(InterviewEvaluator):
        def evaluate(self, *, question, answer):
            entered.set()
            assert release.wait(10)
            result = super().evaluate(question=question, answer=answer)
            for dimension in result.dimensions:
                dimension.score = 1
            return result

    database = tmp_path / "fenced.sqlite3"
    with TestClient(
        create_app(database_path=database, evaluator=OldEvaluator(), job_lease_seconds=1)
    ) as first:
        if mode == "mock_interview":
            ready(first)
        session = start_mock(first) if mode == "mock_interview" else start(first)
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(
                first.post,
                f"/api/v1/sessions/{session['session_id']}/answers",
                json=payload(session),
            )
            try:
                assert entered.wait(5)
                with TestClient(
                    create_app(database_path=database, evaluator=InterviewEvaluator())
                ) as second:
                    running = data(second.get(f"/api/v1/sessions/{session['session_id']}"))
                    job_id = running["submissions"][0]["job_id"]
                    assert data(second.get(f"/api/v1/jobs/{job_id}"))["attempts"] == 1
                    current = wait_done(second, session)
                    assert data(second.get(f"/api/v1/jobs/{job_id}"))["attempts"] >= 2
                    release.set()
                    data(pending.result(timeout=5))
                    assert data(second.get(f"/api/v1/sessions/{session['session_id']}")) == current
                    if mode == "mock_interview":
                        data(
                            second.post(
                                f"/api/v1/sessions/{session['session_id']}/finish",
                                json={"expected_revision": current["revision"]},
                            )
                        )
                        report = data(
                            second.get(f"/api/v1/sessions/{session['session_id']}/report")
                        )
                        assert report["groups"][0]["score"] == 75
                    else:
                        assert current["submissions"][0]["score"] == 75
            finally:
                release.set()


@pytest.mark.parametrize("status", ["queued", "running"])
def test_schema_four_unfinished_jobs_are_recovered_through_http(tmp_path, status):
    database = tmp_path / "legacy.sqlite3"
    # Arrange an interrupted schema-4 database, including the original five-column jobs table.
    with TestClient(create_app(database_path=database, evaluator=InterviewEvaluator())) as client:
        session = start(client)
    with sqlite3.connect(database) as legacy:
        legacy.executescript(
            "DROP TABLE jobs;"
            + "CREATE TABLE jobs (id TEXT PRIMARY KEY, submission_id TEXT NOT NULL UNIQUE REFERENCES submissions(id), status TEXT NOT NULL, phase TEXT NOT NULL, error_json TEXT);"
        )
        legacy.execute(
            "INSERT INTO submissions(id,session_id,turn_id,client_submission_id,request_json,disposition,answer_text,status,job_id) VALUES ('legacy-answer',?,?,?,?,'answered',?,'saved','legacy-job')",
            (
                session["session_id"],
                session["current_turn"]["id"],
                session["current_turn"]["id"],
                json.dumps(payload(session), ensure_ascii=False, sort_keys=True),
                ANSWER,
            ),
        )
        legacy.execute(
            "INSERT INTO jobs VALUES ('legacy-job','legacy-answer',?,'evaluation',NULL)", (status,)
        )
        legacy.execute("UPDATE sessions SET phase='evaluating',revision=revision+1")
        legacy.execute("PRAGMA user_version=4")
    with TestClient(create_app(database_path=database, evaluator=InterviewEvaluator())) as client:
        current = wait_done(client, session)
        assert current["submissions"][0]["id"] == "legacy-answer"
        assert current["submissions"][0]["score"] == 75
        assert data(client.get("/api/v1/jobs/legacy-job"))["status"] == "succeeded"


def test_concurrent_schema_four_startups_restore_the_same_saved_session(tmp_path):
    database = tmp_path / "concurrent-upgrade.sqlite3"
    with TestClient(create_app(database_path=database)) as client:
        session = start(client)
    with sqlite3.connect(database) as legacy:
        legacy.executescript(
            "DROP TABLE jobs;"
            "CREATE TABLE jobs (id TEXT PRIMARY KEY, submission_id TEXT NOT NULL UNIQUE REFERENCES submissions(id), status TEXT NOT NULL, phase TEXT NOT NULL, error_json TEXT);"
            "PRAGMA user_version=4;"
        )

    def restore():
        with TestClient(create_app(database_path=database)) as client:
            return data(client.get(f"/api/v1/sessions/{session['session_id']}"))

    with ThreadPoolExecutor(max_workers=4) as pool:
        with sqlite3.connect(database) as blocker:
            # A separate writer holds the upgrade lock while service startups inspect the schema.
            blocker.execute("BEGIN IMMEDIATE")
            futures = [pool.submit(restore) for _ in range(4)]
            time.sleep(0.3)
            blocker.commit()
        assert [future.result(timeout=10) for future in futures] == [session] * 4


def tcp_server(database, port, entered):
    import uvicorn

    class HoldDuringModel(InterviewEvaluator):
        def evaluate(self, *, question, answer):
            entered.set()
            Event().wait(30)
            raise RuntimeError("Test should kill this server during the provider call")

    uvicorn.run(
        create_app(
            database_path=database,
            evaluator=HoldDuringModel() if entered is not None else InterviewEvaluator(),
            job_lease_seconds=0.4,
        ),
        host="127.0.0.1",
        port=port,
        log_level="error",
    )


def launch_tcp(database, port, entered=None):
    process = multiprocessing.get_context("spawn").Process(
        target=tcp_server, args=(database, port, entered)
    )
    process.start()
    deadline = time.monotonic() + 10
    with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=0.5) as client:
        while time.monotonic() < deadline and process.is_alive():
            try:
                if client.get("/health/live").is_success:
                    return process
            except httpx.HTTPError:
                pass
            time.sleep(0.05)
    process.kill()
    process.join(5)
    pytest.fail("TCP acceptance server did not start")


@pytest.mark.parametrize("mode", ["question_practice", "mock_interview"])
def test_tcp_server_killed_during_model_call_recovers_one_complete_history(tmp_path, mode):
    database = tmp_path / "tcp.sqlite3"
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    entered = multiprocessing.get_context("spawn").Event()
    process = launch_tcp(database, port, entered)
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=5) as client:
            if mode == "mock_interview":
                ready(client)
            session = start_mock(client) if mode == "mock_interview" else start(client)
            data(
                client.post(
                    f"/api/v1/sessions/{session['session_id']}/answers", json=payload(session)
                )
            )
            assert entered.wait(5)
    finally:
        process.kill()
        process.join(5)
    process = launch_tcp(database, port)
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=5) as client:
            current = wait_done(client, session)
            assert len(current["submissions"]) == 1
            assert data(
                client.post(
                    f"/api/v1/sessions/{session['session_id']}/answers", json=payload(session)
                )
            )["idempotent_replay"]
            while mode == "mock_interview" and current["status"] == "active":
                if current["phase"] == "stage_transition":
                    current = data(
                        client.post(
                            f"/api/v1/sessions/{session['session_id']}/next",
                            json={"expected_revision": current["revision"]},
                        )
                    )
                if current["status"] == "active":
                    data(
                        client.post(
                            f"/api/v1/sessions/{session['session_id']}/answers",
                            json=payload(current),
                        )
                    )
                    current = wait_done(client, current)
            assert current["status"] == "completed"
            assert len({s["id"] for s in current["submissions"]}) == len(current["submissions"])
            report = data(client.get(f"/api/v1/sessions/{session['session_id']}/report"))
            assert data(client.get("/api/v1/sessions"))["total"] == 1
    finally:
        process.kill()
        process.join(5)
    process = launch_tcp(database, port)
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=5) as client:
            assert data(client.get(f"/api/v1/sessions/{session['session_id']}")) == current
            assert data(client.get(f"/api/v1/sessions/{session['session_id']}/report")) == report
    finally:
        process.kill()
        process.join(5)
