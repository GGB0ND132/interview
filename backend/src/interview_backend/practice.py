from __future__ import annotations

import json
import random
import secrets
import sqlite3
import time
from typing import Any, cast
from uuid import uuid4

from . import mock_interview
from .contracts import (
    AvailabilityConfig,
    Config,
    CreateSession,
    MockConfig,
    SelectionCriteria,
    SubmitAnswer,
    feedback,
)
from .errors import PracticeError
from .model import INTERVIEW_PROMPT_VERSION, PROMPT_VERSION, Evaluator, ModelError
from .publishing import PACK_ID, TOPICS, topic_counts
from .store import Store


def encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class Practice:
    def __init__(
        self,
        store: Store,
        evaluator: Evaluator,
        model_name: str = "external_adapter",
        *,
        job_lease_seconds: float = 150,
    ):
        self.store = store
        self.evaluator = evaluator
        self.model_name = model_name
        self.job_lease_seconds = job_lease_seconds

    def _pool(
        self, db: sqlite3.Connection, pack_id: str, config: SelectionCriteria
    ) -> list[dict[str, Any]]:
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

    def availability(self, pack_id: str, config: AvailabilityConfig) -> dict[str, Any]:
        with self.store.connect() as db:
            pool = self._pool(db, pack_id, config)
            catalog = self._pool(
                db, pack_id, config.model_copy(update={"focus_competency_ids": []})
            )
            mock_readiness = (
                mock_interview.readiness(db, pool) if config.mode == "mock_interview" else None
            )
        topics = dict(TOPICS) if pack_id == PACK_ID else {}
        topics.update({q["topic"]: q["competency_id"] for q in catalog})
        result = {
            "pack_id": pack_id,
            "mode": config.mode,
            "available_count": len(pool),
            "topic_counts": topic_counts(pool),
            "topics": [
                {
                    "topic": topic,
                    "competency_id": competency,
                    "available_count": sum(q["competency_id"] == competency for q in catalog),
                    "interview_count": sum(
                        q["competency_id"] == competency and q["interview_suitable"]
                        for q in catalog
                    ),
                }
                for topic, competency in topics.items()
            ],
            "can_start": bool(pool),
            "missing": [] if pool else ["published_question"],
        }
        if config.mode == "mock_interview":
            interview_pool = [q for q in pool if q["interview_suitable"]]
            result.update(
                available_count=len(interview_pool),
                topic_counts=topic_counts(interview_pool),
            )
            assert mock_readiness is not None
            result.update(mock_readiness)
        return result

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
        result = {
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
            "available_actions": actions.get(row["phase"], []),
        }
        state = mock_interview.load(db, session_id)
        if state is not None:
            return mock_interview.decorate(result, state)
        if json.loads(row["config_json"])["mode"] == "mock_interview":
            result["mode"] = "mock_interview"
        return result

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
            if (
                isinstance(request.config, MockConfig)
                and not mock_interview.readiness(
                    db, self._pool(db, request.pack_id, request.config)
                )["can_start"]
            ):
                raise PracticeError("INTERVIEW_NOT_READY", "模拟面试环节或技术题池不足", 400)
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
            raw_config = json.loads(row["config_json"])
            if raw_config["mode"] == "mock_interview":
                config = MockConfig.model_validate(raw_config)
                mock_interview.plan(db, session_id, self._pool(db, row["pack_id"], config), config)
                db.execute(
                    "UPDATE sessions SET pack_version=(SELECT version FROM role_packs WHERE id=sessions.pack_id) WHERE id=?",
                    (session_id,),
                )
                return self._view(db, session_id)
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
                    "submission": next(
                        s
                        for s in self._view(db, session_id)["submissions"]
                        if s["id"] == previous["id"]
                    ),
                    "idempotent_replay": True,
                }, None
            if (
                session["revision"] != request.expected_revision
                or session["phase"] != "awaiting_answer"
                or session["turn_id"] != request.turn_id
            ):
                raise PracticeError("STATE_CONFLICT", "当前题目、状态或会话版本已变化")
            state = mock_interview.load(db, session_id)
            special_stage = {
                "no_experience": "experience",
                "no_questions": "candidate_questions",
            }.get(request.disposition)
            if special_stage and (state is None or state["turns"][-1]["stage"] != special_stage):
                raise PracticeError("INVALID_DISPOSITION", "此操作不适用于当前环节", 400)
            submission_id = str(uuid4())
            effective = (
                mock_interview.effective_disposition(
                    state, request.disposition, request.answer_text
                )
                if state is not None
                else request.disposition
            )
            needs_model = effective == "answered"
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
                    "INSERT INTO jobs(id,submission_id,status,phase,recovery_after) "
                    "VALUES (?,?,'queued','evaluation',?)",
                    (job_id, submission_id, time.time() + 1),
                )
            db.execute(
                "UPDATE sessions SET revision=revision+1,phase=?,status=? WHERE id=?",
                (
                    "evaluating" if needs_model else "feedback_ready",
                    "active" if needs_model or state is not None else "completed",
                    session_id,
                ),
            )
            if state is not None and not needs_model:
                saved = db.execute(
                    "SELECT * FROM submissions WHERE id=?", (submission_id,)
                ).fetchone()
                assert saved is not None
                mock_interview.after_answer(db, session_id, state, saved, None)
            view = self._view(db, session_id)
            return {
                "session": view,
                "submission": next(s for s in view["submissions"] if s["id"] == submission_id),
                "idempotent_replay": False,
            }, job_id

    def evaluate(self, job_id: str) -> None:
        claim_token = str(uuid4())
        with self.store.connect(write=True) as db:
            claimed = db.execute(
                "UPDATE jobs SET status='running',claim_token=?,lease_expires_at=?,"
                "attempts=attempts+1 WHERE id=? AND (status='queued' OR "
                "(status='running' AND COALESCE(lease_expires_at,0)<=?))",
                (claim_token, time.time() + self.job_lease_seconds, job_id, time.time()),
            ).rowcount
            if not claimed:
                return
            row = db.execute(
                "SELECT a.*,s.question_json FROM submissions a JOIN sessions s ON s.id=a.session_id WHERE a.job_id=?",
                (job_id,),
            ).fetchone()
            assert row is not None
            question = json.loads(row["question_json"])
            state = mock_interview.load(db, row["session_id"])
            answer = row["answer_text"]
            if state is not None:
                question, answer = mock_interview.evaluation_context(db, state)
        failure = None
        result = None
        try:
            with self.store.connect() as db:
                block = self.store.scoring_block(db, question)
            if block:
                raise ModelError("题目已停用或主题评分暂停；回答已保留，请等待维护复核", block)
            evaluation = self.evaluator.evaluate(question=question, answer=answer)
            result = (
                mock_interview.assess(evaluation, answer, question["stage"])
                if state is not None
                else feedback(evaluation, answer)
            )
            result.update(
                {
                    "answer_version": question["version"],
                    "answer_origin": question["answer_origin"],
                    "reference_answer": question["answer"],
                    "prompt_version": INTERVIEW_PROMPT_VERSION
                    if state is not None
                    else PROMPT_VERSION,
                    "requested_model": self.model_name,
                    "question_source": question["source"],
                    "answer_generation": question.get("generation"),
                    "independent_references": question.get("answer_refs", []),
                }
            )
        except ModelError as exc:
            failure = {
                "code": exc.code,
                "message": str(exc),
                "retryable": True,
                "phase": exc.stage,
                "action": "retry",
            }
        except ValueError:
            failure = {
                "code": "MODEL_OUTPUT_INVALID",
                "message": "模型评价或回答引文无效，回答已保留",
                "retryable": True,
                "phase": "evaluation",
                "action": "retry",
            }
        except Exception:  # noqa: BLE001 -- External evaluator failures become safe retryable results.
            failure = {
                "code": "EVALUATION_FAILED",
                "message": "评价暂时失败，回答已保留，请重试",
                "retryable": True,
                "phase": "evaluation",
                "action": "retry",
            }
        if failure:
            result = None
        with self.store.connect(write=True) as db:
            # Commit only the job claimed above.
            job = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if (
                job is None
                or job["status"] != "running"
                or job["claim_token"] != claim_token
                or job["lease_expires_at"] <= time.time()
            ):
                return
            block = self.store.scoring_block(db, question)
            if block:
                result = None
                failure = {
                    "code": block,
                    "message": "题目已停用或主题评分暂停；回答已保留，请等待维护复核",
                    "retryable": True,
                    "phase": "evaluation",
                    "action": "retry",
                }
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
            if state is not None and not failure:
                mock_interview.after_answer(db, row["session_id"], state, row, result)

    def pending_jobs(self) -> list[str]:
        """Include legacy jobs without leases; never steal an unexpired claim."""
        with self.store.connect() as db:
            return [
                row["id"]
                for row in db.execute(
                    "SELECT id FROM jobs WHERE (status='queued' AND recovery_after<=?) OR "
                    "(status='running' AND COALESCE(lease_expires_at,0)<=?)",
                    (time.time(), time.time()),
                )
            ]

    def retry(self, session_id: str, revision: int) -> str:
        with self.store.connect(write=True) as db:
            session = self._row(db, session_id)
            previous = db.execute(
                "SELECT j.id FROM jobs j JOIN submissions a ON a.id=j.submission_id "
                "WHERE a.session_id=? AND j.retry_revision=?",
                (session_id, revision),
            ).fetchone()
            if previous is not None:
                return str(previous["id"])
            if session["revision"] != revision or session["phase"] != "evaluation_failed":
                raise PracticeError("STATE_CONFLICT", "没有此版本可重试的评价任务")
            row = db.execute(
                "SELECT * FROM submissions WHERE session_id=? AND turn_id=?",
                (session_id, session["turn_id"]),
            ).fetchone()
            assert row is not None
            job_id: str = row["job_id"]
            db.execute(
                "UPDATE jobs SET status='queued',error_json=NULL,claim_token=NULL,"
                "lease_expires_at=NULL,retry_revision=?,recovery_after=? WHERE id=?",
                (revision, time.time() + 1, job_id),
            )
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
                "attempts": row["attempts"],
                "result_entity_id": row["submission_id"] if row["status"] == "succeeded" else None,
                "error": json.loads(row["error_json"]) if row["error_json"] else None,
            }

    def report(self, session_id: str) -> dict[str, Any]:
        with self.store.connect() as db:
            session = self._row(db, session_id)
            if json.loads(session["config_json"])["mode"] == "mock_interview":
                if session["status"] not in {"completed", "ended_early"}:
                    raise PracticeError("REPORT_NOT_READY", "模拟面试结束后才公开详细报告")
                state = mock_interview.load(db, session_id)
                assert state is not None
                submissions = [
                    self._submission(item)
                    for item in db.execute(
                        "SELECT * FROM submissions WHERE session_id=? ORDER BY created_at,id",
                        (session_id,),
                    )
                ]
                return mock_interview.report(session_id, state, submissions)
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

    def advance(self, session_id: str, revision: int) -> dict[str, Any]:
        with self.store.connect(write=True) as db:
            row = self._row(db, session_id)
            state = mock_interview.load(db, session_id)
            if state is None or row["revision"] != revision or row["phase"] != "stage_transition":
                raise PracticeError("STATE_CONFLICT", "当前状态不能进入下一题组")
            mock_interview.advance(db, session_id, state)
            return self._view(db, session_id)

    def finish(self, session_id: str, revision: int) -> dict[str, Any]:
        with self.store.connect(write=True) as db:
            row = self._row(db, session_id)
            state = mock_interview.load(db, session_id)
            if (
                state is None
                or row["revision"] != revision
                or row["status"] != "active"
                or row["phase"] == "evaluating"
            ):
                raise PracticeError("STATE_CONFLICT", "当前状态不能结束模拟面试")
            mock_interview.finish(db, session_id, state, "user_ended")
            return self._view(db, session_id)
