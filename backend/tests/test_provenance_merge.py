import sqlite3

import pytest
from fastapi.testclient import TestClient
from test_provenance import Evaluator, complete, data, start

from interview_backend.api import create_app


@pytest.mark.parametrize("layout", ["provenance4", "main6"])
def test_legacy_sources_scores_and_reports_survive_both_schema_lineages(tmp_path, layout):
    database = tmp_path / "legacy.sqlite3"
    with TestClient(create_app(database_path=database, evaluator=Evaluator())) as client:
        session = start(client)
        submission = complete(client, session)
        receipt = data(
            client.post(
                f"/api/v1/sessions/{session['session_id']}/reports",
                json={
                    "turn_id": session["current_turn"]["id"],
                    "category": "question",
                    "explanation": "请保留历史版本",
                },
            )
        )
    with sqlite3.connect(database) as db:
        if layout == "provenance4":
            for table in (
                "session_jd",
                "jd_mappings",
                "session_resumes",
                "resumes",
                "mock_interviews",
            ):
                db.execute(f"DROP TABLE {table}")
            db.execute("PRAGMA user_version=4")
        else:
            db.execute("UPDATE submissions SET provenance_json=NULL")
            db.execute("ALTER TABLE submissions DROP COLUMN provenance_json")
            db.execute("PRAGMA user_version=6")
    for _ in range(2):
        with TestClient(create_app(database_path=database)) as client:
            saved = data(client.get(f"/api/v1/sessions/{session['session_id']}"))["submissions"][0]
            assert saved["score"] == submission["score"]
            assert saved["feedback"] == submission["feedback"]
            assert saved["provenance"]["question_code"] == session["current_turn"]["question_code"]
            assert saved["provenance"]["answer_version"] == 1
            assert saved["provenance"]["independent_references"] == []
            assert (
                data(
                    client.get(f"/api/v1/sessions/{session['session_id']}/reports/{receipt['id']}")
                )
                == receipt
            )
