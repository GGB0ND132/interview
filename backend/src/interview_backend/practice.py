from __future__ import annotations

import json
import random
import secrets
import sqlite3
from typing import Any, cast
from uuid import uuid4

from .contracts import Config, CreateSession, SubmitAnswer, feedback
from .errors import PracticeError
from .model import PROMPT_VERSION, Evaluator, ModelError
from .publishing import topic_counts
from .store import Store


def encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class Practice:
    def __init__(self, store: Store, evaluator: Evaluator, model_name: str = "external_adapter"):
        self.store = store
        self.evaluator = evaluator
        self.model_name = model_name

    def _pool(self, db: sqlite3.Connection, pack_id: str, config: Config) -> list[dict[str, Any]]:
        pack = db.execute("SELECT * FROM role_packs WHERE id=?", (pack_id,)).fetchone()
        if pack is None or pack["status"] != "published":
            raise PracticeError("PACK_NOT_PUBLISHED", "该岗位包尚未发布", 400)
        pool = self.store.published_questions(db, pack_id)
        return [
            q
            for q in pool
            if q["difficulty"] == config.difficulty
            and q["stage"] == "technical"
            and q["answer"].strip()
            and q["rubric"]
            and (
                not config.focus_competency_ids or q["competency_id"] in config.focus_competency_ids
            )
        ]

    def packs(self) -> list[dict[str, Any]]:
        with self.store.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM role_packs ORDER BY id")]

    def availability(self, pack_id: str, config: Config) -> dict[str, Any]:
        with self.store.connect() as db:
            pool = self._pool(db, pack_id, config)
        return {
            "pack_id": pack_id,
            "mode": config.mode,
            "available_count": len(pool),
            "topic_counts": topic_counts(pool),
            "can_start": bool(pool),
            "missing": [] if pool else ["published_question"],
        }

    @staticmethod
    def _row(db: sqlite3.Connection, session_id: str) -> sqlite3.Row:
        row = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        if row is None:
            raise PracticeError("NOT_FOUND", "会话不存在", 404)
        return cast(sqlite3.Row, row)

    @staticmethod
    def _submission(row: sqlite3.Row) -> dict[str, Any]:
        result = {
            key: row[key]
            for key in (
                "id",
                "turn_id",
                "client_submission_id",
                "disposition",
                "answer_text",
                "status",
                "job_id",
            )
        }
        if row["status"] == "completed":
            result["score"] = row["score"]
            if row["evaluation_json"]:
                result["feedback"] = json.loads(row["evaluation_json"])
        if row["error_json"]:
            result["error"] = json.loads(row["error_json"])
        return result

    def _view(self, db: sqlite3.Connection, session_id: str) -> dict[str, Any]:
        row = self._row(db, session_id)
        turn = None
        if row["question_json"]:
            question = json.loads(row["question_json"])
            turn = {
                "id": row["turn_id"],
                "question_code": question["code"],
                "question_version": question["version"],
                "kind": "main",
                "question_type": "technical",
                "stage": "technical",
                "topic": question["topic"],
                "competency_id": question["competency_id"],
                "text": question["prompt"],
            }
        submissions = db.execute(
            "SELECT * FROM submissions WHERE session_id=? ORDER BY created_at, id", (session_id,)
        ).fetchall()
        actions = {
            "draft": ["start"],
            "awaiting_answer": ["answer", "skip"],
            "evaluating": [],
            "feedback_ready": [],
            "evaluation_failed": ["retry"],
        }
        pack = db.execute("SELECT title FROM role_packs WHERE id=?", (row["pack_id"],)).fetchone()
        return {
            "session_id": row["id"],
            "pack_id": row["pack_id"],
            "pack_version": row["pack_version"],
            "pack_title": pack["title"] if pack else None,
            "created_at": row["created_at"],
            "difficulty": json.loads(row["config_json"])["difficulty"],
            "revision": row["revision"],
            "status": row["status"],
            "phase": row["phase"],
            "current_turn": turn,
            "submissions": [self._submission(item) for item in submissions],
            "available_actions": actions[row["phase"]],
        }

    def view(self, session_id: str) -> dict[str, Any]:
        with self.store.connect() as db:
            db.execute("BEGIN")
            return self._view(db, session_id)

    def history(self, page: int, page_size: int) -> dict[str, Any]:
        with self.store.connect() as db:
            db.execute("BEGIN")
            rows = db.execute(
                "SELECT id FROM sessions ORDER BY created_at DESC, id LIMIT ? OFFSET ?",
                (page_size, (page - 1) * page_size),
            ).fetchall()
            total = db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            return {
                "items": [self._view(db, row["id"]) for row in rows],
                "page": page,
                "page_size": page_size,
                "total": total,
            }

    def create(self, request: CreateSession) -> dict[str, Any]:
        with self.store.connect(write=True) as db:
            if not self._pool(db, request.pack_id, request.config):
                raise PracticeError("QUESTION_POOL_EXHAUSTED", "没有满足条件的已发布题目", 400)
            session_id = str(uuid4())
            version = db.execute(
                "SELECT version FROM role_packs WHERE id=?", (request.pack_id,)
            ).fetchone()[0]
            db.execute(
                "INSERT INTO sessions(id,pack_id,pack_version,config_json,status,phase) VALUES (?,?,?,?,'draft','draft')",
                (session_id, request.pack_id, version, request.config.model_dump_json()),
            )
            return self._view(db, session_id)

    def start(self, session_id: str, revision: int) -> dict[str, Any]:
        with self.store.connect(write=True) as db:
            row = self._row(db, session_id)
            if row["revision"] != revision or row["status"] != "draft":
                raise PracticeError("STATE_CONFLICT", "会话状态或版本已变化")
            pool = self._pool(db, row["pack_id"], Config.model_validate_json(row["config_json"]))
            if not pool:
                raise PracticeError("QUESTION_POOL_EXHAUSTED", "开始时已无可用题目", 400)
            seed = secrets.randbits(64)
            question = random.Random(seed).choice(pool)
            selection = {
                "seed": str(seed),
                "candidate_pool": [{"code": q["code"], "version": q["version"]} for q in pool],
            }
            db.execute(
                "UPDATE sessions SET status='active',phase='awaiting_answer',revision=revision+1,turn_id=?,question_json=?,selection_json=?,pack_version=(SELECT version FROM role_packs WHERE id=sessions.pack_id) WHERE id=?",
                (str(uuid4()), encode(question), encode(selection), session_id),
            )
            return self._view(db, session_id)

    def submit(self, session_id: str, request: SubmitAnswer) -> tuple[dict[str, Any], str | None]:
        request_json = encode(request.model_dump())
        with self.store.connect(write=True) as db:
            session = self._row(db, session_id)
            previous = db.execute(
                "SELECT * FROM submissions WHERE session_id=? AND client_submission_id=?",
                (session_id, request.client_submission_id),
            ).fetchone()
            if previous is not None:
                if previous["request_json"] != request_json:
                    raise PracticeError("STATE_CONFLICT", "提交标识已被不同内容或版本使用")
                return {
                    "session": self._view(db, session_id),
                    "submission": self._submission(previous),
                    "idempotent_replay": True,
                }, None
            if (
                session["revision"] != request.expected_revision
                or session["phase"] != "awaiting_answer"
                or session["turn_id"] != request.turn_id
            ):
                raise PracticeError("STATE_CONFLICT", "当前题目、状态或会话版本已变化")
            submission_id = str(uuid4())
            needs_model = request.disposition == "answered"
            job_id = str(uuid4()) if needs_model else None
            db.execute(
                "INSERT INTO submissions(id,session_id,turn_id,client_submission_id,request_json,disposition,answer_text,status,score,job_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    submission_id,
                    session_id,
                    request.turn_id,
                    request.client_submission_id,
                    request_json,
                    request.disposition,
                    request.answer_text,
                    "saved" if needs_model else "completed",
                    0 if request.disposition == "blank_answer" else None,
                    job_id,
                ),
            )
            if job_id:
                db.execute(
                    "INSERT INTO jobs VALUES (?,?,'queued','evaluation',NULL)",
                    (job_id, submission_id),
                )
            db.execute(
                "UPDATE sessions SET revision=revision+1,phase=?,status=? WHERE id=?",
                (
                    "evaluating" if needs_model else "feedback_ready",
                    "active" if needs_model else "completed",
                    session_id,
                ),
            )
            view = self._view(db, session_id)
            return {
                "session": view,
                "submission": view["submissions"][0],
                "idempotent_replay": False,
            }, job_id

    def evaluate(self, job_id: str) -> None:
        with self.store.connect(write=True) as db:
            claimed = db.execute(
                "UPDATE jobs SET status='running' WHERE id=? AND status='queued'", (job_id,)
            ).rowcount
            if not claimed:
                return
            row = db.execute(
                "SELECT a.*,s.question_json FROM submissions a JOIN sessions s ON s.id=a.session_id WHERE a.job_id=?",
                (job_id,),
            ).fetchone()
            assert row is not None
            question = json.loads(row["question_json"])
        failure = None
        result = None
        try:
            evaluation = self.evaluator.evaluate(question=question, answer=row["answer_text"])
            result = feedback(evaluation, row["answer_text"])
            result.update(
                {
                    "answer_version": question["version"],
                    "answer_origin": question["answer_origin"],
                    "reference_answer": question["answer"],
                    "prompt_version": PROMPT_VERSION,
                    "requested_model": self.model_name,
                    "question_source": question["source"],
                    "answer_generation": question.get("generation"),
                    "independent_references": question.get("answer_refs", []),
                }
            )
        except ModelError as exc:
            failure = {"code": exc.code, "message": str(exc), "retryable": True}
        except ValueError:
            failure = {
                "code": "MODEL_OUTPUT_INVALID",
                "message": "模型评价或回答引文无效，回答已保留",
                "retryable": True,
            }
        with self.store.connect(write=True) as db:
            db.execute(
                "UPDATE submissions SET status=?,score=?,evaluation_json=?,error_json=? WHERE id=?",
                (
                    "failed" if failure else "completed",
                    result["overall_score"] if result else None,
                    encode(result) if result else None,
                    encode(failure) if failure else None,
                    row["id"],
                ),
            )
            db.execute(
                "UPDATE jobs SET status=?,error_json=? WHERE id=?",
                (
                    "failed" if failure else "succeeded",
                    encode(failure) if failure else None,
                    job_id,
                ),
            )
            db.execute(
                "UPDATE sessions SET revision=revision+1,phase=?,status=? WHERE id=?",
                (
                    "evaluation_failed" if failure else "feedback_ready",
                    "active" if failure else "completed",
                    row["session_id"],
                ),
            )

    def retry(self, session_id: str, revision: int) -> str:
        with self.store.connect(write=True) as db:
            session = self._row(db, session_id)
            if session["revision"] != revision or session["phase"] != "evaluation_failed":
                raise PracticeError("STATE_CONFLICT", "没有此版本可重试的评价任务")
            row = db.execute(
                "SELECT * FROM submissions WHERE session_id=?", (session_id,)
            ).fetchone()
            assert row is not None
            job_id: str = row["job_id"]
            db.execute("UPDATE jobs SET status='queued',error_json=NULL WHERE id=?", (job_id,))
            db.execute(
                "UPDATE submissions SET status='saved',error_json=NULL WHERE id=?", (row["id"],)
            )
            db.execute(
                "UPDATE sessions SET phase='evaluating',revision=revision+1 WHERE id=?",
                (session_id,),
            )
            return job_id

    def job(self, job_id: str) -> dict[str, Any]:
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise PracticeError("NOT_FOUND", "任务不存在", 404)
            return {
                "job_id": row["id"],
                "status": row["status"],
                "phase": row["phase"],
                "result_entity_id": row["submission_id"] if row["status"] == "succeeded" else None,
                "error": json.loads(row["error_json"]) if row["error_json"] else None,
            }

    def report(self, session_id: str) -> dict[str, Any]:
        view = self.view(session_id)
        submissions = view["submissions"]
        scores = [
            s["score"] for s in submissions if s["status"] == "completed" and s["score"] is not None
        ]
        return {
            "session_id": session_id,
            "average_score": round(sum(scores) / len(scores)) if scores else None,
            "answered_count": len(scores),
            "blank_count": sum(s["disposition"] == "blank_answer" for s in submissions),
            "skipped_count": sum(s["disposition"] == "skipped" for s in submissions),
            "status": view["status"],
            "scoring_scope": "single_question_training",
        }
