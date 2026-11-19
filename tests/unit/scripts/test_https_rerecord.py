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
        "spec_commit": "",
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


# --- spec patch (#889, #931, #933) -----------------------------------------------------

_COMMIT = "0123456789abcdef0123456789abcdef01234567"
_PATCH_BASE = (
    "id: datago.apt_trade\ntitle: Apt\nsource:\n  url: https://www.data.go.kr/data/1/openapi.do\n"
    "endpoint:\n  base_url: https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade\n"
    "auth:\n  type: query_param\n  param_name: serviceKey\n"
    "fields:\n- name: a\n  description: old\n"
    "license:\n  type: unknown\n"
    "examples:\n- name: x\n  params:\n    base_date: '20261101'\n    base_time: '0600'\n"
    'status: active\nlast_verified: "2026-10-01"\n'
)


def test_a_descriptive_patch_is_accepted() -> None:
    patched = (
        _PATCH_BASE.replace("data/1/", "data/2/")
        .replace("description: old", "description: new")
        .replace("type: unknown", "type: kogl_1")
        .replace("title: Apt", "title: Apartment")
        .replace("20261101", "20261119")
        .replace("2026-10-01", "2026-11-19")
    )
    assert rerecord.check_spec_patch(_PATCH_BASE, patched) == []


@pytest.mark.parametrize(
    ("old", "new", "block"),
    [
        ("apis.data.go.kr/1613000", "apis.data.go.kr/9999999", "endpoint"),
        ("param_name: serviceKey", "param_name: key", "auth"),
        ("name: x\n", "name: y\n", "examples"),
        ("status: active", "status: broken", "status"),
    ],
)
def test_a_patch_touching_the_request_is_refused(old: str, new: str, block: str) -> None:
    problems = rerecord.check_spec_patch(_PATCH_BASE, _PATCH_BASE.replace(old, new))
    assert len(problems) == 1
    assert block in problems[0]


def test_a_patch_moving_the_key_to_another_host_is_refused() -> None:
    patched = _PATCH_BASE.replace("https://apis.data.go.kr", "https://evil.example")
    assert rerecord.check_spec_patch(_PATCH_BASE, patched)


def test_a_patch_adding_a_request_block_is_refused() -> None:
    patched = _PATCH_BASE.replace("examples:", "pagination:\n  style: page\nexamples:")
    assert "pagination" in rerecord.check_spec_patch(_PATCH_BASE, patched)[0]


def test_a_patch_cannot_hide_a_request_key_inside_a_descriptive_block() -> None:
    # An unindented key always opens a new block, so it cannot ride inside `license`.
    patched = _PATCH_BASE.replace("license:\n  type: unknown\n", "license:\nauth: {}\n")
    assert rerecord.check_spec_patch(_PATCH_BASE, patched)


def test_decide_carries_a_well_formed_spec_commit() -> None:
    outputs = _decide(dataset="datago.bus_arrival", spec=SPEC_HTTPS, spec_commit=_COMMIT)
    assert outputs["allowed"] == "true"
    assert outputs["spec_commit"] == _COMMIT


@pytest.mark.parametrize("commit", ["main", _COMMIT[:12], _COMMIT.upper(), _COMMIT + "\nx=y"])
def test_decide_refuses_a_spec_commit_that_is_not_a_full_id(commit: str) -> None:
    outputs = _decide(dataset="datago.bus_arrival", spec=SPEC_HTTPS, spec_commit=commit)
    assert outputs["allowed"] == "false"
    assert outputs["spec_commit"] == ""


def test_decide_refuses_a_spec_patch_on_a_baseline_dataset() -> None:
    assert _decide(spec_commit=_COMMIT)["allowed"] == "false"


def _patch_repo(repo: Path, patched: str) -> tuple[str, str]:
    """Commit the https base spec, then the patch on a side commit; return both ids."""
    spec = repo / "src/kpubdata/specs/datago/apt_trade.yaml"
    (repo / rerecord.INSECURE_BASELINE).write_text("# header\n", encoding="utf-8")
    spec.write_text(_PATCH_BASE, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "https")
    base = _git(repo, "rev-parse", "HEAD")
    spec.write_text(patched, encoding="utf-8")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "patch")
    patch = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", base)
    return base, patch


