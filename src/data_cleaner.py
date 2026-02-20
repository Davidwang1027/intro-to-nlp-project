import re
from pathlib import Path


INPUT_ROOT = Path("data/apollo-journals")
OUTPUT_ROOT = Path("data/apollo-journals-clean")

# Keep lines that begin with a mission timestamp, then remove
# the timestamp + speaker prefix and retain only dialogue text.
DIALOGUE_LINE_RE = re.compile(r"^\s*\d{1,3}:\d{2}:\d{2}\s+[^:]+:\s*(.+?)\s*$")
BRACKET_ANNOTATION_RE = re.compile(r"\[[^\]]*\]")
WHITESPACE_RE = re.compile(r"\s+")
SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,.;:!?])")
LEADING_PUNCT_RE = re.compile(r"^[,.;:!?-]+\s*")
ALNUM_RE = re.compile(r"[A-Za-z0-9]")


def clean_file(input_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cleaned_lines = []
    with input_path.open("r", encoding="utf-8", errors="ignore") as infile:
        for line in infile:
            match = DIALOGUE_LINE_RE.match(line)
            if match:
                text = BRACKET_ANNOTATION_RE.sub("", match.group(1))
                text = WHITESPACE_RE.sub(" ", text).strip()
                text = SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)
                text = LEADING_PUNCT_RE.sub("", text)
                if text and ALNUM_RE.search(text):
                    cleaned_lines.append(text)

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
