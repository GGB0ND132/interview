"""TCP acceptance with synthetic resumes and the configured real model.

Use only against an isolated database: publishes 57 technical and five common questions.
"""

from __future__ import annotations

import argparse
import json
import time
from importlib.resources import files
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import httpx
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def document() -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>项目经历</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>订单 Agent：我负责工具参数校验、权限检查和失败停止机制。</w:t></w:r></w:p>"
            "</w:body></w:document>",
        )
    return output.getvalue()


def pdf(*, scanned: bool = False) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(600, 800)
    if not scanned:
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {
                        NameObject("/F1"): DictionaryObject(
                            {
                                NameObject("/Type"): NameObject("/Font"),
                                NameObject("/Subtype"): NameObject("/Type1"),
                                NameObject("/BaseFont"): NameObject("/Helvetica"),
                            }
                        )
                    }
                )
            }
        )
        stream = DecodedStreamObject()
        stream.set_data(
            b"BT /F1 12 Tf 14 TL 50 700 Td (Projects) Tj T* (Order Agent: tool validation.) Tj ET"
        )
        page[NameObject("/Contents")] = stream
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def run(client: httpx.Client) -> dict:
    def post(path: str, body: dict | None = None) -> dict:
        response = client.post(path, json=body)
        response.raise_for_status()
        return response.json()["data"]

    def get(path: str) -> dict:
        response = client.get(path)
        response.raise_for_status()
        return response.json()["data"]

    def upload(name: str, content: bytes) -> dict:
        response = client.post("/api/v1/resumes", files={"file": (name, content)})
        response.raise_for_status()
        return response.json()["data"]

    def create(resume_id: str) -> dict:
        return post(
            "/api/v1/sessions",
            {
                "pack_id": "pack_agent_basics_mianstack",
                "config": {
                    "mode": "mock_interview",
                    "resume_id": resume_id,
                    "experience_mode": "experience",
                },
            },
        )

    def action(session: dict, name: str) -> dict:
        return post(
            f"/api/v1/sessions/{session['session_id']}/{name}",
            {"expected_revision": session["revision"]},
        )

    def submit(session: dict, text: str | None) -> dict:
        post(
            f"/api/v1/sessions/{session['session_id']}/answers",
            {
                "expected_revision": session["revision"],
                "turn_id": session["current_turn"]["id"],
                "client_submission_id": session["current_turn"]["id"],
                "disposition": "answered" if text else "skipped",
                "answer_text": text or "",
            },
        )
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            session = get(f"/api/v1/sessions/{session['session_id']}")
            if session["phase"] != "evaluating":
                assert session["phase"] != "evaluation_failed", session["submissions"][-1]
                return session
            time.sleep(0.2)
        raise TimeoutError("Model evaluation did not finish")

    bundle = json.loads(
        files("interview_backend").joinpath("first_half_candidates.json").read_text("utf-8")
    )
    assert post("/api/v1/maintenance/question-publications", bundle)["accepted_count"] == 57
    assert post("/api/v1/maintenance/mock-interview-questions/publish")["available_count"] == 5

    docx_preview = upload("synthetic.docx", document())
    pdf_preview = upload("synthetic.pdf", pdf())
    assert docx_preview["project_fragments"][0]["source"] == {"paragraph": 2}
    assert pdf_preview["project_fragments"][0]["source"] == {"page": 1, "line": 2}
    rejected = client.post(
        "/api/v1/sessions",
        json={
            "pack_id": "pack_agent_basics_mianstack",
            "config": {
                "mode": "mock_interview",
                "resume_id": docx_preview["resume_id"],
            },
        },
    )
    assert rejected.status_code == 400
    assert rejected.json()["error"]["code"] == "RESUME_NOT_CONFIRMED"

    confirmed = post(
        f"/api/v1/resumes/{docx_preview['resume_id']}/confirm",
        {
            "expected_revision": 0,
            "fragment_ids": [docx_preview["project_fragments"][0]["id"]],
        },
    )
    session = action(create(confirmed["resume_id"]), "start")
    session = action(submit(session, None), "next")
    assert session["current_turn"]["stage"] == "experience"
    assert "候选人自述" in session["current_turn"]["text"]
    session = submit(
        session,
        "我在课程练习中实现了订单查询 Agent 的工具执行层。我负责参数类型与权限校验，模型只选择工具，程序执行实际查询。我用成功、无权限和超时三类用例检查行为，失败时返回明确错误并停止重试。这个练习没有真实业务指标。",
    )
    # A clarification may be proposed; it remains at the existing published question.
    if session["phase"] == "awaiting_answer":
        session = submit(session, None)
    session = action(session, "next")
    assert session["current_turn"]["stage"] == "technical"
    session = submit(
        session,
        "我会先说明本题涉及的模型与程序边界：模型理解输入并提出调用意图，程序校验工具参数、权限并执行，再把真实结果交回模型。验证时分别构造成功、超时和无权限输入；失败时返回明确错误，并用固定次数上限停止重试。我还不确定本题所有细节，不能用项目自述证明技术结论。",
    )
    session = action(session, "finish")
    report = get(f"/api/v1/sessions/{session['session_id']}/report")
    assert report["resume_context"] == confirmed["confirmed"]
    assert len(session["submissions"]) >= 3
    assert all(s["status"] == "completed" for s in session["submissions"])

    failed = upload("scan.pdf", pdf(scanned=True))
    assert failed["status"] == "parse_failed" and "粘贴" in failed["error"]["message"]
    pasted = post("/api/v1/resumes/text", {"text": "课程项目：我实现了工具调用日志。"})
    assert pasted["status"] == "needs_confirmation" and pasted["confirmed"] is None
    no_project = post(
        f"/api/v1/resumes/{failed['resume_id']}/confirm",
        {
            "expected_revision": 0,
            "no_project_experience": True,
        },
    )
    scenario = action(submit(action(create(no_project["resume_id"]), "start"), None), "next")
    assert scenario["current_turn"]["stage"] == "scenario"
    assert "假设情境" in scenario["current_turn"]["text"]
    return {
        "model_boundary": "configured real provider",
        "docx": confirmed,
        "pdf": pdf_preview,
        "failed": failed,
        "pasted": pasted,
        "no_project": no_project,
        "scenario_session": scenario,
        "session": session,
        "report": report,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8011")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-restart", action="store_true")
    args = parser.parse_args()
    with httpx.Client(base_url=args.base_url, timeout=180) as client:
        if args.verify_restart:
            saved = json.loads(args.output.read_text("utf-8"))
            # The failure preview is subsequently confirmed as no-project on the same record.
            for key in ("docx", "pdf", "pasted", "no_project"):
                response = client.get(f"/api/v1/resumes/{saved[key]['resume_id']}")
                response.raise_for_status()
                assert response.json()["data"] == saved[key]
            response = client.get(f"/api/v1/sessions/{saved['session']['session_id']}/report")
            response.raise_for_status()
            assert response.json()["data"] == saved["report"]
            print("Restart verification passed: four resume records and the report match.")
        else:
            result = run(client)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
            print("Resume TCP acceptance passed; two real model evaluations completed.")


if __name__ == "__main__":
    main()
