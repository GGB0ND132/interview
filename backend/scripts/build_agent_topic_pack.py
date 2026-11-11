"""Build ticket 06 candidates from the fixed snapshot and per-question editorial source."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from interview_backend.publishing import COMMIT, REPOSITORY, TOPICS

ROOT = Path(__file__).parents[1]


def main() -> None:
    content = (ROOT / "content/agent-topics-second-half.md").read_text(encoding="utf-8")
    edits = {}
    for code, section in re.findall(
        r"^## (Q-\d+)\n(.*?)(?=^## Q-|\Z)", content, re.MULTILINE | re.DOTALL
    ):
        fields = dict(line.split(": ", 1) for line in section.splitlines() if ": " in line)
        if code in edits:
            raise ValueError(f"Duplicate editorial entry: {code}")
        edits[code] = fields
    snapshot = json.loads(
        (ROOT / "src/interview_backend/mianstack_snapshot.json").read_text(encoding="utf-8")
    )
    if snapshot["commit"] != COMMIT:
        raise ValueError("Unexpected source revision")
    questions = []
    provenance = {}
    for code, raw in snapshot["files"].items():
        _, metadata, body = raw.split("---", 2)
        source = json.loads(metadata)
        if source["topic"] not in list(TOPICS)[6:]:
            continue
        edit = edits.pop(code)
        if source["answerStatus"] == "ready":
            origin = "maintainer_edited" if "答案" in edit else "source_original"
        else:
            origin = "agent_generated"
        answer = body.strip() if origin == "source_original" else edit["答案"]
        questions.append(
            {
                "code": code,
                "content_version": edit.get("版本", "agent-basics-06-v1"),
                "prompt": source["title"],
                "topic": source["topic"],
                "competency_id": TOPICS[source["topic"]],
                "difficulty": "easy",
                "stage": "technical",
                "answer": answer,
                "rubric": edit["评分"].split("；"),
                "answer_origin": origin,
                "generation": {
                    "author": "Codex (ticket 06 editorial draft; human review pending)",
                    "generated_at": "2026-11-10",
                    "model": "Codex (runtime model identifier not recorded)",
                    "revision": edit.get("修订", "06-editorial-v1"),
                },
                "answer_refs": [],
                "source": {
                    "original_id": code,
                    "commit": COMMIT,
                    "path": f"questions/{code}.md",
                    "url": f"{REPOSITORY}/blob/{COMMIT}/questions/{code}.md",
                    "license": "MIT",
                    "attribution": "Copyright (c) 2026 didilili",
                    "answer_status": source["answerStatus"],
                },
                "interview_suitable": source["type"] not in {"项目深挖", "代码题"}
                and not any(word in source["title"] for word in ("是否使用", "是否阅读", "项目中")),
                "status": "candidate",
            }
        )
        provenance[code] = {
            "source_file_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            "editorial_basis": edit["依据"].split(", "),
            "answer_origin": origin,
            "rubric_origin": "agent_generated",
            "human_review": "pending",
        }
    if edits:
        raise ValueError(f"Unmatched editorial entries: {sorted(edits)}")
    target = ROOT / "src/interview_backend/agent_topics_second_half.json"
    target.write_text(
        json.dumps({"questions": questions}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (ROOT / "content/agent-topics-second-half-provenance.json").write_text(
        json.dumps({"commit": COMMIT, "questions": provenance}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(f"Built {len(questions)} candidates; no publication performed")


if __name__ == "__main__":
    main()
