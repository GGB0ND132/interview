import json
from concurrent.futures import ThreadPoolExecutor
from importlib.resources import files
from threading import Event

import pytest
from fastapi.testclient import TestClient

from interview_backend.api import create_app
from interview_backend.contracts import Dimension, Followup, ModelEvaluation
from interview_backend.model import ModelError

PACK = "pack_agent_basics_mianstack"
CONFIG = {"mode": "mock_interview", "difficulty": "easy"}


def data(response):
    assert response.is_success, response.text
    return response.json()["data"]


def publish_technical(client):
    bundle = json.loads(
        files("interview_backend").joinpath("first_half_candidates.json").read_text("utf-8")
    )
    result = data(client.post("/api/v1/maintenance/question-publications", json=bundle))
    assert result["accepted_count"] == 57


def start(client, **config):
    draft = data(
        client.post("/api/v1/sessions", json={"pack_id": PACK, "config": {**CONFIG, **config}})
    )
    return data(
        client.post(f"/api/v1/sessions/{draft['session_id']}/start", json={"expected_revision": 0})
    )


def test_published_stages_unlock_a_persisted_random_subset_of_topics(tmp_path):
    database = tmp_path / "mock.sqlite3"
    with TestClient(create_app(database_path=database)) as client:
        publish_technical(client)
        url = f"/api/v1/role-packs/{PACK}/availability"
        assert data(client.post(url, json=CONFIG))["can_start"] is False
        assert (
            client.post("/api/v1/sessions", json={"pack_id": PACK, "config": CONFIG}).status_code
            == 400
        )
        published = data(client.post("/api/v1/maintenance/mock-interview-questions/publish"))
        assert published["available_count"] == 5
        assert data(client.post(url, json=CONFIG))["can_start"] is True
        session = start(client)
        plan = session["plan"]
        assert 3 <= len(plan["selected_topics"]) <= 4
        assert len(plan["selected_topics"]) < 6
        assert 7 <= len(plan["questions"]) <= 8
        assert all("answer" not in q and "rubric" not in q for q in plan["questions"])
        assert session["current_turn"]["stage"] == "introduction"
        assert {item["status"] for item in session["coverage"]} == {
            "unobserved",
            "not_applicable",
        }
        assert "seed" in plan and plan["max_main_questions"] == 12
    with TestClient(create_app(database_path=database)) as client:
        assert data(client.get(f"/api/v1/sessions/{session['session_id']}")) == session


class InterviewEvaluator:
    def evaluate(self, *, question, answer):
        return ModelEvaluation(
            dimensions=[
                Dimension(
                    name=name, score=75, reason="回答提供可评价的具体材料", answer_quote=answer[:20]
                )
                for name in ("accuracy", "completeness", "relevance", "structure", "specificity")
            ],
            strengths=["表达具体"],
            improvements=["可进一步说明边界"],
            evidence_status="observed",
            evidence_reason="有具体行动与判断依据",
        )


def answer(
    client,
    session,
    disposition="answered",
    text="我说明具体职责和约束，再用成功、失败两类案例验证结果，记录个人行动并总结改进。",
):
    return data(
        client.post(
            f"/api/v1/sessions/{session['session_id']}/answers",
            json={
                "expected_revision": session["revision"],
                "turn_id": session["current_turn"]["id"],
                "client_submission_id": session["current_turn"]["id"],
                "disposition": disposition,
                "answer_text": text if disposition == "answered" else "",
            },
        )
    )


def refresh(client, session):
    return data(client.get(f"/api/v1/sessions/{session['session_id']}"))


def next_group(client, session):
    return data(
        client.post(
            f"/api/v1/sessions/{session['session_id']}/next",
            json={"expected_revision": session["revision"]},
        )
    )


def ready(client):
    publish_technical(client)
    data(client.post("/api/v1/maintenance/mock-interview-questions/publish"))


