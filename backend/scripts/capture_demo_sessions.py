"""Read saved HTTP sessions/reports into a reviewable artifact. No model calls."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from interview_backend.demo_acceptance import data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8017")
    parser.add_argument("--session", action="append", help="label=session-id")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.verify_existing:
        saved = json.loads(args.output.read_text("utf-8"))
        with httpx.Client(base_url=args.base_url, timeout=30) as client:
            for case in saved["cases"]:
                path = f"/api/v1/sessions/{case['session']['session_id']}"
                assert data(client.get(path)) == case["session"], "Saved session changed"
                if case["report"] is not None:
                    assert data(client.get(f"{path}/report")) == case["report"], "Report changed"
                for job in case["jobs"]:
                    assert data(client.get(f"/api/v1/jobs/{job['job_id']}")) == job, "Job changed"
        saved["restart_verified_at"] = datetime.now(UTC).isoformat()
        args.output.write_text(json.dumps(saved, ensure_ascii=False, indent=2) + "\n", "utf-8")
        print(f"Verified unchanged sessions, reports and jobs: {args.output}")
        return
    if not args.session:
        parser.error("--session is required unless --verify-existing is selected")
    record = {
        "checked_at": datetime.now(UTC).isoformat(),
        "base_url": args.base_url,
        "fixture_notice": "Synthetic acceptance answers; provider identity is retained per feedback",
        "cases": [],
    }
    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        for item in args.session:
            label, session_id = item.split("=", 1)
            path = f"/api/v1/sessions/{session_id}"
            session = data(client.get(path))
            report_response = client.get(f"{path}/report")
            if report_response.status_code != 409:
                report = data(report_response)
            else:
                report = None
            jobs = [
                data(client.get(f"/api/v1/jobs/{submission['job_id']}"))
                for submission in session["submissions"]
                if submission.get("job_id")
            ]
            record["cases"].append(
                {"case": label, "session": session, "report": report, "jobs": jobs}
            )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"Captured {len(record['cases'])} cases: {args.output}")


if __name__ == "__main__":
    main()
