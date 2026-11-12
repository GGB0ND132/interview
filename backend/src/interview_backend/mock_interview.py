"""Persisted interview plan and coverage. Scores never determine completeness."""

from __future__ import annotations

import json
import random
import re
import secrets
import sqlite3
from collections import Counter
from typing import Any
from uuid import uuid4

from .contracts import WEIGHTS, MockConfig, ModelEvaluation, feedback
from .errors import PracticeError
from .mock_catalog import STAGES, common_questions
from .store import Store

MINIMUM_QUESTIONS_PER_TOPIC = 2
IGNORED_DIMENSIONS = {
    "introduction": {"accuracy", "completeness"},
    "experience": {"accuracy"},
    "behavioral": {"accuracy"},
    "candidate_questions": {"accuracy", "completeness"},
}
STAGE_WEIGHTS = {
    "experience": {
        "accuracy": 20,
        "completeness": 20,
        "relevance": 20,
        "structure": 15,
        "specificity": 25,
    },
    "behavioral": {"completeness": 25, "relevance": 25, "structure": 25, "specificity": 25},
}
STOP_REASONS = {
    "coverage_satisfied": "所需环节与本场优先能力均已有充分材料可评价；不代表全部回答正确。",
    "user_ended": "用户提前结束，报告仅基于已完成题组，未完成部分不计分。",
    "safety_limit": "达到本场固定的主问题或总轮次保护上限，仍有未覆盖或证据不足项。",
    "question_pool_exhausted": "待问题目已停用或暂停，当前可用题池无法继续既定计划。",
    "key_evidence_insufficient": "已完成计划中的交流，但关键环节或优先能力仍缺少充分材料。",
}


def eligible_topics(pool: list[dict[str, Any]]) -> list[str]:
    counts = Counter(q["competency_id"] for q in pool)
    return sorted(key for key, count in counts.items() if count >= MINIMUM_QUESTIONS_PER_TOPIC)


def readiness(db: sqlite3.Connection, pool: list[dict[str, Any]]) -> dict[str, Any]:
    pool = [q for q in pool if q["interview_suitable"]]
    eligible = eligible_topics(pool)
    common = common_questions(db)
    stages = []
    for stage, label in STAGES.items():
        count = (
            len(pool)
            if stage == "technical_topics"
            else sum(
                q["stage"]
                in (["experience", "scenario"] if stage == "experience_or_scenario" else [stage])
                for q in common
            )
        )
        ready = len(eligible) >= 3 if stage == "technical_topics" else bool(count)
        # Both paths must be available, including the no-project fallback.
        if stage == "experience_or_scenario":
            ready = {"experience", "scenario"}.issubset({q["stage"] for q in common})
        stages.append({"id": stage, "label": label, "available_count": count, "ready": ready})
    return {
        "eligible_topic_count": len(eligible),
        "minimum_topic_count": 3,
        "minimum_questions_per_topic": MINIMUM_QUESTIONS_PER_TOPIC,
        "stages": stages,
        "can_start": all(s["ready"] for s in stages),
        "missing": [s["id"] for s in stages if not s["ready"]],
    }


def save(db: sqlite3.Connection, session_id: str, state: dict[str, Any]) -> None:
    db.execute(
        "INSERT INTO mock_interviews VALUES (?,?) ON CONFLICT(session_id) DO UPDATE SET state_json=excluded.state_json",
        (session_id, json.dumps(state, ensure_ascii=False)),
    )


def load(db: sqlite3.Connection, session_id: str) -> dict[str, Any] | None:
    row = db.execute(
        "SELECT state_json FROM mock_interviews WHERE session_id=?", (session_id,)
    ).fetchone()
    return json.loads(row[0]) if row else None


def public_question(question: dict[str, Any]) -> dict[str, Any]:
    return {
        key: question[key]
        for key in ("code", "version", "stage", "topic", "competency_id", "prompt")
    }


def resume_snapshot(db: sqlite3.Connection, session_id: str) -> dict[str, Any] | None:
    row = db.execute(
        "SELECT snapshot_json FROM session_resumes WHERE session_id=?", (session_id,)
    ).fetchone()
    return json.loads(row[0]) if row else None


