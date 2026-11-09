"""Rebuild ticket 05 assets from a downloaded, pinned MianStack archive.

This is a mechanical build: authored answers/rubrics live in first_half_editorial.json.
No network access, review approval, or database publication happens here.
"""

import argparse
import hashlib
import json
from collections import Counter
from importlib.resources import files
from pathlib import Path
from zipfile import ZipFile

from interview_backend.first_half_release import SAMPLES, bundle_digest
from interview_backend.publishing import COMMIT, REPOSITORY, TOPICS

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src/interview_backend"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    selected = {}
    inventory = []
    with ZipFile(args.archive) as archive:
        for entry in archive.namelist():
            if "/questions/Q-" not in entry or not entry.endswith(".md"):
                continue
            raw = archive.read(entry).decode("utf-8")
            metadata = json.loads(raw.split("---", 2)[1])
            if metadata["category"] == "agent" and metadata["level"] == "基础":
                inventory.append(metadata)
                if metadata["topic"] in list(TOPICS)[:6]:
                    selected[metadata["id"]] = (metadata, raw)
        license_text = archive.read(f"mianstack-{COMMIT}/LICENSE").decode("utf-8")
        if license_text != (ROOT / "third_party/mianstack-LICENSE.txt").read_text("utf-8"):
            raise ValueError("Pinned archive license differs from bundled MIT license")
    snapshot = json.loads(
        files("interview_backend").joinpath("mianstack_snapshot.json").read_text("utf-8")
    )
    editorial = json.loads((ASSETS / "first_half_editorial.json").read_text("utf-8"))
    scoring_notes = json.loads((ASSETS / "first_half_scoring_notes.json").read_text("utf-8"))
    if set(editorial) != set(selected):
        raise ValueError(f"Editorial inventory mismatch: {set(editorial) ^ set(selected)}")
    if set(scoring_notes) != set(selected):
        raise ValueError("Scoring notes must cover exactly the selected questions")
    for code, note in scoring_notes.items():
        for field in ("optional_point", "common_misconception"):
            if not isinstance(note.get(field), str) or not note[field].strip():
                raise ValueError(f"Missing or blank {field} for {code}")
    questions = []
    for code, (metadata, raw) in sorted(selected.items()):
        snapshot["files"][code] = raw
        entry = editorial[code]
        original = metadata["answerStatus"] in {"ready", "reviewed"}
        question = {
            "code": code,
            "content_version": "05.1",
            "prompt": entry.get("prompt", metadata["title"]),
            "topic": metadata["topic"],
            "competency_id": TOPICS[metadata["topic"]],
            "difficulty": "easy",
            "stage": "technical",
            "answer": raw.split("---", 2)[2].strip() if original else entry["answer"],
            "rubric": [
                "考察点：" + metadata["focus"],
                *["必须点：" + point for point in entry["rubric"]],
                "可选点（不是必答，不因缺少而扣分）：" + scoring_notes[code]["optional_point"],
                "常见误区：" + scoring_notes[code]["common_misconception"],
                "可接受变体：机制等价的表述、不同框架或明确标注的假设例子均可；不要求复述本答案。经历题不因未实践或没有量化指标而直接判错。",
            ],
            "answer_origin": "source_original" if original else "agent_generated",
            "answer_refs": [],
            "source": {
                "original_id": code,
                "commit": COMMIT,
                "path": f"questions/{code}.md",
                "url": f"{REPOSITORY}/blob/{COMMIT}/questions/{code}.md",
                "license": "MIT",
                "attribution": "Copyright (c) 2026 didilili",
                "answer_status": metadata["answerStatus"],
            },
            "interview_suitable": entry.get("interview_suitable", True),
            "status": "candidate",
        }
        if "answer_replacements" in entry:
            for old, new in entry["answer_replacements"]:
                if old not in question["answer"]:
                    raise ValueError(f"Missing replacement text in {code}")
                question["answer"] = question["answer"].replace(old, new)
            question["answer_origin"] = "maintainer_edited"
        if not original or "answer_replacements" in entry:
            question["generation"] = {
                "author": "Codex (ticket 05)",
                "model": "Codex (exact runtime model ID unavailable)",
                "generated_at": "2026-11-10",
                "revision": "05.1",
            }
        questions.append(question)
    bundle = {"questions": questions}
    manifest = {
        "source_commit": COMMIT,
        "archive_sha256": hashlib.sha256(args.archive.read_bytes()).hexdigest(),
        "source_inventory_count": len(inventory),
        "selected_count": len(questions),
        "topics": dict(Counter(q["topic"] for q in questions)),
        "questions": [
            {
                "code": q["code"],
                "topic": q["topic"],
                "answer_status": q["source"]["answer_status"],
                "source_sha256": hashlib.sha256(selected[q["code"]][1].encode()).hexdigest(),
            }
            for q in questions
        ],
    }
    for name, value in [
        ("mianstack_snapshot.json", snapshot),
        ("first_half_candidates.json", bundle),
        ("first_half_inventory.json", manifest),
    ]:
        (ASSETS / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    review_path = ASSETS / "first_half_review.json"
    existing_review = json.loads(review_path.read_text("utf-8")) if review_path.exists() else None
    untouched_template = (
        existing_review is not None
        and existing_review.get("incidents") == []
        and all(sample.get("human_review") is None for sample in existing_review.get("samples", []))
    )
    if existing_review is None or untouched_template:
        template = {
            "source_commit": COMMIT,
            "bundle_sha256": bundle_digest(bundle),
            "instructions": "See docs/verification/05-human-sampling.md. Agent checks are not human approval. After errors, review every question in that topic and record incidents; do not erase failed findings.",
            "samples": [
                {"topic": topic, "code": code, "human_review": None}
                for topic, codes in SAMPLES.items()
                for code in codes
            ],
            "incidents": [],
        }
        review_path.write_text(
            json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    sample_codes = {code for codes in SAMPLES.values() for code in codes}
    sample_doc = [
        "# 05 人工抽查题面、候选答案与评分点\n",
        "本文件由题包机械生成。12 题均为 Agent 补答，尚未人工通过。核查材料、Agent 自查与人工记录方法见 [05-human-sampling.md](05-human-sampling.md)。\n",
    ]
    for question in questions:
        if question["code"] not in sample_codes:
            continue
        sample_doc.extend(
            [
                f"## {question['code']}：{question['prompt']}\n",
                f"主题：{question['topic']}；内容版本：{question['content_version']}；答案来源：{question['answer_origin']}。\n",
                f"[固定原题]({question['source']['url']})\n",
                question["answer"] + "\n",
                "评分点：\n",
                "\n".join(f"- {point}" for point in question["rubric"]) + "\n",
            ]
        )
    (ROOT.parent / "docs/verification/05-sample-questions.md").write_text(
        "\n".join(sample_doc), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "inventory_count": len(inventory),
                "selected_count": len(questions),
                "topics": manifest["topics"],
                "origins": dict(Counter(q["answer_origin"] for q in questions)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
