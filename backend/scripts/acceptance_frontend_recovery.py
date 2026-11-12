"""Isolated browser acceptance server; never calls a paid model.

Start with --outcome failure, submit in both pages, then restart the same
database with --outcome success and retry the saved answers from the UI.
The database is explicit so this cannot silently use the normal practice DB.
"""

import argparse
import json
import time
from importlib.resources import files
from pathlib import Path
from typing import Any

import uvicorn
from fastapi.testclient import TestClient

from interview_backend.api import create_app
from interview_backend.contracts import Dimension, ModelEvaluation
from interview_backend.model import ModelError


class AcceptanceEvaluator:
    def __init__(self, outcome: str):
        self.outcome = outcome

    def evaluate(self, *, question: dict[str, Any], answer: str) -> ModelEvaluation:
        time.sleep(1)
        if self.outcome == "failure":
            raise ModelError("验收模型超时，回答已保存", "MODEL_TIMEOUT")
        return ModelEvaluation(
            dimensions=[
                Dimension(name=name, score=75, reason="受控恢复验收结果", answer_quote=answer[:20])
                for name in ("accuracy", "completeness", "relevance", "structure", "specificity")
            ],
            strengths=["受控适配器已返回"],
            improvements=["本结果仅用于恢复验收，不代表模型评分质量"],
            evidence_status="observed",
            evidence_reason="受控恢复验收",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8016)
    parser.add_argument("--outcome", choices=["failure", "success"], required=True)
    args = parser.parse_args()
    app = create_app(database_path=args.database, evaluator=AcceptanceEvaluator(args.outcome))
    with TestClient(app) as client:
        bundle = json.loads(
            files("interview_backend").joinpath("first_half_candidates.json").read_text("utf-8")
        )
        published = client.post("/api/v1/maintenance/question-publications", json=bundle)
        published.raise_for_status()
        client.post("/api/v1/maintenance/mock-interview-questions/publish").raise_for_status()
    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
