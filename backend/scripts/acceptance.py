"""Exercise the running HTTP service and persist a real-model acceptance record."""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx


def checked(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    body = response.json()
    assert body["error"] is None, body["error"]
    result: dict[str, Any] = body["data"]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = {
        "mode": "question_practice",
        "difficulty": "easy",
        "focus_competency_ids": ["agent_tool_calling"],
    }
    with httpx.Client(base_url=args.base_url, timeout=10) as client:
        availability = checked(
            client.post("/api/v1/role-packs/pack_agent_basics_sample/availability", json=config)
        )
        assert availability["available_count"] == 1 and availability["can_start"]
        draft = checked(
            client.post(
                "/api/v1/sessions", json={"pack_id": "pack_agent_basics_sample", "config": config}
            )
        )
        path = f"/api/v1/sessions/{draft['session_id']}"
        session = checked(
            client.post(f"{path}/start", json={"expected_revision": draft["revision"]})
        )
        assert "answer" not in session["current_turn"]
        answer = "模型先决定需要调用的工具，由程序执行并把实际工具返回结果送回模型。Agent 应读取结果判断下一步，失败时根据错误调整，不能把发出调用当作成功。完成目标就结束，也要设置最大迭代次数，达到限制时停止并说明未完成的部分。"
        request = {
            "turn_id": session["current_turn"]["id"],
            "expected_revision": session["revision"],
            "client_submission_id": "live-acceptance-1",
            "disposition": "answered",
            "answer_text": answer,
        }
        accepted_response = client.post(f"{path}/answers", json=request)
        assert accepted_response.status_code == 202, accepted_response.text
        accepted = checked(accepted_response)
        job_id = accepted["submission"]["job_id"]
        deadline = time.monotonic() + 150
        while True:
            job = checked(client.get(f"/api/v1/jobs/{job_id}"))
            if job["status"] in {"failed", "succeeded"}:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError("Live model evaluation did not finish")
            time.sleep(0.3)
        assert job["status"] == "succeeded", job
        saved = checked(client.get(path))
        submission = saved["submissions"][0]
        assert submission["status"] == "completed"
        evaluation = submission["feedback"]
        assert all(
            d["answer_quote"].strip() and d["answer_quote"] in answer
            for d in evaluation["dimensions"]
        )
        assert evaluation["requested_model"] != "external_adapter"
        weights = {
            "accuracy": 35,
            "completeness": 25,
            "relevance": 15,
            "structure": 15,
            "specificity": 10,
        }
        dimensions = [d for d in evaluation["dimensions"] if d["score"] is not None]
        expected = (
            round(
                sum(d["score"] * weights[d["name"]] for d in dimensions)
                / sum(weights[d["name"]] for d in dimensions)
            )
            if dimensions
            else None
        )
        assert submission["score"] == expected and expected is not None
        replay = checked(client.post(f"{path}/answers", json=request))
        assert replay["idempotent_replay"] and replay["submission"] == submission
        report = checked(client.get(f"{path}/report"))
        assert report["average_score"] == expected and report["answered_count"] == 1
        record = {
            "checked_at": datetime.now(UTC).isoformat(),
            "transport": "real HTTP API and configured external model",
            "pack_scope": "two original Agent samples; not the 115-question release",
            "availability": availability,
            "current_turn": session["current_turn"],
            "submitted_answer": answer,
            "submission": submission,
            "job": job,
            "report": report,
            "duplicate_replay": True,
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"PASS: real-model single question, score={expected}, evidence={args.output}")


if __name__ == "__main__":
    main()
