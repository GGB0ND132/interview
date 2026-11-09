"""Exercise ticket 05 over TCP in a disposable database; never approve human reviews."""

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from importlib.resources import files
from pathlib import Path

import httpx

from interview_backend.first_half_release import SAMPLES
from interview_backend.publishing import PACK_ID


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    bundle = json.loads(
        files("interview_backend").joinpath("first_half_candidates.json").read_text("utf-8")
    )
    with tempfile.TemporaryDirectory(prefix="interview-05-") as temp:
        database = Path(temp) / "acceptance.sqlite3"
        pending = json.loads(
            files("interview_backend").joinpath("first_half_review.json").read_text("utf-8")
        )
        for sample in pending["samples"]:
            sample["human_review"] = None
            sample.pop("agent_review", None)
        pending_path = Path(temp) / "pending-review.json"
        pending_path.write_text(json.dumps(pending, ensure_ascii=False), encoding="utf-8")
        gate = subprocess.run(
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
                str(pending_path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        assert gate.returncode == 2, gate.stderr
        refusal = json.loads(gate.stdout)
        assert refusal["actual_available_count"] == 0
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        env = {**os.environ, "DATABASE_PATH": str(database), "PYTHONUTF8": "1"}
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "interview_backend.api:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=20) as client:
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError(
                            process.stderr.read().decode("utf-8")
                            if process.stderr
                            else "Server exited"
                        )
                    try:
                        if client.get("/api/v1/role-packs").is_success:
                            break
                    except httpx.TransportError:
                        time.sleep(0.1)
                else:
                    raise RuntimeError("Server startup timed out")

                def post(path, body):
                    response = client.post("/api/v1/" + path, json=body)
                    response.raise_for_status()
                    return response.json()["data"]

                config = {"mode": "question_practice", "difficulty": "easy"}
                before = post(f"role-packs/{PACK_ID}/availability", config)
                assert before["available_count"] == 0
                preview = post("maintenance/question-publications/preview", bundle)
                assert preview["accepted_count"] == 57 and preview["rejected_count"] == 0
                # Exercise the real independent-agent policy and saved reviews;
                # the target remains this disposable test database.
                release = subprocess.run(
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
                assert release.returncode == 0, release.stderr + release.stdout
                release_report = json.loads(release.stdout)
                publication = release_report["publication"]
                assert publication["imported_count"] == 57
                available = post(f"role-packs/{PACK_ID}/availability", config)
                assert available["available_count"] == 57
                assert available["topic_counts"] == publication["topic_counts"]
                draws = []
                for topic in available["topics"]:
                    if topic["topic"] not in SAMPLES:
                        continue
                    selection = {**config, "focus_competency_ids": [topic["competency_id"]]}
                    draft = post("sessions", {"pack_id": PACK_ID, "config": selection})
                    session = post(
                        f"sessions/{draft['session_id']}/start", {"expected_revision": 0}
                    )
                    assert session["current_turn"]["topic"] == topic["topic"]
                    draws.append(session["current_turn"])
                replay = post("maintenance/question-publications", bundle)
                assert replay["imported_count"] == 0 and replay["unchanged_count"] == 57
                disabled_code = draws[0]["question_code"]
                post(
                    f"maintenance/questions/{disabled_code}/disable",
                    {
                        "expected_version": 1,
                        "reason": "TEST ONLY: simulated wrong-question quarantine",
                    },
                )
                after_disable = post(f"role-packs/{PACK_ID}/availability", config)
                assert after_disable["available_count"] == 56
                rejected = post("maintenance/question-publications", bundle)
                assert rejected["rejected_count"] == 1
                assert (
                    next(item for item in rejected["items"] if item["code"] == disabled_code)[
                        "reasons"
                    ][0]["code"]
                    == "QUESTION_DISABLED"
                )
                report = {
                    "test_only": True,
                    "human_review_completed": False,
                    "independent_agent_review_completed": True,
                    "release_published": False,
                    "database": "disposable temporary SQLite, removed after verification",
                    "pending_review_refusal": refusal,
                    "agent_gate_policy": release_report["review_policy"],
                    "before": before,
                    "preview": preview,
                    "test_publication": publication,
                    "availability": available,
                    "draws": draws,
                    "idempotent_replay": replay,
                    "after_test_disable": after_disable,
                    "test_rejection": rejected,
                }
                args.output.write_text(
                    json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                print(
                    json.dumps(
                        {
                            "accepted": 57,
                            "rejected": 0,
                            "topics_drawn": len(draws),
                            "after_test_disable": 56,
                            "human_review_completed": False,
                            "independent_agent_review_completed": True,
                            "release_published": False,
                        }
                    )
                )
        finally:
            process.terminate()
            process.wait(timeout=10)
            if process.stderr:
                process.stderr.close()


if __name__ == "__main__":
    main()
