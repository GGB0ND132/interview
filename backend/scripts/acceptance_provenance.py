"""Real TCP/model/document acceptance; use a new isolated database, never the demo database."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import httpx

from interview_backend.model import HttpEvaluator, ModelSettings

PACK = "pack_agent_basics_sample"
SOURCE = "https://www.anthropic.com/research/building-effective-agents"
EXCERPT = (
    "During execution, it's crucial for the agents to gain “ground truth” from the "
    "environment at each step (such as tool call results or code execution) to assess its progress."
)
ANSWER = (
    "模型选择需要的工具，程序实际执行工具并返回结果，Agent 根据工具返回的实际结果判断后续动作、纠错。"
    "完成目标时结束；失败无法恢复或达到最大迭代次数时停止并如实说明，避免循环失控。"
)


def data(response: httpx.Response) -> dict[str, Any]:
    response.raise_for_status()
    return dict(response.json()["data"])


@contextmanager
def server(database: Path) -> Iterator[httpx.Client]:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "interview_backend.api:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        env={**os.environ, "DATABASE_PATH": str(database)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=20) as client:
            deadline = time.monotonic() + 20
            while True:
                try:
                    data(client.get("/health/live"))
                    break
                except httpx.HTTPError:
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError("Acceptance server did not start") from None
                    time.sleep(0.1)
            yield client
    finally:
        process.terminate()
        process.wait(timeout=15)


def start(client: httpx.Client) -> dict[str, Any]:
    session = data(
        client.post(
            "/api/v1/sessions",
            json={
                "pack_id": PACK,
                "config": {"focus_competency_ids": ["agent_tool_calling"]},
            },
        )
    )
    return data(
        client.post(
            f"/api/v1/sessions/{session['session_id']}/start", json={"expected_revision": 0}
        )
    )


def evaluate(
    client: httpx.Client,
    session: dict[str, Any],
    answer: str,
    retries: list[dict[str, str]],
) -> dict[str, Any]:
    path = f"/api/v1/sessions/{session['session_id']}"
    accepted = data(
        client.post(
            f"{path}/answers",
            json={
                "turn_id": session["current_turn"]["id"],
                "expected_revision": session["revision"],
                "client_submission_id": "live-provenance",
                "disposition": "answered",
                "answer_text": answer,
            },
        )
    )
    job_id = accepted["submission"]["job_id"]
    deadline = time.monotonic() + 180
    retry_count = 0
    while True:
        job = data(client.get(f"/api/v1/jobs/{job_id}"))
        if job["status"] == "failed" and job["error"]["retryable"] and retry_count < 2:
            retries.append({"session_id": session["session_id"], "code": job["error"]["code"]})
            print(f"model_retry: {job['error']['code']}", flush=True)
            saved = data(client.get(path))
            data(client.post(f"{path}/retry", json={"expected_revision": saved["revision"]}))
            retry_count += 1
        elif job["status"] in {"failed", "succeeded"}:
            break
        if time.monotonic() > deadline:
            raise TimeoutError("Model acceptance timed out")
        time.sleep(0.2)
    assert job["status"] == "succeeded", job
    return data(client.get(path))["submissions"][0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert not args.database.exists(), "Choose a new isolated database"
    settings = ModelSettings.from_env()
    assert settings.api_key, "A real server-side model key is required"
    results: dict[str, Any] = {"model": settings.model, "source": SOURCE}
    retries: list[dict[str, str]] = []
    with server(args.database.resolve()) as client:
        session = start(client)
        no_evidence = evaluate(client, session, ANSWER, retries)
        assert no_evidence["feedback"]["independent_references"] == []
        results["original_source_only"] = {
            "session_id": session["session_id"],
            "submission": no_evidence,
        }
        print("original_source_only: passed", flush=True)

        evidence = data(
            client.post(
                "/api/v1/maintenance/questions/Q-AGENT-SAMPLE-01/evidence",
                json={
                    "expected_version": 1,
                    "url": SOURCE,
                    "title": "Building effective agents",
                    "excerpt": EXCERPT,
                    "claim": "Agent 需从实际工具执行结果获取环境反馈以判断任务进度。",
                    "reviewer": "Codex source review 2026-11-12",
                },
            )
        )
        session = start(client)
        supported = evaluate(client, session, ANSWER, retries)
        assert supported["feedback"]["independent_references"][0]["excerpt"] == EXCERPT
        assert supported["feedback"]["requested_model"] == settings.model
        results["verified_citation"] = {
            "session_id": session["session_id"],
            "submission": supported,
        }
        print("verified_citation: passed", flush=True)

        # Exercise the real semantic verifier too; API failure paths are deterministic in pytest.
        verifier = HttpEvaluator(settings)
        verdict = verifier.verify_claim(evidence["claim"], [evidence])
        assert verdict.supported and verdict.reference_id == evidence["id"]
        assert verdict.quote.strip() and verdict.quote in EXCERPT
        unrelated = verifier.verify_claim(
            "LangGraph 9.9.9 保证支付工具在重放时恰好执行一次。", [evidence]
        )
        assert not unrelated.supported
        results["live_support_check"] = {
            "supported": verdict.model_dump(),
            "unrelated": unrelated.model_dump(),
        }
        print("live_support_check: passed", flush=True)

        disputed_session = start(client)
        disputed = evaluate(
            client,
            disputed_session,
            ANSWER
            + "另外，LangGraph 9.9.9 的 checkpointer 保证外部支付工具恰好执行一次，官方取消了重放限制。这个版本结论与题库范围不同。",
            retries,
        )
        checks = disputed["feedback"]["technical_checks"]
        assert checks and any(c["status"] != "verified" for c in checks)
        assert disputed["feedback"]["dimensions"][0]["score"] is None
        results["unverified_dispute"] = {
            "session_id": disputed_session["session_id"],
            "submission": disputed,
        }
        print("unverified_dispute: passed", flush=True)

        report = data(
            client.post(
                f"/api/v1/sessions/{disputed_session['session_id']}/reports",
                json={
                    "turn_id": disputed_session["current_turn"]["id"],
                    "category": "score",
                    "explanation": "请复核 LangGraph 版本争议；不应在无证据时确定判断。",
                },
            )
        )
        assert report["answer_version"] == 1 and report["status"] == "open"
        handled = data(
            client.post(
                f"/api/v1/maintenance/reports/{report['id']}",
                json={
                    "expected_status": "open",
                    "status": "in_review",
                    "note": "已收到版本争议，等待资料核对。",
                },
            )
        )
        results["user_report"] = handled
        print("user_report: passed", flush=True)
    with server(args.database.resolve()) as client:
        for case in ("original_source_only", "verified_citation", "unverified_dispute"):
            saved = data(client.get(f"/api/v1/sessions/{results[case]['session_id']}"))
            assert saved["submissions"][0] == results[case]["submission"]
        assert data(client.get(f"/api/v1/maintenance/reports/{handled['id']}")) == handled
    results["restart_equal"] = True
    results["model_retries"] = retries
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("restart_equal: passed", flush=True)


if __name__ == "__main__":
    main()