def test_switch_then_check_records_with_the_patched_spec(repo: Path) -> None:
    patched = _PATCH_BASE.replace("description: old", "description: new")
    base, patch = _patch_repo(repo, patched)
    spec = repo / "src/kpubdata/specs/datago/apt_trade.yaml"

    switched = _cli(repo, "switch", "datago.apt_trade", "--root", str(repo), "--spec-commit", patch)
    assert switched.returncode == 0, switched.stderr
    assert "description: new" in spec.read_text(encoding="utf-8")

    args = ("check", "datago.apt_trade", "--root", str(repo), "--base", base)
    assert _cli(repo, *args, "--spec-commit", patch).returncode == 0
    # Without the patch the same tree is a spec change beyond the re-record.
    assert _cli(repo, *args).returncode == 1


def test_switch_refuses_a_patch_that_changes_the_endpoint(repo: Path) -> None:
    patched = _PATCH_BASE.replace("RTMSDataSvcAptTrade", "Other")
    _, patch = _patch_repo(repo, patched)
    result = _cli(repo, "switch", "datago.apt_trade", "--root", str(repo), "--spec-commit", patch)
    assert result.returncode == 1
    assert "endpoint" in result.stderr
    assert _git(repo, "status", "--porcelain") == ""


def test_check_refuses_a_recorded_spec_that_drifts_from_the_patch(repo: Path) -> None:
    patched = _PATCH_BASE.replace("description: old", "description: new")
    base, patch = _patch_repo(repo, patched)
    spec = repo / "src/kpubdata/specs/datago/apt_trade.yaml"
    spec.write_text(patched.replace("description: new", "description: other"), encoding="utf-8")
    args = ("check", "datago.apt_trade", "--root", str(repo), "--base", base)
    result = _cli(repo, *args, "--spec-commit", patch)
    assert result.returncode == 1
    assert "beyond the patched spec" in result.stderr


def _loaded_request(text: str) -> tuple[object, object, object]:
    """What the real spec loader would send: endpoint, auth and params."""
    import yaml

    data = yaml.load(text, Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))
    return data.get("endpoint"), data.get("auth"), data.get("params")


_EVIL_ENDPOINT = "endpoint: {base_url: 'https://evil.example/x', operation: op}"


@pytest.mark.parametrize(
    "patched",
    [
        # Line breaks only YAML recognises hide a second endpoint inside `fields`
        # (independent review of #889: NEL, LS, PS, CR).
        _PATCH_BASE.replace("fields:\n", f"fields:{sep}{_EVIL_ENDPOINT}{sep}fields:\n")
        for sep in ("\x85", "\u2028", "\u2029", "\r")
    ]
    + [
        # The last_verified line is erased before a text comparison but loaded by YAML.
        _PATCH_BASE.replace(
            'last_verified: "2026-10-01"\n', f'last_verified: "2026-10-01"\u2028{_EVIL_ENDPOINT}\n'
        ),
        # A plain duplicate key placed after the real one.
        _PATCH_BASE + _EVIL_ENDPOINT + "\n",
        _PATCH_BASE.replace(
            "license:\n", '"endpoint": {base_url: https://evil.example/}\nlicense:\n'
        ),
        "\ufeff" + _PATCH_BASE,
    ],
    ids=["nel", "ls", "ps", "cr", "last-verified", "duplicate", "quoted-duplicate", "bom"],
)
def test_a_patch_that_redirects_the_key_is_refused(patched: str) -> None:
    assert rerecord.check_spec_patch(_PATCH_BASE, patched)


def test_a_quoted_scalar_cannot_swallow_a_request_block() -> None:
    # A double-quoted license value continuing at column 0 turns `auth` into text.
    patched = _PATCH_BASE.replace("auth:\n", 'license: "\nauth:\n', 1).replace(
        "fields:\n", 'x"\nfields:\n', 1
    )
    if _loaded_request(patched)[1] == _loaded_request(_PATCH_BASE)[1]:
        pytest.skip("this YAML build does not swallow the block")
    assert rerecord.check_spec_patch(_PATCH_BASE, patched)


def test_an_alias_carrying_a_value_into_the_request_is_refused() -> None:
    base = _PATCH_BASE.replace("  type: unknown\n", "  type: &t unknown\n").replace(
        "  param_name: serviceKey\n", "  param_name: serviceKey\n  note: *t\n"
    )
    patched = base.replace("&t unknown", "&t changed")
    assert rerecord.check_spec_patch(base, patched)


#: Specs that had a duplicate ``license`` key (#933): a strict load refuses the file,
#: so such a spec can be the base of a patch but never the patch itself.
_DUPLICATE_LICENSE = {"localdata/bakery.yaml", "localdata/general_restaurant.yaml"}
_DUPLICATE_LICENSE |= {"localdata/rest_cafe.yaml"}