def plan(
    db: sqlite3.Connection, session_id: str, pool: list[dict[str, Any]], config: MockConfig
) -> None:
    if not readiness(db, pool)["can_start"]:
        raise PracticeError(
            "INTERVIEW_NOT_READY", "模拟面试缺少合格环节或至少三个题量充足的技术主题", 400
        )
    seed = secrets.randbits(64)
    rng = random.Random(seed)
    pool = [q for q in pool if q["interview_suitable"]]
    eligible = eligible_topics(pool)
    selected = rng.sample(eligible, rng.randint(3, min(4, len(eligible))))
    common = {q["stage"]: q for q in common_questions(db)}
    resume_context = resume_snapshot(db, session_id)
    experience_mode = config.experience_mode
    if resume_context is not None:
        experience_mode = "scenario" if resume_context["no_project_experience"] else "experience"
    technical = []
    backups = {}
    for key in selected:
        candidates = [q for q in pool if q["competency_id"] == key]
        rng.shuffle(candidates)
        technical.append(candidates[0])
        backups[key] = candidates[1:]
    questions = [
        common["introduction"],
        common[experience_mode],
        *technical,
        common["behavioral"],
        common["candidate_questions"],
    ]
    state: dict[str, Any] = {
        "seed": str(seed),
        "resume_context": resume_context,
        "selected_topics": selected,
        "candidate_pool": [{"code": q["code"], "version": q["version"]} for q in pool],
        "questions": questions,
        "backups": backups,
        "scenario": common["scenario"],
        "index": -1,
        "groups": [],
        "turns": [],
        "coverage": {
            key: {"status": "unobserved", "group_ids": [], "answer_quotes": [], "unresolved": []}
            for key in [
                "introduction",
                "experience",
                "scenario",
                *selected,
                "behavioral",
                "candidate_questions",
            ]
        },
        "max_main_questions": config.max_main_questions,
        "max_turns": config.max_main_questions * (1 + config.max_followups_per_question),
        "max_followups": config.max_followups_per_question,
        "stop_reason": None,
    }
    if experience_mode == "scenario":
        state["coverage"]["experience"]["status"] = "not_applicable"
        state["coverage"]["experience"]["unresolved"] = ["用户配置选择假设情境，未评价真实项目经历"]
    else:
        state["coverage"]["scenario"]["status"] = "not_applicable"
    save(db, session_id, state)
    begin_group(db, session_id, state)


def begin_group(db: sqlite3.Connection, session_id: str, state: dict[str, Any]) -> None:
    state["index"] += 1
    question = state["questions"][state["index"]]
    group = {
        "id": str(uuid4()),
        "question": question,
        "status": "incomplete",
        "feedback": None,
        "score": None,
        "followups": 0,
    }
    state["groups"].append(group)
    text = question["prompt"]
    resume_context = state.get("resume_context")
    if question["stage"] == "experience" and resume_context and resume_context["projects"]:
        excerpts = "\n".join(p["text"][:500] for p in resume_context["projects"][:3])
        text += "\n【候选人自述，已确认片段，未经外部核实】\n" + excerpts
    issue_turn(db, session_id, state, question, "main", text)


def issue_turn(
    db: sqlite3.Connection,
    session_id: str,
    state: dict[str, Any],
    question: dict[str, Any],
    kind: str,
    text: str,
) -> None:
    turn = {
        "id": str(uuid4()),
        "group_id": state["groups"][-1]["id"],
        "question_code": question["code"],
        "question_version": question["version"],
        "kind": kind,
        "question_type": question["stage"],
        "stage": question["stage"],
        "topic": question["topic"],
        "competency_id": question["competency_id"],
        "text": text,
    }
    state["turns"].append(turn)
    db.execute(
        "UPDATE sessions SET phase='awaiting_answer',status='active',revision=revision+1,turn_id=?,question_json=? WHERE id=?",
        (turn["id"], json.dumps(question, ensure_ascii=False), session_id),
    )
    save(db, session_id, state)


