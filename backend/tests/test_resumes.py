import json
from io import BytesIO
from zipfile import ZipFile

import httpx
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from test_mock_interview import InterviewEvaluator, answer, next_group, ready, refresh

from interview_backend.api import create_app
from interview_backend.contracts import Followup
from interview_backend.model import ModelSettings


def data(response):
    assert response.is_success, response.text
    return response.json()["data"]


def docx_bytes():
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>教育背景</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>杭州电子科技大学</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>项目经历</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>订单 Agent：负责工具参数校验和失败重试。</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>技能清单</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>Python</w:t></w:r></w:p></w:body></w:document>",
        )
    return output.getvalue()


def test_docx_preview_confirmation_and_restart_preserve_source_locations(tmp_path):
    database = tmp_path / "resume.sqlite3"
    with TestClient(create_app(database_path=database)) as client:
        preview = data(
            client.post(
                "/api/v1/resumes",
                files={
                    "file": (
                        "resume.docx",
                        docx_bytes(),
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                },
            )
        )
        assert preview["status"] == "needs_confirmation"
        assert preview["source_type"] == "docx"
        assert preview["blocks"][3]["text"] == "订单 Agent：负责工具参数校验和失败重试。"
        fragment = preview["project_fragments"][0]
        assert fragment["text"] == "订单 Agent：负责工具参数校验和失败重试。"
        assert fragment["source"]["paragraph"] == 4
        assert preview["confirmed"] is None
        confirmed = data(
            client.post(
                f"/api/v1/resumes/{preview['resume_id']}/confirm",
                json={
                    "expected_revision": 0,
                    "fragment_ids": [fragment["id"]],
                    "no_project_experience": False,
                },
            )
        )
        assert confirmed["revision"] == 1
        assert confirmed["confirmed"]["evidence_kind"] == "candidate_statement"
        assert confirmed["confirmed"]["externally_verified"] is False
        assert confirmed["confirmed"]["projects"] == [fragment]
    with TestClient(create_app(database_path=database)) as client:
        assert data(client.get(f"/api/v1/resumes/{preview['resume_id']}")) == confirmed


def pdf_bytes(*, scanned=False, encrypted=False):
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
                        ),
                    }
                )
            }
        )
        stream = DecodedStreamObject()
        stream.set_data(
            b"BT /F1 12 Tf 14 TL 50 700 Td (Projects) Tj T* (Order Agent: I implemented tool validation.) Tj ET"
        )
        page[NameObject("/Contents")] = stream
    if encrypted:
        writer.encrypt("private")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_pdf_extracts_page_and_line_locations_and_paste_is_a_separate_preview(tmp_path):
    with TestClient(create_app(database_path=tmp_path / "pdf.sqlite3")) as client:
        preview = data(
            client.post(
                "/api/v1/resumes", files={"file": ("resume.pdf", pdf_bytes(), "application/pdf")}
            )
        )
        assert preview["status"] == "needs_confirmation"
        fragment = preview["project_fragments"][0]
        assert fragment["text"] == "Order Agent: I implemented tool validation."
        assert fragment["source"] == {"page": 1, "line": 2}
        pasted = data(
            client.post(
                "/api/v1/resumes/text",
                json={"text": "我在订单 Agent 项目负责参数校验。\n用无权限案例验证。"},
            )
        )
        assert pasted["source_type"] == "pasted_text"
        assert len(pasted["project_fragments"]) == 2
        assert pasted["blocks"][0]["source"] == {"line": 1}
        assert pasted["confirmed"] is None


@pytest.mark.parametrize(
    "content", [b"%PDF-broken", pdf_bytes(scanned=True), pdf_bytes(encrypted=True), b"not a pdf"]
)
def test_parse_failure_explains_paste_fallback_and_allows_no_project_confirmation(
    tmp_path, content
):
    with TestClient(create_app(database_path=tmp_path / "failure.sqlite3")) as client:
        preview = data(client.post("/api/v1/resumes", files={"file": ("resume.pdf", content)}))
        assert preview["status"] == "parse_failed"
        assert preview["project_fragments"] == []
        assert "粘贴" in preview["error"]["message"]
        confirmed = data(
            client.post(
                f"/api/v1/resumes/{preview['resume_id']}/confirm",
                json={
                    "expected_revision": 0,
                    "fragment_ids": [],
                    "no_project_experience": True,
                },
            )
        )
        assert confirmed["confirmed"]["no_project_experience"] is True


@pytest.mark.parametrize(
    "filename,content,status",
    [
        ("resume.txt", b"text", 415),
        ("resume.docx", b"X" * (5 * 1024 * 1024 + 1), 413),
    ],
)
def test_upload_checks_filename_format_and_file_size(tmp_path, filename, content, status):
    with TestClient(create_app(database_path=tmp_path / "limits.sqlite3")) as client:
        response = client.post("/api/v1/resumes", files={"file": (filename, content)})
        assert response.status_code == status
        assert response.json()["error"]["code"].startswith("RESUME_")


