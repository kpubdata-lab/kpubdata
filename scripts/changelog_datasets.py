"""Dataset changelog aggregation for release notes.

Extracts additions/removals/verification updates between two points.

Usage:
    uv run python scripts/changelog_datasets.py --from v0.5.0 --to HEAD

Sources:
- Compares the spec directory (git ls-tree) and SUPPORTED_DATA.md at two
  points and summarizes dataset additions/removals and verification-date
  changes. Git-based only, no manual input.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class Snapshot:
    """Dataset state at a specific point in time."""

    specs: set[str]
    catalogue: set[str]
    verified: dict[str, str]  # dataset_id -> final verification date


def _git(args: list[str]) -> str:
    proc = subprocess.run(["git", *args], check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"git 오류: {proc.stderr[:200]}")
        return ""
    return proc.stdout


def _specs_at(rev: str) -> set[str]:
    """Create dataset ids from spec file list at this revision."""
    out = _git(["ls-tree", "-r", "--name-only", rev, "src/kpubdata/specs"])
    found: set[str] = set()
    for line in out.splitlines():
        m = re.match(r"src/kpubdata/specs/([a-z0-9_]+)/([a-z0-9_]+)\.yaml$", line)
        if m:
            found.add(f"{m.group(1)}.{m.group(2)}")
    return found


def _catalogue_at(rev: str) -> set[str]:
    """All catalogue dataset keys at this revision."""
    out = _git(["ls-tree", "-r", "--name-only", rev, "src/kpubdata/providers"])
    found: set[str] = set()
    for line in out.splitlines():
        m = re.match(r"src/kpubdata/providers/([a-z0-9_]+)/catalogue\.json$", line)
        if not m:
            continue
        content = _git(["show", f"{rev}:{line}"])
        try:
            import json

            entries = json.loads(content)
            found.update(f"{m.group(1)}.{e['dataset_key']}" for e in entries)
        except (json.JSONDecodeError, KeyError):
            continue
    return found


def _verified_at(rev: str) -> dict[str, str]:
    """Parse 'live API verification | date' row from SUPPORTED_DATA.md."""
    content = _git(["show", f"{rev}:SUPPORTED_DATA.md"])
    verified: dict[str, str] = {}
    for line in content.splitlines():
        m = re.match(r"\|[^|]+\| 실API 검증 \| ([0-9-]+) \|[^(]+\| `([a-z0-9_.]+)` \|", line)
        if m:
            verified[m.group(2)] = m.group(1)
    return verified


def snapshot(rev: str) -> Snapshot:
    """Create a snapshot at a revision."""
    return Snapshot(specs=_specs_at(rev), catalogue=_catalogue_at(rev), verified=_verified_at(rev))


def report(old: Snapshot, new: Snapshot) -> str:
    """Generate release notes markdown from the difference between two snapshots."""
    lines: list[str] = ["## 데이터셋 변경", ""]
    added = sorted((new.specs | new.catalogue) - (old.specs | old.catalogue))
    removed = sorted((old.specs | old.catalogue) - (new.specs | new.catalogue))
    newly_verified = sorted(k for k, v in new.verified.items() if old.verified.get(k) != v)

    if added:
        lines.append(f"### 추가 ({len(added)}종)")
        lines.extend(f"- `{d}`" for d in added)
        lines.append("")
    if removed:
        lines.append(f"### 제거 ({len(removed)}종)")
        lines.extend(f"- `{d}`" for d in removed)
        lines.append("")
    if newly_verified:
        lines.append(f"### 실API 재검증 ({len(newly_verified)}종)")
        lines.extend(f"- `{d}` → {new.verified[d]}" for d in newly_verified)
        lines.append("")
    if not (added or removed or newly_verified):
        lines.append("변경 없음")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="릴리스 노트용 데이터셋 변경 집계")
    parser.add_argument("--from", dest="from_rev", required=True)
    parser.add_argument("--to", dest="to_rev", default="HEAD")
    args = parser.parse_args(argv)
    print(report(snapshot(args.from_rev), snapshot(args.to_rev)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
