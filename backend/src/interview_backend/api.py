from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

import httpx
from fastapi import BackgroundTasks, FastAPI, File, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from . import jd
from .contracts import AvailabilityConfig, CreateSession, RevisionRequest, SubmitAnswer
from .errors import PracticeError
from .mock_catalog import publish_common
from .model import Evaluator, HttpEvaluator, ModelSettings
from .practice import Practice
from .publishing import DisableQuestion, PublicationRequest, Publishing
from .resumes import MAX_UPLOAD_BYTES, ConfirmResume, Resumes, ResumeText
from .store import Store
from .topic_quality import QualityCorrection, QualityIncident, QualityResume, TopicQuality


def create_app(
    *,
    database_path: Path | None = None,
    evaluator: Evaluator | None = None,
    model_settings: ModelSettings | None = None,
    model_transport: httpx.BaseTransport | None = None,
    source_transport: httpx.BaseTransport | None = None,
) -> FastAPI:
    settings = model_settings or ModelSettings.from_env()
    service = Practice(
        Store(database_path or Path(os.getenv("DATABASE_PATH", "data/practice.sqlite3"))),
        evaluator or HttpEvaluator(settings, model_transport),
        model_name="external_adapter" if evaluator else settings.model,
    )
    app = FastAPI(title="Interview Agent — practice and question publishing API", version="0.2.0")
    publishing = Publishing(service.store, source_transport)
    quality = TopicQuality(publishing)
    resumes = Resumes(service.store)

    def response(data: Any = None, *, error: Any = None, status: int = 200) -> JSONResponse:
        return JSONResponse(
            {"schema_version": "1.0", "request_id": str(uuid4()), "data": data, "error": error},
            status_code=status,
        )

    @app.exception_handler(PracticeError)
    async def practice_error(request: Request, exc: PracticeError) -> JSONResponse:
        return response(
            error={"code": exc.code, "message": exc.message, "retryable": exc.retryable},
            status=exc.status,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Validation errors may contain user input; return field locations without echoing it.
        return response(
            error={
                "code": "VALIDATION_ERROR",
                "message": "请求格式不符合契约",
                "retryable": False,
                "details": [{"field": list(e["loc"]), "type": e["type"]} for e in exc.errors()],
            },
            status=422,
        )

    @app.get("/health/live")
    def live() -> JSONResponse:
        return response({"status": "ok"})

    @app.get("/api/v1/role-packs")
    def packs() -> JSONResponse:
        items = service.packs()
        return response({"items": items, "page": 1, "page_size": len(items), "total": len(items)})

    @app.post("/api/v1/role-packs/{pack_id}/availability")
    def availability(pack_id: str, config: AvailabilityConfig) -> JSONResponse:
        return response(service.availability(pack_id, config))

    @app.post("/api/v1/sessions")
    def create(request: CreateSession) -> JSONResponse:
        return response(service.create(request), status=201)

    @app.post("/api/v1/jd-mappings")
    def preview_jd(request: jd.AnalyzeJD) -> JSONResponse:
        return response(service.preview_jd(request), status=201)

    @app.get("/api/v1/jd-mappings/{mapping_id}")
    def get_jd(mapping_id: str) -> JSONResponse:
        with service.store.connect() as db:
            return response(jd.read(db, mapping_id))

    @app.post("/api/v1/jd-mappings/{mapping_id}/confirm")
    def confirm_jd(mapping_id: str, request: jd.ConfirmJD) -> JSONResponse:
        with service.store.connect(write=True) as db:
            return response(jd.confirm(db, mapping_id, request))

    @app.post("/api/v1/resumes")
    async def upload_resume(file: Annotated[UploadFile, File()]) -> JSONResponse:
        try:
            content = await file.read(MAX_UPLOAD_BYTES + 1)
            preview = await run_in_threadpool(resumes.upload, file.filename or "", content)
            return response(preview, status=201)
        finally:
            await file.close()

    @app.post("/api/v1/resumes/text")
    def paste_resume(request: ResumeText) -> JSONResponse:
        return response(resumes.paste(request), status=201)

    @app.get("/api/v1/resumes/{resume_id}")
    def get_resume(resume_id: str) -> JSONResponse:
        return response(resumes.view(resume_id))

    @app.post("/api/v1/resumes/{resume_id}/confirm")
    def confirm_resume(resume_id: str, request: ConfirmResume) -> JSONResponse:
        return response(resumes.confirm(resume_id, request))

    @app.post("/api/v1/maintenance/question-publications/preview")
    def preview_publication(request: PublicationRequest) -> JSONResponse:
        return response(publishing.review(request, publish=False))

    @app.post("/api/v1/maintenance/mock-interview-questions/publish")
    def publish_interview_stages() -> JSONResponse:
        return response(publish_common(service.store), status=201)

    @app.post("/api/v1/maintenance/question-publications")
    def publish_questions(request: PublicationRequest) -> JSONResponse:
        return response(publishing.review(request, publish=True), status=201)

    @app.get("/api/v1/maintenance/question-publications/{publication_id}")
    def get_publication(publication_id: str) -> JSONResponse:
        return response(publishing.publication(publication_id))

    @app.get("/api/v1/maintenance/questions/{code}")
    def get_question_versions(code: str) -> JSONResponse:
        return response(publishing.question(code))

    @app.post("/api/v1/maintenance/questions/{code}/disable")
    def disable_question(code: str, request: DisableQuestion) -> JSONResponse:
        return response(publishing.disable(code, request))

    @app.get("/api/v1/sessions")
    def history(
        page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)
    ) -> JSONResponse:
        return response(service.history(page, page_size))

    @app.get("/api/v1/maintenance/topic-quality/{competency_id}")
    def topic_quality(competency_id: str) -> JSONResponse:
        return response(quality.view(competency_id))

    @app.post("/api/v1/maintenance/topic-quality/{competency_id}/incidents")
    def topic_incident(competency_id: str, request: QualityIncident) -> JSONResponse:
        return response(quality.incident(competency_id, request))

    @app.post("/api/v1/maintenance/topic-quality/{competency_id}/corrections")
    def topic_correction(competency_id: str, request: QualityCorrection) -> JSONResponse:
        return response(quality.correct(competency_id, request))

    @app.post("/api/v1/maintenance/topic-quality/{competency_id}/resume")
    def resume_topic(competency_id: str, request: QualityResume) -> JSONResponse:
        return response(quality.resume(competency_id, request))

    @app.post("/api/v1/sessions/{session_id}/start")
    def start(session_id: str, request: RevisionRequest) -> JSONResponse:
        return response(service.start(session_id, request.expected_revision))

    @app.get("/api/v1/sessions/{session_id}")
    def get_session(session_id: str) -> JSONResponse:
        return response(service.view(session_id))

    @app.post("/api/v1/sessions/{session_id}/next")
    def next_group(session_id: str, request: RevisionRequest) -> JSONResponse:
        return response(service.advance(session_id, request.expected_revision))

    @app.post("/api/v1/sessions/{session_id}/finish")
    def finish(session_id: str, request: RevisionRequest) -> JSONResponse:
        return response(service.finish(session_id, request.expected_revision))

    @app.post("/api/v1/sessions/{session_id}/answers")
    def submit(session_id: str, request: SubmitAnswer, background: BackgroundTasks) -> JSONResponse:
        result, job_id = service.submit(session_id, request)
        if job_id:
            background.add_task(service.evaluate, job_id)
        return response(result, status=202 if result["submission"]["status"] == "saved" else 200)

    @app.post("/api/v1/sessions/{session_id}/retry")
    def retry(
        session_id: str, request: RevisionRequest, background: BackgroundTasks
    ) -> JSONResponse:
        job_id = service.retry(session_id, request.expected_revision)
        background.add_task(service.evaluate, job_id)
        return response({"job_id": job_id}, status=202)

    @app.get("/api/v1/jobs/{job_id}")
    def job(job_id: str) -> JSONResponse:
        return response(service.job(job_id))

    @app.get("/api/v1/sessions/{session_id}/report")
    def report(session_id: str) -> JSONResponse:
        return response(service.report(session_id))

    return app
