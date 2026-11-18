"""The https re-record moves one spec and guards what its recording changes (#893).

``scripts/https_rerecord.py`` decides in the hosted gate whether a run may start,
switches a baseline-listed spec from ``http://apis.data.go.kr`` to https, and checks the
working tree after ``make record`` against the dispatch commit. The pure functions are
pinned here, and one hermetic git repository runs ``switch`` then ``check`` end to end.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import https_rerecord as rerecord  # noqa: E402

BASELINE = "# header\ndatago.apt_trade\ndatago.air_quality\n"
LEGACY = "# header\ndatago/apt_trade/a.meta.json\ndatago/apt_trade_x/b.meta.json\n"
SPEC_HTTP = (
    'id: datago.apt_trade\nlast_verified: "2026-10-01"\nendpoint:\n'
    "  base_url: http://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev\n"
    "  operation: getRTMSDataSvcAptTradeDev\n"
)
SPEC_HTTPS = SPEC_HTTP.replace("http://", "https://")


def _decide(**overrides: str) -> dict[str, str]:
    arguments = {
        "permission": "write",
        "dataset": "datago.apt_trade",
        "issue_number": "",
        "baseline": BASELINE,
        **overrides,
    }
    lines = rerecord.decide(**arguments)
    return dict(line.split("=", 1) for line in lines)


def test_a_maintainer_may_switch_a_baseline_dataset() -> None:
    assert _decide() == {
        "allowed": "true",
        "reason": "datago.apt_trade https re-record",
        "dataset": "datago.apt_trade",
    }


@pytest.mark.parametrize("permission", ["read", "triage", "maintain", "", "none"])
def test_anyone_without_push_access_is_refused(permission: str) -> None:
    assert _decide(permission=permission)["allowed"] == "false"


@pytest.mark.parametrize(
    "dataset",
    ["datago.bus_arrival", "datago.apt_trade\nx", "../etc.passwd", "Datago.apt_trade", "-x"],
)
def test_only_a_well_formed_baseline_entry_passes(dataset: str) -> None:
    outputs = _decide(dataset=dataset)
    assert outputs["allowed"] == "false"
    assert outputs["dataset"] == ""
    assert "\n" not in outputs["reason"]


def test_an_issue_number_and_a_dataset_together_are_refused() -> None:
    assert _decide(issue_number="42")["allowed"] == "false"


def test_the_switch_changes_the_scheme_of_the_one_base_url() -> None:
    assert rerecord.switch_spec(SPEC_HTTP) == SPEC_HTTPS


@pytest.mark.parametrize(
    "text",
    [
        SPEC_HTTPS,
        SPEC_HTTP.replace("apis.data.go.kr", "example.com"),
        SPEC_HTTP + "  base_url: http://apis.data.go.kr/other\n",
    ],
    ids=["already-https", "other-host", "two-base-urls"],
)
def test_the_switch_refuses_anything_but_one_data_go_kr_http_url(text: str) -> None:
    with pytest.raises(ValueError):
        rerecord.switch_spec(text)


_CHANGED = (
    "src/kpubdata/specs/datago/apt_trade.yaml",
    "tests/fixtures/datago/apt_trade/a.raw.json",
    "tests/fixtures/datago/apt_trade/a.meta.json",
    rerecord.INSECURE_BASELINE,
    rerecord.LEGACY_BASELINE,
    "SUPPORTED_DATA.md",
)


def _evaluate(
    *,
    changed: Sequence[str] = _CHANGED,
    spec: str = SPEC_HTTPS.replace("2026-10-01", "2026-11-18"),
    insecure: str = "# header\ndatago.air_quality\n",
    legacy: str = "# header\ndatago/apt_trade_x/b.meta.json\n",
) -> list[str]:
    return rerecord.evaluate(
        "datago.apt_trade",
        changed=changed,
        base_spec=SPEC_HTTP,
        spec=spec,
        base_insecure=BASELINE,
        insecure=insecure,
        base_legacy=LEGACY,
        legacy=legacy,
    )


def test_a_real_re_record_passes() -> None:
    assert _evaluate() == []


@pytest.mark.parametrize(
    "changed",
    [
        ["README.md"],
        ["scripts/verify_spec.py"],
        ["tests/fixtures/datago/apt_trade_x/a.raw.json"],
        ["src/kpubdata/specs/datago/air_quality.yaml"],
    ],
)
def test_a_path_outside_the_re_record_fails(changed: list[str]) -> None:
    assert _evaluate(changed=changed)


def test_a_spec_change_beyond_the_scheme_fails() -> None:
    assert _evaluate(spec=SPEC_HTTPS.replace("getRTMSDataSvcAptTradeDev", "other"))


def test_a_spec_left_on_http_fails() -> None:
    assert _evaluate(spec=SPEC_HTTP)


@pytest.mark.parametrize(
    "insecure",
    [
        BASELINE,  # nothing removed
        "# header\n",  # another dataset removed too
        "# header\ndatago.air_quality\ndatago.new_http\n",  # a swap
    ],
    ids=["untouched", "extra-removal", "swap"],
)
def test_the_insecure_baseline_loses_exactly_this_dataset(insecure: str) -> None:
    assert _evaluate(insecure=insecure)


@pytest.mark.parametrize(
    "legacy",
    [
        "# header\n",  # another dataset's line removed
        LEGACY + "datago/apt_trade/new.meta.json\n",  # a line added
        "# header\ndatago/apt_trade_x/b.meta.json\ndatago/apt_trade_x/b.meta.json\n",
    ],
    ids=["foreign-removal", "addition", "duplicate"],
)
def test_the_legacy_baseline_only_loses_this_datasets_lines(legacy: str) -> None:
    assert _evaluate(legacy=legacy)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "src/kpubdata/specs/datago").mkdir(parents=True)
    (tmp_path / rerecord.INSECURE_BASELINE).write_text(BASELINE, encoding="utf-8")
    (tmp_path / rerecord.LEGACY_BASELINE).write_text(LEGACY, encoding="utf-8")
    (tmp_path / "src/kpubdata/specs/datago/apt_trade.yaml").write_text(SPEC_HTTP, encoding="utf-8")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(
        tmp_path,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@t",
        "commit",
        "-qm",
        "base",
    )
    return tmp_path


def _cli(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "https_rerecord.py"), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=repo,
    )


def test_switch_then_check_passes_and_a_stray_file_fails(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")

    switched = _cli(repo, "switch", "datago.apt_trade", "--root", str(repo))
    assert switched.returncode == 0, switched.stderr
    spec = (repo / "src/kpubdata/specs/datago/apt_trade.yaml").read_text(encoding="utf-8")
    assert spec == SPEC_HTTPS
    insecure = (repo / rerecord.INSECURE_BASELINE).read_text(encoding="utf-8")
    assert insecure == "# header\ndatago.air_quality\n"
    legacy = (repo / rerecord.LEGACY_BASELINE).read_text(encoding="utf-8")
    assert legacy == "# header\ndatago/apt_trade_x/b.meta.json\n"

    fixtures = repo / "tests/fixtures/datago/apt_trade"
    fixtures.mkdir(parents=True)
    (fixtures / "a.raw.json").write_text("{}\n", encoding="utf-8")
    checked = _cli(repo, "check", "datago.apt_trade", "--root", str(repo), "--base", base)
    assert checked.returncode == 0, checked.stderr

    (repo / "README.md").write_text("stray\n", encoding="utf-8")
    stray = _cli(repo, "check", "datago.apt_trade", "--root", str(repo), "--base", base)
    assert stray.returncode == 1
    assert "README.md" in stray.stderr


def test_switch_refuses_a_dataset_outside_the_baseline(repo: Path) -> None:
    result = _cli(repo, "switch", "datago.air_station", "--root", str(repo))
    assert result.returncode == 1
    assert _git(repo, "status", "--porcelain") == ""
