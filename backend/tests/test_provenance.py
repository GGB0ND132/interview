import json
import sqlite3
from importlib.resources import files
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from interview_backend.api import create_app
from interview_backend.contracts import Dimension, ModelEvaluation, TechnicalCheck

PACK = "pack_agent_basics_sample"
PREFIX = "/api/v1"
URL = "https://docs.python.org/3/library/asyncio-task.html"
EXCERPT = "Tasks are used to schedule coroutines concurrently."


def data(response):
    assert response.is_success, response.text
    return response.json()["data"]


class Evaluator:
    def evaluate(self, *, question, answer):
        return ModelEvaluation(
            dimensions=[
                Dimension(name=name, score=80, reason="按题库答案评价", answer_quote=answer)
                for name in ("accuracy", "completeness", "relevance", "structure", "specificity")
            ],
            strengths=["表达清晰"],
            improvements=["补充边界"],
            used_reference_ids=[r["id"] for r in question.get("verified_references", [])],
        )


def start(client):
    draft = data(client.post(f"{PREFIX}/sessions", json={"pack_id": PACK}))
    return data(
        client.post(f"{PREFIX}/sessions/{draft['session_id']}/start", json={"expected_revision": 0})
    )


def complete(client, session, disposition="answered"):
    data(
        client.post(
            f"{PREFIX}/sessions/{session['session_id']}/answers",
            json={
                "turn_id": session["current_turn"]["id"],
                "expected_revision": session["revision"],
                "client_submission_id": "answer",
                "disposition": disposition,
                "answer_text": "根据真实结果继续执行" if disposition == "answered" else "",
            },
        )
    )
    return data(client.get(f"{PREFIX}/sessions/{session['session_id']}"))["submissions"][0]


def register(client, code, **changes):
    return client.post(
        f"{PREFIX}/maintenance/questions/{code}/evidence",
        json={
            "expected_version": 1,
            "title": "Coroutines and Tasks",
            "url": URL,
            "excerpt": EXCERPT,
            "claim": "Tasks 可并发调度协程",
            "reviewer": "maintainer",
            **changes,
        },
    )


def test_used_citation_keeps_verified_excerpt_and_version_after_restart(tmp_path: Path):
    database = tmp_path / "evidence.sqlite3"
    transport = httpx.MockTransport(lambda _: httpx.Response(200, text=f"<p>{EXCERPT}</p>"))
    with TestClient(
        create_app(database_path=database, evaluator=Evaluator(), evidence_transport=transport)
    ) as client:
        for code in ("Q-AGENT-SAMPLE-01", "Q-AGENT-SAMPLE-02"):
            evidence = data(register(client, code))
            assert evidence["excerpt"] == EXCERPT
        session = start(client)
        submission = complete(client, session)
        feedback = submission["feedback"]
        assert feedback["question_code"] == session["current_turn"]["question_code"]
        assert feedback["answer_version"] == 1
        assert "answer_generation" not in feedback
        assert "answer_origin" not in feedback
        assert len(feedback["independent_references"]) == 1
        reference = feedback["independent_references"][0]
        assert reference["excerpt"] == EXCERPT
        assert reference["claim"] == "Tasks 可并发调度协程"
        assert feedback["question_source"]["locator"].startswith("samples.json#")
        report = data(client.get(f"{PREFIX}/sessions/{session['session_id']}/report"))
        assert report["provenance"]["independent_references"] == [reference]
        internal = data(
            client.get(f"{PREFIX}/maintenance/submissions/{submission['id']}/provenance")
        )
        assert internal["answer_origin"] == "agent_generated"
        assert internal["answer_generation"]["author"] == "Codex"
        assert "agent_generated" not in str(submission)
    with TestClient(create_app(database_path=database)) as client:
        saved = data(client.get(f"{PREFIX}/sessions/{session['session_id']}"))["submissions"][0]
        assert saved == submission


def test_only_original_source_is_not_presented_as_independent_evidence(tmp_path):
    with TestClient(
        create_app(database_path=tmp_path / "original.sqlite3", evaluator=Evaluator())
    ) as client:
        submission = complete(client, start(client))
        assert submission["feedback"]["independent_references"] == []
        assert submission["feedback"]["question_source"]
        assert submission["provenance"]["independent_references"] == []


