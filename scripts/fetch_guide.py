"""Guide document cache — saves data.go.kr dataset pages as text.

Usage:
    uv run python scripts/fetch_guide.py \
        --url "https://www.data.go.kr/data/15001241/openapi.do" --id datago.hospital_info

Output: ``docs/sources/{id}/guide.txt`` (+ an ``url`` file). Agents read this
cache first instead of browsing (step 1 of the AGENTS.md dataset-add
procedure).

Honest limitation: data.go.kr detail pages rely heavily on dynamic
rendering, so a static fetch captures mostly the list and basic info.
When insufficient, consult the original URL directly. On failure it does
not exit 0 silently — it reports status (never hides a missing cache).
"""

from __future__ import annotations

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCES_DIR = REPO_ROOT / "docs" / "sources"


class _TextExtractor(HTMLParser):
    """Collect text from HTML, excluding scripts/styles."""

    _SKIP = {"script", "style", "noscript"}

    def __init__(self) -> None:
        super().__init__()
        self.chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Count skip tag entry depth."""
        if tag in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        """Exit skip tag."""
        if tag in self._SKIP and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        """Collect text nodes (when not skipping)."""
        if self._skip_depth == 0 and data.strip():
            self.chunks.append(data.strip())


def extract_text(html: str) -> str:
    """Clean HTML to line-based text."""
    parser = _TextExtractor()
    parser.feed(html)
    lines = [line for line in parser.chunks if len(line) > 1]
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def fetch_guide(url: str, dataset_id: str, *, sources_dir: Path = SOURCES_DIR) -> Path | None:
    """Fetch guide page and save as text cache."""
    out_dir = sources_dir / dataset_id
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        response = httpx.get(
            url,
            timeout=30,
            follow_redirects=True,
            headers={"User-Agent": "kpubdata-guide-cache/1.0"},
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"실패: {url} — {exc}")
        return None
    text = extract_text(response.text)
    out_path = out_dir / "guide.txt"
    out_path.write_text(f"source: {url}\n\n{text}\n", encoding="utf-8")
    (out_dir / "url").write_text(url, encoding="utf-8")
    print(f"캐시됨: {out_path} ({len(text)}자)")
    if len(text) < 500:
        print("주의: 정적 fetch로 얻은 내용이 짧다(동적 렌더링 추정) — URL 원문 확인 필요")
    return out_path


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="data.go.kr 활용가이드 캐시")
    parser.add_argument("--url", required=True, help="데이터셋 페이지 URL")
    parser.add_argument("--id", required=True, help="데이터셋 id (예: datago.hospital_info)")
    args = parser.parse_args(argv)
    result = fetch_guide(args.url, args.id)
    return 0 if result is not None else 1


if __name__ == "__main__":
    sys.exit(main())