def test_complete_conversation_hides_scores_until_final_group_and_counts_groups_once(tmp_path):
    with TestClient(
        create_app(database_path=tmp_path / "complete.sqlite3", evaluator=InterviewEvaluator())
    ) as client:
        ready(client)
        session = start(client)
        stages = set()
        while session["status"] not in {"completed", "ended_early"}:
            assert client.get(f"/api/v1/sessions/{session['session_id']}/report").status_code == 409
            stages.add(session["current_turn"]["stage"])
            result = answer(client, session)
            assert "score" not in result["submission"] and "feedback" not in result["submission"]
            session = refresh(client, session)
            if session["status"] not in {"completed", "ended_early"}:
                assert all("score" not in a and "feedback" not in a for a in session["submissions"])
                session = next_group(client, session)
        assert stages == {
            "introduction",
            "scenario",
            "technical",
            "behavioral",
            "candidate_questions",
        }
        report = data(client.get(f"/api/v1/sessions/{session['session_id']}/report"))
        assert report["completeness"] == "complete"
        assert report["stop_reason"] == "coverage_satisfied"
        assert 7 <= len(report["groups"]) <= 8
        assert report["average_score"] == 75
        assert report["technical_average_score"] == 75
        assert report["groups"][0]["feedback"]["dimensions"][0]["score"] is None
        assert report["groups"][0]["feedback"]["assessment_coverage"] == 1
        assert report["groups"][0]["feedback"]["assessment_status"] == "complete"


class UnclearEvaluator(InterviewEvaluator):
    def evaluate(self, *, question, answer):
        result = super().evaluate(question=question, answer=answer)
        if question["stage"] == "technical":
            result.evidence_status = "insufficient"
            result.evidence_reason = "只有笼统说法，缺少可判断的具体机制"
            result.followup = Followup(
                text="你提到验证，请说明本题中你会具体检查的一个结果？",
                answer_quote="验证",
                purpose="澄清当前回答的验证机制",
                question_code=question["code"],
                competency_id=question["competency_id"],
            )
        return result


def run_remaining(
    client,
    session,
    *,
    technical_disposition="answered",
    technical_text="我会验证，但说不出具体怎样做。",
):
    while session["status"] not in {"completed", "ended_early"}:
        technical = session["current_turn"]["stage"] == "technical"
        answer(
            client,
            session,
            disposition=technical_disposition if technical else "answered",
            text=technical_text if technical else "先明确目标和职责，再验证结果并记录反思。",
        )
        session = refresh(client, session)
        if session["phase"] == "stage_transition":
            session = next_group(client, session)
    return data(client.get(f"/api/v1/sessions/{session['session_id']}/report"))


def test_vague_answers_trigger_grounded_deduplicated_followups_then_other_published_questions(
    tmp_path,
):
    with TestClient(
        create_app(database_path=tmp_path / "vague.sqlite3", evaluator=UnclearEvaluator())
    ) as client:
        ready(client)
        session = start(client)
        report = run_remaining(client, session)
        assert report["completeness"] == "partial"
        assert report["stop_reason"] == "safety_limit"
        assert len(report["groups"]) == 12
        followups = [t for t in report["turns"] if t["kind"] == "followup"]
        assert len(followups) == 1  # repeated proposals cannot repeat across groups
        assert all(g["followups"] <= 2 for g in report["groups"])
        assert report["gaps"]
        codes = [g["question"]["code"] for g in report["groups"]]
        assert len(codes) == len(set(codes))
        restored = refresh(client, session)
        assert restored["status"] == "ended_early"


@pytest.mark.parametrize("disposition,score", [("blank_answer", 0), ("skipped", None)])
def test_blank_or_skipped_technical_answers_leave_partial_coverage(tmp_path, disposition, score):
    with TestClient(
        create_app(database_path=tmp_path / "missing.sqlite3", evaluator=InterviewEvaluator())
    ) as client:
        ready(client)
        session = start(client)
        report = run_remaining(client, session, technical_disposition=disposition)
        assert report["completeness"] == "partial"
        technical = [g for g in report["groups"] if g["question"]["stage"] == "technical"]
        assert technical and all(g["score"] == score for g in technical)
        assert all(g["followups"] == 0 for g in technical)


def test_no_experience_requires_scenario_evidence_and_no_questions_has_no_quality_score(tmp_path):
    with TestClient(
        create_app(database_path=tmp_path / "scenario.sqlite3", evaluator=InterviewEvaluator())
    ) as client:
        ready(client)
        session = start(client, experience_mode="experience")
        answer(client, session)
        session = next_group(client, refresh(client, session))
        assert session["current_turn"]["stage"] == "experience"
        answer(client, session, "no_experience")
        session = next_group(client, refresh(client, session))
        assert session["current_turn"]["stage"] == "scenario"
        assert "假设" in session["current_turn"]["text"]
        assert {c["competency_id"]: c["status"] for c in session["coverage"]}[
            "experience"
        ] == "not_applicable"
        while session["current_turn"]["stage"] != "candidate_questions":
            answer(client, session)
            session = next_group(client, refresh(client, session))
        answer(client, session, "no_questions")
        report = data(client.get(f"/api/v1/sessions/{session['session_id']}/report"))
        assert report["completeness"] == "complete"
        assert report["groups"][-1]["score"] is None


