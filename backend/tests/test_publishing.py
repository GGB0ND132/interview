import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from importlib.resources import files
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from interview_backend.api import create_app

PACK = "pack_agent_basics_mianstack"
CONFIG = {"difficulty": "easy", "mode": "question_practice"}


def batch():
    return json.loads(
        files("interview_backend").joinpath("mianstack_example.json").read_text(encoding="utf-8")
    )


def data(response):
    assert response.is_success, response.text
    return response.json()["data"]


def test_preview_is_read_only_and_publication_is_idempotent_after_restart(tmp_path: Path):
    database = tmp_path / "publishing.sqlite3"
    with TestClient(create_app(database_path=database)) as client:
        preview = data(
            client.post("/api/v1/maintenance/question-publications/preview", json=batch())
        )
        assert preview["accepted_count"] == 2
        assert preview["rejected_count"] == 0
        assert preview["topic_counts"]["Agent 基础与运行循环"] == 1
        before = data(client.post(f"/api/v1/role-packs/{PACK}/availability", json=CONFIG))
        assert before["available_count"] == 0
        published = data(client.post("/api/v1/maintenance/question-publications", json=batch()))
        assert published["imported_count"] == 2
        available = data(client.post(f"/api/v1/role-packs/{PACK}/availability", json=CONFIG))
        assert available["available_count"] == 2
        assert available["topic_counts"] == preview["topic_counts"]
    with TestClient(create_app(database_path=database)) as client:
        replay = data(client.post("/api/v1/maintenance/question-publications", json=batch()))
        assert replay["imported_count"] == 0
        assert replay["unchanged_count"] == 2
        saved = data(
            client.get(f"/api/v1/maintenance/question-publications/{published['publication_id']}")
        )
        assert saved == published


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"answer": ""}, "INVALID_FIELD"),
        ({"answer": " " * 80}, "INVALID_CONTENT"),
        ({"answer": "TODO：这是一段尚未完成的答案。" * 5}, "INVALID_CONTENT"),
        ({"rubric": ["待补充评分点"]}, "INVALID_CONTENT"),
        ({"rubric": []}, "INVALID_FIELD"),
        ({"competency_id": "unknown_ability"}, "INVALID_CLASSIFICATION"),
        ({"topic": "记忆系统"}, "SOURCE_MISMATCH"),
        ({"content_version": " "}, "INVALID_CONTENT"),
        ({"status": "disabled"}, "QUESTION_DISABLED"),
        ({"generation": None, "answer_origin": "agent_generated"}, "GENERATION_REQUIRED"),
        (
            {"answer_origin": "source_original", "answer": "维护者已改写原始答案。" * 10},
            "ANSWER_ORIGIN_MISMATCH",
        ),
    ],
)
def test_invalid_candidate_is_rejected_without_blocking_valid_rows(tmp_path, change, reason):
    request = batch()
    request["questions"][0].update(change)
    with TestClient(create_app(database_path=tmp_path / "reject.sqlite3")) as client:
        preview = data(
            client.post("/api/v1/maintenance/question-publications/preview", json=request)
        )
        assert preview["accepted_count"] == 1
        assert reason in {item["code"] for item in preview["items"][0]["reasons"]}
        published = data(client.post("/api/v1/maintenance/question-publications", json=request))
        assert published["rejected_count"] == 1
        assert published["items"][0]["reasons"] == preview["items"][0]["reasons"]
        assert (
            data(client.post(f"/api/v1/role-packs/{PACK}/availability", json=CONFIG))[
                "available_count"
            ]
            == 1
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("commit", "main"),
        ("path", "interviews/MJ-NC-2026-0002.md"),
        ("original_id", "Q-0140"),
        ("url", "https://example.com/fake"),
        ("answer_status", "pending"),
        ("license", "unknown"),
        ("attribution", ""),
    ],
)
def test_source_locator_must_match_fixed_standard_question(tmp_path, field, value):
    request = batch()
    request["questions"][0]["source"][field] = value
    with TestClient(create_app(database_path=tmp_path / "source.sqlite3")) as client:
        preview = data(
            client.post("/api/v1/maintenance/question-publications/preview", json=request)
        )
        assert preview["items"][0]["accepted"] is False
        assert preview["items"][0]["reasons"]


