"""Prepare the explicit local demo database under the existing 05/06 review gates.

Requires its server already running at --base-url. No model calls. Never use a
normal practice database for fault injection; that has a separate fixture server.
"""

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import httpx

from interview_backend.demo_acceptance import data, inspect_release
from interview_backend.publishing import TOPICS
from interview_backend.topic_pack import TopicPack


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8017")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume-output", type=Path, required=True)
    args = parser.parse_args()
    database = args.database.resolve(strict=True)
    first = subprocess.run(
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
        check=True,
    )
    first_half = json.loads(first.stdout)
    reports = Path(__file__).resolve().parents[2] / "docs/verification"
    records = [
        json.loads((reports / name).read_text("utf-8"))
        for name in (
            "06-content-protocols-workflow-review.json",
            "06-content-skills-multiagent-review.json",
            "06-content-frameworks-gui-review.json",
        )
    ]
    with httpx.Client(base_url=args.base_url, timeout=60) as client:
        publication_id = first_half["publication"]["publication_id"]
        saved = data(client.get(f"/api/v1/maintenance/question-publications/{publication_id}"))
        assert saved == first_half["publication"], "HTTP server must use the explicit target DB"
        second_half = TopicPack(client).run(
            {
                "source_commit": records[0]["source_commit"],
                "samples": [sample for record in records for sample in record["samples"]],
            },
            publish=True,
            review_policy="agent_full",
            competency_ids=list(TOPICS.values())[6:],
        )
        assert second_half["complete"], "Existing full Agent review gate must pass"
        common = data(client.post("/api/v1/maintenance/mock-interview-questions/publish", json={}))
        inventory = inspect_release(client)
        assert inventory["release_matches_candidates"]
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>项目经历</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>订单 Agent：我负责工具参数校验、权限检查和失败停止机制。"
            "这是课程演示，无真实业务指标。</w:t></w:r></w:p></w:body></w:document>",
        )
    args.resume_output.parent.mkdir(parents=True, exist_ok=True)
    args.resume_output.write_bytes(output.getvalue())
    result = {
        "checked_at": datetime.now(UTC).isoformat(),
        "database": str(database),
        "base_url": args.base_url,
        "model_calls": 0,
        "review_notice": "Existing authorized Agent reviews; no human sampling claimed",
        "first_half": first_half,
        "second_half": second_half,
        "common": common,
        "inventory": inventory,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"Prepared 115 technical + 5 common questions; evidence={args.output}")


if __name__ == "__main__":
    main()
