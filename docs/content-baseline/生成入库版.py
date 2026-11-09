"""Build one-paragraph Markdown import copies from the reviewed source notes."""

from pathlib import Path


ROOT = Path(__file__).parent
SOURCE = ROOT / "知识资料"
DESTINATION = ROOT / "知识资料_入库版"


def flatten_markdown(source: str) -> str:
    parts = []
    for raw_line in source.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("# ") or line.startswith("## "):
            line = line.lstrip("# ").strip() + "。"
        parts.append(line)
    return " ".join(parts) + "\n"


def main() -> None:
    DESTINATION.mkdir(exist_ok=True)
    for path in sorted(SOURCE.glob("KB-*.md")):
        output = DESTINATION / path.name
        output.write_text(flatten_markdown(path.read_text(encoding="utf-8")), encoding="utf-8")


if __name__ == "__main__":
    main()
