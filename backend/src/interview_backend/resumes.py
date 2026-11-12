"""Reviewable project excerpts; confirmation never verifies a candidate's claims."""

from __future__ import annotations

import json
import re
import sqlite3
from io import BytesIO
from pathlib import PurePath
from typing import Any, cast
from uuid import uuid4
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile, ZipFile
from zlib import error as ZlibError

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import fromstring
from pydantic import Field, model_validator
from pypdf import PdfReader
from pypdf.errors import PyPdfError

from .contracts import RequestModel, RevisionRequest
from .errors import PracticeError
from .store import Store

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_TEXT_CHARS = 50000
MAX_EXPANDED_BYTES = 20 * 1024 * 1024
NOTICE = "项目与成果仅为候选人陈述，未经外部核实，不作为技术答案或独立技术依据。"
FALLBACK = "请粘贴相关项目原文后重新预览并确认；也可确认没有相关项目经历。"
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class ResumeText(RequestModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)


class ConfirmResume(RevisionRequest):
    fragment_ids: list[str] = Field(default_factory=list, max_length=20)
    no_project_experience: bool = False

    @model_validator(mode="after")
    def selection(self) -> ConfirmResume:
        if self.no_project_experience == bool(self.fragment_ids):
            raise ValueError("Select projects or explicitly confirm no project experience")
        if len(set(self.fragment_ids)) != len(self.fragment_ids):
            raise ValueError("Duplicate fragment IDs")
        return self


def docx_blocks(content: bytes) -> list[dict[str, Any]]:
    with ZipFile(BytesIO(content)) as archive:
        entries = archive.infolist()
        if len(entries) > 2000 or sum(e.file_size for e in entries) > MAX_EXPANDED_BYTES:
            raise ValueError("DOCX expanded size exceeds limit")
        if any(e.flag_bits & 1 for e in entries):
            raise ValueError("Encrypted DOCX")
        archive.getinfo("[Content_Types].xml")
        root = fromstring(archive.read("word/document.xml"))
    if root.tag != WORD_NS + "document":
        raise ValueError("Invalid Word document")
    blocks = []
    for number, paragraph in enumerate(root.iter(WORD_NS + "p"), 1):
        text = "".join(
            node.text or "" if node.tag == WORD_NS + "t" else "\n"
            for node in paragraph.iter()
            if node.tag in {WORD_NS + "t", WORD_NS + "br", WORD_NS + "tab"}
        )
        if text.strip():
            blocks.append(
                {"id": f"paragraph-{number}", "text": text, "source": {"paragraph": number}}
            )
    return blocks