def test_duplicate_ids_reject_all_occurrences_and_missing_fields_are_per_row(tmp_path):
    request = batch()
    request["questions"].append(deepcopy(request["questions"][0]))
    request["questions"].append({"code": "Q-0597"})
    with TestClient(create_app(database_path=tmp_path / "duplicate.sqlite3")) as client:
        report = data(client.post("/api/v1/maintenance/question-publications", json=request))
        assert report["accepted_count"] == 1
        assert report["rejected_count"] == 3
        assert report["items"][0]["reasons"][0]["code"] == "DUPLICATE_ID"
        assert report["items"][2]["reasons"][0]["code"] == "DUPLICATE_ID"
        assert any(item["field"] == "answer" for item in report["items"][3]["reasons"])


def start(client, code="Q-0058"):
    competency = "agent_loop" if code == "Q-0058" else "agent_workflow_recovery"
    draft = data(
        client.post(
            "/api/v1/sessions",
            json={"pack_id": PACK, "config": {**CONFIG, "focus_competency_ids": [competency]}},
        )
    )
    return data(
        client.post(f"/api/v1/sessions/{draft['session_id']}/start", json={"expected_revision": 0})
    )


def test_content_changes_create_versions_and_old_sessions_keep_their_scoring_snapshot(tmp_path):
    from test_practice import Evaluator

    class CapturingEvaluator(Evaluator):
        def evaluate(self, *, question, answer):
            self.question = question
            return super().evaluate(question=question, answer=answer)

    evaluator = CapturingEvaluator()
    database = tmp_path / "versions.sqlite3"
    original = batch()
    with TestClient(create_app(database_path=database, evaluator=evaluator)) as client:
        data(client.post("/api/v1/maintenance/question-publications", json=original))
        old_session = start(client)
        changed = deepcopy(original)
        changed["questions"][0].update(
            content_version="2",
            answer_origin="maintainer_edited",
            answer="模型根据目标和反馈决定动作，程序执行工具并更新状态；运行循环检查任务完成与执行预算，避免无限重试。",
        )
        changed["questions"][0]["rubric"].append("说明如何根据失败原因限制重试，并避免重复副作用。")
        report = data(client.post("/api/v1/maintenance/question-publications", json=changed))
        assert report["items"][0]["version"] == 2
        assert report["imported_count"] == 1
        assert report["unchanged_count"] == 1
        assert start(client)["current_turn"]["question_version"] == 2
        collision = deepcopy(changed)
        collision["questions"][0]["rubric"].append("同一个内容版本不能悄悄改写评分点。")
        rejected = data(client.post("/api/v1/maintenance/question-publications", json=collision))
        assert rejected["items"][0]["reasons"][0]["code"] == "CONTENT_VERSION_CONFLICT"
        rollback = data(client.post("/api/v1/maintenance/question-publications", json=original))
        assert rollback["items"][0]["reasons"][0]["code"] == "STALE_CONTENT_VERSION"
    with TestClient(create_app(database_path=database, evaluator=evaluator)) as client:
        assert (
            data(client.get(f"/api/v1/sessions/{old_session['session_id']}"))["current_turn"][
                "question_version"
            ]
            == 1
        )
        data(
            client.post(
                f"/api/v1/sessions/{old_session['session_id']}/answers",
                json={
                    "turn_id": old_session["current_turn"]["id"],
                    "expected_revision": 1,
                    "client_submission_id": "old-snapshot",
                    "disposition": "answered",
                    "answer_text": "我会校验参数，限制权限和执行次数，并记录失败以便安全重试。",
                },
            )
        )
        assert evaluator.question["answer"] == original["questions"][0]["answer"]
        assert evaluator.question["rubric"] == original["questions"][0]["rubric"]
        versions = data(client.get("/api/v1/maintenance/questions/Q-0058"))["versions"]
        assert [item["version"] for item in versions] == [1, 2]
        assert versions[0]["source"]["original_title"] == "Agent 是什么，由哪些核心能力和组件组成？"


def test_disabling_latest_version_removes_it_without_falling_back_or_undoing_sessions(tmp_path):
    with TestClient(create_app(database_path=tmp_path / "disabled.sqlite3")) as client:
        data(client.post("/api/v1/maintenance/question-publications", json=batch()))
        session = start(client)
        disabled = data(
            client.post(
                "/api/v1/maintenance/questions/Q-0058/disable",
                json={"expected_version": 1, "reason": "答案有争议，暂停评分"},
            )
        )
        assert disabled["status"] == "disabled"
        assert (
            data(client.post(f"/api/v1/role-packs/{PACK}/availability", json=CONFIG))[
                "available_count"
            ]
            == 1
        )
        assert (
            data(client.get(f"/api/v1/sessions/{session['session_id']}"))["current_turn"]
            == session["current_turn"]
        )
        replay = data(client.post("/api/v1/maintenance/question-publications", json=batch()))
        assert replay["items"][0]["reasons"][0]["code"] == "QUESTION_DISABLED"
        assert start(client, "Q-0140")["current_turn"]["question_code"] == "Q-0140"


