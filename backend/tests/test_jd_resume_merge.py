"""Regression coverage for integrating the two independent schema-5 branches."""

import json
import sqlite3

import httpx
import pytest
from fastapi.testclient import TestClient
from test_jd_weighting import analyze, confirm, reference
from test_mock_interview import InterviewEvaluator, data, ready, run_remaining, start
from test_resumes import confirmed_paste

from interview_backend.api import create_app
from interview_backend.model import ModelSettings


@pytest.mark.parametrize("legacy_layout", ["schema4", "jd5", "resume5"])
def test_legacy_layouts_upgrade_without_losing_records_or_sessions(tmp_path, legacy_layout):
    database = tmp_path / "legacy.sqlite3"
    mapping = resume = None
    config = {}
    with TestClient(create_app(database_path=database)) as client:
        ready(client)
        if legacy_layout == "jd5":
            mapping = confirm(client, analyze(client, "熟悉工具调用"))
            config["jd"] = reference(mapping)
        if legacy_layout == "resume5":
            resume = confirmed_paste(client)
            config["resume_id"] = resume["resume_id"]
        session = start(client, **config)

    # Construct each legacy table layout in a temporary database. Only empty,
    # unavailable-feature tables are removed; real API-created records remain.
    with sqlite3.connect(database) as db:
        if legacy_layout != "jd5":
            db.execute("DROP TABLE session_jd")
            db.execute("DROP TABLE jd_mappings")
        if legacy_layout != "resume5":
            db.execute("DROP TABLE session_resumes")
            db.execute("DROP TABLE resumes")
        db.execute(f"PRAGMA user_version={4 if legacy_layout == 'schema4' else 5}")
        tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        saved_rows = {table: db.execute(f'SELECT * FROM "{table}"').fetchall() for table in tables}

    # Open twice to verify both migration and normal startup retain old data.
    for _ in range(2):
        with TestClient(create_app(database_path=database)) as client:
            assert data(client.get(f"/api/v1/sessions/{session['session_id']}")) == session
            if mapping is not None:
                assert data(client.get(f"/api/v1/jd-mappings/{mapping['id']}")) == mapping
            if resume is not None:
                assert data(client.get(f"/api/v1/resumes/{resume['resume_id']}")) == resume
        with sqlite3.connect(database) as db:
            assert db.execute("PRAGMA user_version").fetchone()[0] == 7
            assert db.execute("PRAGMA foreign_key_check").fetchall() == []
            for table, rows in saved_rows.items():
                assert db.execute(f'SELECT * FROM "{table}"').fetchall() == rows

    with TestClient(create_app(database_path=database)) as client:
        mapping = confirm(client, analyze(client, "熟悉工具调用"))
        resume = confirmed_paste(client)
        combined = start(client, jd=reference(mapping), resume_id=resume["resume_id"])
        assert combined["jd"]["id"] == mapping["id"]
        assert combined["resume_context"] == resume["confirmed"]


@pytest.mark.parametrize("no_project", [False, True])
def test_jd_and_resume_coexist_in_model_context_report_and_restart(tmp_path, no_project):
    calls = []

    def provider(request):
        body = json.loads(request.content)
        context = json.loads(body["messages"][1]["content"])
        calls.append((body["messages"][0]["content"], context))
        result = InterviewEvaluator().evaluate(question=context, answer=context["user_answer"])
        return httpx.Response(
            200, json={"choices": [{"message": {"content": result.model_dump_json()}}]}
        )

    database = tmp_path / "combined.sqlite3"
    with TestClient(
        create_app(
            database_path=database,
            model_settings=ModelSettings(api_key="test-only", base_url="https://model.test/v1"),
            model_transport=httpx.MockTransport(provider),
        )
    ) as client:
        ready(client)
        mapping = confirm(client, analyze(client, "熟悉工具调用；熟悉 Kubernetes 运维"))
        resume = confirmed_paste(client, no_project=no_project)
        session = start(client, jd=reference(mapping), resume_id=resume["resume_id"])
        weights = {c["competency_id"]: c["weight"] for c in session["plan"]["topic_candidates"]}
        assert weights["agent_tool_calling"] == 4
        assert session["plan"]["questions"][1]["stage"] == (
            "scenario" if no_project else "experience"
        )
        report = run_remaining(client, session)
        assert report["resume_context"] == resume["confirmed"]
        assert report["interview_completeness"] == "complete"
        assert report["completeness"] == "partial"  # Unsupported JD remains a gap.
        assert report["jd_gaps"]
        assert report["plan"] == session["plan"]
        for system, context in calls:
            interview = context["interview_context"]
            assert "confirmed_job_requirements" in interview
            assert "不是技术正确性证据" in system and "候选人陈述" in system
            assert "不选中的项目" not in json.dumps(context, ensure_ascii=False)
            if interview["stage"] in {"experience", "technical"}:
                assert interview["resume_context"] == resume["confirmed"]
            if interview["stage"] == "technical":
                saved = data(client.get(f"/api/v1/maintenance/questions/{context['code']}"))
                assert context["answer"] == saved["versions"][-1]["answer"]
                assert context["rubric"] == saved["versions"][-1]["rubric"]
        assert any(c["interview_context"]["stage"] == "technical" for _, c in calls)
        saved_session = data(client.get(f"/api/v1/sessions/{session['session_id']}"))
    with TestClient(create_app(database_path=database)) as client:
        assert data(client.get(f"/api/v1/sessions/{session['session_id']}")) == saved_session
        assert data(client.get(f"/api/v1/sessions/{session['session_id']}/report")) == report
