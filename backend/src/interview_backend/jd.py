"""Explicit JD spans and confirmed mappings; never a source of technical truth."""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from collections.abc import Iterator
from typing import Any, Literal
from uuid import uuid4

from pydantic import Field, field_validator

from .contracts import JDReference, RequestModel, RevisionRequest
from .errors import PracticeError
from .publishing import TOPICS

MAPPING_VERSION = "agent_explicit_terms_v1"
MINIMUM_QUESTIONS_PER_TOPIC = 2
# Deliberately specific terms: generic Python/RAG/AI do not imply Agent competence.
ALIASES = {
    "agent_loop": r"agent\s*(?:基础|运行循环)|智能体(?:基础|运行循环)|运行循环|react\s*(?:循环|模式)|(?-i:\bReAct\b)",
    "agent_application_architecture": r"agent\s*应用架构|智能体应用架构|agent\s*场景设计",
    "agent_planning": r"任务规划|任务拆解|任务分解|规划推理|规划、推理|plan\s*and\s*execute",
    "agent_context_engineering": r"上下文工程|上下文管理|上下文窗口|context\s*engineering",
    "agent_memory": r"记忆系统|长期记忆|短期记忆|agent\s*memory|智能体记忆",
    "agent_tool_calling": r"工具调用|function\s*calling|tool\s*calling",
    "agent_protocols": r"(?<![a-z0-9_])(?:MCP|A2A)(?![a-z0-9_])|工具协议",
    "agent_skills": r"agent\s*skills?\b|skills?\s*(?:能力系统|技能系统|机制|system)|(?:熟悉|掌握|了解|使用)\s*skills?\b|技能系统|(?-i:\bSKILL\.md\b)",
    "agent_workflow_recovery": r"工作流|状态机|执行恢复|断点恢复|workflow",
    "agent_multi_agent": r"多\s*(?:agent|智能体)|multi[ -]?agent",
    "agent_frameworks_harness": r"agent\s*框架|智能体框架|(?<![a-z0-9_])(?:harness|langgraph|autogen)(?![a-z0-9_])",
    "agent_gui": r"(?<![a-z0-9_])GUI(?![a-z0-9_])|computer\s*use|多模态\s*agent",
}


class AnalyzeJD(RequestModel):
    pack_id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=20000)
    difficulty: Literal["easy", "medium", "hard"] = "easy"

    @field_validator("text")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("JD text cannot be blank")
        return value


class ConfirmJD(RevisionRequest):
    confirmed_requirement_ids: list[str] = Field(max_length=1000)

    @field_validator("confirmed_requirement_ids")
    @classmethod
    def unique_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Duplicate requirement ids")
        return value


