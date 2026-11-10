import json
import subprocess
import sys
from importlib.resources import files

import pytest
from fastapi.testclient import TestClient

from interview_backend.api import create_app

PACK = "pack_agent_basics_mianstack"
CONFIG = {"difficulty": "easy", "mode": "question_practice"}
EXPECTED = {
    "Agent 基础与运行循环": 17,
    "Agent 应用架构与场景设计": 18,
    "规划、推理与任务执行": 8,
    "上下文工程": 2,
    "记忆系统": 6,
    "工具调用与 Function Calling": 6,
}


def candidates():
    return json.loads(
        files("interview_backend").joinpath("first_half_candidates.json").read_text("utf-8")
    )


def data(response):
    assert response.is_success, response.text
    return response.json()["data"]


def test_first_half_pack_validates_and_every_topic_can_be_drawn(tmp_path):
    # Only the test database is published. This is not human approval of the content.
    with TestClient(create_app(database_path=tmp_path / "pack.sqlite3")) as client:
        preview = data(
            client.post("/api/v1/maintenance/question-publications/preview", json=candidates())
        )
        assert preview["accepted_count"] == 57, preview
        assert preview["rejected_count"] == 0
        assert {topic: preview["topic_counts"][topic] for topic in EXPECTED} == EXPECTED
        assert (
            data(client.post(f"/api/v1/role-packs/{PACK}/availability", json=CONFIG))[
                "available_count"
            ]
            == 0
        )
        published = data(
            client.post("/api/v1/maintenance/question-publications", json=candidates())
        )
        assert published["imported_count"] == 57
        available = data(client.post(f"/api/v1/role-packs/{PACK}/availability", json=CONFIG))
        assert available["available_count"] == 57
        assert available["topic_counts"] == published["topic_counts"]
        for topic in available["topics"]:
            if topic["topic"] not in EXPECTED:
                assert topic["available_count"] == 0
                continue
            config = {**CONFIG, "focus_competency_ids": [topic["competency_id"]]}
            draft = data(client.post("/api/v1/sessions", json={"pack_id": PACK, "config": config}))
            started = data(
                client.post(
                    f"/api/v1/sessions/{draft['session_id']}/start", json={"expected_revision": 0}
                )
            )
            assert started["current_turn"]["topic"] == topic["topic"]
            assert started["current_turn"]["question_code"] in {
                q["code"] for q in candidates()["questions"]
            }


def test_release_command_refuses_pending_review_without_publishing(tmp_path):
    review = json.loads(
        files("interview_backend").joinpath("first_half_review.json").read_text("utf-8")
    )
    for sample in review["samples"]:
        sample["human_review"] = None
        sample.pop("agent_review", None)
    review_path = tmp_path / "pending.json"
    review_path.write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
    database = tmp_path / "release.sqlite3"
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "-m",
            "interview_backend.first_half_release",
            "--database",
            str(database),
            "--publish",
            "--review-file",
            str(review_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["preview"]["accepted_count"] == 57
    assert report["published"] is False
    assert len(report["review_blockers"]) == 12
    with TestClient(create_app(database_path=database)) as client:
        assert (
            data(client.post(f"/api/v1/role-packs/{PACK}/availability", json=CONFIG))[
                "available_count"
            ]
            == 0
        )


@pytest.mark.parametrize(
    "state",
    [
        "approved",
        "stale",
        "failed",
        "missing_sample",
        "repeated_error",
        "rechecked",
        "partial",
        "rejected_sample",
        "agent_approved",
        "agent_policy_missing",
        "agent_failed",
        "agent_human_veto",
        "expanded_veto",
    ],
)
def test_release_command_respects_review_version_and_expanded_checks(tmp_path, state):
    # Synthetic approval records exercise the gate; they are never shipped as human findings.
    review = json.loads(
        files("interview_backend").joinpath("first_half_review.json").read_text("utf-8")
    )
    approval = {
        "reviewer": "TEST FIXTURE ONLY",
        "reviewed_at": "2026-11-10T00:00:00+08:00",
        "materials": "synthetic test record, not human evidence",
        "findings": "exercise release gating only",
        "conclusion": "passed",
    }
    for sample in review["samples"]:
        sample.pop("agent_review", None)
        sample["human_review"] = dict(approval)
    if state in {"agent_approved", "agent_policy_missing", "agent_failed", "agent_human_veto"}:
        review["review_policy"] = "independent_agent_first"
        for sample in review["samples"]:
            sample["human_review"] = None
            sample["agent_review"] = {**approval, "review_kind": "independent_agent"}
        if state == "agent_policy_missing":
            review.pop("review_policy")
        elif state == "agent_failed":
            review["samples"][0]["agent_review"]["conclusion"] = "failed"
        elif state == "agent_human_veto":
            review["samples"][0]["human_review"] = {**approval, "conclusion": "failed"}
    if state == "stale":
        review["bundle_sha256"] = "0" * 64
    elif state == "failed":
        review["samples"][0]["human_review"]["conclusion"] = "failed"
    elif state == "missing_sample":
        review["samples"].pop()
    elif state in {"repeated_error", "rechecked", "expanded_veto"}:
        review["incidents"] = [
            {
                "topic": "记忆系统",
                "code": code,
                "error_class": "wrong_scope",
                "resolution": "open",
                "expanded_review": [],
            }
            for code in ["Q-0062", "Q-4837"]
        ]
        if state in {"rechecked", "expanded_veto"}:
            for incident in review["incidents"]:
                incident["resolution"] = "corrected_and_rechecked"
                incident["expanded_review"] = [
                    {"code": q["code"], **approval}
                    for q in candidates()["questions"]
                    if q["topic"] == "记忆系统"
                ]
            if state == "expanded_veto":
                review["incidents"][0]["expanded_review"].append(
                    {"code": "Q-0062", **approval, "conclusion": "failed"}
                )
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
    database = tmp_path / "review.sqlite3"
    if state in {"partial", "rejected_sample"}:
        with TestClient(create_app(database_path=database)) as client:
            data(client.post("/api/v1/maintenance/question-publications", json=candidates()))
            code = "Q-0058" if state == "partial" else "Q-0419"
            data(
                client.post(
                    f"/api/v1/maintenance/questions/{code}/disable",
                    json={"expected_version": 1, "reason": "test rejection"},
                )
            )
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "-m",
            "interview_backend.first_half_release",
            "--database",
            str(database),
            "--review-file",
            str(review_path),
            "--publish",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    approved = state in {"approved", "rechecked", "partial", "agent_approved"}
    assert result.returncode == (0 if approved else 2), result.stderr + json.dumps(
        json.loads(result.stdout).get("review_blockers"), ensure_ascii=False
    )
    report = json.loads(result.stdout)
    assert report["published"] is approved
    with TestClient(create_app(database_path=database)) as client:
        availability = data(client.post(f"/api/v1/role-packs/{PACK}/availability", json=CONFIG))
        expected_count = 56 if state in {"partial", "rejected_sample"} else 57 if approved else 0
        assert availability["available_count"] == expected_count
        if approved:
            publication = report["publication"]
            saved = data(
                client.get(
                    f"/api/v1/maintenance/question-publications/{publication['publication_id']}"
                )
            )
            assert saved == publication
            if state == "partial":
                assert report["partial_publication"] is True
                assert publication["accepted_count"] == 56
                assert publication["rejected_count"] == 1
