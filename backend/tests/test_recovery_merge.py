"""Protect data and job recovery across the independent ticket migrations."""

import json
import multiprocessing
import os
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from fastapi.testclient import TestClient
from test_citation_integration import CitingEvaluator
from test_jd_weighting import analyze, confirm, reference
from test_mock_interview import answer, data, ready, refresh, start
from test_provenance import EXCERPT, register
from test_provenance import start as start_practice
from test_recovery import payload, wait_done
from test_resumes import confirmed_paste

from interview_backend.api import create_app
from interview_backend.contracts import TechnicalCheck
from interview_backend.model import ModelSettings


@pytest.mark.parametrize("legacy_layout", ["recovery5", "provenance7"])
def test_concurrent_upgrade_preserves_completed_records_and_feature_snapshots(
    tmp_path, legacy_layout
):
    database = tmp_path / "upgrade.sqlite3"
    with TestClient(
        create_app(
            database_path=database,
            evaluator=CitingEvaluator(),
            evidence_transport=httpx.MockTransport(
                lambda _: httpx.Response(200, text=f"<p>{EXCERPT}</p>")
            ),
        )
    ) as client:
        ready(client)
        config = {}
        if legacy_layout == "provenance7":
            mapping = confirm(client, analyze(client, "熟悉工具调用；熟悉 Kubernetes"))
            resume = confirmed_paste(client)
            config = {"jd": reference(mapping), "resume_id": resume["resume_id"]}
            evidence = data(register(client, "Q-INTERVIEW-INTRODUCTION"))
        session = start(client, **config)
        answer(client, session)
        session = refresh(client, session)
        ended = data(
            client.post(
                f"/api/v1/sessions/{session['session_id']}/finish",
                json={"expected_revision": session["revision"]},
            )
        )
        report = data(client.get(f"/api/v1/sessions/{session['session_id']}/report"))
        if legacy_layout == "provenance7":
            assert report["groups"][0]["feedback"]["independent_references"] == [evidence]
            receipt = data(
                client.post(
                    f"/api/v1/sessions/{session['session_id']}/reports",
                    json={
                        "turn_id": session["current_turn"]["id"],
                        "category": "score",
                        "explanation": "合并后保留历史评分疑问",
                    },
                )
            )

    with sqlite3.connect(database) as db:
        if legacy_layout == "recovery5":
            for table in (
                "session_jd",
                "jd_mappings",
                "session_resumes",
                "resumes",
                "verified_evidence",
                "user_reports",
            ):
                assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
                db.execute(f"DROP TABLE {table}")
            db.execute("ALTER TABLE submissions DROP COLUMN provenance_json")
            db.execute("PRAGMA user_version=5")
            # This old schema had no provenance field; upgrade adds a labeled
            # legacy snapshot while keeping the original feedback unchanged.
            for group in report["groups"]:
                for submission in group["submissions"]:
                    submission.pop("provenance")
        else:
            db.execute("DROP INDEX jobs_pending")
            for column in (
                "claim_token",
                "lease_expires_at",
                "attempts",
                "retry_revision",
                "recovery_after",
            ):
                db.execute(f"ALTER TABLE jobs DROP COLUMN {column}")
            db.execute("PRAGMA user_version=7")
        tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        columns = {
            table: [row[1] for row in db.execute(f"PRAGMA table_info({table})")] for table in tables
        }
        rows = {table: db.execute(f"SELECT * FROM {table}").fetchall() for table in tables}

    def restore():
        with TestClient(create_app(database_path=database)) as client:
            saved = data(client.get(f"/api/v1/sessions/{session['session_id']}"))
            assert saved["current_turn"] == ended["current_turn"]
            assert saved["submissions"][0]["feedback"] == ended["submissions"][0]["feedback"]
            restored_report = data(client.get(f"/api/v1/sessions/{session['session_id']}/report"))
            if legacy_layout == "recovery5":
                for group in restored_report["groups"]:
                    for submission in group["submissions"]:
                        provenance = submission.pop("provenance")
                        assert provenance["provenance_status"] == "legacy_without_evidence_snapshot"
                        assert provenance["question_code"] == group["question"]["code"]
                        assert provenance["answer_version"] == group["question"]["version"]
                        assert provenance["independent_references"] == []
            assert restored_report == report
            if legacy_layout == "provenance7":
                assert saved == ended
                assert data(client.get(f"/api/v1/jd-mappings/{mapping['id']}")) == mapping
                assert data(client.get(f"/api/v1/resumes/{resume['resume_id']}")) == resume
                assert (
                    data(
                        client.get(
                            f"/api/v1/sessions/{session['session_id']}/reports/{receipt['id']}"
                        )
                    )
                    == receipt
                )

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: restore(), range(4)))
    restore()
    with sqlite3.connect(database) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 8
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        for table in tables:
            assert (
                db.execute(f"SELECT {','.join(columns[table])} FROM {table}").fetchall()
                == rows[table]
            )


class DisputedEvaluator(CitingEvaluator):
    def evaluate(self, *, question, answer):
        result = super().evaluate(question=question, answer=answer)
        result.technical_checks = [
            TechnicalCheck(
                claim="Tasks 可并发调度协程",
                query="Tasks",
                reason="outside_answer",
                affected_dimensions=["accuracy"],
            )
        ]
        return result


