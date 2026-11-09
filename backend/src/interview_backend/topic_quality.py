"""Persist wrong-question quarantine, expanded reviews and topic scoring holds."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

from pydantic import Field, field_validator

from .contracts import RequestModel
from .errors import PracticeError
from .publishing import (
    PACK_ID,
    TOPICS,
    PublicationRequest,
    Publishing,
    QuestionCandidate,
    SourceLocator,
)
from .store import active_incidents
from .topic_pack import candidate_digest, review_problem, source_catalog


class QualityIncident(RequestModel):
    code: str
    expected_version: int = Field(ge=1, strict=True)
    error_kind: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("error_kind", "reason")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Quality incident fields cannot be blank")
        return value.strip()


class QualityCorrection(RequestModel):
    expected_version: int = Field(ge=1, strict=True)
    candidate: QuestionCandidate
    review: dict[str, Any]


class QualityResume(RequestModel):
    samples: list[dict[str, Any]] = Field(max_length=500)


def as_candidate(payload: dict[str, Any]) -> dict[str, Any]:
    question = {
        key: value for key, value in payload.items() if key in QuestionCandidate.model_fields
    }
    question["status"] = "candidate"
    question["source"] = {
        key: value for key, value in question["source"].items() if key in SourceLocator.model_fields
    }
    return question


class TopicQuality:
    def __init__(self, publishing: Publishing):
        self.publishing = publishing
        self.store = publishing.store

    @staticmethod
    def _topic(competency: str) -> str:
        for topic, identifier in TOPICS.items():
            if identifier == competency:
                return topic
        raise PracticeError("NOT_FOUND", "未知 Agent 基础主题", 404)

    @staticmethod
    def _state(db: sqlite3.Connection, topic: str) -> dict[str, Any]:
        row = db.execute("SELECT payload FROM topic_quality WHERE topic=?", (topic,)).fetchone()
        if row:
            result: dict[str, Any] = json.loads(row["payload"])
            return result
        return {
            "pack_id": PACK_ID,
            "topic": topic,
            "paused": False,
            "required_sample_count": 2,
            "incidents": [],
            "resolutions": [],
        }

    @staticmethod
    def _save(db: sqlite3.Connection, state: dict[str, Any]) -> None:
        db.execute(
            "INSERT INTO topic_quality VALUES (?,?) "
            "ON CONFLICT(topic) DO UPDATE SET payload=excluded.payload",
            (state["topic"], json.dumps(state, ensure_ascii=False)),
        )

    def view(self, competency: str) -> dict[str, Any]:
        topic = self._topic(competency)
        with self.store.connect() as db:
            state = self._state(db, topic)
            # These are the exact version-bound candidates a reviewer may inspect.
            state["review_candidates"] = [
                {"candidate": candidate, "candidate_sha256": candidate_digest(candidate)}
                for row in db.execute(
                    "SELECT payload FROM questions WHERE pack_id=? AND status='published' "
                    "AND version=(SELECT MAX(q.version) FROM questions q WHERE q.code=questions.code)",
                    (PACK_ID,),
                )
                if (candidate := as_candidate(json.loads(row["payload"])))["topic"] == topic
            ]
            return state

    def incident(self, competency: str, request: QualityIncident) -> dict[str, Any]:
        topic = self._topic(competency)
        with self.store.connect(write=True) as db:
            state = self._state(db, topic)
            for previous in state["incidents"]:
                if (
                    previous["code"] == request.code
                    and previous["expected_version"] == request.expected_version
                ):
                    if previous != request.model_dump(exclude={"schema_version"}):
                        raise PracticeError("STATE_CONFLICT", "同一题目版本已有不同错误记录")
                    return state
            row = db.execute(
                "SELECT * FROM questions WHERE code=? AND pack_id=? ORDER BY version DESC LIMIT 1",
                (request.code, PACK_ID),
            ).fetchone()
            if row is None or json.loads(row["payload"])["topic"] != topic:
                raise PracticeError("NOT_FOUND", "该主题没有此已发布题目", 404)
            if row["version"] != request.expected_version:
                raise PracticeError("STATE_CONFLICT", "题目版本已变化")
            state["incidents"].append(request.model_dump(exclude={"schema_version"}))
            state["paused"] = state["paused"] or len(active_incidents(state)) >= 2
            count = sum(source["topic"] == topic for source in source_catalog())
            state["required_sample_count"] = min(4, count)
            question = json.loads(row["payload"])
            question.update(status="disabled", disabled_reason=request.reason)
            db.execute(
                "UPDATE questions SET status='disabled',payload=? WHERE code=? AND version=?",
                (json.dumps(question, ensure_ascii=False), request.code, row["version"]),
            )
            self._save(db, state)
            db.execute("UPDATE role_packs SET version=version+1 WHERE id=?", (PACK_ID,))
            return state

    def correct(self, competency: str, request: QualityCorrection) -> dict[str, Any]:
        topic = self._topic(competency)
        candidate = request.candidate.model_dump(exclude_none=True)
        if candidate.get("topic") != topic or request.review.get("code") != candidate.get("code"):
            raise PracticeError("INVALID_REVIEW", "更正题目与主题或核查题号不匹配", 400)
        with self.store.connect() as db:
            if not any(
                incident["code"] == candidate["code"]
                and incident["expected_version"] == request.expected_version
                for incident in active_incidents(self._state(db, topic))
            ):
                raise PracticeError(
                    "QUALITY_INCIDENT_REQUIRED", "须先登记该停用版本的错误并进入扩大抽查流程"
                )
        problem = review_problem(request.review, candidate)
        if problem:
            raise PracticeError(problem, "更正须由人工核查并绑定新的完整内容", 400)
        return self.publishing.review(
            PublicationRequest(questions=[candidate]),
            publish=True,
            restorations={candidate["code"]: request.expected_version},
            human_reviews=[request.review],
        )

    def resume(self, competency: str, request: QualityResume) -> dict[str, Any]:
        topic = self._topic(competency)
        with self.store.connect(write=True) as db:
            state = self._state(db, topic)
            active = active_incidents(state)
            if not active:
                raise PracticeError("STATE_CONFLICT", "此主题没有待复查错误")
            current = {
                row["code"]: json.loads(row["payload"])
                for row in db.execute(
                    "SELECT * FROM questions WHERE pack_id=? "
                    "AND version=(SELECT MAX(q.version) FROM questions q WHERE q.code=questions.code)",
                    (PACK_ID,),
                )
                if json.loads(row["payload"])["topic"] == topic
            }
            for issue in active:
                corrected = current.get(issue["code"])
                if (
                    corrected is None
                    or corrected["status"] != "published"
                    or corrected["version"] <= issue["expected_version"]
                ):
                    raise PracticeError("CORRECTIONS_REQUIRED", "错题须更正并复查新版本后恢复")
            approved = set()
            for sample in request.samples:
                code = sample.get("code")
                if (
                    not isinstance(code, str)
                    or code in approved
                    or code not in current
                    or current[code]["status"] != "published"
                    or review_problem(sample, as_candidate(current[code]))
                ):
                    raise PracticeError("INVALID_REVIEW", "复查记录无效、重复或内容版本已变化", 400)
                approved.add(code)
            if len(approved) < state["required_sample_count"] or not {
                issue["code"] for issue in active
            }.issubset(approved):
                raise PracticeError("EXPANDED_REVIEW_REQUIRED", "须扩大抽查并包含全部已更正错题")
            state["paused"] = False
            state["resolved_incident_count"] = len(state["incidents"])
            state["resolutions"].append(
                {
                    "resumed_at": datetime.now(UTC).isoformat(),
                    "samples": request.samples,
                }
            )
            self._save(db, state)
            db.execute("UPDATE role_packs SET version=version+1 WHERE id=?", (PACK_ID,))
            return state