class DisputedEvaluator(Evaluator):
    def evaluate(self, *, question, answer):
        return (
            super()
            .evaluate(question=question, answer=answer)
            .model_copy(
                update={
                    "technical_checks": [
                        TechnicalCheck(
                            claim="Tasks 可并发调度协程",
                            query="Tasks coroutines concurrently",
                            reason="version_dispute",
                            affected_dimensions=["accuracy", "completeness"],
                        )
                    ],
                }
            )
        )


def test_disputed_claim_without_direct_evidence_abstains_and_is_traceable(tmp_path):
    with TestClient(
        create_app(database_path=tmp_path / "dispute.sqlite3", evaluator=DisputedEvaluator())
    ) as client:
        submission = complete(client, start(client))
        feedback = submission["feedback"]
        assert feedback["assessment_status"] == "partial"
        assert feedback["assessment_coverage"] == 0.4
        assert feedback["dimensions"][0]["score"] is None
        assert feedback["dimensions"][1]["score"] is None
        assert feedback["technical_checks"][0]["status"] == "insufficient_evidence"
        assert feedback["technical_checks"][0]["query"] == "Tasks coroutines concurrently"
        assert feedback["technical_explanations"] == []
        assert feedback["independent_references"] == []


@pytest.mark.parametrize(
    "outcome", ["supported", "unrelated", "timeout", "invented_quote", "changed_excerpt"]
)
def test_on_demand_retrieval_requires_direct_support_and_records_failure(tmp_path, outcome):
    def document(_):
        if outcome == "timeout" and registered:
            raise httpx.ReadTimeout("private provider detail must stay private")
        if outcome == "changed_excerpt" and registered:
            return httpx.Response(200, text="Source changed and the original quote disappeared.")
        return httpx.Response(200, text=f"<p>{EXCERPT}</p>")

    def model(request):
        body = json.loads(request.content)
        assert "Tasks 可并发调度协程" in body["messages"][-1]["content"]
        context = json.loads(body["messages"][-1]["content"])
        reference = context["evidence"][0]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "supported": outcome != "unrelated",
                                    "reference_id": reference["id"],
                                    "quote": "invented" if outcome == "invented_quote" else EXCERPT,
                                }
                            )
                        }
                    }
                ]
            },
        )

    from interview_backend.model import ModelSettings

    registered = False
    with TestClient(
        create_app(
            database_path=tmp_path / "retrieval.sqlite3",
            evaluator=DisputedEvaluator(),
            evidence_transport=httpx.MockTransport(document),
            model_transport=httpx.MockTransport(model),
            model_settings=ModelSettings(api_key="test-only"),
        )
    ) as client:
        # Start before adding the evidence: this can only be found through on-demand search.
        session = start(client)
        code = session["current_turn"]["question_code"]
        data(register(client, code))
        registered = True
        submission = complete(client, session)
        feedback = submission["feedback"]
        check = feedback["technical_checks"][0]
        if outcome == "supported":
            assert check["status"] == "verified"
            assert check["support_quote"] == EXCERPT
            assert feedback["technical_explanations"][0]["claim"] == "Tasks 可并发调度协程"
            assert feedback["independent_references"][0]["excerpt"] == EXCERPT
        else:
            assert feedback["technical_explanations"] == []
            assert feedback["independent_references"] == []
            assert feedback["dimensions"][0]["score"] is None
            assert check["status"] == (
                "retrieval_failed"
                if outcome in {"timeout", "invented_quote", "changed_excerpt"}
                else "insufficient_evidence"
            )
            assert check["attempt_id"]
            assert "private provider" not in str(feedback)