def decorate(view: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    view["mode"] = "mock_interview"
    view["current_turn"] = state["turns"][-1] if state["turns"] else None
    view["turns"] = state["turns"]
    view["plan"] = {
        key: state[key]
        for key in ("seed", "selected_topics", "candidate_pool", "max_main_questions", "max_turns")
    }
    view["plan"]["questions"] = [public_question(q) for q in state["questions"]]
    view["coverage"] = [{"competency_id": key, **item} for key, item in state["coverage"].items()]
    view["stop_reason"] = state["stop_reason"]
    view["resume_context"] = state.get("resume_context")
    if view["status"] not in {"completed", "ended_early"}:
        for submission in view["submissions"]:
            submission.pop("score", None)
            submission.pop("feedback", None)
    view["available_actions"] = {
        "draft": ["start"],
        "awaiting_answer": ["answer", "skip", "finish"],
        "evaluating": [],
        "evaluation_failed": ["retry", "finish"],
        "stage_transition": ["next", "finish"],
        "feedback_ready": [],
    }[view["phase"]]
    return view


def evaluation_context(db: sqlite3.Connection, state: dict[str, Any]) -> tuple[dict[str, Any], str]:
    group = state["groups"][-1]
    turn_ids = [t["id"] for t in state["turns"] if t["group_id"] == group["id"]]
    rows = {
        row["turn_id"]: row
        for row in db.execute(
            "SELECT * FROM submissions WHERE turn_id IN (" + ",".join("?" for _ in turn_ids) + ")",
            turn_ids,
        )
    }
    answers = [rows[key]["answer_text"] for key in turn_ids if key in rows]
    question = dict(group["question"])
    question["interview_context"] = {
        "current_turn": state["turns"][-1],
        "group_turns": [t for t in state["turns"] if t["group_id"] == group["id"]],
        "saved_answers": answers,
        "remaining_followups": state["max_followups"] - group["followups"],
        "stage": question["stage"],
    }
    if question["stage"] in {"experience", "technical"} and state.get("resume_context"):
        question["interview_context"]["resume_context"] = state["resume_context"]
    return question, "\n".join(answers)


def assess(evaluation: ModelEvaluation, answer: str, stage: str) -> dict[str, Any]:
    # Expressive stages have no technical truth score. Re-normalize applicable weights.
    ignored = IGNORED_DIMENSIONS.get(stage, set())
    adjusted = evaluation.model_copy(deep=True)
    for dimension in adjusted.dimensions:
        if dimension.name in ignored:
            dimension.score = None
            dimension.answer_quote = ""
            dimension.reason = "此环节不适用该维度"
    weights = {
        key: value for key, value in STAGE_WEIGHTS.get(stage, WEIGHTS).items() if key not in ignored
    }
    result = feedback(adjusted, answer, weights=weights)
    result["rubric_version"] = f"interview_{stage}_v1"
    if stage == "technical" and re.search(
        r"^(?:(?:这道题|这个问题)(?:问的[^，。！？“”\"']{1,80})?)?(?:我)?"
        r"(?:不会(?=$|[，。,.!！?？]|解释|回答)|(?:不知道|不清楚)(?=$|[，。,.!！?？]|其中|该|这))",
        answer.strip(),
    ):
        result.update(
            evidence_status="observed",
            evidence_reason="用户明确陈述本题的知识缺口，不等于掌握；不为促使答对继续追问",
            followup=None,
            knowledge_gap=True,
        )
    return result


def covered(state: dict[str, Any]) -> bool:
    coverage = state["coverage"]
    required = ["introduction", "behavioral", "candidate_questions", *state["selected_topics"]]
    experience = coverage["experience"]["status"]
    required.append("scenario" if experience == "not_applicable" else "experience")
    return all(coverage[key]["status"] == "observed" for key in required)


def finish(db: sqlite3.Connection, session_id: str, state: dict[str, Any], reason: str) -> None:
    state["stop_reason"] = reason
    save(db, session_id, state)
    db.execute(
        "UPDATE sessions SET status=?,phase='feedback_ready',revision=revision+1 WHERE id=?",
        ("completed" if reason == "coverage_satisfied" else "ended_early", session_id),
    )


def record_evidence(state: dict[str, Any], status: str, answer: str, reason: str) -> None:
    group = state["groups"][-1]
    key = group["question"]["competency_id"]
    item = state["coverage"][key]
    if group["id"] not in item["group_ids"]:
        item["group_ids"].append(group["id"])
    if answer.strip():
        item["answer_quotes"].append({"group_id": group["id"], "quote": answer[:500]})
    if item["status"] != "observed":
        item["status"] = status
        item["reason"] = reason
        item["unresolved"] = [reason] if status == "insufficient" else []


def after_answer(
    db: sqlite3.Connection,
    session_id: str,
    state: dict[str, Any],
    submission: sqlite3.Row,
    result: dict[str, Any] | None,
) -> None:
    group = state["groups"][-1]
    question = group["question"]
    disposition = effective_disposition(state, submission["disposition"], submission["answer_text"])
    answer = submission["answer_text"]
    status = "insufficient"
    reason = "跳过或空白，缺少可评价材料"
    if result is not None:
        status = result.get("evidence_status") or "insufficient"
        reason = result.get("evidence_reason") or "模型未给出充分证据判断"
    if disposition == "no_experience":
        status, reason = "not_applicable", "用户确认没有项目经历"
        state["coverage"]["scenario"]["status"] = "unobserved"
        state["questions"].insert(state["index"] + 1, state["scenario"])
        if state.get("resume_context"):
            state["resume_context"] = {
                **state["resume_context"],
                "projects": [],
                "no_project_experience": True,
                "interview_override": "用户在面试中明确确认没有项目经历，不再使用原项目片段",
            }
    if disposition == "no_questions":
        status, reason = "observed", "用户明确选择没有反问，不评分"
    record_evidence(state, status, answer, reason)
    proposal = result.get("followup") if result else None
    if (
        status == "insufficient"
        and proposal
        and group["followups"] < state["max_followups"]
        and len(state["turns"]) < state["max_turns"]
        and proposal["answer_quote"].strip()
        and proposal["answer_quote"] in answer
        and proposal["question_code"] == question["code"]
        and proposal["competency_id"] == question["competency_id"]
        and proposal["text"].strip()
        and normalize(proposal["text"]) not in {normalize(t["text"]) for t in state["turns"]}
    ):
        group["followups"] += 1
        group["feedback"] = result
        issue_turn(db, session_id, state, question, "followup", proposal["text"].strip())
        return
    group["status"] = "completed"
    group["feedback"] = result
    group["score"] = (
        result["overall_score"] if result else (0 if disposition == "blank_answer" else None)
    )
    group["disposition"] = disposition
    if state["index"] == len(state["questions"]) - 1:
        reason = "coverage_satisfied" if covered(state) else "key_evidence_insufficient"
        finish(db, session_id, state, reason)
    else:
        save(db, session_id, state)
        db.execute(
            "UPDATE sessions SET status='active',phase='stage_transition',revision=revision+1 WHERE id=?",
            (session_id,),
        )


def normalize(text: str) -> str:
    return "".join(c for c in text.casefold() if c.isalnum())


def effective_disposition(state: dict[str, Any], disposition: str, answer: str) -> str:
    if disposition != "answered":
        return disposition
    stage = state["turns"][-1]["stage"]
    text = normalize(answer)
    # Only unambiguous self-declarations switch paths; arbitrary narratives do not.
    if stage == "experience" and text in {
        "没有项目经历",
        "我没有项目经历",
        "没有项目",
        "我没有做过项目",
        "没做过项目",
    }:
        return "no_experience"
    if stage == "candidate_questions" and text in {
        "没有问题",
        "我没有问题",
        "暂时没有问题",
        "没有反问",
        "暂无反问",
    }:
        return "no_questions"
    return disposition


def advance(db: sqlite3.Connection, session_id: str, state: dict[str, Any]) -> None:
    if (
        len(state["groups"]) >= state["max_main_questions"]
        or len(state["turns"]) >= state["max_turns"]
    ):
        finish(db, session_id, state, "safety_limit")
        return
    group = state["groups"][-1]
    key = group["question"]["competency_id"]
    backups = state["backups"].get(key, [])
    # Clarify first; then try a different published main question at the same ability.
    if state["coverage"][key]["status"] == "insufficient" and backups:
        state["questions"].insert(state["index"] + 1, backups.pop(0))
    # A selected question may have been disabled after planning; never ask a new
    # turn from it. Keep the snapshot for audit and explain the pool gap.
    next_question = state["questions"][state["index"] + 1]
    if Store.scoring_block(db, next_question):
        finish(db, session_id, state, "question_pool_exhausted")
        return
    begin_group(db, session_id, state)


def report(
    session_id: str, state: dict[str, Any], submissions: list[dict[str, Any]]
) -> dict[str, Any]:
    groups = state["groups"]
    scores = [g["score"] for g in groups if g["status"] == "completed" and g["score"] is not None]
    technical = [
        g["score"]
        for g in groups
        if g["question"]["stage"] == "technical"
        and g["status"] == "completed"
        and g["score"] is not None
    ]
    return {
        "session_id": session_id,
        "status": "completed" if state["stop_reason"] == "coverage_satisfied" else "ended_early",
        "scoring_scope": "mock_interview_training",
        "resume_context": state.get("resume_context"),
        "completeness": "complete" if state["stop_reason"] == "coverage_satisfied" else "partial",
        "stop_reason": state["stop_reason"],
        "stop_reason_detail": STOP_REASONS[state["stop_reason"]],
        "average_score": round(sum(scores) / len(scores)) if scores else None,
        "technical_average_score": round(sum(technical) / len(technical)) if technical else None,
        "answered_count": len(scores),
        "blank_count": sum(g.get("disposition") == "blank_answer" for g in groups),
        "skipped_count": sum(g.get("disposition") == "skipped" for g in groups),
        "coverage": [{"competency_id": key, **item} for key, item in state["coverage"].items()],
        "gaps": [
            {"competency_id": key, **item}
            for key, item in state["coverage"].items()
            if item["status"] in {"unobserved", "insufficient"}
        ],
        "groups": [
            {
                **g,
                "question": public_question(g["question"]),
                "feedback": g["feedback"] if g["status"] == "completed" else None,
                "submissions": [
                    s
                    for s in submissions
                    if s["turn_id"] in {t["id"] for t in state["turns"] if t["group_id"] == g["id"]}
                ],
            }
            for g in groups
        ],
        "turns": state["turns"],
        "limitations": [
            "训练评价不是招聘结论；经历与成果仅为候选人自述",
            "本场只覆盖所选技术主题，不代表全部岗位能力",
        ],
    }
