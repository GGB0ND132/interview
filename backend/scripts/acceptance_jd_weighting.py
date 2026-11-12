"""Compare three JD cases against a running service using synthetic answers."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from acceptance_mock_interview import COMMON_ANSWERS, PACK, checked


def digest(report: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(report, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def check_draws(plan: dict[str, Any]) -> None:
    rng = random.Random(int(plan["seed"]))
    remaining = list(plan["topic_candidates"])
    assert rng.randint(3, min(4, len(remaining))) == len(plan["selected_topics"])
    for draw in plan["topic_draws"]:
        value = rng.random()
        total = sum(c["weight"] for c in remaining)
        assert draw["random_value"] == value and draw["total_weight"] == total
        threshold = total * value
        for candidate in remaining:
            threshold -= candidate["weight"]
            if threshold < 0:
                break
        assert candidate["competency_id"] == draw["selected_topic"]
        remaining.remove(candidate)
    assert [d["selected_topic"] for d in plan["topic_draws"]] == plan["selected_topics"]
    pool = {(q["code"], q["version"]) for q in plan["candidate_pool"]}
    assert all(
        (q["code"], q["version"]) in pool for q in plan["questions"] if q["stage"] == "technical"
    )


def run_case(client: httpx.Client, name: str, text: str | None) -> dict[str, Any]:
    config: dict[str, Any] = {"mode": "mock_interview", "max_followups_per_question": 0}
    mapping = None
    if text:
        preview = checked(client.post("/api/v1/jd-mappings", json={"pack_id": PACK, "text": text}))
        pending = {"mapping_id": preview["id"], "revision": preview["revision"]}
        rejected = client.post(
            "/api/v1/sessions", json={"pack_id": PACK, "config": {**config, "jd": pending}}
        )
        assert (
            rejected.status_code == 409 and rejected.json()["error"]["code"] == "JD_NOT_CONFIRMED"
        )
        mapping = checked(
            client.post(
                f"/api/v1/jd-mappings/{preview['id']}/confirm",
                json={
                    "expected_revision": 0,
                    "confirmed_requirement_ids": [r["id"] for r in preview["requirements"]],
                },
            )
        )
        config["jd"] = {"mapping_id": mapping["id"], "revision": mapping["revision"]}
    draft = checked(client.post("/api/v1/sessions", json={"pack_id": PACK, "config": config}))
    path = f"/api/v1/sessions/{draft['session_id']}"
    session = checked(client.post(f"{path}/start", json={"expected_revision": 0}))
    plan = session["plan"]
    check_draws(plan)
    weights = {c["competency_id"]: c["weight"] for c in plan["topic_candidates"]}
    assert set(weights.values()) == ({1} if not text else {1, 4})
    if text:
        assert weights["agent_tool_calling"] == 4
    while session["status"] not in {"completed", "ended_early"}:
        turn = session["current_turn"]
        answer = COMMON_ANSWERS.get(
            turn["stage"], f"这道题我不会，具体不清楚{turn['topic']}的工作机制和边界。"
        )
        checked(
            client.post(
                f"{path}/answers",
                json={
                    "expected_revision": session["revision"],
                    "turn_id": turn["id"],
                    "client_submission_id": turn["id"],
                    "disposition": "answered",
                    "answer_text": answer,
                },
            )
        )
        deadline = time.monotonic() + 180
        retries = 0
        while True:
            session = checked(client.get(path))
            if session["phase"] == "evaluation_failed" and retries < 2:
                retries += 1
                checked(
                    client.post(f"{path}/retry", json={"expected_revision": session["revision"]})
                )
            elif session["phase"] != "evaluating":
                break
            if time.monotonic() > deadline:
                raise TimeoutError(f"{name}: evaluation did not complete")
            time.sleep(0.5)
        assert session["phase"] != "evaluation_failed", session["submissions"][-1].get("error")
        print(f"{name}: {turn['stage']} -> {session['phase']}", flush=True)
        if session["phase"] == "stage_transition":
            session = checked(
                client.post(f"{path}/next", json={"expected_revision": session["revision"]})
            )
    report = checked(client.get(f"{path}/report"))
    assert report["interview_completeness"] == "complete"
    assert report["plan"] == plan
    assert report["jd"] == session.get("jd")
    if name == "without_jd":
        assert report["completeness"] == "complete" and report["jd_gaps"] == []
    elif name == "supported_jd":
        assert all(r["gap_reason"] is None for r in report["jd"]["requirements"])
        assert all(r["gap_reason"] == "not_selected" for r in report["jd_gaps"])
    else:
        assert report["completeness"] == "partial"
        assert {"熟悉 Kubernetes", "熟悉 MCP"}.issubset({r["text"] for r in report["jd_gaps"]})
    return {
        "case": name,
        "session_id": session["session_id"],
        "confirmed_mapping": mapping,
        "plan": plan,
        "completeness": report["completeness"],
        "interview_completeness": report["interview_completeness"],
        "jd_coverage_status": report["jd_coverage_status"],
        "jd_gaps": report["jd_gaps"],
        "stop_reason": report["stop_reason"],
        "groups": [
            {
                "question": g["question"],
                "score": g["score"],
                "evidence_status": (g["feedback"] or {}).get("evidence_status"),
            }
            for g in report["groups"]
        ],
        "report_sha256": digest(report),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8009")
    parser.add_argument("--output", type=Path, default=Path("../docs/verification/09-live-jd.json"))
    parser.add_argument(
        "--verify-existing", action="store_true", help="Read stored reports only; no model calls"
    )
    args = parser.parse_args()
    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        if args.verify_existing:
            evidence = json.loads(args.output.read_text("utf-8"))
            for case in evidence["cases"]:
                report = checked(client.get(f"/api/v1/sessions/{case['session_id']}/report"))
                assert digest(report) == case["report_sha256"]
            evidence["restart_verified_at"] = datetime.now(UTC).isoformat()
        else:
            availability = checked(
                client.post(
                    f"/api/v1/role-packs/{PACK}/availability", json={"mode": "mock_interview"}
                )
            )
            assert availability["can_start"]
            jobs = [
                ("without_jd", None),
                ("supported_jd", "熟悉工具调用"),
                ("unsupported_jd", "熟悉工具调用；熟悉 Kubernetes；熟悉 MCP"),
            ]
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(run_case, client, *job) for job in jobs]
                cases = [future.result() for future in futures]
            evidence = {
                "passed": True,
                "checked_at": datetime.now(UTC).isoformat(),
                "base_url": args.base_url,
                "model_calls": "real_configured_provider",
                "candidate_answers": "synthetic; explicit technical knowledge gaps",
                "availability": availability,
                "cases": cases,
            }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"passed: {len(evidence['cases'])} cases; {args.output}")


if __name__ == "__main__":
    main()
