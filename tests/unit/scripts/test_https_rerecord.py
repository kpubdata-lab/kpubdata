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
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

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
    arguments: dict[str, str] = {
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
        "reason": "datago.apt_trade https switch and re-record",
        "dataset": "datago.apt_trade",
    }


@pytest.mark.parametrize("permission", ["read", "triage", "maintain", "", "none"])
def test_anyone_without_push_access_is_refused(permission: str) -> None:
    assert _decide(permission=permission)["allowed"] == "false"


@pytest.mark.parametrize(
    "dataset",
    ["datago.no_such", "datago.apt_trade\nx", "../etc.passwd", "Datago.apt_trade", "-x"],
)
def test_a_malformed_or_unknown_dataset_is_refused(dataset: str) -> None:
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


_KST = ZoneInfo("Asia/Seoul")
_KMA_SPEC = (
    "endpoint:\n  base_url: http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0\n"
    "examples:\n- name: a\n  params:\n    base_date: '20260908'\n    base_time: '2300'\n"
    "- name: b\n  params:\n    base_date: '20260908'\n    base_time: '0600'\n"
)


@pytest.mark.parametrize(
    ("now", "base_time", "expected"),
    [
        (datetime(2026, 11, 19, 8, 0, tzinfo=_KST), "0600", "20261119"),
        (datetime(2026, 11, 19, 6, 30, tzinfo=_KST), "0600", "20261118"),  # not out yet
        (datetime(2026, 11, 19, 23, 30, tzinfo=_KST), "2300", "20261118"),
        (datetime(2026, 11, 20, 0, 30, tzinfo=_KST), "2300", "20261119"),
        (datetime(2026, 11, 18, 23, 0, tzinfo=UTC), "0600", "20261119"),  # 08:00 KST
    ],
)
def test_the_release_date_is_the_latest_published_one(
    now: datetime, base_time: str, expected: str
) -> None:
    assert rerecord.latest_release_date(base_time, now) == expected


def test_example_dates_move_to_their_own_latest_release() -> None:
    now = datetime(2026, 11, 19, 8, 0, tzinfo=_KST)
    refreshed = rerecord.refresh_example_dates(_KMA_SPEC, now)
    assert "base_date: '20261118'\n    base_time: '2300'" in refreshed
    assert "base_date: '20261119'\n    base_time: '0600'" in refreshed
    assert rerecord.refresh_example_dates(SPEC_HTTP, now) == SPEC_HTTP


def test_a_base_date_without_a_base_time_is_refused() -> None:
    with pytest.raises(ValueError):
        rerecord.refresh_example_dates("params:\n  base_date: '20260908'\n", datetime.now(_KST))


def test_the_check_allows_a_refreshed_date_and_nothing_else_in_the_examples() -> None:
    switched = rerecord.switch_spec(_KMA_SPEC)
    refreshed = rerecord.refresh_example_dates(switched, datetime(2026, 11, 19, 8, 0, tzinfo=_KST))

    def problems(spec: str) -> list[str]:
        return rerecord.evaluate(
            "datago.village_fcst",
            changed=["src/kpubdata/specs/datago/village_fcst.yaml"],
            base_spec=_KMA_SPEC,
            spec=spec,
            base_insecure="datago.village_fcst\n",
            insecure="",
            base_legacy="",
            legacy="",
        )

    assert problems(refreshed) == []
    assert problems(refreshed.replace("base_time: '0600'", "base_time: '0700'"))
    assert problems(refreshed.replace("name: b", "name: c"))


def test_a_spec_already_on_https_may_be_re_recorded() -> None:
    outputs = _decide(dataset="datago.bus_arrival", spec=SPEC_HTTPS)
    assert outputs["allowed"] == "true"
    assert outputs["dataset"] == "datago.bus_arrival"


def test_an_http_spec_outside_the_baseline_is_refused() -> None:
    assert _decide(dataset="datago.bus_arrival", spec=SPEC_HTTP)["allowed"] == "false"


