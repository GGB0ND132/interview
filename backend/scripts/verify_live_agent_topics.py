"""Verify the persistent 06 deployment through HTTP; --draw creates six skip sessions."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from interview_backend.publishing import PACK_ID, TOPICS
from interview_backend.topic_pack import load_questions


def data(response: httpx.Response) -> dict:
    response.raise_for_status()
    envelope = response.json()
    assert envelope["error"] is None, envelope["error"]
    return envelope["data"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--frontend-url", default="http://127.0.0.1:5174")
    parser.add_argument("--inherited-url", default="http://127.0.0.1:8000")
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--previous", type=Path, help="Recheck saved skip reports after restart")
    parser.add_argument("--draw", action="store_true")
    args = parser.parse_args()
    release = json.loads(args.release.read_text(encoding="utf-8"))
    expected = {row["topic"]: row["source_count"] for row in release["topics"]}
    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        available = data(client.post(f"/api/v1/role-packs/{PACK_ID}/availability", json={}))
        assert available["available_count"] == 115
        assert available["topic_counts"] == expected
        publication_id = release["publication"]["publication_id"]
        saved = data(client.get(f"/api/v1/maintenance/question-publications/{publication_id}"))
        assert saved == release["publication"]
        verified = []
        for question in load_questions():
            versions = data(client.get(f"/api/v1/maintenance/questions/{question['code']}"))
            current = versions["versions"][-1]
            assert current["status"] == "published"
            for key, value in question.items():
                if key == "status":
                    continue
                if key == "source":
                    assert all(current[key][field] == item for field, item in value.items())
                else:
                    assert current[key] == value, (question["code"], key)
            verified.append(
                {"code": question["code"], "content_version": current["content_version"]}
            )
        assert len(verified) == 58
        inherited = data(
            httpx.get(f"{args.inherited_url}/api/v1/sessions?page_size=100", timeout=30)
        )
        assert inherited["total"] >= 7
        assert inherited["total"] == len(inherited["items"]), "Source history exceeds one page"
        inherited_sessions = []
        for session in inherited["items"]:
            route = f"/api/v1/sessions/{session['session_id']}"
            original = data(httpx.get(f"{args.inherited_url}{route}", timeout=30))
            assert data(client.get(route)) == original
            inherited_sessions.append(session["session_id"])
        existing = data(
            httpx.post(
                f"{args.inherited_url}/api/v1/role-packs/{PACK_ID}/availability",
                json={},
                timeout=30,
            )
        )
        assert existing["available_count"] == 57
        # Check every first-half question version remains identical to the live 05 service.
        snapshot = json.loads(
            (Path(__file__).parents[1] / "src/interview_backend/mianstack_snapshot.json").read_text(
                encoding="utf-8"
            )
        )
        first_topics = set(list(TOPICS)[:6])
        preserved = []
        for path, raw in snapshot["files"].items():
            metadata = json.loads(raw.split("---", 2)[1])
            if metadata["topic"] not in first_topics:
                continue
            code = Path(path).stem
            route = f"/api/v1/maintenance/questions/{code}"
            original = data(httpx.get(f"{args.inherited_url}{route}", timeout=30))
            assert data(client.get(route)) == original
            preserved.append(code)
        assert len(preserved) == 57
        persisted_reports = []
        if args.previous:
            previous = json.loads(args.previous.read_text(encoding="utf-8"))
            for draw in previous["draws"]:
                report = data(client.get(f"/api/v1/sessions/{draw['session_id']}/report"))
                assert report == draw["report"]
                persisted_reports.append(draw["session_id"])
            assert len(persisted_reports) == 6
        draws = []
        if args.draw:
            for topic, competency in list(TOPICS.items())[6:]:
                config = {"focus_competency_ids": [competency]}
                focused = data(
                    client.post(f"/api/v1/role-packs/{PACK_ID}/availability", json=config)
                )
                assert focused["available_count"] == expected[topic]
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
                            "client_submission_id": f"06-live-{competency}",
                            "disposition": "skipped",
                            "answer_text": "",
                        },
                    )
                )
                report = data(client.get(f"/api/v1/sessions/{session_id}/report"))
                assert report["average_score"] is None and report["skipped_count"] == 1
                draws.append(
                    {
                        "topic": topic,
                        "competency_id": competency,
                        "available_count": focused["available_count"],
                        "question_code": turn["question_code"],
                        "session_id": session_id,
                        "report": report,
                    }
                )
        page = httpx.get(f"{args.frontend_url}/question-practice", timeout=30)
        page.raise_for_status()
        assert '<div id="root">' in page.text
        proxy = data(
            httpx.post(
                f"{args.frontend_url}/api/v1/role-packs/{PACK_ID}/availability", json={}, timeout=30
            )
        )
        assert proxy == available
    output = {
        "checked_at": datetime.now(UTC).isoformat(),
        "scope": "Local persistent 06 deployment; actual HTTP; no model calls",
        "backend_url": args.base_url,
        "frontend_url": args.frontend_url,
        "expected_database_path": str(
            (Path(__file__).parents[1] / "data/practice.sqlite3").resolve()
        ),
        "publication_id": publication_id,
        "saved_publication_matches": True,
        "availability": available,
        "current_candidates_verified": verified,
        "inherited_question_versions_identical": preserved,
        "inherited_sessions_identical": inherited_sessions,
        "source_05_available_count": existing["available_count"],
        "draws": draws,
        "persisted_skip_reports": persisted_reports,
        "frontend_http_status": page.status_code,
        "frontend_proxy_matches_backend": True,
        "browser_visual_check": "Not performed by this HTTP verification script",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Verified 115 available, 58 current versions, 57 inherited unchanged, {len(draws)} skip sessions, frontend proxy 115"
    )


if __name__ == "__main__":
    main()