def coverage(requirement: dict[str, Any], pool: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(q["competency_id"] for q in pool if q["interview_suitable"])
    topics = {competency: topic for topic, competency in TOPICS.items()}
    items = [
        {
            "competency_id": key,
            "topic": topics[key],
            "eligible_question_count": counts[key],
            "eligible": counts[key] >= MINIMUM_QUESTIONS_PER_TOPIC,
            "reason": None
            if counts[key] >= MINIMUM_QUESTIONS_PER_TOPIC
            else "no_published_questions"
            if not counts[key]
            else "insufficient_topic_questions",
        }
        for key in requirement["competency_ids"]
    ]
    return {
        **requirement,
        "coverage": items,
        "gap_reason": "unmapped_requirement"
        if not items
        else "topic_not_eligible"
        if any(not item["eligible"] for item in items)
        else None,
    }


def requirement_spans(text: str) -> Iterator[tuple[int, int]]:
    # Topic names contain list punctuation themselves; preserve those phrases.
    protected = [
        (match.start(), match.end())
        for topic in [*TOPICS, "Plan and Execute", "C++"]
        for match in re.finditer(re.escape(topic), text, re.IGNORECASE)
    ]
    start = 0
    for delimiter in re.finditer(
        r"[\r\n；;。！？!?，,、/+()（）]|\b(?:and|or)\b|以及|和|(?<!参)与|(?<!涉)及",
        text,
        re.IGNORECASE,
    ):
        if any(left <= delimiter.start() < right for left, right in protected):
            continue
        yield start, delimiter.start()
        start = delimiter.end()
    yield start, len(text)


def preview(
    db: sqlite3.Connection, request: AnalyzeJD, pool: list[dict[str, Any]]
) -> dict[str, Any]:
    requirements: list[dict[str, Any]] = []
    # Keep unmatched statements too, so unsupported requirements cannot disappear.
    for left, right in requirement_spans(request.text):
        raw = request.text[left:right]
        prefix = re.match(r"\s*(?:(?:[-*•]|\d+[.)、])\s*)?", raw)
        assert prefix is not None
        start = left + prefix.end()
        end = right - (len(raw) - len(raw.rstrip()))
        text = request.text[start:end]
        if not text or text.rstrip("：:") in {
            "岗位要求",
            "任职要求",
            "岗位职责",
            "Requirements",
            "Responsibilities",
        }:
            continue
        requirements.append(
            coverage(
                {
                    "id": f"requirement_{len(requirements) + 1}",
                    "text": text,
                    "source_span": {
                        "start": start,
                        "end": end,
                        "line": request.text.count("\n", 0, start) + 1,
                    },
                    "competency_ids": [
                        key
                        for key, pattern in ALIASES.items()
                        if re.search(pattern, text, re.IGNORECASE)
                    ],
                },
                pool,
            )
        )
    if not requirements:
        raise PracticeError("JD_NO_REQUIREMENTS", "未找到要求文本，请粘贴具体岗位要求", 400)
    result = {
        "id": str(uuid4()),
        "revision": 0,
        "status": "preview",
        "pack_id": request.pack_id,
        "difficulty": request.difficulty,
        "text": request.text,
        "mapping_version": MAPPING_VERSION,
        "requirements": requirements,
        "confirmed_requirement_ids": [],
        "usage": "job_matching_and_followup_context_only",
        "limitations": ["仅按明示词表提出映射，须用户核对确认；未识别文本保留为缺口"],
    }
    db.execute(
        "INSERT INTO jd_mappings VALUES (?,?)",
        (result["id"], json.dumps(result, ensure_ascii=False)),
    )
    return result


def read(db: sqlite3.Connection, mapping_id: str) -> dict[str, Any]:
    row = db.execute("SELECT payload FROM jd_mappings WHERE id=?", (mapping_id,)).fetchone()
    if row is None:
        raise PracticeError("NOT_FOUND", "JD 映射不存在", 404)
    result: dict[str, Any] = json.loads(row[0])
    return result


def confirm(db: sqlite3.Connection, mapping_id: str, request: ConfirmJD) -> dict[str, Any]:
    result = read(db, mapping_id)
    if result["revision"] != request.expected_revision:
        raise PracticeError("JD_REVISION_CONFLICT", "JD 映射版本已变化，请重新读取确认")
    known = {r["id"] for r in result["requirements"]}
    if not set(request.confirmed_requirement_ids).issubset(known):
        raise PracticeError("JD_REQUIREMENT_UNKNOWN", "确认项不属于此 JD", 400)
    result.update(
        status="confirmed",
        revision=result["revision"] + 1,
        confirmed_requirement_ids=request.confirmed_requirement_ids,
    )
    db.execute(
        "UPDATE jd_mappings SET payload=? WHERE id=?",
        (json.dumps(result, ensure_ascii=False), mapping_id),
    )
    return result


def attach(
    db: sqlite3.Connection,
    session_id: str,
    reference: JDReference,
    pack_id: str,
    difficulty: str,
) -> None:
    mapping = read(db, reference.mapping_id)
    if mapping["revision"] != reference.revision:
        raise PracticeError("JD_REVISION_CONFLICT", "JD 映射版本已变化，请重新读取确认")
    if mapping["status"] != "confirmed":
        raise PracticeError("JD_NOT_CONFIRMED", "JD 映射尚未由用户确认")
    if mapping["pack_id"] != pack_id or mapping["difficulty"] != difficulty:
        raise PracticeError("JD_SCOPE_MISMATCH", "JD 映射与本场题包或难度不一致", 400)
    mapping["requirements"] = [
        r for r in mapping["requirements"] if r["id"] in mapping["confirmed_requirement_ids"]
    ]
    db.execute(
        "INSERT INTO session_jd VALUES (?,?)",
        (session_id, json.dumps(mapping, ensure_ascii=False)),
    )


def session_mapping(db: sqlite3.Connection, session_id: str) -> dict[str, Any] | None:
    row = db.execute("SELECT payload FROM session_jd WHERE session_id=?", (session_id,)).fetchone()
    return json.loads(row[0]) if row else None


def for_selection(
    mapping: dict[str, Any] | None, pool: list[dict[str, Any]]
) -> dict[str, Any] | None:
    if mapping is None:
        return None
    return {**mapping, "requirements": [coverage(r, pool) for r in mapping["requirements"]]}


def topic_candidates(
    eligible: list[str], pool: list[dict[str, Any]], mapping: dict[str, Any] | None
) -> list[dict[str, Any]]:
    counts = Counter(q["competency_id"] for q in pool)
    requirements = mapping["requirements"] if mapping else []
    result = []
    for key in eligible:
        matched = [r["id"] for r in requirements if key in r["competency_ids"]]
        result.append(
            {
                "competency_id": key,
                "eligible_question_count": counts[key],
                "weight": 4 if matched else 1,
                "matched_requirement_ids": matched,
            }
        )
    return result


def report_coverage(
    mapping: dict[str, Any] | None, observed: dict[str, Any], selected: list[str]
) -> dict[str, Any]:
    gaps = []
    for requirement in mapping["requirements"] if mapping else []:
        reason = requirement["gap_reason"]
        if not reason:
            missing = [key for key in requirement["competency_ids"] if key not in selected]
            if missing:
                reason = "not_selected"
            elif any(
                observed[key]["status"] != "observed" for key in requirement["competency_ids"]
            ):
                reason = "insufficient_evidence"
        if reason:
            gaps.append({**requirement, "gap_reason": reason})
    return {
        "jd": mapping,
        "jd_gaps": gaps,
        "jd_coverage_status": "not_provided"
        if mapping is None
        else "partial"
        if gaps
        else "covered",
    }
