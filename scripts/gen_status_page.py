"""Dataset status page generation — validation status saved as JSON+markdown.

Usage:
    uv run python scripts/gen_status_page.py [--check]

Outputs:
- ``docs/status/latest.json`` — machine-readable snapshot (generation
  time, spec verification dates, per-provider counts)
- ``docs/status.md`` — mkdocs page (human summary)

Feeds the monthly rollup (#384 6.5) and the smoke report.

Nothing here reads the calendar. "Recent" is measured back from the newest
``last_verified`` in the specs, not from today: a today-relative count changed the
rendered page on 2026-12-09 with no content change, and ``--check`` would have failed
every pull request from that day (#620).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from kpubdata.core.spec import discover_specs
from kpubdata.core.status import SUPPORTED_DATA_LEVELS

REPO_ROOT = Path(__file__).resolve().parents[1]
STATUS_DIR = REPO_ROOT / "docs" / "status"
STATUS_JSON = STATUS_DIR / "latest.json"
STATUS_MD = REPO_ROOT / "docs" / "status.md"
SUPPORTED = REPO_ROOT / "SUPPORTED_DATA.md"


def _catalogue_counts() -> dict[str, int]:
    """Dataset count per provider from catalogue."""
    counts: dict[str, int] = {}
    for catalogue in sorted((REPO_ROOT / "src/kpubdata/providers").glob("*/catalogue.json")):
        counts[catalogue.parent.name] = len(json.loads(catalogue.read_text(encoding="utf-8")))
    return counts


#: Levels that count as passing against the real API.
PASSING_LEVELS = frozenset({"live_verified", "production"})

#: Levels whose fixture and contract tests pass (live-verified ones included).
FIXTURE_PASSING_VERIFICATIONS = frozenset({"fixture_verified", "live_verified", "production"})


def _family_pass_rates() -> dict[str, dict[str, object]]:
    """Pass rate per dataset family (provider), from ``dataset_metadata.json`` (#899).

    ``pass_rate`` is the share of the family's datasets that pass against the real API
    (``live_verified`` or ``production``); ``fixture_pass_rate`` is the share whose
    fixture and contract tests pass, whatever else holds for them. Both are percentages
    rounded to one decimal, so a report quotes the number rather than recomputing it.
    """
    metadata = json.loads(
        (REPO_ROOT / "src/kpubdata/dataset_metadata.json").read_text(encoding="utf-8")
    )
    families: dict[str, dict[str, object]] = {}
    for dataset_id, entry in sorted(metadata.items()):
        family = dataset_id.split(".", 1)[0]
        row = families.setdefault(
            family, {"total": 0, "live_passing": 0, "fixture_passing": 0, "levels": {}}
        )
        level = entry["level"]
        row["total"] += 1  # type: ignore[operator]
        if level in PASSING_LEVELS:
            row["live_passing"] += 1  # type: ignore[operator]
        if entry.get("verification") in FIXTURE_PASSING_VERIFICATIONS:
            row["fixture_passing"] += 1  # type: ignore[operator]
        levels: dict[str, int] = row["levels"]  # type: ignore[assignment]
        levels[level] = levels.get(level, 0) + 1
    for row in families.values():
        total = row["total"]
        row["pass_rate"] = round(row["live_passing"] / total * 100, 1)  # type: ignore[operator]
        row["fixture_pass_rate"] = round(row["fixture_passing"] / total * 100, 1)  # type: ignore[operator]
    return families


#: Days a verification counts as recent.
RECENT_DAYS = 90


def _supported_summary() -> dict[str, int]:
    """SUPPORTED_DATA level column summary.

    The levels come from ``SUPPORTED_DATA_LEVELS`` (ADR 0005). A hand-kept subset here
    dropped every level added after it was written, so the totals stopped matching
    the table (#620).
    """
    counts: dict[str, int] = {}
    content = SUPPORTED.read_text(encoding="utf-8") if SUPPORTED.is_file() else ""
    known = set(SUPPORTED_DATA_LEVELS)
    for line in content.splitlines():
        m = re.match(r"\| ([^|]+) \| ([^|]+) \|", line)
        if m and m.group(1).strip() in known:
            status = m.group(1).strip()
            counts[status] = counts.get(status, 0) + 1
    return counts


def build_status() -> dict[str, object]:
    """Create current status snapshot."""
    specs = discover_specs()
    verified = [s for s in specs if s.last_verified]
    reference = max((s.last_verified for s in verified if s.last_verified), default=None)
    cutoff = reference - timedelta(days=RECENT_DAYS) if reference else None
    fresh = [s for s in verified if cutoff and s.last_verified and s.last_verified >= cutoff]
    return {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
        "spec_datasets": {
            "total": len(specs),
            "verified": len(verified),
            "verified_recent_90d": len(fresh),
            "recent_reference": reference.isoformat() if reference else None,
            "per_dataset": {
                s.id: {
                    "last_verified": s.last_verified.isoformat() if s.last_verified else None,
                    "status": s.status,
                }
                for s in sorted(specs, key=lambda x: x.id)
            },
        },
        "catalogue_datasets": _catalogue_counts(),
        "supported_rows": _supported_summary(),
        "family_pass_rate": _family_pass_rates(),
    }


def _family_rows(families: dict[str, dict[str, object]]) -> list[str]:
    """Table rows of the per-family pass rate, with an all-families total row."""
    rows = [
        f"| {name} | {f['total']} | {f['live_passing']} | {f['pass_rate']}% | "
        f"{f['fixture_passing']} | {f['fixture_pass_rate']}% |"
        for name, f in families.items()
    ]
    total = sum(f["total"] for f in families.values())  # type: ignore[misc]
    live = sum(f["live_passing"] for f in families.values())  # type: ignore[misc]
    fixture = sum(f["fixture_passing"] for f in families.values())  # type: ignore[misc]
    rows.append(
        f"| **전체** | {total} | {live} | {round(live / total * 100, 1)}% | "
        f"{fixture} | {round(fixture / total * 100, 1)}% |"
    )
    return rows


def render_md(status: dict[str, object]) -> str:
    """Convert status JSON to human-readable markdown."""
    spec = status["spec_datasets"]  # type: ignore[index]
    catalogue = status["catalogue_datasets"]  # type: ignore[index]
    supported = status["supported_rows"]  # type: ignore[index]
    lines = [
        "# 데이터셋 검증 상태",
        "",
        f"> 생성: `{status['generated_at']}` — `scripts/gen_status_page.py` (직접 편집 금지)",
        "",
        "## 요약",
        "",
        f"- spec 데이터셋: **{spec['total']}종** "
        f"(검증 {spec['verified']}종, 최신 검증일 {spec['recent_reference'] or '-'} "
        f"기준 90일 이내 {spec['verified_recent_90d']}종)",
        f"- catalogue 데이터셋: {sum(catalogue.values())}종"  # type: ignore[call-arg]
        + " ("
        + ", ".join(f"{p} {n}" for p, n in sorted(catalogue.items()))
        + ")",  # type: ignore[union-attr]
        f"- SUPPORTED_DATA 행 분포: {supported} "  # type: ignore[str-format]
        f"(합계 {sum(supported.values())})",  # type: ignore[union-attr]
        "",
        "## 계열별 통과율",
        "",
        "통과율 = 실API 검증을 통과한 데이터셋 / 계열 전체. 테스트 통과율 = fixture·contract "
        "테스트를 통과한 데이터셋 / 계열 전체. 원천은 `src/kpubdata/dataset_metadata.json`.",
        "",
        "| 계열 | 전체 | 실API 통과 | 통과율 | 테스트 통과 | 테스트 통과율 |",
        "|---|---|---|---|---|---|",
        *_family_rows(status["family_pass_rate"]),  # type: ignore[arg-type]
        "",
        "## spec 데이터셋별 최종 검증일",
        "",
        "| 데이터셋 | 최종 검증 | 상태 |",
        "|---|---|---|",
    ]
    per = spec["per_dataset"]  # type: ignore[index]
    for dataset_id, info in per.items():  # type: ignore[union-attr]
        info_dict = info  # type: ignore[assignment]
        lines.append(
            f"| `{dataset_id}` | {info_dict['last_verified'] or '-'} | {info_dict['status']} |"
        )
    lines.append("")
    return "\n".join(lines)


def _without_timestamp(text: str) -> str:
    """Drop the generation timestamp so drift means a content change.

    Both outputs carry when they were rendered. Including that in the comparison makes
    every check fail, which is indistinguishable from a real drift and gets the check
    switched off — as it was.
    """
    text = re.sub(r"`\d{4}-\d{2}-\d{2}T[\d:+\-.]+`", "`<generated_at>`", text)
    return re.sub(r'"generated_at":\s*"[^"]*"', '"generated_at": "<generated_at>"', text)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point — generate or check drift."""
    parser = argparse.ArgumentParser(description="데이터셋 상태 페이지 생성")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    status = build_status()
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    json_text = json.dumps(status, ensure_ascii=False, indent=2) + "\n"
    md_text = render_md(status)
    if args.check:
        # The generation timestamp changes on every run, so comparing it would make the
        # check fail for ever — which is why this was never wired into CI, and why
        # docs/status.md drifted to claiming 22 spec datasets while the README said 23
        # (#498). What matters is whether the content moved, not when it was rendered.
        json_ok = STATUS_JSON.is_file() and _without_timestamp(
            STATUS_JSON.read_text(encoding="utf-8")
        ) == _without_timestamp(json_text)
        md_ok = STATUS_MD.is_file() and _without_timestamp(
            STATUS_MD.read_text(encoding="utf-8")
        ) == _without_timestamp(md_text)
        if not (json_ok and md_ok):
            print("드리프트: 상태 페이지가 최신이 아님 — 재생성 후 커밋하세요.")
            return 1
        print("일치: 상태 페이지 최신")
        return 0
    STATUS_JSON.write_text(json_text, encoding="utf-8")
    STATUS_MD.write_text(md_text, encoding="utf-8")
    print(f"생성: {STATUS_JSON.relative_to(REPO_ROOT)}, {STATUS_MD.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
