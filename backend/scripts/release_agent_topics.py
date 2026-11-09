"""Preview by default. --publish imports only topics with complete human attestations."""

import argparse
import json
from pathlib import Path

import httpx

from interview_backend.topic_pack import TopicPack, review_template


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--reviews", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--review-template", action="store_true")
    args = parser.parse_args()
    if args.review_template:
        if args.publish:
            parser.error("--review-template cannot be combined with --publish")
        report = review_template()
    else:
        if args.publish and not args.reviews:
            parser.error("--publish requires --reviews with human review attestations")
        reviews = json.loads(args.reviews.read_text(encoding="utf-8")) if args.reviews else {}
        with httpx.Client(base_url=args.base_url, timeout=60) as client:
            report = TopicPack(client).run(reviews, publish=args.publish)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if not args.review_template:
        print(
            f"Source {report['source_count']}; prepared {report['prepared_count']}; "
            f"validated {report['validation_passed_count']}; rejected {report['rejected_count']}; "
            f"human-reviewed {report['reviewed_count']}; available {report['available_count']}"
        )
        if args.publish and not report["complete"]:
            raise SystemExit(2)


if __name__ == "__main__":
    main()
