from argparse import ArgumentParser
from pathlib import Path


def iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file():
            yield path


def normalize_sentence(line: str) -> str:
    # Strip surrounding whitespace and collapse repeated inner whitespace.
    return " ".join(line.strip().split())


def build_dataset(input_dirs: list[Path], output_path: Path) -> tuple[int, int]:
    seen = set()
    unique_sentences = []
    total_sentences = 0

    for input_dir in input_dirs:
        if not input_dir.exists():
            continue

        for file_path in iter_files(input_dir):
            with file_path.open("r", encoding="utf-8", errors="ignore") as infile:
                for raw_line in infile:
                    sentence = normalize_sentence(raw_line)
                    if not sentence:
                        continue

                    total_sentences += 1
                    if sentence in seen:
                        continue

                    seen.add(sentence)
                    unique_sentences.append(sentence)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as outfile:
        outfile.write("\n".join(unique_sentences))
        if unique_sentences:
            outfile.write("\n")

    return total_sentences, len(unique_sentences)


def parse_args():
    parser = ArgumentParser(
        description="Aggregate cleaned mission text and remove duplicate sentences."
    )
    parser.add_argument(
        "--input",
        nargs="+",
        type=Path,
        default=[Path("data/apollo-journals-clean"), Path("data/missions-clean")],
        help="One or more input directories to scan recursively.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/training_dataset.txt"),
        help="Output file path for deduplicated training text.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    total_sentences, unique_sentences = build_dataset(args.input, args.output)
    print(f"Output: {args.output}")
    print(f"Total sentences read: {total_sentences}")
    print(f"Unique sentences written: {unique_sentences}")
    print(f"Duplicates removed: {total_sentences - unique_sentences}")


if __name__ == "__main__":
    main()
