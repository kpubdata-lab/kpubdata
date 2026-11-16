#!/usr/bin/env python3
"""Summarise a pytest JUnit XML report for a workflow log (#516).

The summary used to live inline in ``smoke.yml`` and read the counts off the
**root** element. pytest writes ``<testsuites>`` as the root and puts the counts
on the child ``<testsuite>``, so every value came back zero -- and with
``failed == 0`` the step printed ``smoke=PASS`` on a run where a test had failed.

The job itself still failed on pytest's exit code, so no failure was hidden. What
was wrong is that the only human-readable summary was false: someone opening the
log saw "0 passed, smoke=PASS" and read it as nothing having happened. EPIC-A is
about the evidence behind "verified" being trustworthy, and this was the step
that displayed it.

It lives in a script rather than inline in YAML because nothing can test YAML.
That is why the defect survived.
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Counts:
    total: int
    failed: int
    skipped: int

    @property
    def passed(self) -> int:
        return self.total - self.failed - self.skipped

    def render(self, label: str) -> str:
        return (
            f"{label}: {self.passed} passed, {self.failed} failed, "
            f"{self.skipped} skipped (total {self.total})"
        )


class NoTestsuite(Exception):
    """The report contains no ``testsuite`` element.

    Not the same as "everything passed". A report with nothing in it means the
    run did not happen, or the file is not a pytest report -- either way the
    answer is not PASS.
    """


def _suites(root: ET.Element) -> list[ET.Element]:
    """Every ``testsuite`` in the document, whichever shape it has.

    pytest nests them under ``<testsuites>``; some tools emit a bare
    ``<testsuite>`` as the root. Both are handled, because assuming one and
    silently reading zeros from the other is the bug this replaces.
    """
    if root.tag == "testsuite":
        return [root]
    return list(root.iter("testsuite"))


def summarise(path: Path, *, validate_testcases: bool = False) -> Counts:
    """Sum the counts across every ``testsuite`` in the report.

    Raises:
        NoTestsuite: The report has no ``testsuite`` element.
    """
    suites = _suites(ET.parse(path).getroot())
    if not suites:
        raise NoTestsuite(str(path))
    total = failed = skipped = 0
    for suite in suites:
        suite_total = int(suite.attrib.get("tests", 0))
        suite_failures = int(suite.attrib.get("failures", 0))
        suite_errors = int(suite.attrib.get("errors", 0))
        suite_skipped = int(suite.attrib.get("skipped", 0))
        if validate_testcases:
            counters = (suite_total, suite_failures, suite_errors, suite_skipped)
            if any(count < 0 for count in counters) or sum(counters[1:]) > suite_total:
                raise ValueError("invalid testsuite counters")
            cases = suite.findall("testcase")
            observed = (
                len(cases),
                sum(len(case.findall("failure")) for case in cases),
                sum(len(case.findall("error")) for case in cases),
                sum(len(case.findall("skipped")) for case in cases),
            )
            if observed != counters or any(
                len(case.findall("failure") + case.findall("error") + case.findall("skipped")) > 1
                for case in cases
            ):
                raise ValueError("testcase outcomes do not match testsuite counters")
        total += suite_total
        failed += suite_failures + suite_errors
        skipped += suite_skipped
    return Counts(total=total, failed=failed, skipped=skipped)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--label", default="tests")
    parser.add_argument(
        "--require-passed",
        action="store_true",
        help="Fail when no selected test passed (including all-skipped live runs)",
    )
    args = parser.parse_args()

    try:
        counts = summarise(args.report, validate_testcases=args.require_passed)
    except (OSError, ET.ParseError, ValueError) as exc:
        print(f"error: cannot read {args.report}: {exc}", file=sys.stderr)
        return 2
    except NoTestsuite:
        print(f"error: {args.report} contains no testsuite element", file=sys.stderr)
        return 2

    print(counts.render(args.label))
    if counts.total == 0:
        # Having run nothing is not a pass. The old version reported exactly this
        # as PASS, which is how a failing smoke run looked healthy in the log.
        print("smoke=FAIL")
        print("error: the report declares zero tests", file=sys.stderr)
        return 1
    if args.require_passed and counts.passed <= 0:
        print("smoke=FAIL")
        print("error: no tests passed; live API verification is unverified", file=sys.stderr)
        return 1
    print(f"smoke={'FAIL' if counts.failed else 'PASS'}")
    return 1 if counts.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
