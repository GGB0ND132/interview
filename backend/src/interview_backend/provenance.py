from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from pydantic import Field, field_validator

from .contracts import RequestModel
from .errors import PracticeError
from .store import Store


def timestamp() -> str:
    return datetime.now(UTC).isoformat()


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class DocumentText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


class EvidenceRequest(RequestModel):
    expected_version: int = Field(ge=1, strict=True)
    title: str = Field(min_length=1, max_length=300)
    url: str = Field(min_length=1, max_length=2000)
    excerpt: str = Field(min_length=20, max_length=5000)
    claim: str = Field(min_length=1, max_length=2000)
    reviewer: str = Field(min_length=1, max_length=200)

    @field_validator("title", "excerpt", "claim", "reviewer")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Must not be blank")
        return value


def public_provenance(provenance: dict[str, Any]) -> dict[str, Any]:
    result = {
        k: v for k, v in provenance.items() if k not in {"answer_origin", "answer_generation"}
    }
    if "independent_references" in result:
        result["independent_references"] = [
            r
            for r in result["independent_references"]
            if all(
                r.get(key) for key in ("id", "excerpt", "claim", "checked_at", "document_sha256")
            )
        ]
    return result


def snapshot(question: dict[str, Any]) -> dict[str, Any]:
    return {
        "question_code": question["code"],
        "question_version": question["version"],
        "answer_version": question["version"],
        "content_version": question.get("content_version"),
        "answer_origin": question["answer_origin"],
        "answer_generation": question.get("generation"),
        "source_answer_status": question["source"].get("answer_status"),
        "question_source": question["source"],
        "independent_references": [],
    }


class Evidence:
    def __init__(self, store: Store, transport: httpx.BaseTransport | None = None):
        self.store = store
        self.transport = transport
        self.allowed_hosts = set(
            os.getenv(
                "EVIDENCE_ALLOWED_HOSTS",
                "docs.python.org,www.anthropic.com,modelcontextprotocol.io,"
                "platform.openai.com,developers.openai.com,docs.langchain.com",
            ).split(",")
        )

    def fetch(self, url: str) -> str:
        try:
            parsed = urlsplit(url)
            port = parsed.port
        except ValueError as exc:
            raise PracticeError("EVIDENCE_URL_NOT_ALLOWED", "资料 URL 格式无效", 400) from exc
        if (
            parsed.scheme != "https"
            or parsed.hostname not in self.allowed_hosts
            or parsed.username
            or parsed.password
            or port not in {None, 443}
        ):
            raise PracticeError(
                "EVIDENCE_URL_NOT_ALLOWED", "资料须来自服务端允许的 HTTPS 文档域名", 400
            )
        try:
            with (
                httpx.Client(
                    transport=self.transport, timeout=10, follow_redirects=False
                ) as client,
                client.stream("GET", url) as response,
            ):
                response.raise_for_status()
                chunks = bytearray()
                for chunk in response.iter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > 2_000_000:
                        raise PracticeError("EVIDENCE_TOO_LARGE", "资料正文超过读取上限", 400)
            parser = DocumentText()
            parser.feed(chunks.decode("utf-8"))
            return normalized(" ".join(parser.parts))
        except (httpx.HTTPError, UnicodeError) as exc:
            raise PracticeError("EVIDENCE_UNAVAILABLE", "资料无法读取，未生成引用", 400) from exc

    def register(self, code: str, request: EvidenceRequest) -> dict[str, Any]:
        with self.store.connect() as db:
            current = db.execute(
                "SELECT MAX(version) FROM questions WHERE code=?", (code,)
            ).fetchone()[0]
        if current is None:
            raise PracticeError("NOT_FOUND", "题目不存在", 404)
        if current != request.expected_version:
            raise PracticeError("STATE_CONFLICT", "题目答案版本已变化")
        document = self.fetch(request.url)
        excerpt = normalized(request.excerpt)
        if excerpt not in document:
            raise PracticeError("EVIDENCE_QUOTE_MISMATCH", "支持片段不在真实资料正文中", 400)
        record = {
            "id": str(uuid4()),
            "question_code": code,
            "answer_version": current,
            "title": request.title,
            "url": request.url,
            "excerpt": excerpt,
            "claim": request.claim,
            "reviewer": request.reviewer,
            "checked_at": timestamp(),
            "document_sha256": hashlib.sha256(document.encode()).hexdigest(),
        }
        with self.store.connect(write=True) as db:
            current = db.execute(
                "SELECT MAX(version) FROM questions WHERE code=?", (code,)
            ).fetchone()[0]
            if current != request.expected_version:
                raise PracticeError("STATE_CONFLICT", "核验期间题目答案版本已变化")
            db.execute(
                "INSERT INTO verified_evidence VALUES (?,?,?,?)",
                (
                    record["id"],
                    code,
                    current,
                    json.dumps(record, ensure_ascii=False),
                ),
            )
        return record

    def references(self, code: str, version: int) -> list[dict[str, Any]]:
        with self.store.connect() as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT payload FROM verified_evidence WHERE question_code=? AND answer_version=? ORDER BY id",
                    (code, version),
                )
            ]

    def search(self, query: str, code: str, version: int) -> list[dict[str, Any]]:
        # Search only evidence reviewed for this answer version. A later answer's
        # sources cannot silently change the meaning of an older assessment.
        terms = set(re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]{2}", query.lower()))
        ranked = []
        for reference in self.references(code, version):
            text = (reference["title"] + reference["claim"] + reference["excerpt"]).lower()
            score = sum(term in text for term in terms)
            if score:
                ranked.append((score, reference))
        ranked.sort(key=lambda item: (-item[0], item[1]["id"]))
        return [reference for _, reference in ranked[:5]]
