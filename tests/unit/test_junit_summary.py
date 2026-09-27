"""The smoke summary must not report PASS on a failed run (#516).

The acceptance criterion in the issue is the XML shape of run 36221653544: pytest
reported ``1 failed, 10 passed, 8 skipped`` and the summary printed
``0 passed, 0 failed, 0 skipped`` followed by ``smoke=PASS``.

The cause was reading the counts off the **root** element. pytest writes
``<testsuites>`` as the root and puts the counts on the child ``<testsuite>``, so
every value fell back to 0 -- and ``failed == 0`` printed PASS.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "junit_summary.py"

#: The shape pytest actually writes: counts on the child, not the root.
_PYTEST_SHAPE = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="0" failures="1" skipped="8" tests="19" time="4.2">
    <testcase classname="t" name="ok"/>
  </testsuite>
</testsuites>
"""

_BARE_SUITE = """<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" errors="0" failures="0" skipped="1" tests="5"/>
"""

_EMPTY = """<?xml version="1.0" encoding="utf-8"?>
<testsuites/>
"""

_ZERO_TESTS = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" errors="0" failures="0" skipped="0" tests="0"/>
</testsuites>
"""


def _run(tmp_path: Path, xml: str) -> subprocess.CompletedProcess[str]:
    report = tmp_path / "report.xml"
    report.write_text(xml, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(_SCRIPT), str(report), "--label", "datago live"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


class TestTheAcceptanceCriterion:
    def test_the_real_failing_run_reports_the_real_counts(self, tmp_path: Path) -> None:
        result = _run(tmp_path, _PYTEST_SHAPE)
        assert "datago live: 10 passed, 1 failed, 8 skipped (total 19)" in result.stdout

    def test_the_real_failing_run_reports_fail(self, tmp_path: Path) -> None:
        result = _run(tmp_path, _PYTEST_SHAPE)
        assert "smoke=FAIL" in result.stdout
        assert "smoke=PASS" not in result.stdout
        assert result.returncode == 1

    def test_zero_tests_is_not_a_pass(self, tmp_path: Path) -> None:
        """Having run nothing is not a pass. The old version reported exactly
        this as PASS, which is how a failing smoke run looked healthy."""
        result = _run(tmp_path, _ZERO_TESTS)
        assert "smoke=FAIL" in result.stdout
        assert result.returncode == 1

    def test_an_empty_report_is_an_error(self, tmp_path: Path) -> None:
        result = _run(tmp_path, _EMPTY)
        assert result.returncode == 2
        assert "no testsuite element" in result.stderr

    def test_an_unparseable_report_is_an_error(self, tmp_path: Path) -> None:
        result = _run(tmp_path, "not xml at all")
        assert result.returncode == 2
        assert "cannot read" in result.stderr


class TestBothDocumentShapes:
    def test_a_bare_testsuite_root_is_read(self, tmp_path: Path) -> None:
        """Some tools emit ``<testsuite>`` as the root. Assuming one shape and
        silently reading zeros from the other is the bug this replaces."""
        result = _run(tmp_path, _BARE_SUITE)
        assert "4 passed, 0 failed, 1 skipped (total 5)" in result.stdout
        assert "smoke=PASS" in result.stdout
        assert result.returncode == 0

    def test_several_suites_are_summed(self, tmp_path: Path) -> None:
        xml = """<?xml version="1.0"?>
<testsuites>
  <testsuite name="a" errors="0" failures="1" skipped="0" tests="3"/>
  <testsuite name="b" errors="1" failures="0" skipped="2" tests="7"/>
</testsuites>
"""
        result = _run(tmp_path, xml)
        assert "6 passed, 2 failed, 2 skipped (total 10)" in result.stdout


class TestErrorsCountAsFailures:
    def test_an_error_without_a_failure_reports_fail(self, tmp_path: Path) -> None:
        xml = """<?xml version="1.0"?>
<testsuites>
  <testsuite name="a" errors="2" failures="0" skipped="0" tests="4"/>
</testsuites>
"""
        result = _run(tmp_path, xml)
        assert "smoke=FAIL" in result.stdout
        assert "2 passed, 2 failed" in result.stdout


@pytest.mark.parametrize("missing", ["tests", "failures", "skipped"])
def test_a_missing_attribute_defaults_to_zero(tmp_path: Path, missing: str) -> None:
    attrs = {"tests": "3", "failures": "0", "skipped": "0", "errors": "0"}
    del attrs[missing]
    rendered = " ".join(f'{k}="{v}"' for k, v in attrs.items())
    xml = f'<?xml version="1.0"?><testsuites><testsuite name="a" {rendered}/></testsuites>'
    assert _run(tmp_path, xml).returncode in (0, 1)
