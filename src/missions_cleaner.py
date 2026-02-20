import argparse
import re
from pathlib import Path

TIMESTAMP_RE = re.compile(r"^\s*\[-?\d{2}:\d{2}:\d{2}:\d{2}\]\s*$")
META_RE = re.compile(r"^\s*_[A-Za-z0-9-]+\s*:")
SPEAKER_RE = re.compile(
    r"^([^\W\d_][\w()'/-]{0,24}(?: [\w()'/-]{1,24}){0,3}):\s*(.*)$"
)
GLOSSARY_RE = re.compile(r"\[glossary:([^\]|]+)(?:\|[^\]]*)?\]")
BRACKET_TERM_RE = re.compile(r"\[[A-Za-z0-9_-]+:([^\]|]+)(?:\|[^\]]*)?\]")
TAG_RE = re.compile(r"<(?!/?(?:sub|sup)\b)/?[^>]+>", flags=re.IGNORECASE)
SPACE_RE = re.compile(r"\s+")


def clean_text(text: str) -> str:
    """Keep dialogue words only while preserving punctuation."""
    text = GLOSSARY_RE.sub(lambda m: m.group(1).strip(), text)
    text = BRACKET_TERM_RE.sub(lambda m: m.group(1).strip(), text)
    text = TAG_RE.sub("", text)
    text = SPACE_RE.sub(" ", text)
    return text.strip()


def extract_dialogue(raw_text: str) -> list[str]:
    utterances: list[str] = []
    current_parts: list[str] = []

    for raw_line in raw_text.splitlines():
        line = raw_line.rstrip("\r\n")
        stripped = line.strip()

        if not stripped:
            if current_parts:
                utterances.append(" ".join(current_parts))
                current_parts = []
            continue

        if TIMESTAMP_RE.match(stripped):
            if current_parts:
                utterances.append(" ".join(current_parts))
                current_parts = []
            continue

        if META_RE.match(stripped):
            if current_parts:
                utterances.append(" ".join(current_parts))
                current_parts = []
            continue

        speaker_match = SPEAKER_RE.match(line)
        if speaker_match:
            if current_parts:
                utterances.append(" ".join(current_parts))
                current_parts = []

            spoken = clean_text(speaker_match.group(2))
            if spoken:
                current_parts.append(spoken)
            continue

        # Continuation of previous speaker line (line-wrapped transcript text).
        if current_parts:
            continuation = clean_text(stripped)
            if continuation:
                current_parts.append(continuation)

    if current_parts:
        utterances.append(" ".join(current_parts))

    return utterances


def read_text_with_fallback(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp1251", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def clean_missions(input_dir: Path, output_dir: Path) -> tuple[int, int]:
    files_written = 0
    utterance_count = 0

    for src_path in sorted(input_dir.rglob("*")):
        if not src_path.is_file():
            continue
        if "transcripts" not in src_path.parts:
            continue

        raw_text = read_text_with_fallback(src_path)
        utterances = extract_dialogue(raw_text)

        dst_path = output_dir / src_path.relative_to(input_dir)
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        output_text = "\n".join(utterances)
        if output_text:
            output_text += "\n"
        dst_path.write_text(output_text, encoding="utf-8")

        files_written += 1
        utterance_count += len(utterances)

    return files_written, utterance_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Clean mission transcripts by keeping dialogue only, removing timestamps/"
            "speaker names/meta lines, unwrapping bracketed glossary terms, and "
            "joining wrapped lines from the same speaker."
        )
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/missions"),
        help="Input missions root (default: data/missions)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/missions-clean"),
        help="Output root for cleaned transcripts (default: data/missions-clean)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.input_dir.exists():
        raise SystemExit(f"Input directory not found: {args.input_dir}")

    files_written, utterance_count = clean_missions(args.input_dir, args.output_dir)
    print(f"Wrote {files_written} cleaned transcript files to {args.output_dir}")
    print(f"Extracted {utterance_count} dialogue lines")


if __name__ == "__main__":
    main()