def test_disabling_updated_question_rechecks_drafts_and_never_falls_back_to_version_one(tmp_path):
    with TestClient(create_app(database_path=tmp_path / "draft.sqlite3")) as client:
        request = batch()
        data(client.post("/api/v1/maintenance/question-publications", json=request))
        draft = data(
            client.post(
                "/api/v1/sessions",
                json={
                    "pack_id": PACK,
                    "config": {**CONFIG, "focus_competency_ids": ["agent_loop"]},
                },
            )
        )
        request["questions"][0]["content_version"] = "2"
        request["questions"][0]["rubric"].append("说明预算耗尽不代表任务完成。")
        data(client.post("/api/v1/maintenance/question-publications", json=request))
        assert (
            client.post(
                "/api/v1/maintenance/questions/Q-0058/disable",
                json={"expected_version": 1, "reason": "暂停"},
            ).status_code
            == 409
        )
        data(
            client.post(
                "/api/v1/maintenance/questions/Q-0058/disable",
                json={"expected_version": 2, "reason": "暂停"},
            )
        )
        unavailable = data(
            client.post(
                f"/api/v1/role-packs/{PACK}/availability",
                json={**CONFIG, "focus_competency_ids": ["agent_loop"]},
            )
        )
        assert unavailable["available_count"] == 0 and unavailable["can_start"] is False
        assert (
            client.post(
                f"/api/v1/sessions/{draft['session_id']}/start", json={"expected_revision": 0}
            ).json()["error"]["code"]
            == "QUESTION_POOL_EXHAUSTED"
        )
        request["questions"][0]["content_version"] = "3"
        report = data(client.post("/api/v1/maintenance/question-publications", json=request))
        assert report["items"][0]["reasons"][0]["code"] == "QUESTION_DISABLED"


def test_concurrent_publications_do_not_duplicate_versions(tmp_path):
    app = create_app(database_path=tmp_path / "concurrent.sqlite3")

    def publish(_):
        with TestClient(app) as client:
            return data(client.post("/api/v1/maintenance/question-publications", json=batch()))

    with ThreadPoolExecutor(max_workers=4) as workers:
        reports = list(workers.map(publish, range(4)))
    assert sum(report["imported_count"] for report in reports) == 2
    with TestClient(app) as client:
        assert len(data(client.get("/api/v1/maintenance/questions/Q-0058"))["versions"]) == 1
        assert (
            data(client.post(f"/api/v1/role-packs/{PACK}/availability", json=CONFIG))[
                "available_count"
            ]
            == 2
        )


@pytest.mark.parametrize(
    "failure", ["missing", "timeout", "wrong_category", "wrong_level", "malformed"]
)
def test_uncached_source_is_verified_at_pinned_url_and_failure_is_per_candidate(tmp_path, failure):
    request = batch()
    question = request["questions"][0]
    question["code"] = question["source"]["original_id"] = "Q-9999"
    question["source"]["path"] = "questions/Q-9999.md"
    question["source"]["url"] = (
        "https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/questions/Q-9999.md"
    )

    def source_response(http_request):
        assert (
            str(http_request.url)
            == "https://raw.githubusercontent.com/didilili/mianstack/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/questions/Q-9999.md"
        )
        if failure == "missing":
            return httpx.Response(404)
        if failure == "timeout":
            raise httpx.ReadTimeout("network unavailable")
        if failure == "malformed":
            return httpx.Response(200, text="not a question")
        metadata = {
            "id": "Q-9999",
            "title": "External fixture question",
            "category": "software" if failure == "wrong_category" else "agent",
            "level": "进阶" if failure == "wrong_level" else "基础",
            "topic": question["topic"],
            "answerStatus": "ready",
        }
        return httpx.Response(
            200, text="---\n" + json.dumps(metadata) + "\n---\n" + question["answer"]
        )

    with TestClient(
        create_app(
            database_path=tmp_path / "external.sqlite3",
            source_transport=httpx.MockTransport(source_response),
        )
    ) as client:
        report = data(client.post("/api/v1/maintenance/question-publications", json=request))
        assert report["accepted_count"] == 1
        expected = (
            "SOURCE_UNAVAILABLE"
            if failure in {"missing", "timeout"}
            else "INVALID_SOURCE_FILE"
            if failure == "malformed"
            else "SOURCE_MISMATCH"
        )
        assert report["items"][0]["reasons"][0]["code"] == expected


