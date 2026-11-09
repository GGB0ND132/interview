"""Preview ticket 05; publish only after its recorded review policy passes."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from importlib.resources import files
from pathlib import Path
from typing import Any

from .publishing import COMMIT, TOPICS, PublicationRequest, Publishing
from .store import Store

SAMPLES = {
    "Agent 基础与运行循环": ["Q-0419", "Q-1674"],
    "Agent 应用架构与场景设计": ["Q-0898", "Q-2078"],
    "规划、推理与任务执行": ["Q-0883", "Q-2506"],
    "上下文工程": ["Q-7020", "Q-7196"],
    "记忆系统": ["Q-0062", "Q-4837"],
    "工具调用与 Function Calling": ["Q-1675", "Q-4836"],
}


def bundle_digest(bundle: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(bundle, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def review_blockers(bundle: dict[str, Any], review: dict[str, Any]) -> list[str]:
    if review.get("source_commit") != COMMIT or review.get("bundle_sha256") != bundle_digest(
        bundle
    ):
        return ["题包或来源版本变化，须重新核对并记录人工抽查。"]
    samples = review.get("samples")
    if not isinstance(samples, list):
        return ["缺少人工抽查记录。"]
    expected = {code for codes in SAMPLES.values() for code in codes}
    if (
        len(samples) != len(expected)
        or {s.get("code") for s in samples if isinstance(s, dict)} != expected
    ):
        return ["必须提供前六主题各两道指定抽查题的完整记录。"]
    blockers = []
    allow_agents = review.get("review_policy") == "independent_agent_first"
    for sample in samples:
        human = sample.get("human_review")
        agent = sample.get("agent_review")
        failed = any(
            isinstance(record, dict) and record.get("conclusion") == "failed"
            for record in (human, agent)
        )
        agent_passed = (
            allow_agents
            and isinstance(agent, dict)
            and agent.get("review_kind") == "independent_agent"
            and passed_review(agent)
        )
        if failed or not (passed_review(human) or agent_passed):
            blockers.append(f"{sample['code']} 尚无符合审核策略的完整通过结论。")
    # A failed expanded review blocks the whole batch. Corrections require a new digest
    # and fresh reviews, including all affected-topic questions after a detected error.
    incidents = review.get("incidents")
    if not isinstance(incidents, list):
        return [*blockers, "必须保留 incidents 列表；无发现错误时使用空列表。"]
    for finding in incidents:
        if not isinstance(finding, dict):
            blockers.append("错误与扩大抽查记录格式无效。")
            continue
        topic = finding.get("topic")
        affected = {q["code"] for q in bundle["questions"] if q["topic"] == topic}
        expanded = finding.get("expanded_review", [])
        reviewed = (
            {r.get("code") for r in expanded if isinstance(r, dict) and passed_review(r)}
            if isinstance(expanded, list)
            else set()
        )
        if (
            topic not in SAMPLES
            or not affected.issubset(reviewed)
            or (
                isinstance(expanded, list) and any(not passed_review(record) for record in expanded)
            )
            or finding.get("resolution") != "corrected_and_rechecked"
        ):
            blockers.append(f"{topic} 发现错误后须停用错题、扩大至全主题抽查；复查前暂停本批发布。")
    return blockers


def passed_review(human: Any) -> bool:
    if not isinstance(human, dict) or human.get("conclusion") != "passed":
        return False
    if not all(
        isinstance(human.get(k), str) and human[k].strip()
        for k in ("reviewer", "reviewed_at", "materials", "findings")
    ):
        return False
    try:
        reviewed_at = datetime.fromisoformat(human["reviewed_at"])
    except ValueError:
        return False
    return reviewed_at.tzinfo is not None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database", type=Path, required=True, help="Target SQLite file (explicit)."
    )
    parser.add_argument("--review-file", type=Path)
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Requires completed review under the recorded policy.",
    )
    args = parser.parse_args()
    assets = files("interview_backend")
    bundle = json.loads(assets.joinpath("first_half_candidates.json").read_text("utf-8"))
    review = json.loads(
        args.review_file.read_text("utf-8")
        if args.review_file
        else assets.joinpath("first_half_review.json").read_text("utf-8")
    )
    publishing = Publishing(Store(args.database))
    request = PublicationRequest.model_validate(bundle)
    preview = publishing.review(request, publish=False)
    blockers = review_blockers(bundle, review)
    sample_codes = {code for codes in SAMPLES.values() for code in codes}
    for item in preview["items"]:
        if not item["accepted"] and item["code"] in sample_codes:
            blockers.append(f"抽查题 {item['code']} 未通过发布校验；须修正后重新抽查。")
    report: dict[str, Any] = {
        "bundle_sha256": bundle_digest(bundle),
        "review_policy": review.get("review_policy", "human_sample"),
        "preview": preview,
        "review_blockers": blockers,
        "published": False,
    }
    if args.publish and not blockers:
        publication = publishing.review(request, publish=True)
        report["publication"] = publication
        report["published"] = publication["accepted_count"] > 0
        report["partial_publication"] = publication["rejected_count"] > 0
    # Publish reports distinguish this batch from any already-published questions.
    with publishing.store.connect() as db:
        pool = publishing.store.published_questions(db, preview["pack_id"])
    report["actual_available_count"] = len(pool)
    report["actual_topic_counts"] = {
        topic: sum(q["topic"] == topic for q in pool) for topic in TOPICS
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if args.publish and (blockers or not report["published"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
