"""README dataset section auto-generation — creates summary table from specs + catalogue.

Usage:
    uv run python scripts/gen_readme_datasets.py           # generate (replaces the marker section)
    uv run python scripts/gen_readme_datasets.py --check   # drift check (exit 1)

Only the README section between `<!-- BEGIN: datasets -->` and `<!-- END: datasets -->` is replaced.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kpubdata.core.spec import discover_specs

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"
BEGIN = "<!-- BEGIN: datasets -->"
END = "<!-- END: datasets -->"


def _catalogue_counts() -> dict[str, int]:
    """Dataset count per provider from catalogue."""
    counts: dict[str, int] = {}
    providers_dir = REPO_ROOT / "src" / "kpubdata" / "providers"
    for catalogue in sorted(providers_dir.glob("*/catalogue.json")):
        provider = catalogue.parent.name
        counts[provider] = len(json.loads(catalogue.read_text(encoding="utf-8")))
    return counts


def build_section() -> str:
    """Generate dataset summary section markdown."""
    specs = discover_specs()
    spec_ids = sorted(spec.id for spec in specs)
    catalogue = _catalogue_counts()

    catalogue_summary = ", ".join(
        f"{provider} {count}" for provider, count in sorted(catalogue.items())
    )
    # The per-dataset table lives in SUPPORTED_DATA.md, not here (#546). A README is
    # read to decide whether to use the project, and 23 rows of verification dates do
    # not help that decision — the counts do, and the table is one link away.
    verified = sum(1 for spec in specs if spec.last_verified is not None)
    lines = [
        BEGIN,
        "",
        f"- **spec 기반 데이터셋** {len(spec_ids)}종 — `make verify` 4단계 기계 검증 통과"
        f" ({verified}종은 실API 검증 날짜까지 기록)",
        f"- **catalogue 기반 데이터셋** {sum(catalogue.values())}종 ({catalogue_summary})",
        "",
        "> 이 수치는 `scripts/gen_readme_datasets.py`로 생성했다 — 직접 편집 금지."
        " 데이터셋별 상태는 [SUPPORTED_DATA.md](./SUPPORTED_DATA.md).",
        END,
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point — generate or check drift."""
    parser = argparse.ArgumentParser(description="README 데이터셋 섹션 생성")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    content = README.read_text(encoding="utf-8") if README.is_file() else ""
    section = build_section()
    if BEGIN not in content or END not in content:
        print(f"오류: README에 {BEGIN}/{END} 마커가 없다 — 먼저 삽입해야 한다.")
        return 1
    current = content[content.index(BEGIN) : content.index(END) + len(END)]
    if args.check:
        if current != section:
            print("드리프트: README 데이터셋 섹션이 소스와 불일치 — 재생성 후 커밋하세요.")
            return 1
        print("일치: README 데이터셋 섹션 최신")
        return 0
    README.write_text(content.replace(current, section), encoding="utf-8")
    print("생성 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
