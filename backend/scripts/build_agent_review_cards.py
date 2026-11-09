"""Generate human-review cards, leaving conclusions and reviewer identities blank."""

import json
from pathlib import Path

from interview_backend.topic_pack import load_questions, review_template


def main() -> None:
    root = Path(__file__).parents[2]
    target = root / "docs/content-baseline/agent-topics-06"
    target.mkdir(parents=True, exist_ok=True)
    reviews = review_template()
    review_path = target / "human-reviews.json"
    if review_path.exists():
        # Never erase a human's work when regenerating display cards.
        reviews = json.loads(review_path.read_text(encoding="utf-8"))
    else:
        review_path.write_text(
            json.dumps(reviews, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    questions = {q["code"]: q for q in load_questions()}
    cards = [
        "# 06 人工抽查卡片",
        "",
        "本文件由候选题生成，不是人工审核结论。请在 human-reviews.json 记录真实核查。",
        "每主题优先选补答题；GUI 只有一题，不能满足两道不同题的门槛。",
        "答案与评分点均需检查；项目经历题接受诚实的未使用回答，不能要求虚构经历。",
        "独立资料须由审核人打开核对，编辑阅读清单不能代替核查材料。",
    ]
    for sample in reviews["samples"]:
        question = questions[sample["code"]]
        cards.extend(
            [
                "",
                f"## {question['code']} · {question['topic']}",
                "",
                question["prompt"],
                "",
                f"答案来源：{question['answer_origin']}；内容版本：{question['content_version']}",
                f"原题：{question['source']['url']}",
                f"当前内容 SHA-256：`{sample['candidate_sha256']}`",
                "",
                "### 参考答案",
                "",
                question["answer"],
                "",
                "### 本项目评分点",
                "",
                *[f"- {point}" for point in question["rubric"]],
                "",
                "核查记录：未填写。请记录资料定位、版本、核对片段、发现和批准/要求修改结论。",
            ]
        )
    (target / "review-cards.md").write_text("\n".join(cards) + "\n", encoding="utf-8")
    print(f"Prepared {len(reviews['samples'])} review cards; no approvals generated")


if __name__ == "__main__":
    main()
