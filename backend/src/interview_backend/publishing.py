from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from importlib.resources import files
from typing import Any, Literal
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .contracts import RequestModel
from .errors import PracticeError
from .store import Store

COMMIT = "b1e033dd72db1d4e23fa0c5b8d0ae28fd330de77"
PACK_ID = "pack_agent_basics_mianstack"
PACK_TITLE = "Agent 原理与系统基础档（MianStack）"
REPOSITORY = "https://github.com/didilili/mianstack"
TOPICS = {
    "Agent 基础与运行循环": "agent_loop",
    "Agent 应用架构与场景设计": "agent_application_architecture",
    "规划、推理与任务执行": "agent_planning",
    "上下文工程": "agent_context_engineering",
    "记忆系统": "agent_memory",
    "工具调用与 Function Calling": "agent_tool_calling",
    "MCP、A2A 与工具协议": "agent_protocols",
    "Skills 能力系统": "agent_skills",
    "工作流、状态与执行恢复": "agent_workflow_recovery",
    "多 Agent 编排与协作": "agent_multi_agent",
    "Agent 框架与 Harness": "agent_frameworks_harness",
    "GUI、Computer Use 与多模态 Agent": "agent_gui",
}


class SourceLocator(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    original_id: str
    commit: str
    path: str
    url: str
    license: Literal["MIT"]
    attribution: Literal["Copyright (c) 2026 didilili"]
    answer_status: Literal["pending", "outline", "draft", "ready", "reviewed"]


class QuestionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    code: str = Field(pattern=r"^Q-\d{4,}$")
    content_version: str = Field(min_length=1, max_length=100)
    prompt: str = Field(min_length=8, max_length=5000)
    topic: str
    competency_id: str
    difficulty: Literal["easy"]
    stage: Literal["technical"]
    answer: str = Field(min_length=40, max_length=50000)
    rubric: list[str] = Field(min_length=1, max_length=30)
    answer_origin: Literal["source_original", "agent_generated", "maintainer_edited"]
    generation: dict[str, Any] | None = None
    answer_refs: list[dict[str, Any]] = Field(default_factory=list)
    source: SourceLocator
    interview_suitable: bool
    status: Literal["candidate", "published", "disabled"] = "candidate"


class PublicationRequest(RequestModel):
    # Validate each row separately so one bad candidate does not hide the others.
    questions: list[dict[str, Any]] = Field(min_length=1, max_length=500)


class DisableQuestion(RequestModel):
    expected_version: int = Field(ge=1, strict=True)
    reason: str = Field(min_length=1, max_length=2000)


class Publishing:
    def __init__(self, store: Store, source_transport: httpx.BaseTransport | None = None):
        self.store = store
        self.source_transport = source_transport
        snapshot = json.loads(
            files("interview_backend")
            .joinpath("mianstack_snapshot.json")
            .read_text(encoding="utf-8")
        )
        assert snapshot["commit"] == COMMIT
        self.sources: dict[str, str] = snapshot["files"]

    def _validate_source(self, candidate: QuestionCandidate) -> dict[str, Any]:
        source = candidate.source
        expected_path = f"questions/{candidate.code}.md"
        if (
            source.commit != COMMIT
            or source.original_id != candidate.code
            or source.path != expected_path
            or source.url != f"{REPOSITORY}/blob/{COMMIT}/{expected_path}"
        ):
            raise PracticeError("INVALID_SOURCE_LOCATOR", "必须定位到固定提交中的同号标准题", 400)
        raw = self.sources.get(candidate.code)
        if raw is None:
            # Only a constructed URL at the pinned revision is fetched, never a caller's URL.
            try:
                with httpx.Client(transport=self.source_transport, timeout=10) as client:
                    response = client.get(
                        f"https://raw.githubusercontent.com/didilili/mianstack/{COMMIT}/{expected_path}"
                    )
                    response.raise_for_status()
                    raw = response.text
            except httpx.HTTPError as exc:
                raise PracticeError(
                    "SOURCE_UNAVAILABLE", "固定版本原题无法读取，未放行；可稍后重试", 400
                ) from exc
        try:
            _, frontmatter, body = raw.split("---", 2)
            metadata = json.loads(frontmatter)
            if not isinstance(metadata, dict):
                raise TypeError("Invalid metadata")
            if not isinstance(metadata.get("title"), str) or not metadata["title"].strip():
                raise ValueError("Missing original title")
            if (
                metadata["id"] != candidate.code
                or metadata["category"] != "agent"
                or metadata["level"] != "基础"
                or metadata["topic"] != candidate.topic
                or metadata["answerStatus"] != source.answer_status
            ):
                raise PracticeError(
                    "SOURCE_MISMATCH", "原题身份、Agent 基础分类、主题或答案状态与固定来源不符", 400
                )
        except (ValueError, TypeError, KeyError) as exc:
            raise PracticeError("INVALID_SOURCE_FILE", "固定版本原题格式无效", 400) from exc
        if candidate.answer_origin == "source_original" and (
            source.answer_status not in {"ready", "reviewed"}
            or candidate.answer.strip() != body.strip()
        ):
            raise PracticeError(
                "ANSWER_ORIGIN_MISMATCH", "原文答案须与固定版本正文一致；补写或修改须另行标记", 400
            )
        return {
            **source.model_dump(),
            "repository": REPOSITORY,
            "original_title": metadata["title"],
            "category": metadata["category"],
            "topic": metadata["topic"],
            "level": metadata["level"],
            "file_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            "license_url": f"{REPOSITORY}/blob/{COMMIT}/LICENSE",
        }

    def _validate_candidate(self, candidate: QuestionCandidate) -> dict[str, Any]:
        if candidate.status == "disabled":
            raise PracticeError("QUESTION_DISABLED", "停用题不可发布", 400)
        for field, text in [
            ("prompt", candidate.prompt),
            ("answer", candidate.answer),
            ("content_version", candidate.content_version),
            *[("rubric", point) for point in candidate.rubric],
        ]:
            minimum = 40 if field == "answer" else 6 if field == "rubric" else 1
            if (
                len(text.strip()) < minimum
                or not any(char.isalnum() for char in text)
                or re.search(
                    r"\bTODO\b|\bTBD\b|placeholder|待补|待完善|占位|答案略|待填写|待完成",
                    text,
                    re.IGNORECASE,
                )
            ):
                raise PracticeError("INVALID_CONTENT", f"{field} 为空、不完整或含占位内容", 400)
        if candidate.answer_origin == "agent_generated":
            generation = candidate.generation or {}
            if not all(
                isinstance(generation.get(key), str) and generation[key].strip()
                for key in ("author", "generated_at", "model", "revision")
            ):
                raise PracticeError(
                    "GENERATION_REQUIRED", "Agent 补写须记录作者、生成时间、模型与版本", 400
                )
            try:
                datetime.fromisoformat(generation["generated_at"])
            except ValueError as exc:
                raise PracticeError(
                    "GENERATION_REQUIRED", "生成时间须为 ISO 日期时间", 400
                ) from exc
        source = self._validate_source(candidate)
        if TOPICS.get(candidate.topic) != candidate.competency_id:
            raise PracticeError(
                "INVALID_CLASSIFICATION", "主题与能力必须匹配 Agent 基础能力表", 400
            )
        return source

    def review(self, request: PublicationRequest, *, publish: bool) -> dict[str, Any]:
        duplicates = Counter(
            item.get("code") for item in request.questions if isinstance(item.get("code"), str)
        )
        validated: list[
            tuple[QuestionCandidate | None, dict[str, Any] | None, list[dict[str, Any]]]
        ] = []
        # Remote source verification never holds a database write lock.
        for raw in request.questions:
            try:
                parsed_candidate = QuestionCandidate.model_validate(raw)
                if duplicates[parsed_candidate.code] > 1:
                    raise PracticeError("DUPLICATE_ID", "批次内题号重复，所有同号项均拒绝", 400)
                validated.append((parsed_candidate, self._validate_candidate(parsed_candidate), []))
            except ValidationError as exc:
                validated.append(
                    (
                        None,
                        None,
                        [
                            {
                                "code": "INVALID_FIELD",
                                "field": ".".join(map(str, e["loc"])),
                                "message": "字段缺失或格式无效",
                            }
                            for e in exc.errors()
                        ],
                    )
                )
            except PracticeError as exc:
                validated.append((None, None, [{"code": exc.code, "message": exc.message}]))
        results: list[dict[str, Any]] = []
        with self.store.connect(write=publish) as db:
            if not publish:
                db.execute("BEGIN")
            pool = {
                row["code"]: json.loads(row["payload"])
                for row in db.execute(
                    "SELECT code,payload FROM questions WHERE pack_id=? AND status='published' "
                    "AND version=(SELECT MAX(q.version) FROM questions q WHERE q.code=questions.code)",
                    (PACK_ID,),
                )
            }
            for index, (candidate, source, reasons) in enumerate(validated):
                result: dict[str, Any] = {
                    "index": index,
                    "code": request.questions[index].get("code"),
                    "accepted": False,
                    "reasons": reasons,
                }
                results.append(result)
                if candidate is None:
                    continue
                payload = candidate.model_dump(exclude_none=True)
                payload["source"] = source
                payload["status"] = "published"
                previous = db.execute(
                    "SELECT * FROM questions WHERE code=? ORDER BY version DESC LIMIT 1",
                    (candidate.code,),
                ).fetchone()
                version = 1
                unchanged = False
                if previous is not None:
                    error = None
                    if previous["pack_id"] != PACK_ID:
                        error = ("ID_CONFLICT", "题号已属于另一题包")
                    elif previous["status"] == "disabled":
                        error = ("QUESTION_DISABLED", "已停用题不可通过重新导入恢复")
                    else:
                        versions = db.execute(
                            "SELECT version,payload FROM questions WHERE code=?", (candidate.code,)
                        ).fetchall()
                        matching = next(
                            (
                                row
                                for row in versions
                                if json.loads(row["payload"]).get("content_version")
                                == candidate.content_version
                            ),
                            None,
                        )
                        if matching is not None:
                            old = json.loads(matching["payload"])
                            old.pop("version")
                            if old != payload:
                                error = (
                                    "CONTENT_VERSION_CONFLICT",
                                    "相同内容版本不可改写；请增加 content_version",
                                )
                            elif matching["version"] != previous["version"]:
                                error = ("STALE_CONTENT_VERSION", "旧版本不可覆盖或恢复当前版本")
                            else:
                                unchanged = True
                        version = previous["version"] if unchanged else previous["version"] + 1
                    if error:
                        result["reasons"] = [{"code": error[0], "message": error[1]}]
                        continue
                payload["version"] = version
                result.update(
                    accepted=True,
                    version=version,
                    action="unchanged" if unchanged else "imported",
                    reasons=[{"code": "VALIDATED", "message": "内容结构、分类与固定来源校验通过"}],
                )
                pool[candidate.code] = payload
                if publish and not unchanged:
                    db.execute(
                        "INSERT INTO questions VALUES (?,?,?,?,?,?)",
                        (
                            candidate.code,
                            version,
                            PACK_ID,
                            candidate.difficulty,
                            "published",
                            json.dumps(payload, ensure_ascii=False),
                        ),
                    )
            report = {
                "pack_id": PACK_ID,
                "source_commit": COMMIT,
                "committed": publish,
                "accepted_count": sum(item["accepted"] for item in results),
                "rejected_count": sum(not item["accepted"] for item in results),
                "imported_count": sum(item.get("action") == "imported" for item in results),
                "unchanged_count": sum(item.get("action") == "unchanged" for item in results),
                "available_count": len(pool),
                "topic_counts": {
                    topic: sum(q["topic"] == topic for q in pool.values()) for topic in TOPICS
                },
                "items": results,
            }
            if publish:
                report["publication_id"] = str(uuid4())
                if report["imported_count"]:
                    db.execute("UPDATE role_packs SET version=version+1 WHERE id=?", (PACK_ID,))
                db.execute(
                    "INSERT INTO question_publications VALUES (?,?)",
                    (report["publication_id"], json.dumps(report, ensure_ascii=False)),
                )
            return report

    def publication(self, publication_id: str) -> dict[str, Any]:
        with self.store.connect() as db:
            row = db.execute(
                "SELECT report FROM question_publications WHERE id=?", (publication_id,)
            ).fetchone()
            if row is None:
                raise PracticeError("NOT_FOUND", "发布记录不存在", 404)
            report: dict[str, Any] = json.loads(row["report"])
            return report

    def question(self, code: str) -> dict[str, Any]:
        with self.store.connect() as db:
            rows = db.execute(
                "SELECT payload FROM questions WHERE code=? AND pack_id=? ORDER BY version",
                (code, PACK_ID),
            ).fetchall()
            if not rows:
                raise PracticeError("NOT_FOUND", "已发布题不存在", 404)
            return {"code": code, "versions": [json.loads(row["payload"]) for row in rows]}

    def disable(self, code: str, request: DisableQuestion) -> dict[str, Any]:
        if not request.reason.strip():
            raise PracticeError("INVALID_REASON", "停用原因不可为空白", 400)
        with self.store.connect(write=True) as db:
            row = db.execute(
                "SELECT * FROM questions WHERE code=? AND pack_id=? ORDER BY version DESC LIMIT 1",
                (code, PACK_ID),
            ).fetchone()
            if row is None:
                raise PracticeError("NOT_FOUND", "已发布题不存在", 404)
            if row["version"] != request.expected_version:
                raise PracticeError("STATE_CONFLICT", "题目版本已变化")
            payload: dict[str, Any] = json.loads(row["payload"])
            if row["status"] != "disabled":
                payload.update(status="disabled", disabled_reason=request.reason)
                db.execute(
                    "UPDATE questions SET status='disabled',payload=? WHERE code=? AND version=?",
                    (json.dumps(payload, ensure_ascii=False), code, row["version"]),
                )
                db.execute("UPDATE role_packs SET version=version+1 WHERE id=?", (PACK_ID,))
            return payload