def exit_during_verification(database, session):
    def verifier(_):
        os._exit(23)

    with TestClient(
        create_app(
            database_path=database,
            evaluator=DisputedEvaluator(),
            model_settings=ModelSettings(api_key="test-only"),
            model_transport=httpx.MockTransport(verifier),
            evidence_transport=httpx.MockTransport(lambda _: httpx.Response(200, text=EXCERPT)),
            job_lease_seconds=0.3,
        )
    ) as client:
        client.post(f"/api/v1/sessions/{session['session_id']}/answers", json=payload(session))


def test_process_exit_in_provenance_verification_recovers_jd_resume_interview_once(tmp_path):
    database = tmp_path / "verification-crash.sqlite3"
    with TestClient(
        create_app(
            database_path=database,
            evidence_transport=httpx.MockTransport(lambda _: httpx.Response(200, text=EXCERPT)),
        )
    ) as client:
        ready(client)
        mapping = confirm(client, analyze(client, "熟悉工具调用"))
        resume = confirmed_paste(client)
        evidence = data(register(client, "Q-INTERVIEW-INTRODUCTION"))
        session = start(client, jd=reference(mapping), resume_id=resume["resume_id"])
    process = multiprocessing.get_context("spawn").Process(
        target=exit_during_verification, args=(database, session)
    )
    process.start()
    process.join(15)
    try:
        assert process.exitcode == 23
    finally:
        if process.is_alive():
            process.kill()
            process.join(5)

    def verifier(request):
        context = json.loads(json.loads(request.content)["messages"][1]["content"])
        assert context["evidence"][0]["id"] == evidence["id"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "supported": True,
                                    "reference_id": evidence["id"],
                                    "quote": EXCERPT,
                                }
                            )
                        }
                    }
                ]
            },
        )

    with TestClient(
        create_app(
            database_path=database,
            evaluator=DisputedEvaluator(),
            model_settings=ModelSettings(api_key="test-only"),
            model_transport=httpx.MockTransport(verifier),
            evidence_transport=httpx.MockTransport(lambda _: httpx.Response(200, text=EXCERPT)),
        )
    ) as client:
        current = wait_done(client, session)
        assert current["phase"] == "stage_transition"
        assert current["jd"] == session["jd"]
        assert current["resume_context"] == session["resume_context"]
        assert len(current["submissions"]) == 1
        job = data(client.get(f"/api/v1/jobs/{current['submissions'][0]['job_id']}"))
        assert job["status"] == "succeeded" and job["attempts"] == 2
        ended = data(
            client.post(
                f"/api/v1/sessions/{session['session_id']}/finish",
                json={"expected_revision": current["revision"]},
            )
        )
        report = data(client.get(f"/api/v1/sessions/{session['session_id']}/report"))
        assert report["groups"][0]["feedback"]["technical_checks"][0]["status"] == "verified"
        assert report["groups"][0]["feedback"]["independent_references"] == [evidence]
    with TestClient(create_app(database_path=database)) as client:
        assert data(client.get(f"/api/v1/sessions/{session['session_id']}")) == ended
        assert data(client.get(f"/api/v1/sessions/{session['session_id']}/report")) == report


def test_default_lease_covers_sequential_evaluation_and_evidence_verification(
    tmp_path, monkeypatch
):
    # Advance time at the external boundary, so no real network calls or long waits
    # are needed. Each 55-second model call is within the default 60-second timeout.
    clock = time.time()
    calls = []

    class SlowEvaluation(DisputedEvaluator):
        def evaluate(self, *, question, answer):
            nonlocal clock
            clock += 55
            result = super().evaluate(question=question, answer=answer)
            result.technical_checks *= 2
            return result

    def verifier(request):
        nonlocal clock
        clock += 55
        calls.append(request)
        context = json.loads(json.loads(request.content)["messages"][1]["content"])
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "supported": True,
                                    "reference_id": context["evidence"][0]["id"],
                                    "quote": EXCERPT,
                                }
                            )
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr("interview_backend.practice.time.time", lambda: clock)
    with TestClient(
        create_app(
            database_path=tmp_path / "long-task.sqlite3",
            evaluator=SlowEvaluation(),
            model_settings=ModelSettings(api_key="test-only"),
            model_transport=httpx.MockTransport(verifier),
            evidence_transport=httpx.MockTransport(lambda _: httpx.Response(200, text=EXCERPT)),
        )
    ) as client:
        for code in ("Q-AGENT-SAMPLE-01", "Q-AGENT-SAMPLE-02"):
            data(register(client, code))
        session = start_practice(client)
        data(
            client.post(f"/api/v1/sessions/{session['session_id']}/answers", json=payload(session))
        )
        current = refresh(client, session)
        assert current["phase"] == "feedback_ready"
        assert len(calls) == 2
        saved = current["submissions"][0]
        assert all(check["status"] == "verified" for check in saved["feedback"]["technical_checks"])
        job = data(client.get(f"/api/v1/jobs/{saved['job_id']}"))
        assert job["status"] == "succeeded" and job["attempts"] == 1
