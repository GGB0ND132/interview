"""Render the HTTP inventory and prepare, but never approve, human sampling."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from interview_backend.first_half_release import SAMPLES
from interview_backend.topic_pack import candidate_digest

ROOT = Path(__file__).resolve().parents[2]


def cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def render(inventory: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    if not inventory["counts_match_availability"]:
        raise ValueError(
            "Inventory and live availability differ; capture a new consistent inventory"
        )
    sample_codes = {topic: list(codes) for topic, codes in SAMPLES.items()}
    second = json.loads(
        (ROOT / "docs/content-baseline/agent-topics-06/human-reviews.json").read_text("utf-8")
    )
    for sample in second["samples"]:
        sample_codes.setdefault(sample["topic"], []).append(sample["code"])
    rows = {row["code"]: row for row in inventory["questions"]}
    record = [
        "# 17：固定来源 115 题发布处理记录",
        "",
        f"HTTP 核对时间：{inventory['checked_at']}。固定来源提交：`{inventory['source_commit']}`。",
        "",
        (
            f"来源 {inventory['source_count']}；候选校验通过 {inventory['validation_passed_count']}；"
            f"候选拒绝 {inventory['rejected_count']}；当前 published {inventory['published_source_count']}；"
            f"实际可评分 {inventory['scorable_source_count']}；排除 {inventory['excluded_source_count']}。"
        ),
        "",
        (
            "实际可评分数按当前已发布版本及质量隔离/暂停状态计算，并与服务端逐主题可用数核对。"
            "候选预检的拒绝原因与当前版本的评分排除原因分别列出；候选预检通过不等于已发布或人工通过。"
            "此处沿用 05/06 已授权的 Agent 发布策略；17 的人工验收仍未通过。"
        ),
        "",
        "| 主题 | 来源数 | 实际可评分 | 排除 | 人工抽查结论 |",
        "| --- | --- | --- | --- | --- |",
    ]
    packet = [
        "# 17：人工抽查材料与待填写结论",
        "",
        f"捕获时间：{inventory['checked_at']}；来源提交：`{inventory['source_commit']}`。",
        "",
        (
            "本文件是待审材料，未执行人工审核。共 23 道不同来源题、24 个要求位；"
            "GUI 只有 Q-0897，第二位缺题。人工通过 0、人工失败 0、待审 23、来源缺位 1。"
        ),
        "",
        (
            "请逐题核对答案和评分要点，记录实际查阅资料的定位、版本、支持片段、问题与结论，"
            "再填写同目录 17-human-reviews.json 的 reviewer、reviewed_at、materials、findings、conclusion。"
            "通过填 passed，发现错误填 failed；不得直接把 Agent 结论复制成人工结论。"
            "答案内参考链接只是待核验材料，题目来源不自动成为独立评分依据。"
        ),
        "",
        (
            "发现错误后先用维护 API 报告并隔离相应版本；扩大主题抽查，完成修正/复查前不计入可评分数。"
            "题目版本或摘要改变后须重新抽查。GUI 第二位需维护者明确验收例外或修改来源范围。"
        ),
    ]
    form: dict[str, Any] = {
        "source_commit": inventory["source_commit"],
        "inventory_checked_at": inventory["checked_at"],
        "status": "pending_human_review",
        "samples": [],
        "missing_slots": [],
    }
    for topic in inventory["topics"]:
        name = topic["topic"]
        codes = sample_codes[name]
        conclusion = "待人工抽查" if len(codes) == 2 else "待人工抽查；第二位来源缺题"
        record.append(
            f"| {name} | {topic['source_count']} | {topic['scorable_source_count']} | "
            f"{topic['source_count'] - topic['scorable_source_count']} | {conclusion} |"
        )
        packet.extend(["", f"## {name}"])
        for code in codes:
            row = rows[code]
            question = row["current_candidate"]
            if question is None or candidate_digest(question) != row["current_candidate_sha256"]:
                raise ValueError(f"{code}: current published snapshot missing or digest differs")
            packet.extend(
                [
                    "",
                    f"### {code}：{question['prompt']}",
                    "",
                    (
                        f"发布版本 {row['published_version']}；内容版本 `{question['content_version']}`；"
                        f"答案身份 `{question['answer_origin']}`；实际可评分：{row['available_for_scoring']}。"
                    ),
                    "",
                    f"候选摘要：`{row['current_candidate_sha256']}`。",
                    "",
                    f"固定来源：[原题]({question['source']['url']})。",
                    "",
                    "评分要点：",
                    "",
                    *(f"- {item}" for item in question["rubric"]),
                    "",
                    "当前答案：",
                    "",
                    question["answer"],
                    "",
                    "人工结论：待审核。审核人/时间/核验资料/发现/通过或失败：待填写。",
                ]
            )
            form["samples"].append(
                {
                    "code": code,
                    "topic": name,
                    "published_version": row["published_version"],
                    "content_version": question["content_version"],
                    "candidate_sha256": row["current_candidate_sha256"],
                    "actor_type": "human",
                    "reviewer": "",
                    "reviewed_at": "",
                    "materials": [],
                    "findings": "",
                    "conclusion": "pending",
                }
            )
        if len(codes) < 2:
            packet.extend(["", "第二位：缺少不同的固定来源题，未以重复题或生成题补齐。"])
            form["missing_slots"].append({"topic": name, "slot": 2, "reason": "SOURCE_SHORTAGE"})
    record.extend(
        [
            "",
            "逐题处理见下表；空原因表示无拒绝/排除。当前内容、完整原因、版本摘要见同次 JSON 清单。",
            "",
            "| 题号 | 主题 | 来源答案状态 | 当前处理/答案身份 | 发布/内容版本 | 候选校验 | 实际可评分 | 拒绝/排除原因 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in inventory["questions"]:
        current = row["current_candidate"]
        reasons = [
            f"{reason['code']}: {reason.get('message', '')}"
            for reason in row["validation"]["reasons"]
            if not row["validation"]["accepted"]
        ] + row["exclusion_reasons"]
        if row["disabled_reason"]:
            reasons.append(row["disabled_reason"])
        values = [
            row["code"],
            row["topic"],
            row["source_answer_status"],
            f"{row['status']} / {current['answer_origin'] if current else '无当前答案'}",
            f"{row['published_version']} / {row['published_content_version']}",
            "通过" if row["validation"]["accepted"] else "拒绝",
            "是" if row["available_for_scoring"] else "否",
            "; ".join(reasons),
        ]
        record.append("| " + " | ".join(cell(value) for value in values) + " |")
    return "\n".join(record) + "\n", "\n".join(packet) + "\n", form


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    form_path = args.output_dir / "17-human-reviews.json"
    if form_path.exists():
        parser.error(
            "Human review form already exists; use a new directory to preserve reviewer work"
        )
    record, packet, form = render(json.loads(args.inventory.read_text("utf-8")))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "17-publication-record.md").write_text(record, "utf-8")
    (args.output_dir / "17-human-review-packet.md").write_text(packet, "utf-8")
    form_path.write_text(json.dumps(form, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"Recorded 115 questions; prepared {len(form['samples'])} pending human samples")


if __name__ == "__main__":
    main()