def test_confirmation_rejects_invented_or_ambiguous_selections_and_stale_revisions(tmp_path):
    with TestClient(create_app(database_path=tmp_path / "confirm.sqlite3")) as client:
        preview = data(
            client.post("/api/v1/resumes", files={"file": ("resume.docx", docx_bytes())})
        )
        url = f"/api/v1/resumes/{preview['resume_id']}/confirm"
        assert client.post(url, json={"expected_revision": 0}).status_code == 422
        assert (
            client.post(
                url, json={"expected_revision": 0, "fragment_ids": ["invented"]}
            ).status_code
            == 400
        )
        assert (
            client.post(
                url,
                json={
                    "expected_revision": 0,
                    "fragment_ids": [preview["project_fragments"][0]["id"]],
                    "no_project_experience": True,
                },
            ).status_code
            == 422
        )
        assert (
            client.post(
                url, json={"expected_revision": 99, "no_project_experience": True}
            ).status_code
            == 409
        )
        confirmed = data(
            client.post(url, json={"expected_revision": 0, "no_project_experience": True})
        )
        assert (
            client.post(
                url, json={"expected_revision": 0, "no_project_experience": True}
            ).status_code
            == 409
        )
        assert data(client.get(f"/api/v1/resumes/{preview['resume_id']}")) == confirmed


def draft_with_resume(client, resume_id, **config):
    return client.post(
        "/api/v1/sessions",
        json={
            "pack_id": "pack_agent_basics_mianstack",
            "config": {
                "mode": "mock_interview",
                "resume_id": resume_id,
                **config,
            },
        },
    )


def test_unconfirmed_resume_cannot_influence_a_session(tmp_path):
    with TestClient(create_app(database_path=tmp_path / "unconfirmed.sqlite3")) as client:
        ready(client)
        preview = data(
            client.post("/api/v1/resumes/text", json={"text": "候选人声称项目节省 90% 成本。"})
        )
        rejected = draft_with_resume(client, preview["resume_id"])
        assert rejected.status_code == 400
        assert rejected.json()["error"]["code"] == "RESUME_NOT_CONFIRMED"
        assert draft_with_resume(client, "missing").status_code == 404


def confirmed_paste(client, *, no_project=False):
    preview = data(
        client.post(
            "/api/v1/resumes/text",
            json={"text": "订单 Agent：由我负责工具参数校验。\n不选中的项目不得发送给模型。"},
        )
    )
    return data(
        client.post(
            f"/api/v1/resumes/{preview['resume_id']}/confirm",
            json={
                "expected_revision": 0,
                "no_project_experience": no_project,
                "fragment_ids": [] if no_project else [preview["project_fragments"][0]["id"]],
            },
        )
    )


def test_confirmed_resume_is_used_as_candidate_context_for_published_questions_and_followups(
    tmp_path,
):
    calls = []

    def provider(request):
        body = json.loads(request.content)
        context = json.loads(body["messages"][1]["content"])
        calls.append((body["messages"][0]["content"], context))
        result = InterviewEvaluator().evaluate(question={}, answer=context["user_answer"])
        if context["interview_context"]["stage"] == "technical":
            result.evidence_status = "insufficient"
            result.followup = Followup(
                text="结合你自述的工具校验，说明当前回答中的验证步骤？",
                answer_quote=context["user_answer"][:5],
                purpose="澄清本题回答",
                question_code=context["code"],
                competency_id=context["interview_context"]["current_turn"]["competency_id"],
            )
        return httpx.Response(
            200, json={"choices": [{"message": {"content": result.model_dump_json()}}]}
        )

    database = tmp_path / "context.sqlite3"
    with TestClient(
        create_app(
            database_path=database,
            model_settings=ModelSettings(api_key="test"),
            model_transport=httpx.MockTransport(provider),
        )
    ) as client:
        ready(client)
        confirmed = confirmed_paste(client)
        draft = data(draft_with_resume(client, confirmed["resume_id"]))
        assert draft["resume_context"] == confirmed["confirmed"]
        session = data(
            client.post(
                f"/api/v1/sessions/{draft['session_id']}/start", json={"expected_revision": 0}
            )
        )
        answer(client, session, "skipped")
        session = next_group(client, refresh(client, session))
        assert session["current_turn"]["stage"] == "experience"
        assert "订单 Agent" in session["current_turn"]["text"]
        assert "候选人自述" in session["current_turn"]["text"]
        answer(client, session)
        experience_context = calls[-1][1]["interview_context"]["resume_context"]
        assert experience_context == confirmed["confirmed"]
        assert "不选中的项目" not in str(calls)
        session = next_group(client, refresh(client, session))
        assert session["current_turn"]["stage"] == "technical"
        original_question = session["current_turn"]["question_code"]
        answer(client, session)
        system, technical = calls[-1]
        assert technical["interview_context"]["resume_context"] == experience_context
        assert "候选人陈述" in system and "技术答案" in system
        assert "订单 Agent" not in technical["answer"]
        session = refresh(client, session)
        assert session["current_turn"]["kind"] == "followup"
        assert session["current_turn"]["question_code"] == original_question
        saved = session
    with TestClient(create_app(database_path=database)) as client:
        assert data(client.get(f"/api/v1/sessions/{saved['session_id']}")) == saved
        ended = data(
            client.post(
                f"/api/v1/sessions/{saved['session_id']}/finish",
                json={"expected_revision": saved["revision"]},
            )
        )
        report = data(client.get(f"/api/v1/sessions/{ended['session_id']}/report"))
        assert report["resume_context"] == experience_context


