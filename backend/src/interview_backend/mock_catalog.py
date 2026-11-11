"""Explicit publication of original, reusable interview stage questions."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .store import Store

COMMON_PACK = "pack_agent_interview_common"
STAGES = {
    "introduction": "开场",
    "experience_or_scenario": "经历或假设情境",
    "technical_topics": "技术",
    "behavioral": "行为",
    "candidate_questions": "候选人反问",
}

# These are expression/decision rubrics, not claims that a personal history is true.
CATALOG = [
    (
        "introduction",
        "请简要介绍你的学习背景、Agent 相关准备，以及希望在这个岗位解决什么问题。",
        "按背景、相关准备、岗位目标组织表达。只评价相关性、结构与具体性，不核实个人经历真实性。",
        ["说明背景与岗位关联", "用具体学习或实践支撑", "表达清晰有重点"],
    ),
    (
        "experience",
        "请介绍一个你参与的项目：目标是什么、你具体负责什么、作过什么技术决策、如何验证结果？没有项目经历请明确说明。",
        "围绕候选人自述观察职责、决策理由、验证与反思；个人成果未经外部核实，不评价真实性。无经历转假设情境，不编造项目。",
        ["区分个人贡献与团队成果", "解释决策与验证", "不把自述当已核实事实"],
    ),
    (
        "scenario",
        "【假设情境，并非你的真实经历】团队要做一个能查询订单的 Agent。你会怎样拆分模型、工具和程序的职责，并验证失败时能安全停止？",
        "模型选择工具并理解结果，程序校验参数与权限、执行工具并返回真实结果；设置执行与重试上限，用成功、超时、无权限等案例验证。允许合理替代方案，不要求宣称实际做过。",
        ["明确模型与执行程序边界", "设置权限及失败停止机制", "说明验证案例与取舍"],
    ),
    (
        "behavioral",
        "请用一次学习、协作或生活中的困难说明：你采取了什么具体行动、结果怎样、下次会如何改进？不要求工作经历。",
        "观察情境、具体行动、结果与反思是否可理解；不核验经历真实性，不因没有工作经历扣分。",
        ["说明具体困难", "解释个人行动", "给出结果和可执行反思"],
    ),
    (
        "candidate_questions",
        "面试即将结束，你想向团队了解什么？也可以明确选择没有问题。",
        "评价与岗位或本场交流的相关性、问题清晰度与思考深度；不评价技术准确性或答案覆盖率。没有问题表示环节完成但无提问质量分数。",
        ["问题与岗位或交流相关", "表达清楚且有思考", "无反问不按技术答错计分"],
    ),
]


def publish_common(store: Store) -> dict[str, Any]:
    with store.connect(write=True) as db:
        db.execute(
            "INSERT OR IGNORE INTO role_packs VALUES (?,?,'published',1)",
            (COMMON_PACK, "Agent 通用面试环节"),
        )
        for stage, prompt, answer, rubric in CATALOG:
            question = {
                "code": f"Q-INTERVIEW-{stage.upper()}",
                "version": 1,
                "content_version": "07.1",
                "difficulty": "easy",
                "stage": stage,
                "topic": STAGES.get(stage, "经历或假设情境"),
                "competency_id": stage,
                "prompt": prompt,
                "answer": answer,
                "rubric": rubric,
                "status": "published",
                "interview_suitable": True,
                "answer_origin": "project_original",
                "answer_refs": [],
                "source": {
                    "kind": "project_original",
                    "path": "backend/src/interview_backend/mock_catalog.py",
                    "revision": "07.1",
                },
            }
            # Repeating publication never re-enables a disabled question.
            db.execute(
                "INSERT OR IGNORE INTO questions VALUES (?,?,?,'easy','published',?)",
                (question["code"], 1, COMMON_PACK, json.dumps(question, ensure_ascii=False)),
            )
        return {"pack_id": COMMON_PACK, "available_count": len(common_questions(db))}


def common_questions(db: sqlite3.Connection) -> list[dict[str, Any]]:
    return Store.published_questions(db, COMMON_PACK)