def test_user_report_binds_saved_answer_version_and_maintainer_can_handle_it(tmp_path):
    database = tmp_path / "reports.sqlite3"
    batch = json.loads(
        files("interview_backend").joinpath("mianstack_example.json").read_text(encoding="utf-8")
    )
    batch["questions"] = batch["questions"][:1]
    pack = "pack_agent_basics_mianstack"
    with TestClient(create_app(database_path=database, evaluator=Evaluator())) as client:
        data(client.post(f"{PREFIX}/maintenance/question-publications", json=batch))
        draft = data(client.post(f"{PREFIX}/sessions", json={"pack_id": pack}))
        session = data(
            client.post(
                f"{PREFIX}/sessions/{draft['session_id']}/start", json={"expected_revision": 0}
            )
        )
        complete(client, session)
        # The live bank changes, but the report must refer to the answer actually assessed.
        batch["questions"][0].update(content_version="report-v2", answer_origin="maintainer_edited")
        batch["questions"][0]["answer"] += "\n维护者已补充边界说明。"
        data(client.post(f"{PREFIX}/maintenance/question-publications", json=batch))
        body = {
            "turn_id": session["current_turn"]["id"],
            "category": "score",
            "explanation": "这项技术判断存在版本差异，请核查。",
        }
        report = data(client.post(f"{PREFIX}/sessions/{session['session_id']}/reports", json=body))
        assert report["question_code"] == "Q-0058"
        assert report["answer_version"] == 1
        assert report["status"] == "open"
        assert report["explanation"] == body["explanation"]
        assert report["submission_id"]
        report_id = report["id"]
        # A user cannot forge the target version or set processing state.
        forged = client.post(
            f"{PREFIX}/sessions/{session['session_id']}/reports", json={**body, "answer_version": 2}
        )
        assert forged.status_code == 422
        assert (
            client.post(
                f"{PREFIX}/sessions/{session['session_id']}/reports",
                json={**body, "turn_id": "other"},
            ).status_code
            == 409
        )
        pending = data(client.get(f"{PREFIX}/maintenance/reports?status=open"))
        assert [r["id"] for r in pending["items"]] == [report_id]
        handled = data(
            client.post(
                f"{PREFIX}/maintenance/reports/{report_id}",
                json={
                    "expected_status": "open",
                    "status": "resolved",
                    "note": "已复核，停用新版等待修正。",
                },
            )
        )
        assert handled["status"] == "resolved"
        data(
            client.post(
                f"{PREFIX}/maintenance/questions/Q-0058/disable",
                json={"expected_version": 2, "reason": "复核确认答案错误"},
            )
        )
        available = data(client.post(f"{PREFIX}/role-packs/{pack}/availability", json={}))
        assert available["available_count"] == 0
        assert client.post(f"{PREFIX}/sessions", json={"pack_id": pack}).status_code == 400
        assert (
            data(client.get(f"{PREFIX}/sessions/{session['session_id']}/reports/{report_id}"))
            == handled
        )
    with TestClient(create_app(database_path=database)) as client:
        assert data(client.get(f"{PREFIX}/maintenance/reports/{report_id}")) == handled


@pytest.mark.parametrize(
    "problem", ["invented_excerpt", "script_only", "redirect", "untrusted_url", "stale_version"]
)
def test_unverified_material_cannot_be_registered_as_evidence(tmp_path, problem):
    def document(_):
        if problem == "redirect":
            return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})
        text = f"<script>{EXCERPT}</script>" if problem == "script_only" else "unrelated document"
        return httpx.Response(200, text=text)

    with TestClient(
        create_app(
            database_path=tmp_path / "bad-evidence.sqlite3",
            evidence_transport=httpx.MockTransport(document),
        )
    ) as client:
        changes = (
            {"url": "http://127.0.0.1/private"}
            if problem == "untrusted_url"
            else {"expected_version": 2}
            if problem == "stale_version"
            else {}
        )
        response = register(client, "Q-AGENT-SAMPLE-01", **changes)
        assert response.status_code in {400, 409}
        assert (
            data(
                client.get(
                    f"{PREFIX}/maintenance/questions/Q-AGENT-SAMPLE-01/evidence?answer_version=1"
                )
            )["items"]
            == []
        )


@pytest.mark.parametrize("disposition", ["blank_answer", "skipped"])
def test_blank_and_skip_also_keep_provenance_without_claiming_evidence_use(tmp_path, disposition):
    with TestClient(create_app(database_path=tmp_path / "blank.sqlite3")) as client:
        session = start(client)
        submission = complete(client, session, disposition)
        assert submission["provenance"]["answer_version"] == 1
        assert submission["provenance"]["question_code"] == session["current_turn"]["question_code"]
        assert submission["provenance"]["independent_references"] == []


