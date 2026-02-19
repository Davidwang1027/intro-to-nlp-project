import re
from pathlib import Path


INPUT_ROOT = Path("data/apollo-journals")
OUTPUT_ROOT = Path("data/apollo-journals-clean")

# Keep lines that begin with a mission timestamp, then remove
# the timestamp + speaker prefix and retain only dialogue text.
DIALOGUE_LINE_RE = re.compile(r"^\s*\d{1,3}:\d{2}:\d{2}\s+[^:]+:\s*(.+?)\s*$")


def clean_file(input_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cleaned_lines = []
    with input_path.open("r", encoding="utf-8", errors="ignore") as infile:
        for line in infile:
            match = DIALOGUE_LINE_RE.match(line)
            if match:
                cleaned_lines.append(match.group(1))

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