def test_user_can_end_with_an_unanswered_scenario_as_an_explicit_gap(tmp_path):
    with TestClient(
        create_app(database_path=tmp_path / "ended.sqlite3", evaluator=InterviewEvaluator())
    ) as client:
        ready(client)
        session = start(client)
        answer(client, session)
        session = next_group(client, refresh(client, session))
        ended = data(
            client.post(
                f"/api/v1/sessions/{session['session_id']}/finish",
                json={"expected_revision": session["revision"]},
            )
        )
        report = data(client.get(f"/api/v1/sessions/{session['session_id']}/report"))
        assert ended["stop_reason"] == "user_ended"
        assert report["completeness"] == "partial"
        assert report["groups"][-1]["status"] == "incomplete"
        assert any(
            g["competency_id"] == "scenario" and g["status"] == "unobserved" for g in report["gaps"]
        )


class FlakyEvaluator(InterviewEvaluator):
    def evaluate(self, *, question, answer):
        if question["stage"] == "scenario" and not getattr(self, "failed", False):
            self.failed = True
            raise ModelError("暂时不可用")
        return super().evaluate(question=question, answer=answer)


def test_retry_targets_current_group_and_replay_never_leaks_earlier_scores(tmp_path):
    with TestClient(
        create_app(database_path=tmp_path / "retry.sqlite3", evaluator=FlakyEvaluator())
    ) as client:
        ready(client)
        session = start(client)
        original = session
        answer(client, session)
        session = next_group(client, refresh(client, session))
        answer(client, session)
        failed = refresh(client, session)
        assert failed["phase"] == "evaluation_failed"
        data(
            client.post(
                f"/api/v1/sessions/{session['session_id']}/retry",
                json={"expected_revision": failed["revision"]},
            )
        )
        retried = refresh(client, session)
        assert retried["phase"] == "stage_transition"
        assert len(retried["submissions"]) == 2
        assert all(s["status"] == "completed" for s in retried["submissions"])
        replay = answer(client, original)
        assert replay["idempotent_replay"] is True
        assert "score" not in replay["submission"]
        assert all(
            "feedback" not in s
            for s in data(client.get("/api/v1/sessions"))["items"][0]["submissions"]
        )


def test_typed_no_project_statement_also_switches_to_hypothetical_scenario(tmp_path):
    with TestClient(
        create_app(database_path=tmp_path / "typed.sqlite3", evaluator=InterviewEvaluator())
    ) as client:
        ready(client)
        session = start(client, experience_mode="experience")
        answer(client, session)
        session = next_group(client, refresh(client, session))
        answer(client, session, text="我没有项目经历。")
        session = next_group(client, refresh(client, session))
        assert session["current_turn"]["stage"] == "scenario"


class LowScoreEvaluator(InterviewEvaluator):
    def evaluate(self, *, question, answer):
        result = super().evaluate(question=question, answer=answer)
        if question["stage"] == "technical":
            for d in result.dimensions:
                d.score = 0
            result.evidence_reason = "已明确观察到知识缺口，不是掌握"
        return result


@pytest.mark.parametrize(
    "text",
    [
        "工具调用只要模型说成功就一定完成，不需要程序执行也不用校验结果。",
        "我不会解释当前主问题中的机制，具体不知道工具执行与模型决策如何衔接。",
    ],
)
def test_wrong_or_explicit_unknown_answers_can_be_observed_without_being_marked_mastered(
    tmp_path, text
):
    with TestClient(
        create_app(database_path=tmp_path / "low.sqlite3", evaluator=LowScoreEvaluator())
    ) as client:
        ready(client)
        report = run_remaining(client, start(client), technical_text=text)
        assert report["completeness"] == "complete"  # coverage, not a pass grade
        assert report["technical_average_score"] == 0
        assert all(
            "知识缺口" in g["feedback"]["evidence_reason"]
            for g in report["groups"]
            if g["question"]["stage"] == "technical"
        )


class FollowupEvaluator(UnclearEvaluator):
    def evaluate(self, *, question, answer):
        result = super().evaluate(question=question, answer=answer)
        if result.followup:
            count = len(question["interview_context"]["group_turns"])
            result.followup.text = f"你提到验证，请补充本题第{count}个失败检查的具体步骤？"
        return result