def project_fragments(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prefer a named project section; uncertain excerpts remain user-reviewable."""
    active = False
    found_section = False
    fragments = []
    for block in blocks:
        text = block["text"]
        heading = re.sub(r"[\s:：\-—#]+", "", text).casefold()
        if heading in {
            "项目经历",
            "项目经验",
            "个人项目",
            "相关项目",
            "项目实践",
            "projects",
            "projectexperience",
        }:
            active = found_section = True
            continue
        if heading in {
            "教育背景",
            "教育经历",
            "技能清单",
            "专业技能",
            "个人技能",
            "工作经历",
            "实习经历",
            "自我评价",
            "education",
            "skills",
            "experience",
        }:
            active = False
        if active:
            fragments.append({**block, "id": f"project-{block['id']}"})
    if not found_section:
        # A resume without a recognizable heading is not silently interpreted as projects.
        return []
    return fragments


def pdf_blocks(content: bytes) -> list[dict[str, Any]]:
    reader = PdfReader(BytesIO(content))
    if reader.is_encrypted:
        raise ValueError("Encrypted PDF")
    if len(reader.pages) > 30:
        raise ValueError("PDF exceeds 30 page limit")
    blocks = []
    total = 0
    for number, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        total += len(text)
        if total > MAX_TEXT_CHARS:
            raise ValueError("Extracted text exceeds limit")
        for line, value in enumerate(text.splitlines(), 1):
            if value.strip():
                blocks.append(
                    {
                        "id": f"page-{number}-line-{line}",
                        "text": value,
                        "source": {"page": number, "line": line},
                    }
                )
    return blocks


class Resumes:
    def __init__(self, store: Store):
        self.store = store

    @staticmethod
    def read(db: sqlite3.Connection, resume_id: str) -> dict[str, Any]:
        row = db.execute("SELECT payload FROM resumes WHERE id=?", (resume_id,)).fetchone()
        if row is None:
            raise PracticeError("RESUME_NOT_FOUND", "简历预览不存在", 404)
        return cast(dict[str, Any], json.loads(row[0]))

    def view(self, resume_id: str) -> dict[str, Any]:
        with self.store.connect() as db:
            return self.read(db, resume_id)

    def upload(self, filename: str, content: bytes) -> dict[str, Any]:
        suffix = PurePath(filename).suffix.lower()
        if suffix not in {".pdf", ".docx"}:
            raise PracticeError(
                "RESUME_FORMAT_UNSUPPORTED", "仅支持文字版 PDF 或 DOCX。" + FALLBACK, 415
            )
        if len(content) > MAX_UPLOAD_BYTES:
            raise PracticeError("RESUME_TOO_LARGE", "简历大小不能超过 5 MiB。" + FALLBACK, 413)
        blocks: list[dict[str, Any]] = []
        error = None
        try:
            if suffix == ".docx" and content.startswith(b"PK"):
                blocks = docx_blocks(content)
            elif suffix == ".pdf" and content.startswith(b"%PDF-"):
                blocks = pdf_blocks(content)
            else:
                raise ValueError("Content does not match the declared format")
            if not blocks:
                raise ValueError("No extractable text")
            if sum(len(b["text"]) for b in blocks) > MAX_TEXT_CHARS:
                raise ValueError("Extracted text exceeds limit")
        except (
            ValueError,
            LookupError,
            BadZipFile,
            ParseError,
            DefusedXmlException,
            PyPdfError,
            OSError,
            ZlibError,
            TypeError,
            OverflowError,
            NotImplementedError,
        ):
            blocks = []
            error = {
                "code": "RESUME_PARSE_FAILED",
                "message": "无法提取可用原文：可能是扫描件（不支持 OCR）、加密/损坏文件、格式不匹配，或超过 30 页/50000 字解析上限。"
                + FALLBACK,
            }
        return self._preview(suffix[1:], blocks, error)

    def paste(self, request: ResumeText) -> dict[str, Any]:
        if not request.text.strip():
            raise PracticeError("RESUME_TEXT_EMPTY", "请粘贴非空项目原文", 400)
        blocks = [
            {"id": f"line-{number}", "text": text, "source": {"line": number}}
            for number, text in enumerate(request.text.splitlines(), 1)
            if text.strip()
        ]
        return self._preview("pasted_text", blocks, None, pasted=True)

    def _preview(
        self,
        source_type: str,
        blocks: list[dict[str, Any]],
        error: dict[str, str] | None,
        *,
        pasted: bool = False,
    ) -> dict[str, Any]:
        fragments = (
            [{**block, "id": f"project-{block['id']}"} for block in blocks]
            if pasted
            else project_fragments(blocks)
        )
        preview = {
            "resume_id": str(uuid4()),
            "revision": 0,
            "status": "parse_failed" if error else "needs_confirmation",
            "source_type": source_type,
            "blocks": blocks,
            "project_fragments": fragments,
            "confirmed": None,
            "error": error,
            "notice": NOTICE,
            "fallback": FALLBACK,
            "warnings": []
            if fragments or error
            else ["未识别到项目章节。请粘贴相关项目原文重新预览，或明确确认没有相关项目经历。"],
        }
        with self.store.connect(write=True) as db:
            db.execute(
                "INSERT INTO resumes VALUES (?,?)",
                (preview["resume_id"], json.dumps(preview, ensure_ascii=False)),
            )
        return preview

    def confirm(self, resume_id: str, request: ConfirmResume) -> dict[str, Any]:
        with self.store.connect(write=True) as db:
            preview = self.read(db, resume_id)
            if preview["revision"] != request.expected_revision or preview["confirmed"] is not None:
                raise PracticeError("STATE_CONFLICT", "简历版本已变化或已确认；修改请创建新预览")
            fragments = {f["id"]: f for f in preview["project_fragments"]}
            if any(key not in fragments for key in request.fragment_ids):
                raise PracticeError("RESUME_FRAGMENT_INVALID", "只能确认本次预览中的项目片段", 400)
            projects = [fragments[key] for key in request.fragment_ids]
            if sum(len(p["text"]) for p in projects) > 12000:
                raise PracticeError(
                    "RESUME_CONTEXT_TOO_LARGE",
                    "确认项目片段总计不能超过 12000 字；请粘贴精简片段重新预览",
                    400,
                )
            preview.update(
                status="confirmed",
                revision=1,
                confirmed={
                    "resume_id": resume_id,
                    "source_type": preview["source_type"],
                    "revision": 1,
                    "projects": projects,
                    "no_project_experience": request.no_project_experience,
                    "evidence_kind": "candidate_statement",
                    "externally_verified": False,
                    "notice": NOTICE,
                },
            )
            db.execute(
                "UPDATE resumes SET payload=? WHERE id=?",
                (json.dumps(preview, ensure_ascii=False), resume_id),
            )
            return preview
