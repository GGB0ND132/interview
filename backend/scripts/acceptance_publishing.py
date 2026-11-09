"""Exercise ticket 03 through TCP HTTP against a fresh, local acceptance database."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import UTC, datetime
from importlib.resources import files
from typing import Any

import httpx

PACK = "pack_agent_basics_mianstack"
CONFIG = {"mode": "question_practice", "difficulty": "easy"}


def run(base_url: str) -> dict[str, Any]:
    candidates = json.loads(
        files("interview_backend").joinpath("mianstack_example.json").read_text(encoding="utf-8")
    )
    with httpx.Client(base_url=base_url, timeout=30) as client:

        def call(method: str, path: str, body: Any = None) -> dict[str, Any]:
            response = client.request(method, "/api/v1/" + path, json=body)
            response.raise_for_status()
            value: dict[str, Any] = response.json()["data"]
            return value

        before = call("POST", f"role-packs/{PACK}/availability", CONFIG)
        assert before["available_count"] == 0, "Use a fresh acceptance database"
        preview = call("POST", "maintenance/question-publications/preview", candidates)
        assert preview["accepted_count"] == 2 and preview["rejected_count"] == 0
        assert call("POST", f"role-packs/{PACK}/availability", CONFIG)["available_count"] == 0
        published = call("POST", "maintenance/question-publications", candidates)
        assert published["imported_count"] == 2
        available = call("POST", f"role-packs/{PACK}/availability", CONFIG)
        assert available["available_count"] == 2
        assert available["topic_counts"] == published["topic_counts"]
        replay = call("POST", "maintenance/question-publications", candidates)
        assert replay["imported_count"] == 0 and replay["unchanged_count"] == 2

        rejections = {}
        for case in ("missing_field", "duplicate_id", "invalid_locator"):
            bad = deepcopy(candidates)
            if case == "missing_field":
                del bad["questions"][0]["answer"]
            elif case == "duplicate_id":
                bad["questions"].append(deepcopy(bad["questions"][0]))
            else:
                bad["questions"][0]["source"]["path"] = "interviews/MJ-NC-2026-0002.md"
            result = call("POST", "maintenance/question-publications", bad)
            assert result["rejected_count"] >= 1
            rejections[case] = result

        sessions = []
        for question in candidates["questions"]:
            config = {**CONFIG, "focus_competency_ids": [question["competency_id"]]}
            draft = call("POST", "sessions", {"pack_id": PACK, "config": config})
            session = call(
                "POST", f"sessions/{draft['session_id']}/start", {"expected_revision": 0}
            )
            assert session["current_turn"]["question_code"] == question["code"]
            sessions.append(session)

        revised = deepcopy(candidates)
        revised["questions"][0]["content_version"] = "2"
        revised["questions"][0]["rubric"].append("说明运行预算耗尽与任务完成的区别。")
        revision = call("POST", "maintenance/question-publications", revised)
        assert revision["items"][0]["version"] == 2
        assert (
            call("GET", f"sessions/{sessions[0]['session_id']}")["current_turn"]["question_version"]
            == 1
        )
        call(
            "POST",
            "maintenance/questions/Q-0058/disable",
            {"expected_version": 2, "reason": "发布链路验收：验证停用隔离"},
        )
        disabled_import = call("POST", "maintenance/question-publications", revised)
        assert disabled_import["items"][0]["reasons"][0]["code"] == "QUESTION_DISABLED"
        rejections["disabled"] = disabled_import
        after_disable = call("POST", f"role-packs/{PACK}/availability", CONFIG)
        assert after_disable["available_count"] == 1
        assert (
            call("GET", f"maintenance/question-publications/{published['publication_id']}")
            == published
        )
        return {
            "verified_at": datetime.now(UTC).isoformat(),
            "transport": "TCP HTTP to local FastAPI; actual SQLite; no model invocation",
            "scope": "two fixed-source questions for ticket 03, not the 115-question release or human topic sampling",
            "published": published,
            "replayed": replay,
            "available_after_publish": available,
            "rejection_records": rejections,
            "revision": revision,
            "available_after_disable": after_disable,
            "passed": True,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    print(json.dumps(run(args.base_url), ensure_ascii=False, indent=2))