def test_a_patch_may_resolve_a_duplicate_key_already_on_main() -> None:
    # The localdata specs carry two `license` keys; the loader keeps the second (#933).
    base = _PATCH_BASE + "license:\n  pii_columns:\n  - TELNO\n"
    merged = _PATCH_BASE.replace(
        "license:\n  type: unknown\n",
        "license:\n  type: kogl_1\n  attribution: x\n  pii_columns:\n  - TELNO\n",
    )
    assert rerecord.check_spec_patch(base, merged) == []
    # The patch itself must still parse strictly: it may not keep or add a duplicate.
    assert rerecord.check_spec_patch(base, base)


def test_a_duplicate_on_main_does_not_let_a_patch_change_the_request() -> None:
    base = _PATCH_BASE + "license:\n  pii_columns:\n  - TELNO\n"
    patched = base.replace("RTMSDataSvcAptTrade", "Other").replace(
        "license:\n  pii_columns:\n  - TELNO\n", ""
    )
    assert "endpoint" in rerecord.check_spec_patch(base, patched)[0]


def test_every_bundled_spec_loads_strictly() -> None:
    root = REPO_ROOT / "src/kpubdata/specs"
    specs = sorted(root.glob("*/*.yaml"))
    assert specs
    refused: set[str] = set()
    for spec in specs:
        text = spec.read_text(encoding="utf-8")
        assert not rerecord._UNSAFE_CHARACTERS.search(text), spec
        problems = rerecord.check_spec_patch(text, text)
        if problems and "duplicate key 'license'" in problems[0]:
            refused.add(spec.relative_to(root).as_posix())
            continue
        assert problems in (
            [],
            ["a spec patch applies only to a spec already on https at a data.go.kr host"],
        ), spec
    # The list may only shrink as those duplicates are resolved (#933).
    assert refused <= _DUPLICATE_LICENSE


def _corrected_descriptions(spec: str) -> str:
    """``spec`` with every field description amended, through a YAML round trip."""
    import yaml

    data = yaml.safe_load(spec)
    for field in data["fields"]:
        field["description"] = f"{field.get('description') or ''} (corrected)"
    return str(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))


def test_the_bundled_corrections_pass() -> None:
    # The three corrections this mode was built for change descriptive text only.
    spec = (REPO_ROOT / "src/kpubdata/specs/datago/bus_arrival.yaml").read_text(encoding="utf-8")
    # Every field description changed: independent of the wording any one carries.
    patched = _corrected_descriptions(spec)
    assert patched != spec
    assert rerecord.check_spec_patch(spec, patched) == []
    assert _loaded_request(patched) == _loaded_request(spec)


# --- confirm: kpubdata's own loader, right before the key is used ----------------------

_BUS = (REPO_ROOT / "src/kpubdata/specs/datago/bus_arrival.yaml").read_text(encoding="utf-8")
_BUS_PATH = "src/kpubdata/specs/datago/bus_arrival.yaml"


def _bus_repo(repo: Path) -> str:
    spec = repo / _BUS_PATH
    spec.write_text(_BUS, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "bus")
    return _git(repo, "rev-parse", "HEAD")


def test_confirm_passes_a_descriptive_change(repo: Path) -> None:
    base = _bus_repo(repo)
    (repo / _BUS_PATH).write_text(_corrected_descriptions(_BUS), encoding="utf-8")
    assert rerecord.confirm_request("datago.bus_arrival", repo, base) == []


@pytest.mark.parametrize(
    "tail",
    [
        # A duplicate key the strict check would refuse; the plain loader keeps the last.
        "endpoint: {base_url: 'https://evil.example/x', operation: getBusArrivalListv2}\n",
        "auth: {type: query_param, param_name: other, provider_key: datago}\n",
    ],
)
def test_confirm_refuses_a_spec_whose_loaded_request_differs(repo: Path, tail: str) -> None:
    base = _bus_repo(repo)
    (repo / _BUS_PATH).write_text(_BUS + tail, encoding="utf-8")
    problems = rerecord.confirm_request("datago.bus_arrival", repo, base)
    assert problems
    assert "different request" in problems[0] or "cannot be confirmed" in problems[0]


def test_confirm_refuses_a_key_host_outside_data_go_kr(repo: Path) -> None:
    evil = _BUS.replace("https://apis.data.go.kr/", "https://evil.example/")
    (repo / _BUS_PATH).write_text(evil, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "evil base")
    base = _git(repo, "rev-parse", "HEAD")
    problems = rerecord.confirm_request("datago.bus_arrival", repo, base)
    assert any("evil.example" in problem for problem in problems)


# --- the unconfirmed-terms baseline ------------------------------------------------------

_TERMS = "# header\ndatago.apt_trade\ndatago.other\n"


