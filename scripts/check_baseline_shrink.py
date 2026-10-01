#!/usr/bin/env python3
"""The agent may shrink the insecure-http baseline, and nothing else (#738).

The Build Dataset workflow stages ``scripts/insecure_http_baseline.txt``
next to the spec and the fixtures, so an https conversion lands with its
baseline line removed. Staging alone would also carry an addition or a
swap: the ratchet in ``verify_spec.py`` compares entry counts against a
frozen constant, so once one conversion lands (22 entries) a new
plain-http spec could ride the baseline through the agent's own pull
request. This script is the gate the #765 review asked for — the diff
may delete exactly the converting dataset's line, add nothing, and only
when that spec's ``base_url`` now says ``https://``.

The spec is read with a regex on purpose, the same choice
``check_required_checks.py`` documents: this runs on a bare runner with
nothing installed beyond Python itself.

Usage:
    python scripts/check_baseline_shrink.py --dataset datago.apt_trade

Exits 0 when the baseline is untouched, or shrinks by exactly that
dataset with its spec on https; exits 1 with ``::error::`` lines
otherwise.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_BASE_URL = re.compile(r"^\s*base_url:\s*(\S+)", re.MULTILINE)


def _changed_lines(diff_text: str, marker: str) -> list[str]:
    """Diff lines starting with `marker`, minus the marker and the file headers."""
    header = marker * 3
    return [
        line[1:]
        for line in diff_text.splitlines()
        if line.startswith(marker) and not line.startswith(header)
    ]


def evaluate(diff_text: str, dataset: str, base_url: str | None) -> list[str]:
    """Problems with this baseline diff; an empty list means it may stage.

    An empty diff passes whatever the spec says — a dataset-add run does
    not touch the baseline at all. Any non-empty diff must be exactly one
    deletion, the converting dataset's own line, earned by that spec's
    base_url now starting with ``https://``.
    """
    added = _changed_lines(diff_text, "+")
    removed = _changed_lines(diff_text, "-")
    if not added and not removed:
        return []
    problems: list[str] = []
    if added:
        problems.append(f"baseline 에 추가된 줄이 있다 ({', '.join(added)}) — 축소만 허용한다")
    if removed != [dataset]:
        problems.append(
            f"지워진 줄은 정확히 {dataset} 한 줄이어야 한다 — 실제 지워진 것: "
            f"{', '.join(removed) if removed else '없음'}"
        )
    if base_url is None:
        problems.append(f"{dataset} 의 스펙을 찾을 수 없다 — base_url 확인 대상이 없다")
    elif not base_url.startswith("https://"):
        problems.append(f"{dataset} 의 base_url 이 아직 https 가 아니다: {base_url}")
    return problems


def _spec_base_url(root: Path, dataset: str) -> str | None:
    """The spec's base_url, or None when the spec (or the line) is missing."""
    provider, _, key = dataset.partition(".")
    spec = root / "src" / "kpubdata" / "specs" / provider / f"{key}.yaml"
    if not spec.is_file():
        return None
    match = _BASE_URL.search(spec.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def main(argv: list[str] | None = None) -> int:
    """Check the working-tree baseline diff once. Returns 0 when it may stage."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dataset", required=True, help="the dataset this run converts")
    parser.add_argument("--baseline", default="scripts/insecure_http_baseline.txt")
    parser.add_argument("--root", default=str(REPO_ROOT))
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    diff = subprocess.run(
        ["git", "diff", "HEAD", "--", args.baseline],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    problems = evaluate(diff, args.dataset, _spec_base_url(root, args.dataset))
    if not problems:
        print(f"baseline 축소 검사 통과 — {args.dataset}")
        return 0
    for problem in problems:
        print(f"::error::{problem}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