def test_legacy_score_migrates_without_exposing_old_unverifiable_citations(tmp_path):
    database = tmp_path / "legacy.sqlite3"
    resource = files("interview_backend")
    sample = json.loads(resource.joinpath("samples.json").read_text(encoding="utf-8"))
    question = {**sample["questions"][0], "version": 1, "generation": sample["generation"]}
    with sqlite3.connect(database) as legacy:
        legacy.executescript(resource.joinpath("schema.sql").read_text(encoding="utf-8"))
        legacy.executescript(resource.joinpath("migration_2.sql").read_text(encoding="utf-8"))
        legacy.executescript(resource.joinpath("migration_3.sql").read_text(encoding="utf-8"))
        legacy.execute("INSERT INTO role_packs VALUES (?,?,?,?)", (PACK, "sample", "published", 1))
        legacy.execute(
            "INSERT INTO sessions(id,pack_id,pack_version,config_json,status,phase,turn_id,question_json) VALUES ('legacy',?,1,'{\"difficulty\":\"easy\"}','completed','feedback_ready','turn',?)",
            (PACK, json.dumps(question)),
        )
        legacy.execute(
            "INSERT INTO submissions(id,session_id,turn_id,client_submission_id,request_json,disposition,answer_text,status,score,evaluation_json) VALUES ('old','legacy','turn','submitted','{}','answered','answer','completed',80,?)",
            (
                json.dumps(
                    {
                        "answer_version": 1,
                        "answer_origin": "agent_generated",
                        "answer_generation": sample["generation"],
                        "independent_references": question["answer_refs"],
                    }
                ),
            ),
        )
    with TestClient(create_app(database_path=database)) as client:
        submission = data(client.get(f"{PREFIX}/sessions/legacy"))["submissions"][0]
        assert submission["score"] == 80
        assert submission["provenance"]["answer_version"] == 1
        assert submission["provenance"]["question_code"] == "Q-AGENT-SAMPLE-01"
        assert submission["feedback"]["independent_references"] == []
        assert "agent_generated" not in str(submission)
        internal = data(client.get(f"{PREFIX}/maintenance/submissions/old/provenance"))
        assert internal["answer_origin"] == "agent_generated"


def test_model_cannot_invent_reference_ids_and_answer_remains_retryable(tmp_path):
    class InventedReference(Evaluator):
        def evaluate(self, **kwargs):
            return (
                super()
                .evaluate(**kwargs)
                .model_copy(update={"used_reference_ids": ["fake-document"]})
            )

    with TestClient(
        create_app(database_path=tmp_path / "invented.sqlite3", evaluator=InventedReference())
    ) as client:
        submission = complete(client, start(client))
        assert submission["status"] == "failed"
        assert submission["error"]["code"] == "MODEL_OUTPUT_INVALID"
        assert submission["answer_text"] == "根据真实结果继续执行"
        assert "feedback" not in submission


def test_rejected_support_cannot_survive_as_startup_citation_or_unaffected_prose(tmp_path):
    class OverconfidentEvaluator(DisputedEvaluator):
        def evaluate(self, **kwargs):
            result = super().evaluate(**kwargs)
            return result.model_copy(
                update={
                    "dimensions": [
                        d.model_copy(update={"reason": "UNVERIFIED_CONCLUSION is definitely true"})
                        for d in result.dimensions
                    ]
                }
            )

    def reject(_):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "supported": False,
                                    "reference_id": None,
                                    "quote": "",
                                }
                            )
                        }
                    }
                ]
            },
        )

    from interview_backend.model import ModelSettings

    with TestClient(
        create_app(
            database_path=tmp_path / "rejected.sqlite3",
            evaluator=OverconfidentEvaluator(),
            evidence_transport=httpx.MockTransport(lambda _: httpx.Response(200, text=EXCERPT)),
            model_transport=httpx.MockTransport(reject),
            model_settings=ModelSettings(api_key="test-only"),
        )
    ) as client:
        for code in ("Q-AGENT-SAMPLE-01", "Q-AGENT-SAMPLE-02"):
            data(register(client, code))
        feedback = complete(client, start(client))["feedback"]
        assert feedback["technical_checks"][0]["status"] == "insufficient_evidence"
        assert feedback["independent_references"] == []
        assert all("UNVERIFIED_CONCLUSION" not in d["reason"] for d in feedback["dimensions"])
