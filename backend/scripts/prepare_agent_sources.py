"""Rebuild the complete fixed-revision Agent basics snapshot from upstream."""

from __future__ import annotations

import io
import json
from pathlib import Path
from zipfile import ZipFile

import httpx

from interview_backend.publishing import COMMIT, TOPICS


def main() -> None:
    response = httpx.get(
        f"https://codeload.github.com/didilili/mianstack/zip/{COMMIT}",
        follow_redirects=True,
        timeout=120,
    )
    response.raise_for_status()
    sources = {}
    with ZipFile(io.BytesIO(response.content)) as archive:
        for name in sorted(archive.namelist()):
            if "/questions/Q-" not in name or not name.endswith(".md"):
                continue
            raw = archive.read(name).decode("utf-8")
            _, metadata, _ = raw.split("---", 2)
            source = json.loads(metadata)
            if source["category"] == "agent" and source["level"] == "基础":
                if source["topic"] not in TOPICS:
                    raise ValueError(f"Unmapped topic: {source['topic']}")
                sources[source["id"]] = raw
    target = Path(__file__).parents[1] / "src/interview_backend/mianstack_snapshot.json"
    target.write_text(
        json.dumps({"commit": COMMIT, "files": sources}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for topic in TOPICS:
        rows = [json.loads(raw.split("---", 2)[1]) for raw in sources.values()]
        items = [row for row in rows if row["topic"] == topic]
        print(topic, len(items))
        if topic in list(TOPICS)[6:]:
            for row in items:
                print(row["id"], row["answerStatus"], row["title"])


if __name__ == "__main__":
    main()
