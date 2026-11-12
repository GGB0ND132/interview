from __future__ import annotations

import json
from typing import Any, Literal
from uuid import uuid4

from pydantic import Field, field_validator

from . import mock_interview
from .contracts import RequestModel
from .errors import PracticeError
from .provenance import timestamp
from .store import Store

ReportStatus = Literal["open", "in_review", "resolved", "dismissed"]


class UserReport(RequestModel):
    turn_id: str = Field(min_length=1, max_length=100)
    category: Literal["question", "score"]
    explanation: str = Field(min_length=1, max_length=5000)

    @field_validator("explanation")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Explanation must not be blank")
        return value


class HandleReport(RequestModel):
    expected_status: ReportStatus
    status: ReportStatus
    note: str = Field(min_length=1, max_length=5000)

    @field_validator("note")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Handling note must not be blank")
        return value


class Reports:
    def __init__(self, store: Store):
        self.store = store

    def create(self, session_id: str, request: UserReport) -> dict[str, Any]:
        with self.store.connect(write=True) as db:
            session = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
            if session is None:
                raise PracticeError("NOT_FOUND", "会话不存在", 404)
            state = mock_interview.load(db, session_id)
            if state is not None:
                turn = next((t for t in state["turns"] if t["id"] == request.turn_id), None)
                if turn is None:
                    raise PracticeError("STATE_CONFLICT", "报错轮次不属于已保存题目")
                question = next(
                    g["question"] for g in state["groups"] if g["id"] == turn["group_id"]
                )
                if request.category == "score" and session["status"] not in {
                    "completed",
                    "ended_early",
                }:
                    raise PracticeError("STATE_CONFLICT", "请在面试结束后核对评分")
            else:
                if session["turn_id"] != request.turn_id or not session["question_json"]:
                    raise PracticeError("STATE_CONFLICT", "报错轮次不属于已保存题目")
                question = json.loads(session["question_json"])
            submission = db.execute(
                "SELECT id,status FROM submissions WHERE session_id=? AND turn_id=?",
                (session_id, request.turn_id),
            ).fetchone()
            if request.category == "score" and (
                submission is None or submission["status"] != "completed"
            ):
                raise PracticeError("STATE_CONFLICT", "尚无完成的评分可供报错")
            record = {
                "id": str(uuid4()),
                "session_id": session_id,
                "turn_id": request.turn_id,
                "submission_id": submission["id"] if submission else None,
                "question_code": question["code"],
                "answer_version": question["version"],
                "content_version": question.get("content_version"),
                "category": request.category,
                "explanation": request.explanation,
                "status": "open",
                "created_at": timestamp(),
                "history": [],
            }
            db.execute(
                "INSERT INTO user_reports VALUES (?,?,?,?,?)",
                (
                    record["id"],
                    session_id,
                    question["code"],
                    question["version"],
                    json.dumps(record, ensure_ascii=False),
                ),
            )
            return record

    def view(self, report_id: str, session_id: str | None = None) -> dict[str, Any]:
        with self.store.connect() as db:
            row = db.execute(
                "SELECT payload,session_id FROM user_reports WHERE id=?", (report_id,)
            ).fetchone()
            if row is None or (session_id is not None and session_id != row["session_id"]):
                raise PracticeError("NOT_FOUND", "报错记录不存在", 404)
            record: dict[str, Any] = json.loads(row["payload"])
            return record

    def list(self, status: ReportStatus | None, page: int, page_size: int) -> dict[str, Any]:
        with self.store.connect() as db:
            # Payload stores the processing audit trail with its current status.
            where = " WHERE json_extract(payload,'$.status')=?" if status else ""
            params = (status,) if status else ()
            total = db.execute("SELECT COUNT(*) FROM user_reports" + where, params).fetchone()[0]
            rows = db.execute(
                "SELECT payload FROM user_reports"
                + where
                + " ORDER BY json_extract(payload,'$.created_at') DESC,id LIMIT ? OFFSET ?",
                (*params, page_size, (page - 1) * page_size),
            )
            return {
                "items": [json.loads(row[0]) for row in rows],
                "total": total,
                "page": page,
                "page_size": page_size,
            }

    def handle(self, report_id: str, request: HandleReport) -> dict[str, Any]:
        with self.store.connect(write=True) as db:
            row = db.execute("SELECT payload FROM user_reports WHERE id=?", (report_id,)).fetchone()
            if row is None:
                raise PracticeError("NOT_FOUND", "报错记录不存在", 404)
            record: dict[str, Any] = json.loads(row[0])
            if record["status"] != request.expected_status:
                raise PracticeError("STATE_CONFLICT", "报错处理状态已变化")
            record["history"].append(
                {
                    "from_status": record["status"],
                    "status": request.status,
                    "note": request.note,
                    "handled_at": timestamp(),
                }
            )
            record["status"] = request.status
            db.execute(
                "UPDATE user_reports SET payload=? WHERE id=?",
                (
                    json.dumps(record, ensure_ascii=False),
                    report_id,
                ),
            )
            return record
