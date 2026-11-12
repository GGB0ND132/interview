from __future__ import annotations

from typing import Any
from uuid import uuid4

from .contracts import CheckedClaim, ModelEvaluation
from .errors import PracticeError
from .model import ClaimVerifier, ModelError
from .provenance import Evidence, timestamp


def abstain(evaluation: ModelEvaluation, checks: list[CheckedClaim]) -> ModelEvaluation:
    unresolved = [c for c in checks if c.status != "verified"]
    if not unresolved:
        return evaluation
    affected = {name for c in unresolved for name in c.affected_dimensions}
    # A technical dispute always makes technical accuracy and completeness uncertain.
    affected.update({"accuracy", "completeness"})
    dimensions = [
        d.model_copy(
            update={
                "score": None,
                "reason": "存在答案范围外或版本争议，缺少直接资料证据，暂不判断。",
            }
        )
        if d.name in affected
        else d.model_copy(
            update={"reason": "仅按已保存回答的表达评价此维度；争议技术结论暂不判断。"}
        )
        for d in evaluation.dimensions
    ]
    return evaluation.model_copy(
        update={
            "dimensions": dimensions,
            "strengths": ["已保留实际回答及可评估维度。"],
            "improvements": ["争议技术结论尚无直接证据，请提交疑问供维护者复核。"],
        }
    )


def resolve_checks(
    evaluation: ModelEvaluation,
    question: dict[str, Any],
    evidence: Evidence,
    verifier: ClaimVerifier,
) -> tuple[list[CheckedClaim], list[dict[str, Any]]]:
    checks: list[CheckedClaim] = []
    used: dict[str, dict[str, Any]] = {}
    for check in evaluation.technical_checks:
        outcome: dict[str, Any] = {
            **check.model_dump(),
            "status": "insufficient_evidence",
            "error_code": None,
            "attempt_id": str(uuid4()),
            "checked_at": timestamp(),
        }
        candidates = evidence.search(check.query, question["code"], question["version"])
        outcome["candidate_ids"] = [r["id"] for r in candidates]
        try:
            available = []
            failures = []
            for reference in candidates:
                try:
                    document = evidence.fetch(reference["url"])
                    if reference["excerpt"] not in document:
                        raise PracticeError("EVIDENCE_QUOTE_MISMATCH", "资料片段已变化", 400)
                    available.append(reference)
                except PracticeError as exc:
                    failures.append({"reference_id": reference["id"], "code": exc.code})
            outcome["source_failures"] = failures
            if available:
                verdict = verifier.verify_claim(check.claim, available)
                if verdict.supported:
                    selected = next((r for r in available if r["id"] == verdict.reference_id), None)
                    if (
                        selected is None
                        or not verdict.quote.strip()
                        or verdict.quote not in selected["excerpt"]
                    ):
                        raise ModelError("支持引文无法匹配保存资料", "EVIDENCE_CHECK_INVALID")
                    outcome.update(
                        status="verified", reference_id=selected["id"], support_quote=verdict.quote
                    )
                    used[selected["id"]] = selected
            if outcome["status"] != "verified" and failures:
                outcome.update(status="retrieval_failed", error_code=failures[0]["code"])
        except ModelError as exc:
            outcome.update(status="retrieval_failed", error_code=exc.code)
        checks.append(CheckedClaim.model_validate(outcome))
    return checks, list(used.values())
