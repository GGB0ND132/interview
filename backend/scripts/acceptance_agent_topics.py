"""Exercise topic content over TCP in a disposable database, without model calls."""

from __future__ import annotations

import argparse
import json
import socket
import tempfile
import threading
import time
from pathlib import Path

import httpx
import uvicorn

from interview_backend.api import create_app
from interview_backend.publishing import PACK_ID, TOPICS
from interview_backend.topic_pack import TopicPack, load_questions


def data(response: httpx.Response) -> dict:
    response.raise_for_status()
    return response.json()["data"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reviews = json.loads(
        (
            Path(__file__).parents[2] / "docs/content-baseline/agent-topics-06/human-reviews.json"
        ).read_text(encoding="utf-8")
    )
    with tempfile.TemporaryDirectory(prefix="agent-topics-06-") as directory:
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        base = f"http://127.0.0.1:{listener.getsockname()[1]}"
        server = uvicorn.Server(
            uvicorn.Config(
                create_app(database_path=Path(directory) / "practice.sqlite3"), log_level="error"
            )
        )
        worker = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        worker.start()
        try:
            with httpx.Client(base_url=base, timeout=30) as client:
                for _ in range(100):
                    try:
                        client.get("/health/live").raise_for_status()
                        break
                    except httpx.TransportError:
                        time.sleep(0.1)
                else:
                    raise RuntimeError("Acceptance service did not start")
                formal = TopicPack(client).run(reviews, publish=True)
                assert formal["published_now_count"] == 0
                assert formal["available_count"] == 0
                # Deliberately test the generic trusted-maintainer import in this
                # disposable DB. This is not a human-approved content release.
                questions = load_questions()
                published = data(
                    client.post(
                        "/api/v1/maintenance/question-publications", json={"questions": questions}
                    )
                )
                assert published["accepted_count"] == 58
                assert published["rejected_count"] == 0
                assert published["available_count"] == 58
                draws = []
                for topic, competency in list(TOPICS.items())[6:]:
                    config = {
                        "mode": "question_practice",
                        "difficulty": "easy",
                        "focus_competency_ids": [competency],
                    }
                    available = data(
                        client.post(f"/api/v1/role-packs/{PACK_ID}/availability", json=config)
                    )
                    assert available["available_count"] == sum(
                        q["topic"] == topic for q in questions
                    )
                    created = data(
                        client.post("/api/v1/sessions", json={"pack_id": PACK_ID, "config": config})
                    )
                    session_id = created["session_id"]
                    started = data(
                        client.post(
                            f"/api/v1/sessions/{session_id}/start", json={"expected_revision": 0}
                        )
                    )
                    turn = started["current_turn"]
                    assert turn["competency_id"] == competency
                    data(
                        client.post(
                            f"/api/v1/sessions/{session_id}/answers",
                            json={
                                "turn_id": turn["id"],
                                "expected_revision": started["revision"],
                                "client_submission_id": f"06-{competency}",
                                "disposition": "skipped",
                                "answer_text": "",
                            },
                        )
                    )
                    report = data(client.get(f"/api/v1/sessions/{session_id}/report"))
                    assert report["average_score"] is None
                    assert report["skipped_count"] == 1
                    draws.append(
                        {
                            "competency_id": competency,
                            "topic": topic,
                            "available_count": available["available_count"],
                            "question_code": turn["question_code"],
                            "report": report,
                        }
                    )
                output = {
                    "scope": "TCP HTTP, disposable database; no model calls or human approvals",
                    "formal_release": formal,
                    "generic_import_mechanism_only": published,
                    "practice_draws_mechanism_only": draws,
                    "production_database_modified": False,
                }
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(
                    json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                print(
                    "TCP verified: 58 validated; formal release 0; six-topic draws in disposable DB"
                )
        finally:
            server.should_exit = True
            worker.join(timeout=10)
            listener.close()
            if worker.is_alive():
                raise RuntimeError("Acceptance service did not stop")


if __name__ == "__main__":
    main()
