"""The drift report says what it found, or that it could not look (#859).

A failed ``gh`` call was read as an empty answer: a 403 on the run list ended as "not
enough history" with exit status 0, and a failed ``gh issue create`` printed that the
issue was filed. Drift could go unreported under a green job.
"""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "report_drift.py"


def _load_script() -> Any:
    spec = importlib.util.spec_from_file_location("report_drift", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["report_drift"] = module
    spec.loader.exec_module(module)
    return module


drift = _load_script()


def _junit(*failed_tests: str) -> bytes:
    """A zipped junit report in which ``failed_tests`` failed and one test passed."""
    cases = "".join(
        f'<testcase classname="tests.integration.test_datago_live" name="{name}">'
        "<failure>boom</failure></testcase>"
        for name in failed_tests
    )
    xml = (
        '<testsuite><testcase classname="tests.integration.test_datago_live" '
        f'name="test_datago_passing"/>{cases}</testsuite>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("junit.xml", xml)
    return buffer.getvalue()


class FakeGh:
    """Answers the ``gh`` calls the script makes, from what a test sets up."""

    def __init__(self) -> None:
        #: Newest first, as ``gh run list`` returns them.
        self.runs: list[dict[str, Any]] = []
        #: run id -> junit zips; a run with no entry lists no artifacts.
        self.artifacts: dict[str, list[bytes]] = {}
        self.open_issues: list[dict[str, Any]] = []
        #: The first words of a call that should fail, e.g. ``("run", "list")``.
        self.failing: set[tuple[str, ...]] = set()
        self.garbled: set[tuple[str, ...]] = set()
        self.calls: list[list[str]] = []

    def run(self, command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[Any]:
        assert command[0] == "gh"
        args = command[1:]
        self.calls.append(args)
        text = bool(kwargs.get("text"))

        def answer(out: str | bytes, code: int = 0, err: str = "") -> Any:
            if text and isinstance(out, bytes):
                out = out.decode()
            return subprocess.CompletedProcess(command, code, out, err if text else err.encode())

        kind = self._kind(args)
        if kind in self.failing:
            return answer(
                "" if text else b"", 1, "HTTP 403: Resource not accessible by integration"
            )
        if kind in self.garbled:
            return answer("<html>not json</html>" if text else b"not a zip")
        if kind == ("run", "list"):
            return answer(json.dumps(self.runs))
        if kind == ("api", "artifacts"):
            run_id = args[1].split("/runs/")[1].split("/")[0]
            ids = [f"{run_id}-{i}" for i in range(len(self.artifacts.get(run_id, [])))]
            return answer("\n".join(ids) + ("\n" if ids else ""))
        if kind == ("api", "zip"):
            run_id, index = args[1].split("/artifacts/")[1].split("/")[0].rsplit("-", 1)
            return answer(self.artifacts[run_id][int(index)])
        if kind == ("issue", "list"):
            return answer(json.dumps(self.open_issues))
        if kind == ("issue", "comment"):
            return answer("")
        if kind == ("issue", "create"):
            return answer("https://github.com/kpubdata-lab/kpubdata/issues/999\n")
        raise AssertionError(f"unexpected gh call: {args}")

    @staticmethod
    def _kind(args: list[str]) -> tuple[str, ...]:
        if args[0] == "api":
            return ("api", "zip" if args[1].endswith("/zip") else "artifacts")
        return (args[0], args[1])

    def made(self, *kind: str) -> list[list[str]]:
        return [call for call in self.calls if self._kind(call) == kind]


@pytest.fixture()
def gh(monkeypatch: pytest.MonkeyPatch) -> FakeGh:
    fake = FakeGh()
    monkeypatch.setattr(drift.subprocess, "run", fake.run)
    return fake


def _run(run_id: int, conclusion: str | None) -> dict[str, Any]:
    return {"databaseId": run_id, "status": "completed", "conclusion": conclusion}


def _verdict(capsys: pytest.CaptureFixture[str]) -> str:
    lines = [line for line in capsys.readouterr().out.splitlines() if line.startswith("verdict=")]
    assert len(lines) == 1, lines
    return lines[0].removeprefix("verdict=")


# ----------------------------------------------------------------- the three answers


def test_two_good_runs_are_ok(gh: FakeGh, capsys: pytest.CaptureFixture[str]) -> None:
    gh.runs = [_run(2, "success"), _run(1, "success")]

    assert drift.main([]) == 0

    assert _verdict(capsys) == "ok"
    assert gh.made("issue", "create") == []


def test_a_dataset_that_failed_twice_in_a_row_is_drift_and_is_filed(
    gh: FakeGh, capsys: pytest.CaptureFixture[str]
) -> None:
    gh.runs = [_run(2, "failure"), _run(1, "failure")]
    gh.artifacts = {
        "2": [_junit("test_datago_village_fcst", "test_datago_apt_trade")],
        "1": [_junit("test_datago_village_fcst")],
    }

    assert drift.main([]) == 0

    out = capsys.readouterr().out
    assert "verdict=drift" in out
    created = gh.made("issue", "create")
    assert len(created) == 1 and "datago.village_fcst" in " ".join(created[0])
    # Failed once only: a transient outage, not drift.
    assert "datago.apt_trade" not in " ".join(created[0][: created[0].index("--body")])


def test_one_failure_after_a_good_run_is_not_drift(
    gh: FakeGh, capsys: pytest.CaptureFixture[str]
) -> None:
    gh.runs = [_run(2, "failure"), _run(1, "success")]
    gh.artifacts = {"2": [_junit("test_datago_village_fcst")]}

    assert drift.main([]) == 0

    assert _verdict(capsys) == "ok"
    assert gh.made("issue", "create") == []


def test_too_few_completed_runs_is_said_as_that(
    gh: FakeGh, capsys: pytest.CaptureFixture[str]
) -> None:
    """The list was read; there is simply not enough in it yet."""
    gh.runs = [_run(2, None), _run(1, "success")]

    assert drift.main([]) == 0

    assert _verdict(capsys) == "insufficient_history"


# ------------------------------------------------- "could not look" is not "nothing"


def test_a_refused_run_list_is_undetermined_not_too_little_history(
    gh: FakeGh, capsys: pytest.CaptureFixture[str]
) -> None:
    """The case that passed green: 403 on the list, read as an empty list."""
    gh.failing = {("run", "list")}

    assert drift.main([]) == 2

    out = capsys.readouterr().out
    assert "verdict=undetermined" in out and "insufficient_history" not in out


def test_a_run_list_that_is_not_json_is_undetermined(
    gh: FakeGh, capsys: pytest.CaptureFixture[str]
) -> None:
    gh.garbled = {("run", "list")}

    assert drift.main([]) == 2
    assert _verdict(capsys) == "undetermined"


def test_a_failed_run_with_no_results_is_not_read_as_a_run_with_no_failures(
    gh: FakeGh, capsys: pytest.CaptureFixture[str]
) -> None:
    """No artifact: which datasets failed is unknown. A good run says so itself."""
    gh.runs = [_run(2, "failure"), _run(1, "failure")]
    gh.artifacts = {"1": [_junit("test_datago_village_fcst")]}

    assert drift.main([]) == 2

    assert _verdict(capsys) == "undetermined"
    assert gh.made("issue", "create") == []


@pytest.mark.parametrize("broken", [("api", "artifacts"), ("api", "zip")])
def test_results_that_cannot_be_fetched_are_undetermined(
    gh: FakeGh, capsys: pytest.CaptureFixture[str], broken: tuple[str, str]
) -> None:
    gh.runs = [_run(2, "failure"), _run(1, "failure")]
    gh.artifacts = {"2": [_junit("test_datago_x")], "1": [_junit("test_datago_x")]}
    gh.failing = {broken}

    assert drift.main([]) == 2
    assert _verdict(capsys) == "undetermined"


def test_results_that_cannot_be_parsed_are_undetermined(
    gh: FakeGh, capsys: pytest.CaptureFixture[str]
) -> None:
    gh.runs = [_run(2, "failure"), _run(1, "failure")]
    gh.artifacts = {"2": [_junit("test_datago_x")], "1": [_junit("test_datago_x")]}
    gh.garbled = {("api", "zip")}

    assert drift.main([]) == 2
    assert _verdict(capsys) == "undetermined"


def test_an_artifact_without_a_test_report_is_undetermined(
    gh: FakeGh, capsys: pytest.CaptureFixture[str]
) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("notes.txt", "no junit here")
    gh.runs = [_run(2, "failure"), _run(1, "success")]
    gh.artifacts = {"2": [buffer.getvalue()]}

    assert drift.main([]) == 2
    assert _verdict(capsys) == "undetermined"


def test_an_unreadable_run_outside_the_streak_window_does_not_stop_the_verdict(
    gh: FakeGh, capsys: pytest.CaptureFixture[str]
) -> None:
    """Negative: only the runs a streak is counted over are read."""
    gh.runs = [_run(3, "success"), _run(2, "success"), _run(1, "failure")]

    assert drift.main([]) == 0

    assert _verdict(capsys) == "ok"
    assert gh.made("api", "artifacts") == []


# ------------------------------------------------------------------------ reporting


def _two_failures(gh: FakeGh, *tests: str) -> None:
    gh.runs = [_run(2, "failure"), _run(1, "failure")]
    gh.artifacts = {"2": [_junit(*tests)], "1": [_junit(*tests)]}


def test_an_issue_that_could_not_be_created_is_not_reported_as_filed(
    gh: FakeGh, capsys: pytest.CaptureFixture[str]
) -> None:
    _two_failures(gh, "test_datago_village_fcst")
    gh.failing = {("issue", "create")}

    assert drift.main([]) == 1

    out = capsys.readouterr().out
    assert "verdict=report_failed" in out
    assert "발행:" not in out


def test_a_failed_search_files_nothing_so_no_second_issue_is_made(
    gh: FakeGh, capsys: pytest.CaptureFixture[str]
) -> None:
    """Read as "no issue yet", a failed search is how a duplicate gets filed."""
    _two_failures(gh, "test_datago_village_fcst")
    gh.failing = {("issue", "list")}

    assert drift.main([]) == 1

    assert _verdict(capsys) == "report_failed"
    assert gh.made("issue", "create") == []


def test_an_open_issue_for_the_dataset_is_updated_not_duplicated(
    gh: FakeGh, capsys: pytest.CaptureFixture[str]
) -> None:
    _two_failures(gh, "test_datago_village_fcst")
    gh.open_issues = [{"number": 77, "title": "[drift] datago.village_fcst 실API 스모크 연속 실패"}]

    assert drift.main([]) == 0

    assert _verdict(capsys) == "drift"
    assert gh.made("issue", "create") == []
    assert [call[2] for call in gh.made("issue", "comment")] == ["77"]


def test_a_comment_that_could_not_be_posted_is_a_failed_report(
    gh: FakeGh, capsys: pytest.CaptureFixture[str]
) -> None:
    _two_failures(gh, "test_datago_village_fcst")
    gh.open_issues = [{"number": 77, "title": "[drift] datago.village_fcst"}]
    gh.failing = {("issue", "comment")}

    assert drift.main([]) == 1

    out = capsys.readouterr().out
    assert "verdict=report_failed" in out and "갱신:" not in out


def test_one_failed_report_does_not_stop_the_others(
    gh: FakeGh, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _two_failures(gh, "test_datago_alpha", "test_datago_beta")
    real = gh.run

    def run(command: list[str], **kwargs: Any) -> Any:
        # By the title: each issue's body lists every dataset that failed in the runs.
        creating = command[1:3] == ["issue", "create"]
        if creating and "datago.alpha" in command[command.index("--title") + 1]:
            gh.calls.append(command[1:])
            return subprocess.CompletedProcess(command, 1, "", "HTTP 500")
        return real(command, **kwargs)

    monkeypatch.setattr(drift.subprocess, "run", run)

    assert drift.main([]) == 1

    out = capsys.readouterr().out
    assert "verdict=report_failed" in out
    assert "발행:" in out and "datago.beta" in out
    assert "드리프트가 있으나 보고하지 못함: datago.alpha" in out


def test_a_dry_run_says_what_it_found_and_touches_no_issue(
    gh: FakeGh, capsys: pytest.CaptureFixture[str]
) -> None:
    _two_failures(gh, "test_datago_village_fcst")

    assert drift.main(["--dry-run"]) == 0

    assert _verdict(capsys) == "drift"
    assert gh.made("issue", "list") == [] and gh.made("issue", "create") == []
