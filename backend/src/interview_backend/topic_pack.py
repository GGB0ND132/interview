"""Release the curated topic pack through the existing publishing HTTP boundary.

Review identity is preserved. Agent review must be explicitly selected by the maintainer.
The generic ticket-03 maintenance API remains available to trusted maintainers.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from importlib.resources import files
from typing import Any, Literal, Protocol

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


def review_problem(
    sample: dict[str, Any], question: dict[str, Any], *, actor_type: str = "human"
) -> str | None:
    if sample.get("candidate_sha256") != candidate_digest(question):
        return "REVIEW_CONTENT_CHANGED"
    if sample.get("actor_type") != actor_type:
        return "HUMAN_REVIEW_REQUIRED" if actor_type == "human" else "AGENT_REVIEW_REQUIRED"
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

    def run(
        self,
        reviews: dict[str, Any],
        *,
        publish: bool = False,
        review_policy: Literal["human_sample", "agent_full"] = "human_sample",
        competency_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        if review_policy not in {"human_sample", "agent_full"}:
            raise ValueError("Unknown release review policy")
        scope = set(competency_ids if competency_ids is not None else TOPICS.values())
        if not scope or not scope.issubset(set(TOPICS.values())):
            raise ValueError("Release scope must contain known Agent competencies")
        questions = [q for q in load_questions() if q["competency_id"] in scope]
        if not questions:
            raise ValueError("No prepared candidates in selected scope")
        by_code = {question["code"]: question for question in questions}
        preview = self._post("maintenance/question-publications/preview", {"questions": questions})
        passed = {item["code"] for item in preview["items"] if item["accepted"]}
        review_errors: list[dict[str, Any]] = []
        if review_policy == "agent_full" and reviews.get("source_commit") != COMMIT:
            review_errors.append({"reason": "REVIEW_SOURCE_MISMATCH"})
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
                problem = review_problem(
                    sample,
                    by_code[code],
                    actor_type="agent" if review_policy == "agent_full" else "human",
                )
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
            selected = competency in scope
            if review_policy == "human_sample" and len(source_rows) < 2:
                blockers.append("INSUFFICIENT_DISTINCT_SOURCE_QUESTIONS")
            if len(candidates) != len(source_rows):
                blockers.append("INCOMPLETE_TOPIC_PACK")
            if review_policy == "agent_full":
                if codes - reviewed or not codes:
                    blockers.append("FULL_AGENT_REVIEW_REQUIRED")
            elif len(reviewed) < 2:
                blockers.append("TWO_HUMAN_SAMPLES_REQUIRED")
            generated = {q["code"] for q in candidates if q["answer_origin"] == "agent_generated"}
            if generated and not (generated & reviewed):
                blockers.append("GENERATED_ANSWER_SAMPLE_REQUIRED")
            if selected and not blockers:
                eligible.update(codes & passed)
            topics.append(
                {
                    "topic": topic,
                    "competency_id": competency,
                    "selected_for_release": selected,
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
        gate_passed = (
            not review_errors
            and preview["rejected_count"] == 0
            and all(not row["blockers"] for row in topics if row["selected_for_release"])
        )
        if (
            publish
            and eligible
            and not review_errors
            and (review_policy == "human_sample" or gate_passed)
        ):
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
        release_succeeded = publication is not None and (
            publication["rejected_count"] == 0
            and publication["accepted_count"] == len(questions)
            and all(
                row["available_count"] >= row["prepared_count"]
                for row in topics
                if row["selected_for_release"]
            )
        )
        return {
            "source_commit": COMMIT,
            "review_policy": review_policy,
            "scope_competency_ids": sorted(scope),
            "source_count": len(sources),
            "prepared_count": len(questions),
            "unprepared_count": len(sources) - len(questions),
            "validation_passed_count": preview["accepted_count"],
            "rejected_count": preview["rejected_count"],
            "reviewed_count": len(approved),
            "agent_reviewed_count": len(approved) if review_policy == "agent_full" else 0,
            "human_reviewed_count": len(approved) if review_policy == "human_sample" else 0,
            "eligible_for_release_count": len(eligible) if not review_errors else 0,
            "published_now_count": publication["imported_count"] if publication else 0,
            "available_count": available["available_count"],
            "topics": topics,
            "validation_items": preview["items"],
            "review_errors": review_errors,
            "human_reviews": samples if review_policy == "human_sample" else [],
            "review_records": samples,
            "publication": publication,
            "complete": gate_passed and (not publish or release_succeeded),
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
