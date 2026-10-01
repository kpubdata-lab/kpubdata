"""The agent may shrink the insecure-http baseline, and nothing else (#738).

The pure core is pinned here: each refusal the #765 review named — an
added line, another dataset's line removed, a swap, an unearned
deletion — plus the two passes (no diff at all, and the one deletion a
real https switch earns). One hermetic git run pins the CLI wiring end
to end, the same way the authorship gate tests do.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_baseline_shrink.py"


def _load_script():
    """Load the script as a module (scripts/ is not a package)."""
    spec = importlib.util.spec_from_file_location("check_baseline_shrink", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_baseline_shrink"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def script():
    return _load_script()


HTTPS = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev"
HTTP = "http://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev"


def test_no_diff_passes_whatever_the_spec_says(script) -> None:
    assert script.evaluate("", "datago.apt_trade", HTTP) == []


def test_the_one_earned_deletion_passes(script) -> None:
    assert script.evaluate("-datago.apt_trade\n", "datago.apt_trade", HTTPS) == []


def test_an_added_line_fails(script) -> None:
    problems = script.evaluate("+datago.some_new_http_spec\n", "datago.apt_trade", HTTPS)

    assert any("추가된 줄" in problem for problem in problems)


def test_another_datasets_line_removed_fails(script) -> None:
    problems = script.evaluate("-datago.village_fcst\n", "datago.apt_trade", HTTPS)

    assert any("한 줄이어야 한다" in problem for problem in problems)


def test_a_swap_fails_even_with_the_earned_deletion(script) -> None:
    problems = script.evaluate(
        "-datago.apt_trade\n+datago.some_new_http_spec\n", "datago.apt_trade", HTTPS
    )

    assert any("추가된 줄" in problem for problem in problems)


def test_an_unearned_deletion_fails(script) -> None:
    problems = script.evaluate("-datago.apt_trade\n", "datago.apt_trade", HTTP)

    assert any("https 가 아니다" in problem for problem in problems)


def test_two_deletions_fail(script) -> None:
    problems = script.evaluate(
        "-datago.apt_trade\n-datago.village_fcst\n", "datago.apt_trade", HTTPS
    )

    assert any("한 줄이어야 한다" in problem for problem in problems)


def test_a_missing_spec_fails(script) -> None:
    problems = script.evaluate("-datago.apt_trade\n", "datago.apt_trade", None)

    assert any("스펙을 찾을 수 없다" in problem for problem in problems)


def _git_repo_with_baseline(tmp_path: Path, *, after: str) -> Path:
    """A tiny repository holding one baseline and one spec, committed, then
    rewritten to the `after` baseline text so HEAD holds the shrink diff."""
    baseline = tmp_path / "scripts" / "insecure_http_baseline.txt"
    baseline.parent.mkdir(parents=True)
    before = "datago.apt_trade\ndatago.village_fcst\n"
    baseline.write_text(before, encoding="utf-8")
    spec = tmp_path / "src" / "kpubdata" / "specs" / "datago" / "apt_trade.yaml"
    spec.parent.mkdir(parents=True)
    spec.write_text(f"endpoint:\n  base_url: {HTTPS}\n", encoding="utf-8")
    for command in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "test@kpubdata.local"],
        ["git", "config", "user.name", "test"],
        ["git", "add", "-A"],
        ["git", "commit", "-qm", "init"],
    ):
        subprocess.run(command, cwd=tmp_path, check=True)
    baseline.write_text(after, encoding="utf-8")
    return tmp_path


def test_main_passes_the_earned_shrink_end_to_end(script, tmp_path: Path) -> None:
    root = _git_repo_with_baseline(tmp_path, after="datago.village_fcst\n")

    assert (
        script.main(
            [
                "--dataset",
                "datago.apt_trade",
                "--baseline",
                "scripts/insecure_http_baseline.txt",
                "--base",
                "HEAD",
                "--root",
                str(root),
            ]
        )
        == 0
    )


def test_a_quoted_base_url_still_counts_as_https(script, tmp_path: Path) -> None:
    """The #765 review: a quoted value must not read as a missing switch."""
    root = _git_repo_with_baseline(tmp_path, after="datago.village_fcst\n")
    spec = root / "src" / "kpubdata" / "specs" / "datago" / "apt_trade.yaml"
    spec.write_text(f'endpoint:\n  base_url: "{HTTPS}"\n', encoding="utf-8")

    assert (
        script.main(
            [
                "--dataset",
                "datago.apt_trade",
                "--baseline",
                "scripts/insecure_http_baseline.txt",
                "--base",
                "HEAD",
                "--root",
                str(root),
            ]
        )
        == 0
    )


def test_main_refuses_an_addition_end_to_end(script, tmp_path: Path, capsys) -> None:
    root = _git_repo_with_baseline(
        tmp_path, after="datago.apt_trade\ndatago.village_fcst\ndatago.rider\n"
    )

    code = script.main(
        [
            "--dataset",
            "datago.apt_trade",
            "--baseline",
            "scripts/insecure_http_baseline.txt",
            "--base",
            "HEAD",
            "--root",
            str(root),
        ]
    )

    assert code == 1
    assert "::error::" in capsys.readouterr().err


def test_a_committed_swap_still_fails_against_the_run_base(script, tmp_path: Path) -> None:
    """The #765 review: an agent that commits its baseline swap empties the
    working-tree diff — HEAD would pass it, the run's base must not."""
    root = _git_repo_with_baseline(tmp_path, after="datago.village_fcst\n")
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    baseline = root / "scripts" / "insecure_http_baseline.txt"
    baseline.write_text("datago.village_fcst\ndatago.rider\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "agent swap"], cwd=root, check=True)

    code = script.main(
        [
            "--dataset",
            "datago.apt_trade",
            "--baseline",
            "scripts/insecure_http_baseline.txt",
            "--base",
            base,
            "--root",
            str(root),
        ]
    )

    assert code == 1
