#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.request import Request, urlopen

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
HTML_EXTENSIONS = {"", ".html", ".htm", ".shtml", ".php", ".asp", ".aspx"}


class LiLinkExtractor(HTMLParser):
    """Extract href from <a> tags that are inside first-level <li> tags."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.li_depth = 0
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "li":
            self.li_depth += 1
            return

        if tag == "a" and self.li_depth == 1:
            attr_map = dict(attrs)
            href = attr_map.get("href")
            if href:
                self.hrefs.append(href.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "li" and self.li_depth > 0:
            self.li_depth -= 1


class PlainTextExtractor(HTMLParser):
    """Convert HTML to normalized plain text, skipping non-content tags."""

    BLOCK_TAGS = {
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "dd",
        "div",
        "dl",
        "dt",
        "figcaption",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "td",
        "th",
        "tr",
        "ul",
    }
    SKIP_TAGS = {"noscript", "picture", "script", "style", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth == 0 and tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS and self.skip_depth > 0:
            self.skip_depth -= 1
            return
        if self.skip_depth == 0 and tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth == 0:
            self.parts.append(data)

    def get_text(self) -> str:
        raw_text = "".join(self.parts)
        lines = [re.sub(r"\s+", " ", line).strip() for line in raw_text.splitlines()]
        return "\n".join(line for line in lines if line)


def read_urls(urls_file: Path) -> list[str]:
    urls: list[str] = []
    for line in urls_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


def fetch_html(url: str, timeout: float) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as response:
        body = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
    try:
        return body.decode(charset, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def normalize_link(base_url: str, href: str) -> str | None:
    href = href.strip()
    if not href:
        return None
    lowered = href.lower()
    if lowered.startswith(("javascript:", "mailto:", "tel:", "#")):
        return None

    absolute = urljoin(base_url, href)
    absolute, _ = urldefrag(absolute)
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"}:
        return None
    return absolute


def is_probably_html(url: str) -> bool:
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix in HTML_EXTENSIONS


def extract_second_layer_links(main_url: str, html: str) -> list[str]:
    parser = LiLinkExtractor()
    parser.feed(html)

    unique_links: list[str] = []
    seen: set[str] = set()
    for href in parser.hrefs:
        absolute = normalize_link(main_url, href)
        if not absolute or not is_probably_html(absolute):
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        unique_links.append(absolute)
    return unique_links


def extract_plain_text(html: str) -> str:
    parser = PlainTextExtractor()
    parser.feed(html)
    return parser.get_text()


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "page"


def mission_name_from_url(url: str) -> str:
    path_parts = [p for p in urlparse(url).path.split("/") if p]
    if len(path_parts) >= 2:
        return safe_name(path_parts[-2])
    if path_parts:
        return safe_name(Path(path_parts[-1]).stem)
    return "mission"


def build_output_path(mission_dir: Path, index: int, transcript_url: str) -> Path:
    parsed = urlparse(transcript_url)
    stem = Path(parsed.path).stem or "index"
    base = f"{index:03d}_{safe_name(stem)}"
    candidate = mission_dir / f"{base}.txt"
    serial = 2
    while candidate.exists():
        candidate = mission_dir / f"{base}_{serial}.txt"
        serial += 1
    return candidate


def scrape(
    main_urls: list[str],
    output_dir: Path,
    timeout: float,
    delay_seconds: float,
    max_links_per_main: int | None,
) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, str]] = []
    total_saved = 0

    for main_url in main_urls:
        print(f"[main] {main_url}")
        try:
            main_html = fetch_html(main_url, timeout=timeout)
        except (HTTPError, URLError, TimeoutError) as exc:
            print(f"  ! failed to fetch main page: {exc}", file=sys.stderr)
            continue

        links = extract_second_layer_links(main_url, main_html)
        if max_links_per_main is not None:
            links = links[:max_links_per_main]
        print(f"  - second-layer links found: {len(links)}")

        mission_dir = output_dir / mission_name_from_url(main_url)
        mission_dir.mkdir(parents=True, exist_ok=True)

        for idx, transcript_url in enumerate(links, start=1):
            try:
                transcript_html = fetch_html(transcript_url, timeout=timeout)
            except (HTTPError, URLError, TimeoutError) as exc:
                print(f"    ! failed: {transcript_url} ({exc})", file=sys.stderr)
                continue

            text = extract_plain_text(transcript_html)
            if not text:
                print(f"    ! empty text: {transcript_url}", file=sys.stderr)
                continue

            output_path = build_output_path(mission_dir, idx, transcript_url)
            output_path.write_text(text + "\n", encoding="utf-8")
            total_saved += 1

            manifest.append(
                {
                    "main_url": main_url,
                    "transcript_url": transcript_url,
                    "output_file": str(output_path.as_posix()),
                }
            )
            print(f"    + saved {output_path}")
            if delay_seconds > 0:
                time.sleep(delay_seconds)

    manifest_path = output_dir / "scrape_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"[done] saved {total_saved} transcript files")
    print(f"[done] manifest: {manifest_path}")
    return total_saved


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Scrape Apollo Journal transcript pages from second-layer <li> links "
            "listed on each main URL."
        )
    )
    parser.add_argument(
        "--urls-file",
        type=Path,
        default=Path("data/apollo-journals/urls.txt"),
        help="Path to a text file containing one main URL per line.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/apollo-journals"),
        help="Directory where scraped transcript text files are written.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="HTTP timeout per request in seconds.",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=0.2,
        help="Delay between transcript-page requests.",
    )
    parser.add_argument(
        "--max-links-per-main",
        type=int,
        default=None,
        help="Optional cap on number of second-layer links per main URL.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.urls_file.exists():
        print(f"URLs file not found: {args.urls_file}", file=sys.stderr)
        return 1

    main_urls = read_urls(args.urls_file)
    if not main_urls:
        print(f"No URLs found in: {args.urls_file}", file=sys.stderr)
        return 1

    scrape(
        main_urls=main_urls,
        output_dir=args.output_dir,
        timeout=args.timeout,
        delay_seconds=args.delay_seconds,
        max_links_per_main=args.max_links_per_main,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
