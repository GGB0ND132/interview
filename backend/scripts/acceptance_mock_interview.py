"""Run real TCP/model interview cases. Uses declared synthetic answer fixtures."""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from typing import Any

import httpx

PACK = "pack_agent_basics_mianstack"
COMMON_ANSWERS = {
    "introduction": "我是一名计算机专业学生，最近学习 Agent 的工具调用和执行循环，做过课程中的订单查询练习。我负责接口参数校验和失败记录，希望在这个岗位学习如何把模型能力接入可靠的业务流程。",
    "scenario": "在这个假设中，我会让模型理解请求、选择允许的查询工具和组织参数。程序校验订单编号格式、用户身份和订单访问权限，执行查询后把真实结果或结构化错误返回模型，模型再解释结果。权限失败立即停止，不让模型臆造订单；网络超时只作有限重试，设置最多三轮和总超时。分别测试成功、无权限、订单不存在、超时，核对结果及日志，验证不能越权和无限循环。",
    "behavioral": "课程小组整合接口时，大家使用的字段名不一致，导致联调失败。我先整理最小请求响应样例，和同学逐项确认，再统一字段并补充失败样例。最终四个接口都能对接；复盘发现沟通太晚，下次会在编码前一起确定契约，再安排一次早期联调。",
    "candidate_questions": "团队如何验证 Agent 工具调用的失败恢复和权限边界？新人会从哪些场景入手，如何获得代码审查和反馈？",
}


def checked(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    body = response.json()
    assert body["error"] is None
    return dict(body["data"])


def run_case(client: httpx.Client, name: str, answers: dict[str, str]) -> dict[str, Any]:
    config: dict[str, Any] = {"mode": "mock_interview", "max_followups_per_question": 2}
    if name != "complete":
        config["max_main_questions"] = 3
    if name == "no_project":
        config["experience_mode"] = "experience"
    draft = checked(client.post("/api/v1/sessions", json={"pack_id": PACK, "config": config}))
    path = f"/api/v1/sessions/{draft['session_id']}"
    session = checked(client.post(f"{path}/start", json={"expected_revision": 0}))
    initial_plan = session["plan"]
    requests = []
    while session["status"] not in {"completed", "ended_early"}:
        turn = session["current_turn"]
        disposition = "answered"
        answer = COMMON_ANSWERS.get(turn["stage"], answers.get(turn["question_code"], ""))
        if turn["stage"] == "experience":
            disposition, answer = "no_experience", ""
        if name == "no_project" and turn["stage"] == "scenario":
            disposition, answer = "blank_answer", ""
        if turn["stage"] == "technical" and name != "complete":
            answer = {
                "vague": "大概会吧，就是用一下，具体说不清楚。",
                "incorrect": "我认为模型输出就是执行成功，不需要工具程序实际执行，也无需结果、权限或失败检查。",
                "unknown": f"这道题问的{turn['topic']}我不会，具体不清楚其中的工作机制和边界。",
            }[name]
        assert answer or disposition != "answered", turn
        assert client.get(f"{path}/report").status_code == 409
        request = {
            "expected_revision": session["revision"],
            "turn_id": turn["id"],
            "client_submission_id": turn["id"],
            "disposition": disposition,
            "answer_text": answer,
        }
        submitted = checked(client.post(f"{path}/answers", json=request))
        if submitted["session"]["status"] not in {"completed", "ended_early"}:
            assert (
                "score" not in submitted["submission"] and "feedback" not in submitted["submission"]
            )
        requests.append({"turn": turn, "request": request})
        deadline = time.monotonic() + 180
        retries = 0
        while True:
            session = checked(client.get(path))
            if session["phase"] == "evaluation_failed" and retries < 2:
                retries += 1
                print(f"{name}: retrying preserved answer ({retries})", flush=True)
                checked(
                    client.post(f"{path}/retry", json={"expected_revision": session["revision"]})
                )
                deadline = time.monotonic() + 180
                continue
            if session["phase"] != "evaluating":
                break
            if time.monotonic() > deadline:
                raise TimeoutError(f"{name}: model evaluation timeout")
            time.sleep(0.5)
        assert session["phase"] != "evaluation_failed", session["submissions"][-1].get("error")
        print(f"{name}: {turn['stage']}/{turn['kind']} -> {session['phase']}", flush=True)
        if session["status"] not in {"completed", "ended_early"}:
            assert all("score" not in s and "feedback" not in s for s in session["submissions"])
        if session["phase"] == "stage_transition":
            session = checked(
                client.post(f"{path}/next", json={"expected_revision": session["revision"]})
            )
    report = checked(client.get(f"{path}/report"))
    assert len(report["groups"]) <= 12
    assert all(g["followups"] <= 2 for g in report["groups"])
    if name == "complete":
        assert report["completeness"] == "complete", report["gaps"]
        assert report["stop_reason"] == "coverage_satisfied"
        assert 3 <= len(initial_plan["selected_topics"]) <= 4
    else:
        assert report["completeness"] == "partial"
        if name == "vague":
            assert any(c["status"] == "insufficient" for c in report["coverage"])
        if name == "no_project":
            coverage = {c["competency_id"]: c["status"] for c in report["coverage"]}
            assert (
                coverage["experience"] == "not_applicable"
                and coverage["scenario"] == "insufficient"
            )
        if name in {"incorrect", "unknown"}:
            technical = [g for g in report["groups"] if g["question"]["stage"] == "technical"]
            assert technical and all(g["score"] is None or g["score"] < 60 for g in technical)
    return {
        "case": name,
        "session_id": session["session_id"],
        "plan": initial_plan,
        "requests": requests,
        "report": report,
        "submissions": session["submissions"],
        "passed": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8007")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--case",
        action="append",
        choices=("complete", "vague", "incorrect", "unknown", "no_project"),
    )
    args = parser.parse_args()
    bundle = json.loads(
        files("interview_backend").joinpath("first_half_candidates.json").read_text("utf-8")
    )
    answers = {q["code"]: q["answer"] for q in bundle["questions"]}
    record: dict[str, Any] = {
        "checked_at": datetime.now(UTC).isoformat(),
        "transport": "real TCP HTTP and configured external model",
        "fixture_notice": "Synthetic scripted candidates; technical full-path answers use published reference text. This verifies orchestration, not model grading quality or a real candidate's ability.",
        "cases": [],
        "passed": False,
    }
    try:
        with httpx.Client(base_url=args.base_url, timeout=15) as client:
            cases = args.case or ["complete", "vague", "incorrect", "unknown", "no_project"]
            # Independent sessions can wait for the provider concurrently.
            with ThreadPoolExecutor(max_workers=min(5, len(cases))) as executor:
                pending = {executor.submit(run_case, client, case, answers): case for case in cases}
                for future in as_completed(pending):
                    try:
                        record["cases"].append(future.result())
                    except Exception as exc:
                        record["cases"].append(
                            {
                                "case": pending[future],
                                "passed": False,
                                "failure_type": type(exc).__name__,
                            }
                        )
                        print(f"FAIL: {pending[future]} ({type(exc).__name__})", flush=True)
        record["passed"] = all(case["passed"] for case in record["cases"])
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    assert record["passed"], (
        "Some live cases failed; inspect saved case statuses and server sessions"
    )
    print(f"PASS: {len(record['cases'])} real-model interview cases; evidence={args.output}")


if __name__ == "__main__":
    main()
