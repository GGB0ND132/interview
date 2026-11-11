from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"] = "1.0"


class SelectionCriteria(BaseModel):
    model_config = ConfigDict(extra="forbid")
    difficulty: Literal["easy", "medium", "hard"] = "easy"
    language: Literal["zh-CN"] = "zh-CN"
    question_types: list[Literal["technical"]] = Field(default=["technical"], min_length=1)
    focus_competency_ids: list[str] = Field(default_factory=list)


class QuestionSelection(SelectionCriteria):
    max_followups_per_question: Literal[0] = 0
    feedback_timing: Literal["after_question_group"] = "after_question_group"


class Config(QuestionSelection):
    mode: Literal["question_practice"] = "question_practice"


class AvailabilityConfig(SelectionCriteria):
    mode: Literal["question_practice", "mock_interview"] = "question_practice"
    max_followups_per_question: int = Field(default=0, ge=0, le=2, strict=True)
    feedback_timing: Literal["after_question_group", "after_session"] = "after_question_group"
    experience_mode: Literal["experience", "scenario"] = "scenario"
    max_main_questions: int = Field(default=12, ge=1, le=12, strict=True)


class MockConfig(SelectionCriteria):
    mode: Literal["mock_interview"]
    max_followups_per_question: int = Field(default=2, ge=0, le=2, strict=True)
    feedback_timing: Literal["after_session"] = "after_session"
    experience_mode: Literal["experience", "scenario"] = "scenario"
    max_main_questions: int = Field(default=12, ge=1, le=12, strict=True)


class CreateSession(RequestModel):
    pack_id: str
    config: Config | MockConfig = Field(default_factory=Config)


class RevisionRequest(RequestModel):
    expected_revision: int = Field(ge=0, strict=True)


class SubmitAnswer(RevisionRequest):
    turn_id: str
    client_submission_id: str = Field(min_length=1, max_length=100)
    disposition: Literal["answered", "blank_answer", "skipped", "no_experience", "no_questions"]
    answer_text: str = ""

    @field_validator("answer_text")
    @classmethod
    def answer_length(cls, value: str) -> str:
        if len(value.strip()) > 5000:
            raise ValueError("answer_text must contain at most 5000 characters")
        return value

    @model_validator(mode="after")
    def consistent_disposition(self) -> SubmitAnswer:
        if self.disposition == "answered" and not self.answer_text.strip():
            raise ValueError("Use blank_answer for a blank submission")
        if self.disposition != "answered" and self.answer_text != "":
            raise ValueError("blank_answer and skipped require answer_text='' ")
        return self


class Dimension(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Literal["accuracy", "completeness", "relevance", "structure", "specificity"]
    score: int | None = Field(ge=0, le=100, strict=True)
    reason: str = Field(min_length=1, max_length=2000)
    answer_quote: str = Field(max_length=5000)


class Followup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=500)
    answer_quote: str = Field(min_length=1, max_length=500)
    purpose: str = Field(min_length=1, max_length=500)
    question_code: str = Field(min_length=1, max_length=100)
    competency_id: str = Field(min_length=1, max_length=100)


class ModelEvaluation(BaseModel):
    # A provider-supplied overall_score is deliberately ignored.
    model_config = ConfigDict(extra="ignore")
    dimensions: list[Dimension] = Field(min_length=5, max_length=5)
    strengths: list[str] = Field(min_length=1, max_length=10)
    improvements: list[str] = Field(min_length=1, max_length=10)
    evidence_status: Literal["observed", "insufficient"] | None = None
    evidence_reason: str = Field(default="", max_length=2000)
    followup: Followup | None = None

    @model_validator(mode="after")
    def unique_dimensions(self) -> ModelEvaluation:
        if {item.name for item in self.dimensions} != set(WEIGHTS):
            raise ValueError("Exactly one of each scoring dimension is required")
        return self


WEIGHTS = {"accuracy": 35, "completeness": 25, "relevance": 15, "structure": 15, "specificity": 10}
RUBRIC_VERSION = "technical_v1"


def feedback(
    evaluation: ModelEvaluation, answer: str, *, weights: dict[str, int] | None = None
) -> dict[str, Any]:
    evaluation = ModelEvaluation.model_validate(evaluation.model_dump())
    scoring_weights = WEIGHTS if weights is None else weights
    for item in evaluation.dimensions:
        if item.name in scoring_weights and (
            not item.answer_quote.strip() or item.answer_quote not in answer
        ):
            raise ValueError("Model quoted text that is absent from the saved answer")
    applicable_weight = sum(scoring_weights.values())
    assessed_weight = sum(
        scoring_weights.get(item.name, 0)
        for item in evaluation.dimensions
        if item.score is not None
    )
    weighted_sum = sum(
        item.score * scoring_weights.get(item.name, 0)
        for item in evaluation.dimensions
        if item.score is not None
    )
    return {
        **evaluation.model_dump(),
        "overall_score": round(weighted_sum / assessed_weight) if assessed_weight else None,
        "assessment_coverage": assessed_weight / applicable_weight,
        "assessment_status": "complete"
        if assessed_weight == applicable_weight
        else "partial"
        if assessed_weight
        else "insufficient",
        "rubric_version": RUBRIC_VERSION,
        "limitations": ["部分维度未评估"] if assessed_weight < applicable_weight else [],
    }