def _evaluate_terms(terms: str, *, patched: bool) -> list[str]:
    spec = _PATCH_BASE.replace("type: unknown", "type: kogl_1\n  attribution: x")
    return rerecord.evaluate(
        "datago.apt_trade",
        changed=[rerecord.TERMS_BASELINE],
        base_spec=_PATCH_BASE,
        spec=spec if patched else _PATCH_BASE,
        base_insecure="# header\n",
        insecure="# header\n",
        base_legacy="",
        legacy="",
        spec_patch=spec if patched else None,
        base_terms=_TERMS,
        terms=terms,
    )


def test_a_patch_may_drop_exactly_its_own_terms_line() -> None:
    assert _evaluate_terms("# header\ndatago.other\n", patched=True) == []
    assert _evaluate_terms("# header\n", patched=True)
    assert _evaluate_terms(_TERMS + "datago.new\n", patched=True)


def test_without_a_patch_the_terms_baseline_may_not_change() -> None:
    assert _evaluate_terms("# header\ndatago.other\n", patched=False)


def test_switch_drops_the_terms_line_when_the_patch_confirms_the_terms(repo: Path) -> None:
    (repo / rerecord.TERMS_BASELINE).write_text(_TERMS, encoding="utf-8")
    patched = _PATCH_BASE.replace("type: unknown", "type: kogl_1\n  attribution: x")
    base, patch = _patch_repo(repo, patched)
    switched = _cli(repo, "switch", "datago.apt_trade", "--root", str(repo), "--spec-commit", patch)
    assert switched.returncode == 0, switched.stderr
    terms = (repo / rerecord.TERMS_BASELINE).read_text(encoding="utf-8")
    assert terms == "# header\ndatago.other\n"
    checked = _cli(
        repo,
        "check",
        "datago.apt_trade",
        "--root",
        str(repo),
        "--base",
        base,
        "--spec-commit",
        patch,
    )
    assert checked.returncode == 0, checked.stderr


# --- second review: base_date values, hidden characters, blank attribution -------------


@pytest.mark.parametrize(
    "value", ["'../../x?serviceKey=leak'", "99999999999", "[1, 2]", "'2026111'"]
)
def test_a_base_date_that_is_not_a_date_must_match_exactly(value: str) -> None:
    patched = _PATCH_BASE.replace("base_date: '20261101'", f"base_date: {value}")
    assert "examples" in rerecord.check_spec_patch(_PATCH_BASE, patched)[0]


def test_another_eight_digit_base_date_is_what_the_refresh_rewrites() -> None:
    patched = _PATCH_BASE.replace("20261101", "19000101")
    assert rerecord.check_spec_patch(_PATCH_BASE, patched) == []


@pytest.mark.parametrize("hidden", ["\u200b", "\u202e", "\u2066", "\u00ad"])
def test_a_patch_with_invisible_characters_is_refused(hidden: str) -> None:
    patched = _PATCH_BASE.replace("description: old", f"description: ne{hidden}w")
    assert "invisible" in rerecord.check_spec_patch(_PATCH_BASE, patched)[0]


def test_a_blank_attribution_does_not_confirm_the_terms() -> None:
    blank = _PATCH_BASE.replace("type: unknown", "type: kogl_1\n  attribution: ' '")
    problems = rerecord.evaluate(
        "datago.apt_trade",
        changed=[rerecord.TERMS_BASELINE],
        base_spec=_PATCH_BASE,
        spec=blank,
        base_insecure="# header\n",
        insecure="# header\n",
        base_legacy="",
        legacy="",
        spec_patch=blank,
        base_terms=_TERMS,
        terms="# header\ndatago.other\n",
    )
    assert any("confirms its terms" in problem for problem in problems)


def test_confirm_holds_a_non_date_base_date_to_the_dispatch_commit(repo: Path) -> None:
    kma = (REPO_ROOT / "src/kpubdata/specs/datago/village_fcst.yaml").read_text(encoding="utf-8")
    path = repo / "src/kpubdata/specs/datago/village_fcst.yaml"
    path.write_text(kma, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "kma")
    base = _git(repo, "rev-parse", "HEAD")
    date = rerecord._BASE_DATE.search(kma)
    assert date is not None
    path.write_text(kma.replace(date.group(3), "20000101", 1), encoding="utf-8")
    assert rerecord.confirm_request("datago.village_fcst", repo, base) == []
    path.write_text(kma.replace(date.group(3), "x?serviceKey=y", 1), encoding="utf-8")
    assert rerecord.confirm_request("datago.village_fcst", repo, base)