def test_confirming_no_project_overrides_experience_mode_with_a_labeled_scenario(tmp_path):
    with TestClient(create_app(database_path=tmp_path / "none.sqlite3")) as client:
        ready(client)
        confirmed = confirmed_paste(client, no_project=True)
        draft = data(
            draft_with_resume(client, confirmed["resume_id"], experience_mode="experience")
        )
        session = data(
            client.post(
                f"/api/v1/sessions/{draft['session_id']}/start", json={"expected_revision": 0}
            )
        )
        answer(client, session, "skipped")
        session = next_group(client, refresh(client, session))
        assert session["current_turn"]["stage"] == "scenario"
        assert "假设情境" in session["current_turn"]["text"]
        assert session["resume_context"]["projects"] == []
        assert (
            next(x for x in session["coverage"] if x["competency_id"] == "experience")["status"]
            == "not_applicable"
        )


@pytest.mark.parametrize(
    "xml",
    [
        b"<broken",
        b'<!DOCTYPE x [<!ENTITY x "expanded">]><x>&x;</x>',
        b'<?xml version="1.0" encoding="unknown-resume-encoding"?><x/>',
    ],
)
def test_invalid_docx_xml_returns_a_failure_preview(tmp_path, xml):
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", xml)
    with TestClient(create_app(database_path=tmp_path / "xml.sqlite3")) as client:
        preview = data(
            client.post("/api/v1/resumes", files={"file": ("resume.docx", output.getvalue())})
        )
        assert preview["status"] == "parse_failed"
        assert preview["blocks"] == []


def test_model_cannot_quote_a_resume_excerpt_as_the_candidates_answer(tmp_path):
    class ResumeQuotingEvaluator(InterviewEvaluator):
        def evaluate(self, *, question, answer):
            result = super().evaluate(question=question, answer=answer)
            for dimension in result.dimensions:
                dimension.answer_quote = "订单 Agent：由我负责工具参数校验。"
            return result

    with TestClient(
        create_app(database_path=tmp_path / "quote.sqlite3", evaluator=ResumeQuotingEvaluator())
    ) as client:
        ready(client)
        confirmed = confirmed_paste(client)
        draft = data(draft_with_resume(client, confirmed["resume_id"]))
        session = data(
            client.post(
                f"/api/v1/sessions/{draft['session_id']}/start", json={"expected_revision": 0}
            )
        )
        answer(client, session, "skipped")
        session = next_group(client, refresh(client, session))
        answer(client, session, text="我的回答没有提供具体实现。")
        failed = refresh(client, session)
        assert failed["phase"] == "evaluation_failed"
        assert failed["submissions"][-1]["answer_text"] == "我的回答没有提供具体实现。"
        assert failed["submissions"][-1]["error"]["code"] == "MODEL_OUTPUT_INVALID"


def test_withdrawing_project_experience_removes_resume_context_from_subsequent_questions(tmp_path):
    with TestClient(create_app(database_path=tmp_path / "withdraw.sqlite3")) as client:
        ready(client)
        confirmed = confirmed_paste(client)
        draft = data(draft_with_resume(client, confirmed["resume_id"]))
        session = data(
            client.post(
                f"/api/v1/sessions/{draft['session_id']}/start", json={"expected_revision": 0}
            )
        )
        answer(client, session, "skipped")
        session = next_group(client, refresh(client, session))
        answer(client, session, "no_experience")
        session = next_group(client, refresh(client, session))
        assert session["current_turn"]["stage"] == "scenario"
        assert session["resume_context"]["no_project_experience"] is True
        assert session["resume_context"]["projects"] == []
        # Original confirmation is retained for provenance, the session records the override.
        assert (
            data(client.get(f"/api/v1/resumes/{confirmed['resume_id']}"))["confirmed"]
            == confirmed["confirmed"]
        )
