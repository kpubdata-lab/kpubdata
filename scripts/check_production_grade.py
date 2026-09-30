#!/usr/bin/env python3
"""Evaluate docs/production_grade.yaml's machine-checkable checks (#625, #463).

production_grade.yaml names the checks a production-grade dataset must pass,
but nothing evaluated them — a rule without a gate is a wish (VERIFICATION 3).
This script evaluates the subset a machine can check from the repository
alone, for every spec-defined dataset:

- ``source_url``: ``spec.source.url`` is set.
- ``supported_data_listed``: SUPPORTED_DATA.md carries a row for the dataset.
- ``fixture_exists``: a recorded fixture exists — any ``*.meta.json`` under
  ``tests/fixtures/<provider>/<key>/``, because the recorder names fixtures
  after the example, not always ``default`` (tour_kor_area records
  ``seoul_restaurants.meta.json``).
- ``example_script``: ``examples/<provider>/<key>.py`` exists.

The criteria describe the **verified tier**, so the tier's claims decide what
gates: a dataset whose SUPPORTED_DATA.md row claims live-API verification must
pass everything above, while an in-progress row already says the work is
unfinished and gates nothing — ocean_buoy's missing fixture is #627, not a
surprise. ``supported_data_listed`` and ``source_url`` gate for every spec:
whatever the tier, the document must name the dataset and the spec must say
where it comes from.

``fields_declared`` is reported, not gated: four verified specs
(airkorea_forecast and the three localdata permits) declare no fields yet,
and adding them changes casting, which needs a live re-record — a follow-up,
not a silent regression here.

The remaining base checks (verify_passes, example_replay, casting_consistent,
validation_clean, typed_exceptions, pagination_complete, raw_escape_hatch)
are covered by the existing pytest and ``make verify`` gates; this script
defers to them instead of duplicating them, and prints which checks it
deferred so a renamed id in the yaml is visible.

Exit status: 0 when every gating check passes, 1 otherwise, 2 when the
repository cannot be read as expected.

    $ python3 scripts/check_production_grade.py
    datasets=23 gated=22 failures=0 warnings=4 deferred=7
    PASS
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import yaml

from kpubdata.core.spec import SpecDefinition, discover_specs

REPO_ROOT = Path(__file__).resolve().parents[1]

#: SUPPORTED_DATA.md's status for a dataset that claims live-API verification
#: (#498) — the tier production_grade.yaml describes.
VERIFIED_STATUS = "지원"

_BACKTICK = re.compile(r"`([^`]+)`")


@dataclass(frozen=True)
class CheckResult:
    """One machine check for one dataset."""

    dataset_id: str
    check_id: str
    passed: bool
    detail: str


def supported_statuses(repo: Path) -> dict[tuple[str, str], str]:
    """The ``(provider, dataset_key) → row status`` map read off SUPPORTED_DATA.md.

    The document's rows carry the dataset key bare (``apt_trade``) with the
    provider in its own column, not the dotted spec id, so the map is keyed
    the way the document is written.
    """
    statuses: dict[tuple[str, str], str] = {}
    for line in (repo / "SUPPORTED_DATA.md").read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if len(cells) < 5:
            continue
        provider = _BACKTICK.search(cells[3])
        key = _BACKTICK.search(cells[4])
        if provider is None or key is None:
            continue
        statuses[(provider.group(1), key.group(1))] = cells[0]
    return statuses


def _source_url(spec: SpecDefinition, repo: Path, status: str) -> CheckResult:
    url = spec.source.url if spec.source is not None else None
    return CheckResult(spec.id, "source_url", bool(url), url or "spec.source.url is not set")


def _supported_data_listed(spec: SpecDefinition, repo: Path, status: str) -> CheckResult:
    listed = (spec.provider, spec.dataset_key) in supported_statuses(repo)
    return CheckResult(
        spec.id,
        "supported_data_listed",
        listed,
        f"{spec.provider}/{spec.dataset_key}" if listed else "no row in SUPPORTED_DATA.md",
    )


def _fixture_exists(spec: SpecDefinition, repo: Path, status: str) -> CheckResult:
    directory = repo / "tests" / "fixtures" / spec.provider / spec.dataset_key
    metas = sorted(directory.glob("*.meta.json"))
    return CheckResult(spec.id, "fixture_exists", bool(metas), ", ".join(p.name for p in metas))


def _example_script(spec: SpecDefinition, repo: Path, status: str) -> CheckResult:
    path = repo / "examples" / spec.provider / f"{spec.dataset_key}.py"
    relative = path.relative_to(repo)
    return CheckResult(spec.id, "example_script", path.is_file(), str(relative))


def _fields_declared(spec: SpecDefinition, repo: Path, status: str) -> CheckResult:
    count = len(spec.fields)
    return CheckResult(
        spec.id,
        "fields_declared",
        count > 0,
        f"{count} field(s)" if count else "spec.fields is empty — needs a live re-record",
    )


#: Checks every spec must pass, whatever its tier.
_ALWAYS: dict[str, Callable[[SpecDefinition, Path, str], CheckResult]] = {
    "source_url": _source_url,
    "supported_data_listed": _supported_data_listed,
}

#: Checks only the verified tier must pass — the row already says the rest is
#: unfinished.
_VERIFIED_ONLY: dict[str, Callable[[SpecDefinition, Path, str], CheckResult]] = {
    "fixture_exists": _fixture_exists,
    "example_script": _example_script,
}

#: Evaluated and printed, but not gating, for the reason in the module docstring.
_REPORT_ONLY: dict[str, Callable[[SpecDefinition, Path, str], CheckResult]] = {
    "fields_declared": _fields_declared,
}


def evaluate(repo: Path) -> tuple[list[CheckResult], list[CheckResult], list[str]]:
    """Run the checks for every spec dataset.

    Returns (gating results, report-only results, deferred check ids). The
    deferred ids are production_grade.yaml's base checks this script does not
    evaluate — they belong to the existing pytest / make verify gates.
    """
    document = yaml.safe_load((repo / "docs" / "production_grade.yaml").read_text(encoding="utf-8"))
    base_ids = [check.get("id") for check in document.get("base", []) if isinstance(check, dict)]
    known = set(_ALWAYS) | set(_VERIFIED_ONLY) | set(_REPORT_ONLY)
    deferred = [check_id for check_id in base_ids if check_id not in known]

    statuses = supported_statuses(repo)
    results: list[CheckResult] = []
    reports: list[CheckResult] = []
    for spec in discover_specs():
        status = statuses.get((spec.provider, spec.dataset_key), "")
        for check_id, check in _ALWAYS.items():
            if check_id in base_ids:
                results.append(check(spec, repo, status))
        if status == VERIFIED_STATUS:
            for check_id, check in _VERIFIED_ONLY.items():
                if check_id in base_ids:
                    results.append(check(spec, repo, status))
        for check_id, check in _REPORT_ONLY.items():
            if check_id in base_ids:
                reports.append(check(spec, repo, status))
    return results, reports, deferred


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo", default=str(REPO_ROOT), help="repository root (default: this one)"
    )
    args = parser.parse_args(argv)

    repo = Path(args.repo)
    try:
        results, reports, deferred = evaluate(repo)
    except (OSError, ValueError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 2

    failures = [result for result in results if not result.passed]
    for result in failures:
        print(f"FAIL {result.dataset_id} {result.check_id}: {result.detail}")
    for report in reports:
        if not report.passed:
            print(f"WARN {report.dataset_id} {report.check_id}: {report.detail}")

    datasets = len({result.dataset_id for result in results})
    gated = len(results) // max(len(_ALWAYS) + len(_VERIFIED_ONLY), 1)
    warnings = [report for report in reports if not report.passed]
    print(
        f"datasets={datasets} gated={gated} checks={len(results)} "
        f"failures={len(failures)} warnings={len(warnings)} deferred={len(deferred)}"
    )
    if deferred:
        print(f"deferred to existing gates: {', '.join(deferred)}")

    if failures:
        print("::error::production-grade checks failed — see the FAIL lines above", file=sys.stderr)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
