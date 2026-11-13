"""Read-only release inventory over HTTP; never publishes or calls a model.

Candidate validation, current availability and historical review identity are
separate facts. This command does not certify the whole stage-demo checklist.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from typing import Any, Protocol

import httpx

from .publishing import COMMIT, PACK_ID, TOPICS
from .topic_pack import source_catalog


class ReleaseClient(Protocol):
    def get(self, url: str) -> httpx.Response: ...

    def post(self, url: str, *, json: Any) -> httpx.Response: ...


def data(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    return dict(response.json()["data"])


def inspect_release(client: ReleaseClient) -> dict[str, Any]:
    assets = files("interview_backend")
    candidates = [
        question
        for name in ("first_half_candidates.json", "agent_topics_second_half.json")
        for question in json.loads(assets.joinpath(name).read_text("utf-8"))["questions"]
    ]
    sources = source_catalog()
    expected = {question["code"]: question for question in candidates}
    if len(expected) != 115 or set(expected) != {row["id"] for row in sources}:
        raise ValueError("Candidate inventory differs from the fixed 115-question source")
    preview = data(
        client.post(
            "/api/v1/maintenance/question-publications/preview", json={"questions": candidates}
        )
    )
    validation = {row["code"]: row for row in preview["items"]}
    available = data(
        client.post(
            f"/api/v1/role-packs/{PACK_ID}/availability",
            json={"mode": "question_practice", "difficulty": "easy"},
        )
    )
    questions = []
    for source in sources:
        code = source["id"]
        response = client.get(f"/api/v1/maintenance/questions/{code}")
        current = None
        if response.status_code != 404:
            versions = data(response)["versions"]
            current = max(versions, key=lambda row: row["version"])
        candidate = expected[code]
        status = current["status"] if current else "unpublished"
        matches = (
            current is not None
            and all(
                current.get(key) == value
                for key, value in candidate.items()
                if key not in {"status", "source"}
            )
            and all(
                current["source"].get(key) == value for key, value in candidate["source"].items()
            )
        )
        questions.append(
            {
                "code": code,
                "topic": source["topic"],
                "source_answer_status": source["answerStatus"],
                "answer_origin": candidate["answer_origin"],
                "candidate_content_version": candidate["content_version"],
                "validation": validation[code],
                "status": status,
                "published_version": current["version"] if current else None,
                "published_content_version": current["content_version"] if current else None,
                "matches_candidate": matches,
                "disabled_reason": current.get("disabled_reason") if current else None,
            }
        )
    published = [row for row in questions if row["status"] == "published"]
    topics = [
        {
            "topic": topic,
            "source_count": sum(row["topic"] == topic for row in sources),
            "available_count": available["topic_counts"][topic],
            "distinct_human_samples_required": 2,
            "two_distinct_source_questions_exist": sum(row["topic"] == topic for row in sources)
            >= 2,
        }
        for topic in TOPICS
    ]
    return {
        "checked_at": datetime.now(UTC).isoformat(),
        "scope": "HTTP inventory only; not browser/model/human acceptance",
        "source_commit": COMMIT,
        "source_count": len(sources),
        "source_ready_count": sum(row["answerStatus"] == "ready" for row in sources),
        "validation_passed_count": preview["accepted_count"],
        "rejected_count": preview["rejected_count"],
        "published_source_count": len(published),
        "available_count": available["available_count"],
        "release_matches_candidates": len(published) == available["available_count"] == 115
        and all(row["matches_candidate"] and row["validation"]["accepted"] for row in questions),
        "topics": topics,
        "questions": questions,
        "availability": available,
        "mock_availability": data(
            client.post(
                f"/api/v1/role-packs/{PACK_ID}/availability", json={"mode": "mock_interview"}
            )
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8017")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        report = inspect_release(client)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(
        f"Source {report['source_count']}; validated {report['validation_passed_count']}; "
        f"rejected {report['rejected_count']}; available {report['available_count']}"
    )
    if not report["release_matches_candidates"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