def test_a_re_record_on_https_keeps_the_spec_and_the_insecure_baseline() -> None:
    def problems(**overrides: str) -> list[str]:
        arguments = {
            "spec": SPEC_HTTPS.replace("2026-10-01", "2026-11-19"),
            "insecure": "# header\ndatago.air_quality\n",
        }
        arguments.update(overrides)
        return rerecord.evaluate(
            "datago.apt_trade",
            changed=["src/kpubdata/specs/datago/apt_trade.yaml"],
            base_spec=SPEC_HTTPS,
            spec=arguments["spec"],
            base_insecure="# header\ndatago.air_quality\n",
            insecure=arguments["insecure"],
            base_legacy=LEGACY,
            legacy="# header\ndatago/apt_trade_x/b.meta.json\n",
        )

    assert problems() == []
    assert problems(insecure="# header\n")
    assert problems(spec=SPEC_HTTPS.replace("getRTMSDataSvcAptTradeDev", "other"))


def test_switch_re_records_a_spec_already_on_https(repo: Path) -> None:
    spec = repo / "src/kpubdata/specs/datago/apt_trade.yaml"
    spec.write_text(SPEC_HTTPS, encoding="utf-8")
    (repo / rerecord.INSECURE_BASELINE).write_text(
        "# header\ndatago.air_quality\n", encoding="utf-8"
    )
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "https")

    result = _cli(repo, "switch", "datago.apt_trade", "--root", str(repo))

    assert result.returncode == 0, result.stderr
    assert spec.read_text(encoding="utf-8") == SPEC_HTTPS
    assert (repo / rerecord.INSECURE_BASELINE).read_text(encoding="utf-8") == (
        "# header\ndatago.air_quality\n"
    )


def test_an_https_spec_on_another_host_is_refused() -> None:
    other = SPEC_HTTPS.replace("apis.data.go.kr", "example.com")
    assert _decide(dataset="datago.bus_arrival", spec=other)["allowed"] == "false"


def test_the_check_refuses_a_dispatch_spec_neither_listed_nor_on_https() -> None:
    problems = rerecord.evaluate(
        "datago.apt_trade",
        changed=[],
        base_spec=SPEC_HTTP,
        spec=SPEC_HTTP,
        base_insecure="# header\n",
        insecure="# header\n",
        base_legacy="",
        legacy="",
    )
    assert any("cannot be re-recorded" in problem for problem in problems)


def test_switch_refuses_an_http_spec_outside_the_baseline(repo: Path) -> None:
    (repo / rerecord.INSECURE_BASELINE).write_text("# header\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "unlisted")

    result = _cli(repo, "switch", "datago.apt_trade", "--root", str(repo))

    assert result.returncode == 1
    assert _git(repo, "status", "--porcelain") == ""


def test_the_decide_cli_reads_the_real_spec() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "https_rerecord.py"),
            "decide",
            "--permission=write",
            "--dataset=datago.bus_arrival",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "allowed=true" in result.stdout.splitlines()


_SCRIPT = (
    'batch = client.dataset("datago.village_fcst").list(\n'
    '    base_date="20260908", base_time="2300", nx=55, ny=127, page=1, page_size=100\n'
    ")\n"
)


def test_example_script_dates_follow_the_spec() -> None:
    now = datetime(2026, 11, 19, 9, 0, tzinfo=_KST)
    refreshed = rerecord.refresh_script_dates(_SCRIPT, now)
    assert 'base_date="20261118", base_time="2300"' in refreshed


def test_the_check_allows_only_date_changes_in_the_example_script() -> None:
    refreshed = rerecord.refresh_script_dates(_SCRIPT, datetime(2026, 11, 19, 9, 0, tzinfo=_KST))

    def problems(script: str) -> list[str]:
        return rerecord.evaluate(
            "datago.apt_trade",
            changed=["examples/datago/apt_trade.py"],
            base_spec=SPEC_HTTPS,
            spec=SPEC_HTTPS,
            base_insecure="",
            insecure="",
            base_legacy="",
            legacy="",
            base_script=_SCRIPT,
            script=script,
        )

    assert problems(refreshed) == []
    assert problems(refreshed.replace("nx=55", "nx=56"))
    assert problems(refreshed + "import os\n")


def test_switch_refreshes_the_example_script(repo: Path) -> None:
    script = repo / "examples/datago/apt_trade.py"
    script.parent.mkdir(parents=True)
    script.write_text(_SCRIPT, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "script")
    base = _git(repo, "rev-parse", "HEAD")

    assert _cli(repo, "switch", "datago.apt_trade", "--root", str(repo)).returncode == 0
    assert "20260908" not in script.read_text(encoding="utf-8")
    checked = _cli(repo, "check", "datago.apt_trade", "--root", str(repo), "--base", base)
    assert checked.returncode == 0, checked.stderr