def test_generated_answer_preserves_original_pending_status_and_generation_metadata(tmp_path):
    request = batch()
    question = request["questions"][0]
    question["code"] = question["source"]["original_id"] = "Q-9999"
    question["source"]["path"] = "questions/Q-9999.md"
    question["source"]["url"] = (
        "https://github.com/didilili/mianstack/blob/b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77/questions/Q-9999.md"
    )
    question["source"]["answer_status"] = "pending"
    question["answer_origin"] = "agent_generated"
    question["generation"] = {
        "author": "test author",
        "generated_at": "2026-11-09T12:00:00+08:00",
        "model": "test-model",
        "revision": "1",
    }
    raw = (
        "---\n"
        + json.dumps(
            {
                "id": "Q-9999",
                "title": "来源中尚未回答的问题",
                "category": "agent",
                "level": "基础",
                "topic": question["topic"],
                "answerStatus": "pending",
            }
        )
        + "\n---\n"
    )
    with TestClient(
        create_app(
            database_path=tmp_path / "generated.sqlite3",
            source_transport=httpx.MockTransport(lambda _: httpx.Response(200, text=raw)),
        )
    ) as client:
        report = data(client.post("/api/v1/maintenance/question-publications", json=request))
        assert report["accepted_count"] == 2
        saved = data(client.get("/api/v1/maintenance/questions/Q-9999"))["versions"][0]
        assert saved["source"]["answer_status"] == "pending"
        assert saved["generation"] == question["generation"]
        assert saved["answer_origin"] == "agent_generated"


def test_schema_one_database_migrates_without_changing_saved_sessions(tmp_path):
    database = tmp_path / "legacy.sqlite3"
    sample = json.loads(
        files("interview_backend").joinpath("samples.json").read_text(encoding="utf-8")
    )
    question = {**sample["questions"][0], "version": 1, "generation": sample["generation"]}
    # Arrange a legacy schema-1 file; all observations remain through the HTTP API.
    with sqlite3.connect(database) as legacy:
        legacy.executescript(
            files("interview_backend").joinpath("schema.sql").read_text(encoding="utf-8")
        )
        legacy.execute(
            "INSERT INTO role_packs VALUES (?,?,?,?)",
            (sample["pack_id"], sample["title"], "published", 1),
        )
        legacy.execute(
            "INSERT INTO sessions(id,pack_id,pack_version,config_json,status,phase,revision,turn_id,question_json) VALUES (?,?,1,?,'active','awaiting_answer',1,'old-turn',?)",
            ("old-session", sample["pack_id"], json.dumps(CONFIG), json.dumps(question)),
        )
        legacy.execute("PRAGMA user_version=1")
    with TestClient(create_app(database_path=database)) as client:
        restored = data(client.get("/api/v1/sessions/old-session"))
        assert restored["current_turn"]["question_code"] == "Q-AGENT-SAMPLE-01"
        assert restored["revision"] == 1
        assert restored["pack_version"] == 1
        assert (
            data(client.post(f"/api/v1/role-packs/{PACK}/availability", json=CONFIG))[
                "available_count"
            ]
            == 0
        )
        assert (
            data(client.post("/api/v1/maintenance/question-publications", json=batch()))[
                "imported_count"
            ]
            == 2
        )


def test_unverified_independent_references_cannot_enter_published_feedback(tmp_path):
    request = batch()
    request["questions"][0]["answer_refs"] = [
        {"title": "fabricated unchecked reference", "url": "https://example.invalid/not-real"}
    ]
    with TestClient(create_app(database_path=tmp_path / "references.sqlite3")) as client:
        report = data(client.post("/api/v1/maintenance/question-publications", json=request))
        assert report["accepted_count"] == 1
        assert report["items"][0]["reasons"][0]["field"] == "answer_refs"
        assert (
            data(client.post(f"/api/v1/role-packs/{PACK}/availability", json=CONFIG))[
                "available_count"
            ]
            == 1
        )
