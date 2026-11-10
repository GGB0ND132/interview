"""Publish reviewed ticket 05 to an explicit durable database and verify its live API.

Creates six practice sessions without submitting answers or invoking a model.
The server must already use the specified database. Saves release and HTTP evidence.
"""

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path

import httpx

from interview_backend.first_half_release import SAMPLES, bundle_digest, review_blockers
from interview_backend.publishing import PACK_ID


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    database = args.database.resolve(strict=True)
    assets = files("interview_backend")
    bundle = json.loads(assets.joinpath("first_half_candidates.json").read_text("utf-8"))
    review = json.loads(assets.joinpath("first_half_review.json").read_text("utf-8"))
    assert not review_blockers(bundle, review), "Review gate must pass before publication"
    config = {"mode": "question_practice", "difficulty": "easy"}

    def release():
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
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if result.returncode:
            raise RuntimeError(result.stderr + result.stdout)
        return json.loads(result.stdout)

    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=30) as client:

        def post(path, body):
            response = client.post("/api/v1/" + path, json=body)
            response.raise_for_status()
            return response.json()["data"]

        before = post(f"role-packs/{PACK_ID}/availability", config)
        publication = release()
        # Read the persisted publication through the running server to confirm
        # this is the same database, rather than accepting coincidental counts.
        publication_id = publication["publication"]["publication_id"]
        response = client.get(f"/api/v1/maintenance/question-publications/{publication_id}")
        response.raise_for_status()
        persisted = response.json()["data"]
        assert persisted == publication["publication"]
        available = post(f"role-packs/{PACK_ID}/availability", config)
        assert publication["published"] and publication["publication"]["accepted_count"] == 57
        assert publication["publication"]["rejected_count"] == 0
        assert available["available_count"] == publication["actual_available_count"] == 57
        assert available["topic_counts"] == publication["actual_topic_counts"]
        expected = {q["code"]: q for q in bundle["questions"]}
        draws = []
        for topic in available["topics"]:
            if topic["topic"] not in SAMPLES:
                continue
            selection = {**config, "focus_competency_ids": [topic["competency_id"]]}
            focused = post(f"role-packs/{PACK_ID}/availability", selection)
            assert focused["available_count"] == topic["available_count"] > 0
            draft = post("sessions", {"pack_id": PACK_ID, "config": selection})
            session = post(f"sessions/{draft['session_id']}/start", {"expected_revision": 0})
            turn = session["current_turn"]
            assert turn["topic"] == topic["topic"]
            assert turn["question_code"] in expected
            draws.append(
                {
                    "topic": topic["topic"],
                    "available_count": focused["available_count"],
                    "session_id": session["session_id"],
                    "question_code": turn["question_code"],
                    "question_version": turn["question_version"],
                    "phase": session["phase"],
                }
            )
        assert len(draws) == 6
        replay = release()
        assert replay["publication"]["imported_count"] == 0
        assert replay["publication"]["unchanged_count"] == 57
        assert replay["actual_available_count"] == 57
        report = {
            "verified_at": datetime.now(UTC).isoformat(),
            "target_scope": "current workspace persistent local database; not remote deployment",
            "database": str(database),
            "base_url": args.base_url,
            "bundle_sha256": bundle_digest(bundle),
            "independent_agent_review_completed": True,
            "human_review_completed": False,
            "release_published": True,
            "model_calls": 0,
            "before": before,
            "release": publication,
            "availability": available,
            "draws": draws,
            "idempotent_replay": replay,
        }
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "publication_id": publication_id,
                    "accepted": 57,
                    "rejected": 0,
                    "available": 57,
                    "topics_drawn": len(draws),
                    "replay_imported": 0,
                    "output": str(args.output),
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