def test_followups_stop_at_configured_cap_and_are_not_counted_as_separate_scores(tmp_path):
    with TestClient(
        create_app(database_path=tmp_path / "cap.sqlite3", evaluator=FollowupEvaluator())
    ) as client:
        ready(client)
        session = start(client, max_followups_per_question=2, max_main_questions=3)
        report = run_remaining(client, session)
        assert report["stop_reason"] == "safety_limit"
        assert len(report["groups"]) == 3
        assert report["groups"][-1]["followups"] == 2
        assert len(report["turns"]) == 5
        assert report["answered_count"] == 3


def test_disabled_planned_question_stops_with_pool_gap_and_preserves_selection(tmp_path):
    with TestClient(
        create_app(database_path=tmp_path / "disabled.sqlite3", evaluator=InterviewEvaluator())
    ) as client:
        ready(client)
        session = start(client)
        chosen = session["plan"]["questions"][2]
        data(
            client.post(
                f"/api/v1/maintenance/questions/{chosen['code']}/disable",
                json={"expected_version": chosen["version"], "reason": "验收中停用待问题目"},
            )
        )
        answer(client, session)
        session = next_group(client, refresh(client, session))
        answer(client, session)
        session = next_group(client, refresh(client, session))
        assert session["stop_reason"] == "question_pool_exhausted"
        report = data(client.get(f"/api/v1/sessions/{session['session_id']}/report"))
        assert report["completeness"] == "partial"


def test_user_end_during_model_call_conflicts_then_can_end_after_evaluation(tmp_path):
    entered, release = Event(), Event()

    class BlockingEvaluator(InterviewEvaluator):
        def evaluate(self, *, question, answer):
            entered.set()
            assert release.wait(10)
            return super().evaluate(question=question, answer=answer)

    with TestClient(
        create_app(database_path=tmp_path / "cancelled.sqlite3", evaluator=BlockingEvaluator())
    ) as client:
        ready(client)
        session = start(client)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(answer, client, session)
            try:
                assert entered.wait(5)
                pending = refresh(client, session)
                assert "finish" not in pending["available_actions"]
                assert (
                    client.post(
                        f"/api/v1/sessions/{session['session_id']}/finish",
                        json={"expected_revision": pending["revision"]},
                    ).status_code
                    == 409
                )
                assert (
                    client.get(f"/api/v1/sessions/{session['session_id']}/report").status_code
                    == 409
                )
            finally:
                release.set()
            future.result(timeout=10)
        evaluated = refresh(client, session)
        assert evaluated["phase"] == "stage_transition"
        ended = data(
            client.post(
                f"/api/v1/sessions/{session['session_id']}/finish",
                json={"expected_revision": evaluated["revision"]},
            )
        )
        assert ended["status"] == "ended_early"
        assert (
            data(client.get(f"/api/v1/sessions/{session['session_id']}/report"))["completeness"]
            == "partial"
        )


def test_explicit_observed_unknown_with_null_accuracy_does_not_trigger_repeated_questions(tmp_path):
    class UnknownEvaluator(LowScoreEvaluator):
        def evaluate(self, *, question, answer):
            result = super().evaluate(question=question, answer=answer)
            if question["stage"] == "technical":
                result.dimensions[0].score = None
            return result

    with TestClient(
        create_app(database_path=tmp_path / "null-accuracy.sqlite3", evaluator=UnknownEvaluator())
    ) as client:
        ready(client)
        session = start(client)
        report = run_remaining(
            client,
            session,
            technical_text="我不会解释这道题中的具体机制，明确不知道模型决策与工具执行的衔接方式。",
        )
        assert report["completeness"] == "complete"
        assert len(report["groups"]) == len(session["plan"]["questions"])
        assert all(g["followups"] == 0 for g in report["groups"])


def test_report_uses_behavior_and_experience_weights_with_applicable_coverage(tmp_path):
    class VariedEvaluator(InterviewEvaluator):
        def evaluate(self, *, question, answer):
            result = super().evaluate(question=question, answer=answer)
            scores = {
                "accuracy": 100,
                "completeness": 80,
                "relevance": 40,
                "structure": 60,
                "specificity": 20,
            }
            for dimension in result.dimensions:
                dimension.score = scores[dimension.name]
            return result

    with TestClient(
        create_app(database_path=tmp_path / "weights.sqlite3", evaluator=VariedEvaluator())
    ) as client:
        ready(client)
        report = run_remaining(client, start(client, experience_mode="experience"))
        groups = {g["question"]["stage"]: g for g in report["groups"]}
        assert groups["behavioral"]["score"] == 50
        assert groups["experience"]["score"] == 48
        assert groups["technical"]["score"] == 72
        assert all(g["feedback"]["assessment_coverage"] == 1 for g in report["groups"])


