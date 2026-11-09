"""Release the curated topic pack through the existing publishing HTTP boundary.

Human review is an explicit local-maintainer attestation, not model-generated evidence.
The generic ticket-03 maintenance API remains available to trusted maintainers.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from importlib.resources import files
from typing import Any, Protocol

import httpx

from .publishing import COMMIT, PACK_ID, TOPICS


class PublicationClient(Protocol):
    def post(self, url: str, *, json: Any) -> httpx.Response: ...


def candidate_digest(question: dict[str, Any]) -> str:
    serialized = json.dumps(question, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def load_questions() -> list[dict[str, Any]]:
    resource = files("interview_backend")
    questions: list[dict[str, Any]] = []
    # Ticket 05 may add its own artifact without changing this inventory code.
    for name in ("agent_topics_first_half.json", "agent_topics_second_half.json"):
        path = resource.joinpath(name)
        if path.is_file():
            questions.extend(json.loads(path.read_text(encoding="utf-8"))["questions"])
    return questions


def source_catalog() -> list[dict[str, Any]]:
    snapshot = json.loads(
        files("interview_backend").joinpath("mianstack_snapshot.json").read_text(encoding="utf-8")
    )
    if snapshot["commit"] != COMMIT:
        raise ValueError("Unexpected source revision")
    return [json.loads(raw.split("---", 2)[1]) for raw in snapshot["files"].values()]


def review_problem(sample: dict[str, Any], question: dict[str, Any]) -> str | None:
    if sample.get("candidate_sha256") != candidate_digest(question):
        return "REVIEW_CONTENT_CHANGED"
    if sample.get("actor_type") != "human":
        return "HUMAN_REVIEW_REQUIRED"
    if any(
        not isinstance(sample.get(field), str) or not sample[field].strip()
        for field in ("reviewer", "reviewed_at", "findings")
    ):
        return "INCOMPLETE_REVIEW"
    try:
        timestamp = datetime.fromisoformat(sample["reviewed_at"])
        if timestamp.utcoffset() is None:
            return "INVALID_REVIEW_TIME"
    except ValueError:
        return "INVALID_REVIEW_TIME"
    materials = sample.get("materials")
    if not isinstance(materials, list) or not materials:
        return "MISSING_REVIEW_MATERIALS"
    for material in materials:
        if not isinstance(material, dict) or any(
            not isinstance(material.get(field), str) or not material[field].strip()
            for field in ("locator", "version", "checked_excerpt")
        ):
            return "INCOMPLETE_REVIEW_MATERIAL"
    if sample.get("conclusion") != "approved":
        return "REVIEW_NOT_APPROVED"
    return None


class TopicPack:
    def __init__(self, client: PublicationClient):
        self.client = client

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        response = self.client.post(f"/api/v1/{path}", json=body)
        response.raise_for_status()
        result: dict[str, Any] = response.json()["data"]
        return result

    def run(self, reviews: dict[str, Any], *, publish: bool = False) -> dict[str, Any]:
        questions = load_questions()
        by_code = {question["code"]: question for question in questions}
        preview = self._post("maintenance/question-publications/preview", {"questions": questions})
        passed = {item["code"] for item in preview["items"] if item["accepted"]}
        review_errors = []
        approved = set()
        samples = reviews.get("samples", [])
        if not isinstance(samples, list):
            raise TypeError("reviews.samples must be a list")
        seen = set()
        for index, sample in enumerate(samples):
            if not isinstance(sample, dict):
                review_errors.append({"index": index, "reason": "INVALID_REVIEW"})
                continue
            code = sample.get("code")
            problem: str | None
            if not isinstance(code, str) or code not in by_code:
                problem = "UNKNOWN_REVIEW_QUESTION"
            elif code in seen:
                problem = "DUPLICATE_REVIEW_QUESTION"
                approved.discard(code)
            else:
                seen.add(code)
                if sample.get("conclusion") == "pending":
                    continue
                problem = review_problem(sample, by_code[code])
                if problem is None:
                    approved.add(code)
            if problem:
                review_errors.append({"index": index, "code": code, "reason": problem})
        sources = source_catalog()
        topics = []
        eligible = set()
        for topic, competency in TOPICS.items():
            source_rows = [row for row in sources if row["topic"] == topic]
            candidates = [row for row in questions if row["topic"] == topic]
            codes = {row["code"] for row in candidates}
            reviewed = codes & approved
            blockers = []
            if len(source_rows) < 2:
                blockers.append("INSUFFICIENT_DISTINCT_SOURCE_QUESTIONS")
            if len(candidates) != len(source_rows):
                blockers.append("INCOMPLETE_TOPIC_PACK")
            if len(reviewed) < 2:
                blockers.append("TWO_HUMAN_SAMPLES_REQUIRED")
            generated = {q["code"] for q in candidates if q["answer_origin"] == "agent_generated"}
            if generated and not (generated & reviewed):
                blockers.append("GENERATED_ANSWER_SAMPLE_REQUIRED")
            if not blockers:
                eligible.update(codes & passed)
            topics.append(
                {
                    "topic": topic,
                    "competency_id": competency,
                    "source_count": len(source_rows),
                    "source_ready_count": sum(
                        row["answerStatus"] == "ready" for row in source_rows
                    ),
                    "prepared_count": len(candidates),
                    "unprepared_count": len(source_rows) - len(candidates),
                    "validation_passed_count": len(codes & passed),
                    "rejected_count": len(codes - passed),
                    "reviewed_count": len(reviewed),
                    "reviewed_codes": sorted(reviewed),
                    "blockers": blockers,
                }
            )
        publication = None
        # A malformed review file must never partially authorize a publication.
        if publish and eligible and not review_errors:
            publication = self._post(
                "maintenance/question-publications",
                {"questions": [q for q in questions if q["code"] in eligible]},
            )
        available = self._post(
            f"role-packs/{PACK_ID}/availability",
            {"mode": "question_practice", "difficulty": "easy"},
        )
        for row in topics:
            row["available_count"] = available["topic_counts"][row["topic"]]
        return {
            "source_commit": COMMIT,
            "source_count": len(sources),
            "prepared_count": len(questions),
            "unprepared_count": len(sources) - len(questions),
            "validation_passed_count": preview["accepted_count"],
            "rejected_count": preview["rejected_count"],
            "reviewed_count": len(approved),
            "eligible_for_release_count": len(eligible) if not review_errors else 0,
            "published_now_count": publication["imported_count"] if publication else 0,
            "available_count": available["available_count"],
            "topics": topics,
            "validation_items": preview["items"],
            "review_errors": review_errors,
            "human_reviews": samples,
            "publication": publication,
            "complete": all(not row["blockers"] for row in topics) and not review_errors,
        }


def review_template() -> dict[str, Any]:
    questions = load_questions()
    samples = []
    for topic in TOPICS:
        rows = sorted(
            (q for q in questions if q["topic"] == topic),
            key=lambda q: (q["answer_origin"] != "agent_generated", q["code"]),
        )
        for question in rows[:2]:
            samples.append(
                {
                    "code": question["code"],
                    "topic": topic,
                    "candidate_sha256": candidate_digest(question),
                    "actor_type": "human",
                    "reviewer": "",
                    "reviewed_at": "",
                    "materials": [{"locator": "", "version": "", "checked_excerpt": ""}],
                    "findings": "",
                    "conclusion": "pending",
                }
            )
    return {"source_commit": COMMIT, "status": "pending_human_review", "samples": samples}
