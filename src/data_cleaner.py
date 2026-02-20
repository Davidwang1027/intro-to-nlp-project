import re
from pathlib import Path


INPUT_ROOT = Path("data/apollo-journals")
OUTPUT_ROOT = Path("data/apollo-journals-clean")

# Match lines that begin with a mission timestamp + speaker.
TIMESTAMP_SPEAKER_RE = re.compile(r"^\s*\d{1,3}:\d{2}:\d{2}\s+[^:]+:\s*(.*)$")
NON_DIALOGUE_LINE_RE = re.compile(
    r"^\s*(Public Affairs Officer\s*-|Comm break\.|Long comm break\.|Very long comm break\.)",
    re.IGNORECASE,
)
SENTENCE_END_RE = re.compile(r"[.?!][\"')\]]?\s*$")
BRACKET_ANNOTATION_RE = re.compile(r"\[[^\]]*\]")
WHITESPACE_RE = re.compile(r"\s+")
SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,.;:!?])")
LEADING_PUNCT_RE = re.compile(r"^[,.;:!?-]+\s*")
ALNUM_RE = re.compile(r"[A-Za-z0-9]")


def normalize_text(text: str) -> str:
    text = BRACKET_ANNOTATION_RE.sub("", text)
    text = WHITESPACE_RE.sub(" ", text).strip()
    text = SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)
    text = LEADING_PUNCT_RE.sub("", text)
    return text


def clean_file(input_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cleaned_lines = []
    with input_path.open("r", encoding="utf-8", errors="ignore") as infile:
        lines = infile.readlines()

    i = 0
    while i < len(lines):
        match = TIMESTAMP_SPEAKER_RE.match(lines[i])
        if not match:
            i += 1
            continue

        text = match.group(1).strip()
        if not text:
            j = i + 1
            continuation_parts = []
            while j < len(lines):
                candidate = lines[j].strip()
                if not candidate:
                    j += 1
                    continue
                if TIMESTAMP_SPEAKER_RE.match(lines[j]):
                    break
                if NON_DIALOGUE_LINE_RE.match(candidate):
                    break

                normalized_candidate = normalize_text(candidate)
                if normalized_candidate and ALNUM_RE.search(normalized_candidate):
                    continuation_parts.append(normalized_candidate)
                    if SENTENCE_END_RE.search(candidate):
                        break

                j += 1

            if continuation_parts:
                text = " ".join(continuation_parts)
                i = j

        text = normalize_text(text)
        if text and ALNUM_RE.search(text):
            cleaned_lines.append(text)

        i += 1

    if len(cleaned_lines) == 0:
        return
    with output_path.open("w", encoding="utf-8") as outfile:
        outfile.write("\n".join(cleaned_lines))
        if cleaned_lines:
            outfile.write("\n")


def main() -> None:
    for input_path in INPUT_ROOT.rglob("*.txt"):
        relative_path = input_path.relative_to(INPUT_ROOT)
        output_path = OUTPUT_ROOT / relative_path
        clean_file(input_path, output_path)


if __name__ == "__main__":
    main()