def test_inapplicable_dimensions_do_not_require_a_fabricated_answer_quote(tmp_path):
    class InapplicableQuote(InterviewEvaluator):
        def evaluate(self, *, question, answer):
            result = super().evaluate(question=question, answer=answer)
            if question["stage"] == "introduction":
                result.dimensions[0].score = None
                result.dimensions[0].answer_quote = "不适用"
            return result

    with TestClient(
        create_app(database_path=tmp_path / "inapplicable.sqlite3", evaluator=InapplicableQuote())
    ) as client:
        ready(client)
        session = start(client)
        answer(client, session)
        assert refresh(client, session)["phase"] == "stage_transition"


def test_explicit_unknown_is_not_followed_by_pressure_even_if_model_requests_it(tmp_path):
    with TestClient(
        create_app(database_path=tmp_path / "unknown-policy.sqlite3", evaluator=UnclearEvaluator())
    ) as client:
        ready(client)
        session = start(client)
        report = run_remaining(
            client, session, technical_text="这道题我不会，具体不知道其中的工作机制和边界。"
        )
        assert report["completeness"] == "complete"
        assert len(report["groups"]) == len(session["plan"]["questions"])
        assert all(g["followups"] == 0 for g in report["groups"])
        assert all(
            g["feedback"]["knowledge_gap"]
            for g in report["groups"]
            if g["question"]["stage"] == "technical"
        )


@pytest.mark.parametrize(
    "score,quote,phase",
    [
        (None, "", "stage_transition"),
        (None, "不存在的引文", "evaluation_failed"),
        (75, "", "evaluation_failed"),
    ],
)
def test_unassessed_dimensions_can_omit_quotes_but_scores_and_nonempty_quotes_stay_checked(
    tmp_path, score, quote, phase
):
    class NullableQuote(InterviewEvaluator):
        def evaluate(self, *, question, answer):
            result = super().evaluate(question=question, answer=answer)
            if question["stage"] == "technical":
                result.dimensions[0].score = score
                result.dimensions[0].answer_quote = quote
                result.evidence_status = "insufficient"
            return result

    with TestClient(
        create_app(database_path=tmp_path / "nullable.sqlite3", evaluator=NullableQuote())
    ) as client:
        ready(client)
        session = start(client)
        for _ in range(2):
            answer(client, session)
            session = next_group(client, refresh(client, session))
        assert session["current_turn"]["stage"] == "technical"
        answer(client, session)
        assert refresh(client, session)["phase"] == phase


@pytest.mark.parametrize(
    "text",
    [
        "我不会这样做，我会优化一下。",
        "我不会这么设计，我会换一下。",
        "不能把‘我不会回答’当作工具执行结果，后面再优化。",
    ],
)
def test_negative_design_intentions_and_quoted_unknowns_do_not_override_vague_evidence(
    tmp_path, text
):
    with TestClient(
        create_app(
            database_path=tmp_path / "not-a-declaration.sqlite3", evaluator=UnclearEvaluator()
        )
    ) as client:
        ready(client)
        session = start(client, max_main_questions=3)
        report = run_remaining(client, session, technical_text=text)
        technical = [g for g in report["groups"] if g["question"]["stage"] == "technical"]
        assert all(not g["feedback"].get("knowledge_gap") for g in technical)
        key = session["plan"]["selected_topics"][0]
        assert (
            next(c["status"] for c in report["coverage"] if c["competency_id"] == key)
            == "insufficient"
        )


@pytest.mark.parametrize("violation", ["quote", "question", "competency"])
def test_ungrounded_or_wrong_topic_proposals_cannot_become_followups(tmp_path, violation):
    class InvalidFollowup(UnclearEvaluator):
        def evaluate(self, *, question, answer):
            result = super().evaluate(question=question, answer=answer)
            if result.followup:
                if violation == "quote":
                    result.followup.answer_quote = "回答中不存在的引文"
                elif violation == "question":
                    result.followup.question_code = "OTHER-QUESTION"
                else:
                    result.followup.competency_id = "other_topic"
            return result

    with TestClient(
        create_app(database_path=tmp_path / "invalid-followup.sqlite3", evaluator=InvalidFollowup())
    ) as client:
        ready(client)
        report = run_remaining(client, start(client, max_main_questions=3))
        assert len(report["turns"]) == 3
        assert report["completeness"] == "partial"
