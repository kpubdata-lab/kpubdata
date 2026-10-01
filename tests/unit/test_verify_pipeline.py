"""Phase 2 verification pipeline unit tests-verify record/verify/replay

Live calls recorded separately via make record (integration).
FakeTransport injection deterministically verifies record output files,
verify integrity rules, and replay matching rules.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

import httpx
import pytest

from kpubdata import Client

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
SPECS_DIR = REPO_ROOT / "src" / "kpubdata" / "specs"


def _load_script(name: str):
    """Load scripts/ module (add to sys.path for redact import support)."""
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


record_mod = _load_script("record")
verify_mod = _load_script("verify_spec")
#: The real base-branch reader, kept before the autouse fixture below swaps it.
_REAL_BASE_BASELINE_TEXT = verify_mod._base_baseline_text


@pytest.fixture(autouse=True)
def _base_branch_is_the_working_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Judge each baseline against itself unless a test says otherwise (#766).

    The shrink-only ratchet reads the base branch through git, which the test
    job's shallow checkout does not have and which would tie unrelated tests
    to the repository's history. Tests of the ratchet itself override this.
    """

    def _same_file(path: Path) -> str | None:
        return path.read_text(encoding="utf-8") if path.is_file() else None

    monkeypatch.setattr(verify_mod, "_base_baseline_text", _same_file)


# ----------------------------------------------------------------------
# record: 3 output types + sanitization + hash
# ----------------------------------------------------------------------


class FakeLiveTransport:
    """Transport layer returning standard envelope instead of live calls."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
        json_body: object = None,
        dataset_id: str | None = None,
        provider: str | None = None,
        secret_values: tuple[str, ...] = (),
    ) -> object:

        self.calls.append({"url": url, "params": dict(params or {})})
        # village_fcst XML example mimics XML response
        fmt = (
            (params or {}).get("dataType")
            or (params or {}).get("_type")
            or (params or {}).get("resultType")
        )
        key = dataset_id or ""
        if key == "datago.village_fcst" and fmt == "XML":
            xml = (
                "<response><header><resultCode>00</resultCode></header>"
                "<body><items><item><category>T1H</category></item></items>"
                "<totalCount>1</totalCount></body></response>"
            )
            return httpx.Response(
                200,
                content=xml.encode(),
                headers={"content-type": "text/xml"},
                request=httpx.Request("GET", url),
            )
        payload = {
            "response": {
                "header": {"resultCode": "00", "resultMsg": "OK"},
                "body": {"items": {"item": [{"no": 1}, {"no": 2}]}, "totalCount": "2"},
            }
        }
        return httpx.Response(
            200,
            content=json.dumps(payload).encode(),
            headers={"content-type": "application/json"},
            request=httpx.Request("GET", url),
        )


class FakeLiveConfig(record_mod.KPubDataConfig):
    """Config providing fixed API key value."""

    def get_provider_key(self, provider: str) -> str | None:
        return "real-secret-key" if provider == "datago" else None

    def require_provider_key(self, provider: str) -> str:
        return "real-secret-key"


def test_record_dataset_writes_three_files(tmp_path: Path) -> None:
    """Each example records raw/meta/expected 3-tuple with sanitized key."""
    transport = FakeLiveTransport()
    written = record_mod.record_dataset(
        "datago.apt_trade",
        fixtures_root=tmp_path,
        config=FakeLiveConfig(),
        transport=transport,  # type: ignore[arg-type]
        recorded_by="agent-test",
    )
    out_dir = tmp_path / "datago" / "apt_trade"
    examples = sorted(path.name.removesuffix(".raw.json") for path in out_dir.glob("*.raw.json"))
    assert len(examples) >= 1
    assert len(written) == len(examples) * 3

    for name in examples:
        raw = json.loads((out_dir / f"{name}.raw.json").read_text(encoding="utf-8"))
        meta = json.loads((out_dir / f"{name}.meta.json").read_text(encoding="utf-8"))
        expected = json.loads((out_dir / f"{name}.expected.json").read_text(encoding="utf-8"))

        # Key sanitization: no actual key in meta params or raw
        assert "real-secret-key" not in json.dumps(meta) + json.dumps(raw)
        assert meta["params"]["serviceKey"] == "[REDACTED]"
        assert meta["recorded_by"] == "agent-test"
        assert meta["dataset_id"] == "datago.apt_trade"
        assert meta["endpoint"].endswith("getRTMSDataSvcAptTradeDev")
        # Hash match: verify recalculates with same rule and must match
        canon = json.dumps(raw, ensure_ascii=False, sort_keys=True, indent=1) + "\n"
        import hashlib

        assert hashlib.sha256(canon.encode()).hexdigest() == meta["response_sha256"]
        # expected snapshot
        assert expected == {"items": [{"no": 1}, {"no": 2}], "total_count": 2}


# ----------------------------------------------------------------------
# verify: integrity and replay contract
# ----------------------------------------------------------------------


def _record_apt(tmp_path: Path) -> None:
    """Record apt_trade fixture for verify test."""
    record_mod.record_dataset(
        "datago.apt_trade",
        fixtures_root=tmp_path,
        config=FakeLiveConfig(),
        transport=FakeLiveTransport(),  # type: ignore[arg-type]
        recorded_by="test",
    )


def test_verify_passes_on_fresh_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Just-recorded fixture passes verification."""
    _record_apt(tmp_path)
    monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", tmp_path)
    steps = verify_mod._verify_fixtures(_spec("datago.apt_trade"))
    assert steps, "fixture 검증 단계가 생성되어야 한다"
    assert all(step.passed for step in steps)


def test_verify_fails_when_fixture_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fails if fixture missing and prints record guidance."""
    monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", Path("/nonexistent"))
    steps = verify_mod._verify_fixtures(_spec("datago.apt_trade"))
    assert not all(step.passed for step in steps)
    assert any("make record" in step.detail for step in steps)


def test_verify_fails_on_hash_tamper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Hash mismatch fails if raw modified after record (block forgery)."""
    _record_apt(tmp_path)
    monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", tmp_path)
    raw_file = next((tmp_path / "datago" / "apt_trade").glob("*.raw.json"))
    payload = json.loads(raw_file.read_text(encoding="utf-8"))
    payload["response"]["body"]["totalCount"] = "999"
    raw_file.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1) + "\n", encoding="utf-8"
    )
    steps = verify_mod._verify_fixtures(_spec("datago.apt_trade"))
    assert any("해시" in step.name and not step.passed for step in steps)


# ----------------------------------------------------------------------
# evidence binding: spec digest + commit + run (#522)
# ----------------------------------------------------------------------


def test_record_binds_the_spec_commit_and_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """meta carries the digest of the spec it executed, and the commit and
    run only when the environment provides them."""
    for name in ("GITHUB_SHA", "GITHUB_RUN_ID", "KPUBDATA_RECORD_COMMIT", "KPUBDATA_RECORD_RUN"):
        monkeypatch.delenv(name, raising=False)
    _record_apt(tmp_path)

    meta_path = next((tmp_path / "datago" / "apt_trade").glob("*.meta.json"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    from kpubdata.core.spec import spec_file_digest

    expected = spec_file_digest(Path(record_mod.SPEC_ROOT) / "datago" / "apt_trade.yaml")
    assert meta["spec_sha256"] == expected
    assert "record_commit" not in meta
    assert "run_ref" not in meta


def test_record_captures_the_commit_and_run_when_ci_provides_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_SHA", "abc123def456")
    monkeypatch.setenv("GITHUB_RUN_ID", "9876543210")
    _record_apt(tmp_path)

    meta_path = next((tmp_path / "datago" / "apt_trade").glob("*.meta.json"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    assert meta["record_commit"] == "abc123def456"
    assert meta["run_ref"] == "9876543210"


def test_verify_voids_evidence_when_the_spec_changed_after_recording(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The issue's negative test: a spec edit after recording makes the
    evidence void, and verify says so instead of replaying it silently."""
    _record_apt(tmp_path)
    monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", tmp_path)

    source = (Path(verify_mod.SPEC_ROOT) / "datago" / "apt_trade.yaml").read_text(encoding="utf-8")
    spec_root = tmp_path / "specs"
    (spec_root / "datago").mkdir(parents=True)
    (spec_root / "datago" / "apt_trade.yaml").write_text(
        source + "\n# a field changed after recording\n", encoding="utf-8"
    )
    monkeypatch.setattr(verify_mod, "SPEC_ROOT", spec_root)

    steps = verify_mod._verify_fixtures(_spec("datago.apt_trade"))

    binding = [step for step in steps if "spec 결속" in step.name]
    assert binding and not binding[0].passed
    assert "재기록" in binding[0].detail


def test_verify_tolerates_the_last_verified_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The recorder rewrites last_verified after recording — that rewrite
    must not void the record it just made."""
    _record_apt(tmp_path)
    monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", tmp_path)

    source = (Path(verify_mod.SPEC_ROOT) / "datago" / "apt_trade.yaml").read_text(encoding="utf-8")
    stripped = "\n".join(
        line for line in source.splitlines() if not line.startswith("last_verified:")
    )
    spec_root = tmp_path / "specs"
    (spec_root / "datago").mkdir(parents=True)
    (spec_root / "datago" / "apt_trade.yaml").write_text(
        stripped + '\nlast_verified: "1999-12-31"\n', encoding="utf-8"
    )
    monkeypatch.setattr(verify_mod, "SPEC_ROOT", spec_root)

    steps = verify_mod._verify_fixtures(_spec("datago.apt_trade"))

    assert all(step.passed for step in steps)


# ----------------------------------------------------------------------
# legacy evidence is a frozen baseline, not a missing field (#717)
# ----------------------------------------------------------------------

_MISSING = object()


def _set_spec_digest(tmp_path: Path, value: object) -> list[str]:
    """Rewrite every recorded apt_trade meta's spec_sha256 (``_MISSING`` deletes it).

    Returns the meta paths as the baseline names them.
    """
    keys: list[str] = []
    for meta_path in sorted((tmp_path / "datago" / "apt_trade").glob("*.meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if value is _MISSING:
            del meta["spec_sha256"]
        else:
            meta["spec_sha256"] = value
        meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
            encoding="utf-8",
        )
        keys.append(meta_path.relative_to(tmp_path).as_posix())
    return keys


def _use_baseline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entries: list[str]) -> None:
    baseline = tmp_path / "legacy_evidence_baseline.txt"
    baseline.write_text("# test baseline\n" + "".join(f"{e}\n" for e in entries), encoding="utf-8")
    monkeypatch.setattr(verify_mod, "LEGACY_BASELINE", baseline)


def _binding_steps(steps: list) -> list:
    return [step for step in steps if "spec 결속" in step.name]


def test_verify_passes_baselined_legacy_evidence_without_a_spec_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fixture listed in the frozen baseline stays valid without a digest —
    retrofitting it is #522's non-goal."""
    _record_apt(tmp_path)
    monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", tmp_path)
    keys = _set_spec_digest(tmp_path, _MISSING)
    _use_baseline(tmp_path, monkeypatch, keys)

    steps = verify_mod._verify_fixtures(_spec("datago.apt_trade"))

    assert all(step.passed for step in steps)
    binding = _binding_steps(steps)
    assert binding and all("legacy" in step.detail for step in binding)
    assert all(step.passed for step in verify_mod._check_legacy_baseline())


@pytest.mark.parametrize(
    "value",
    [_MISSING, None, ""],
    ids=["deleted-key", "null", "empty-string"],
)
def test_verify_fails_a_bound_fixture_whose_digest_was_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: object
) -> None:
    """The #717 bypass: deleting the key, or setting it to null or "", on a
    fixture outside the baseline no longer passes as legacy — even after the
    spec changed, which is exactly when it used to slip through."""
    _record_apt(tmp_path)
    monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", tmp_path)
    _set_spec_digest(tmp_path, value)
    _use_baseline(tmp_path, monkeypatch, [])

    source = (Path(verify_mod.SPEC_ROOT) / "datago" / "apt_trade.yaml").read_text(encoding="utf-8")
    spec_root = tmp_path / "specs"
    (spec_root / "datago").mkdir(parents=True)
    (spec_root / "datago" / "apt_trade.yaml").write_text(
        source + "\n# a field changed after recording\n", encoding="utf-8"
    )
    monkeypatch.setattr(verify_mod, "SPEC_ROOT", spec_root)

    steps = verify_mod._verify_fixtures(_spec("datago.apt_trade"))

    binding = _binding_steps(steps)
    assert binding and not any(step.passed for step in binding)
    assert all("baseline" in step.detail and "재기록" in step.detail for step in binding)


@pytest.mark.parametrize("value", [None, ""], ids=["null", "empty-string"])
def test_a_baselined_fixture_with_a_null_or_empty_digest_still_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: object
) -> None:
    """The baseline excuses an absent key only — a recorder never writes null
    or "" any more, so those values are an edit, not legacy."""
    _record_apt(tmp_path)
    monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", tmp_path)
    keys = _set_spec_digest(tmp_path, value)
    _use_baseline(tmp_path, monkeypatch, keys)

    steps = verify_mod._verify_fixtures(_spec("datago.apt_trade"))

    binding = _binding_steps(steps)
    assert binding and not any(step.passed for step in binding)


def test_verify_fails_an_unknown_fixture_without_a_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fixture not in the baseline cannot join legacy by lacking the field,
    even while other fixtures are baselined."""
    _record_apt(tmp_path)
    monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", tmp_path)
    _set_spec_digest(tmp_path, _MISSING)
    _use_baseline(tmp_path, monkeypatch, ["datago/air_quality/seoul.meta.json"])

    steps = verify_mod._verify_fixtures(_spec("datago.apt_trade"))

    binding = _binding_steps(steps)
    assert binding and not any(step.passed for step in binding)


def test_the_baseline_fails_on_an_entry_that_now_has_a_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-recording binds the fixture; its baseline line is then stale and
    must go, or it stays a hole for the next unbound fixture at that path."""
    _record_apt(tmp_path)
    monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", tmp_path)
    keys = [p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*.meta.json")]
    _use_baseline(tmp_path, monkeypatch, keys)

    steps = verify_mod._check_legacy_baseline()

    assert not any(step.passed for step in steps)
    assert all("spec_sha256" in step.detail for step in steps)


def test_the_baseline_fails_on_an_entry_that_no_longer_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", tmp_path)
    _use_baseline(tmp_path, monkeypatch, ["datago/gone/default.meta.json"])

    steps = verify_mod._check_legacy_baseline()

    assert len(steps) == 1 and not steps[0].passed
    assert "더 이상 없음" in steps[0].detail


def test_the_baseline_rejects_a_repeated_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _record_apt(tmp_path)
    monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", tmp_path)
    keys = _set_spec_digest(tmp_path, _MISSING)
    _use_baseline(tmp_path, monkeypatch, [keys[0], keys[0]])

    steps = verify_mod._check_legacy_baseline()

    assert any(not step.passed and "중복" in step.detail for step in steps)


def test_run_verify_fails_on_a_stale_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The baseline check is wired into the verify run itself, so a stale
    entry fails `make verify` and not only this unit."""
    _use_baseline(tmp_path, monkeypatch, ["datago/gone/default.meta.json"])
    monkeypatch.setattr(verify_mod, "discover_specs", lambda: [])

    assert verify_mod.run_verify() == 1
    assert "[실패] legacy evidence baseline" in capsys.readouterr().out


def test_the_repository_baseline_is_exactly_the_unbound_fixtures() -> None:
    """Every tracked fixture without a digest is listed, every listed one is
    tracked and unbound, and the list passes its own checks. Sweeps with
    `git ls-files`, not a hand-written path list (AGENTS.md)."""
    import subprocess

    tracked = subprocess.run(
        ["git", "ls-files", "tests/fixtures/*.meta.json"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    unbound = sorted(
        path.removeprefix("tests/fixtures/")
        for path in tracked
        if "spec_sha256" not in json.loads((REPO_ROOT / path).read_text(encoding="utf-8"))
    )

    baseline = verify_mod._load_legacy_baseline()

    assert sorted(baseline) == unbound
    assert all(step.passed for step in verify_mod._check_legacy_baseline())


def test_record_aborts_when_the_spec_digest_cannot_be_computed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """record.py stops instead of writing `"spec_sha256": null` — that fixture
    would be unbound evidence the moment it was made."""
    transport = FakeLiveTransport()
    written = record_mod.record_dataset(
        "datago.apt_trade",
        fixtures_root=tmp_path / "fixtures",
        spec_root=tmp_path / "no-specs",
        config=FakeLiveConfig(),
        transport=transport,  # type: ignore[arg-type]
        recorded_by="test",
    )

    assert written == []
    assert transport.calls == []
    assert not (tmp_path / "fixtures").exists()
    assert "spec digest" in capsys.readouterr().out


def test_verify_fails_when_spec_field_changed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Changing items_path in spec fails at replay (cutover validation)."""
    _record_apt(tmp_path)
    monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", tmp_path)
    from dataclasses import replace

    spec = _spec("datago.apt_trade")
    tampered = replace(
        spec, response=replace(spec.response, items_path="response.body.items.OTHER")
    )
    steps = verify_mod._verify_fixtures(tampered)
    assert not all(step.passed for step in steps)


def _spec(dataset_id: str):
    from kpubdata.core.spec import find_spec

    spec = find_spec(dataset_id)
    assert spec is not None
    return spec


# ----------------------------------------------------------------------
# replay: matching and failure guidance
# ----------------------------------------------------------------------


def test_replay_matches_recorded_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Recorded signature (key excluded) returns fixture response."""
    _record_apt(tmp_path)
    monkeypatch.setenv("KPUBDATA_REPLAY_DIR", str(tmp_path))
    from kpubdata.transport.replay import replay_response

    response = replay_response(
        "GET",
        "http://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev",
        params={
            "serviceKey": "any-other-key",
            "pageNo": "1",
            "numOfRows": "100",
            "LAWD_CD": "11110",
            "DEAL_YMD": "202401",
            "resultType": "json",
        },
        dataset_id="datago.apt_trade",
        provider="datago",
    )
    payload = json.loads(response.content)
    assert payload["response"]["header"]["resultCode"] == "00"


def test_replay_miss_raises_with_record_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Registered dataset/endpoint fails with make record guidance if params differ."""
    _record_apt(tmp_path)
    monkeypatch.setenv("KPUBDATA_REPLAY_DIR", str(tmp_path))
    from kpubdata.exceptions import InvalidRequestError
    from kpubdata.transport.replay import replay_response

    # Unregistered dataset/endpoint bypassed (None)-unrelated calls go live.
    assert replay_response("GET", "https://never.recorded/api", params={}) is None

    # Registered combo + different params → strict fail.
    with pytest.raises(InvalidRequestError, match="make record"):
        replay_response(
            "GET",
            "http://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev",
            params={"pageNo": "99", "numOfRows": "1", "LAWD_CD": "11110", "DEAL_YMD": "202401"},
            dataset_id="datago.apt_trade",
            provider="datago",
        )


def test_client_replay_mode_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Client queries in KPUBDATA_MODE=replay served from fixtures (zero live)."""
    _record_apt(tmp_path)
    monkeypatch.setenv("KPUBDATA_REPLAY_DIR", str(tmp_path))
    monkeypatch.setenv("KPUBDATA_MODE", "replay")

    client = Client(provider_keys={"datago": "test-key"}, cache=False)
    batch = client.dataset("datago.apt_trade").list(
        LAWD_CD="11110", DEAL_YMD="202401", page=1, page_size=100
    )
    assert batch.items == [{"no": 1}, {"no": 2}]
    assert batch.total_count == 2


# ----------------------------------------------------------------------
# verify stage 4: example script replay + gen_docs_examples
# ----------------------------------------------------------------------


def test_verify_step4_missing_example_script_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Stage 4 fails if example script missing and prints contract."""
    monkeypatch.setattr(verify_mod, "REPO_ROOT", tmp_path)
    step = verify_mod._run_example_script(_spec("datago.apt_trade"))
    assert not step.passed
    assert "예제 스크립트 없음" in step.detail
    assert "examples/README.md" in step.detail


def test_gen_docs_examples_check_mode(tmp_path: Path) -> None:
    """gen_docs_examples --check catches drift."""
    import importlib.util

    script_path = SCRIPTS / "gen_docs_examples.py"
    spec = importlib.util.spec_from_file_location("gen_docs", script_path)
    assert spec is not None and spec.loader is not None
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)

    # generate → check passes
    monkeyped_out = tmp_path / "dataset-examples.md"
    gen.OUTPUT_PATH = monkeyped_out
    assert gen.main([]) == 0
    assert monkeyped_out.is_file()
    assert gen.main(["--check"]) == 0

    # drift → check fails
    monkeyped_out.write_text("손으로 수정한 내용", encoding="utf-8")
    assert gen.main(["--check"]) == 1


def test_record_with_a_fake_transport_does_not_touch_repository_specs(tmp_path: Path) -> None:
    """Fake transport recording must not update repo spec last_verified.

    Only fixtures_root was arg; spec path was REPO_ROOT-fixed; running this test
    changes src/kpubdata/specs/datago/apt_trade.yaml last_verified to today.

    That value sources SUPPORTED_DATA.md/docs/status.md/README final live API
    verification date and re-verify if >90 days rule lives here - tests updating it breaks
    the rule.
    """
    repo_spec = Path(record_mod.SPEC_ROOT) / "datago" / "apt_trade.yaml"
    before = repo_spec.read_text(encoding="utf-8")

    _ = record_mod.record_dataset(
        "datago.apt_trade",
        fixtures_root=tmp_path,
        config=FakeLiveConfig(),
        transport=FakeLiveTransport(),  # type: ignore[arg-type]
        recorded_by="agent-test",
    )

    assert repo_spec.read_text(encoding="utf-8") == before


def test_spec_root_redirects_the_last_verified_write(tmp_path: Path) -> None:
    """Pass spec_root to check only that-never touch repo path."""
    spec_root = tmp_path / "specs"
    (spec_root / "datago").mkdir(parents=True)
    target = spec_root / "datago" / "apt_trade.yaml"
    target.write_text('status: active\nlast_verified: "2020-01-01"\n', encoding="utf-8")
    repo_spec = Path(record_mod.SPEC_ROOT) / "datago" / "apt_trade.yaml"
    before = repo_spec.read_text(encoding="utf-8")

    _ = record_mod.record_dataset(
        "datago.apt_trade",
        fixtures_root=tmp_path / "fixtures",
        spec_root=spec_root,
        config=FakeLiveConfig(),
        transport=FakeLiveTransport(),  # type: ignore[arg-type]
        recorded_by="agent-test",
    )

    assert repo_spec.read_text(encoding="utf-8") == before


def test_a_live_transport_still_updates_last_verified(tmp_path: Path) -> None:
    """Live path must keep working - verification date update must persist."""
    from kpubdata.transport.http import HttpTransport

    live = HttpTransport()
    live.request = FakeLiveTransport().request  # type: ignore[method-assign]
    spec_root = tmp_path / "specs"
    (spec_root / "datago").mkdir(parents=True)
    target = spec_root / "datago" / "apt_trade.yaml"
    target.write_text('status: active\nlast_verified: "2020-01-01"\n', encoding="utf-8")

    _ = record_mod.record_dataset(
        "datago.apt_trade",
        fixtures_root=tmp_path / "fixtures",
        spec_root=spec_root,
        config=FakeLiveConfig(),
        transport=live,
        recorded_by="live",
    )

    assert '"2020-01-01"' not in target.read_text(encoding="utf-8")


# ----------------------------------------------------------------------
# example recency: a declared window fails stale examples (#734)
# ----------------------------------------------------------------------


def _recency_spec(value: object, *, max_age_days: int = 3, alias: str | None = None):
    """An apt_trade spec carrying one dated example under a declared window."""
    import dataclasses

    from kpubdata.core.spec import ExampleSpec, ParamSpec

    base = _spec("datago.apt_trade")
    param = ParamSpec(
        name="base_date", type="date_yyyymmdd", alias=alias, max_age_days=max_age_days
    )
    example = ExampleSpec(name="dated", params={param.exposed_name: value})
    return dataclasses.replace(base, params=(param,), examples=(example,))


class TestExampleRecency:
    def test_a_fresh_example_passes_with_its_age(self) -> None:
        steps = verify_mod._verify_example_recency(
            _recency_spec("20260930"), today=date(2026, 10, 1)
        )

        assert len(steps) == 1 and steps[0].passed
        assert "(1일/창 3일)" in steps[0].detail

    def test_a_stale_example_fails_naming_the_cause_and_the_refresh(self) -> None:
        steps = verify_mod._verify_example_recency(
            _recency_spec("20260920"), today=date(2026, 10, 1)
        )

        assert len(steps) == 1 and not steps[0].passed
        assert "만료" in steps[0].detail
        assert "make record" in steps[0].detail

    def test_a_future_issue_date_never_answers(self) -> None:
        """The #731 morning trap, date-shaped: an example dated tomorrow is
        not fresh — it is unanswerable."""
        steps = verify_mod._verify_example_recency(
            _recency_spec("20261002"), today=date(2026, 10, 1)
        )

        assert len(steps) == 1 and not steps[0].passed
        assert "미래" in steps[0].detail

    def test_a_spec_without_a_window_emits_nothing(self) -> None:
        """The step appears only where the contract exists — the other 24
        datasets keep their verify output unchanged."""
        assert (
            verify_mod._verify_example_recency(_spec("datago.apt_trade"), today=date(2026, 10, 1))
            == []
        )

    def test_a_window_on_a_non_date_value_is_a_spec_bug(self) -> None:
        steps = verify_mod._verify_example_recency(_recency_spec("0600"), today=date(2026, 10, 1))

        assert len(steps) == 1 and not steps[0].passed
        assert "날짜로 읽을 수 없" in steps[0].detail

    def test_the_example_is_looked_up_by_the_alias(self) -> None:
        spec = _recency_spec("20260930", alias="bd")

        steps = verify_mod._verify_example_recency(spec, today=date(2026, 10, 1))

        assert len(steps) == 1 and steps[0].passed


# ----------------------------------------------------------------------
# licence terms: allowed needs the attribution proof (#732)
# ----------------------------------------------------------------------


def _licence_spec(spec_id: str, **changes: object):
    """A real spec whose licence block is replaced field-wise."""
    import dataclasses

    base = _spec(spec_id)
    assert base.license is not None
    licence = dataclasses.replace(base.license, **changes)
    return dataclasses.replace(base, license=licence)


class TestLicenceTerms:
    def test_allowed_with_the_attribution_proof_emits_nothing(self) -> None:
        assert verify_mod._verify_licence_terms(_spec("datago.apt_trade")) == []

    def test_unknown_redistribution_emits_nothing(self) -> None:
        spec = _licence_spec("datago.apt_trade", redistribution="unknown")

        assert verify_mod._verify_licence_terms(spec) == []

    def test_a_claim_without_a_baseline_entry_fails(self) -> None:
        """The negative test #732 asks for: allowed with no attribution and no
        exemption is refused — Builder's publish gate reads exactly this flag
        (kpubdata-builder#892), and #728 shipped two such claims."""
        spec = _licence_spec("datago.apt_trade", attribution=None)

        steps = verify_mod._verify_licence_terms(spec)

        assert len(steps) == 1 and not steps[0].passed
        assert "attribution" in steps[0].detail
        assert "unknown" in steps[0].detail

    def test_a_baseline_listed_claim_passes_with_the_exemption_note(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        baseline = tmp_path / "terms.txt"
        baseline.write_text("datago.apt_trade\n", encoding="utf-8")
        monkeypatch.setattr(verify_mod, "UNCONFIRMED_TERMS_BASELINE", baseline)

        spec = _licence_spec("datago.apt_trade", attribution=None)

        steps = verify_mod._verify_licence_terms(spec)

        assert len(steps) == 1 and steps[0].passed
        assert "baseline" in steps[0].detail

    def test_a_stale_baseline_entry_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A listed spec whose terms were confirmed (attribution filled) or
        whose claim was withdrawn must leave the list — a stale entry is a
        hole a new pull request could hide behind."""
        baseline = tmp_path / "terms.txt"
        baseline.write_text("datago.apt_trade\n", encoding="utf-8")
        monkeypatch.setattr(verify_mod, "UNCONFIRMED_TERMS_BASELINE", baseline)

        steps = verify_mod._check_terms_baseline()

        assert any(not step.passed and "더 이상 위반이 아님" in step.detail for step in steps)


# ----------------------------------------------------------------------
# transport security: plain http needs its reason (#738)
# ----------------------------------------------------------------------


def _http_spec(spec_id: str, **changes: object):
    """A real spec whose endpoint block is replaced field-wise."""
    import dataclasses

    base = _spec(spec_id)
    assert base.endpoint is not None
    endpoint = dataclasses.replace(base.endpoint, **changes)
    return dataclasses.replace(base, endpoint=endpoint)


class TestInsecureHttp:
    def test_an_https_base_url_emits_nothing(self) -> None:
        assert verify_mod._verify_insecure_http(_spec("datago.bus_arrival")) == []

    def test_a_written_reason_emits_nothing(self) -> None:
        spec = _http_spec(
            "datago.apt_trade", insecure_http_reason="제공기관이 https 를 서비스하지 않는다"
        )

        assert verify_mod._verify_insecure_http(spec) == []

    def test_plain_http_without_a_baseline_entry_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        baseline = tmp_path / "insecure-http.txt"
        baseline.write_text("", encoding="utf-8")
        monkeypatch.setattr(verify_mod, "INSECURE_HTTP_BASELINE", baseline)

        steps = verify_mod._verify_insecure_http(_spec("datago.apt_trade"))

        assert len(steps) == 1 and not steps[0].passed
        assert "insecure_http_reason" in steps[0].detail

    def test_a_baseline_listed_spec_passes_with_the_exemption_note(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        baseline = tmp_path / "insecure-http.txt"
        baseline.write_text("datago.apt_trade\n", encoding="utf-8")
        monkeypatch.setattr(verify_mod, "INSECURE_HTTP_BASELINE", baseline)

        steps = verify_mod._verify_insecure_http(_spec("datago.apt_trade"))

        assert len(steps) == 1 and steps[0].passed
        assert "baseline 등록" in steps[0].detail

    def test_a_stale_baseline_entry_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        baseline = tmp_path / "insecure-http.txt"
        baseline.write_text("datago.bus_arrival\n", encoding="utf-8")
        monkeypatch.setattr(verify_mod, "INSECURE_HTTP_BASELINE", baseline)

        steps = verify_mod._check_insecure_http_baseline()

        assert any(not step.passed and "더 이상 위반이 아님" in step.detail for step in steps)


# ----------------------------------------------------------------------
# baseline ratchets: shrink-only against the base branch (#766)
# ----------------------------------------------------------------------

# Each ratchet: the module attribute naming its file, and its check.
_RATCHETS = [
    pytest.param("LEGACY_BASELINE", "_check_legacy_baseline", id="legacy-evidence"),
    pytest.param("UNCONFIRMED_TERMS_BASELINE", "_check_terms_baseline", id="unconfirmed-terms"),
    pytest.param("INSECURE_HTTP_BASELINE", "_check_insecure_http_baseline", id="insecure-http"),
]

_BASE_ENTRIES = ["entry.a", "entry.b", "entry.c"]


def _write_baseline(path: Path, entries: list[str]) -> None:
    path.write_text("# test baseline\n" + "".join(f"{e}\n" for e in entries), encoding="utf-8")


def _ratchet_failures(steps: list) -> list:
    """Steps the shrink-only comparison failed — not the staleness checks,
    which also fire here because the test entries name nothing real."""
    return [step for step in steps if not step.passed and "기준 브랜치" in step.detail]


def _run_ratchet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    attr: str,
    check: str,
    head: list[str],
    base: list[str] | None = _BASE_ENTRIES,
) -> list:
    baseline = tmp_path / "baseline.txt"
    _write_baseline(baseline, head)
    monkeypatch.setattr(verify_mod, attr, baseline)
    base_text = None if base is None else "".join(f"{e}\n" for e in base)
    monkeypatch.setattr(verify_mod, "_base_baseline_text", lambda path: base_text)
    return _ratchet_failures(getattr(verify_mod, check)())


@pytest.mark.parametrize(("attr", "check"), _RATCHETS)
class TestShrinkOnlyAgainstBase:
    def test_adding_after_a_shrink_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, attr: str, check: str
    ) -> None:
        """The list shrank by two, then gained one: still under the old size,
        which a fixed ceiling let through."""
        failures = _run_ratchet(tmp_path, monkeypatch, attr, check, ["entry.a", "entry.new"])

        assert [step.name.split("[")[1].rstrip("]") for step in failures] == ["entry.new"]
        assert "줄기만" in failures[0].detail

    def test_a_swap_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, attr: str, check: str
    ) -> None:
        """Same size as the base, one entry exchanged for a new one."""
        failures = _run_ratchet(
            tmp_path, monkeypatch, attr, check, ["entry.a", "entry.b", "entry.new"]
        )

        assert len(failures) == 1 and "entry.new" in failures[0].name

    def test_a_pure_removal_passes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, attr: str, check: str
    ) -> None:
        assert _run_ratchet(tmp_path, monkeypatch, attr, check, ["entry.a", "entry.c"]) == []

    def test_an_unchanged_baseline_passes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, attr: str, check: str
    ) -> None:
        assert _run_ratchet(tmp_path, monkeypatch, attr, check, list(_BASE_ENTRIES)) == []

    def test_a_baseline_the_base_branch_lacks_is_not_compared(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, attr: str, check: str
    ) -> None:
        """The pull request introducing a baseline sets its first contents."""
        assert _run_ratchet(tmp_path, monkeypatch, attr, check, ["entry.new"], base=None) == []

    def test_an_unreadable_base_fails_closed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, attr: str, check: str
    ) -> None:
        """Without the base, a removal and a swap look the same — so nothing
        passes, not even an unchanged list."""
        baseline = tmp_path / "baseline.txt"
        _write_baseline(baseline, list(_BASE_ENTRIES))
        monkeypatch.setattr(verify_mod, attr, baseline)

        def _unavailable(path: Path) -> str | None:
            raise verify_mod.BaselineBaseUnavailable("기준 ref `origin/main` 를 찾을 수 없음")

        monkeypatch.setattr(verify_mod, "_base_baseline_text", _unavailable)

        failures = _ratchet_failures(getattr(verify_mod, check)())

        assert len(failures) == 1
        assert "비교할 수 없음" in failures[0].detail
        assert "origin/main" in failures[0].detail


def _git(repo: Path, *args: str) -> str:
    import subprocess

    return subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=test",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def base_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repository whose ``origin/main`` lists the insecure-http baseline's
    entries, with the module pointed at it and the real git reader restored."""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _write_baseline(repo / "scripts" / "insecure_http_baseline.txt", _BASE_ENTRIES)
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    monkeypatch.setattr(verify_mod, "REPO_ROOT", repo)
    monkeypatch.setattr(
        verify_mod, "INSECURE_HTTP_BASELINE", repo / "scripts" / "insecure_http_baseline.txt"
    )
    monkeypatch.setattr(verify_mod, "_base_baseline_text", _REAL_BASE_BASELINE_TEXT)
    monkeypatch.delenv("KPUBDATA_BASELINE_BASE", raising=False)
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
    return repo


def _http_ratchet_failures() -> list:
    return _ratchet_failures(verify_mod._check_insecure_http_baseline())


class TestShrinkOnlyThroughGit:
    """The same rule end to end through git, on the baseline #765 lets the
    dataset agent commit: an agent listing its new http spec must fail."""

    @pytest.mark.parametrize(
        ("head", "added"),
        [
            pytest.param(["entry.a", "entry.new"], ["entry.new"], id="shrink-then-add"),
            pytest.param(["entry.a", "entry.b", "entry.new"], ["entry.new"], id="swap"),
            pytest.param(["entry.a", "entry.b"], [], id="pure-removal"),
        ],
    )
    def test_the_working_copy_is_judged_against_origin_main(
        self, base_repo: Path, head: list[str], added: list[str]
    ) -> None:
        _write_baseline(base_repo / "scripts" / "insecure_http_baseline.txt", head)

        failures = _http_ratchet_failures()

        assert [step.name for step in failures] == [
            f"insecure http baseline[{entry}]" for entry in added
        ]

    def test_a_committed_addition_on_the_branch_still_fails(self, base_repo: Path) -> None:
        _git(base_repo, "checkout", "-q", "-b", "agent/datago.new")
        _write_baseline(
            base_repo / "scripts" / "insecure_http_baseline.txt", [*_BASE_ENTRIES, "entry.new"]
        )
        _git(base_repo, "commit", "-q", "-am", "list the new http spec")

        failures = _http_ratchet_failures()

        assert len(failures) == 1 and "entry.new" in failures[0].name

    def test_a_branch_behind_the_base_is_judged_at_its_fork_point(self, base_repo: Path) -> None:
        """main removed entry.c after the branch forked; the branch still has
        it, which is not an addition — the merge takes main's removal."""
        _git(base_repo, "checkout", "-q", "-b", "feature")
        _git(base_repo, "checkout", "-q", "main")
        _write_baseline(
            base_repo / "scripts" / "insecure_http_baseline.txt", ["entry.a", "entry.b"]
        )
        _git(base_repo, "commit", "-q", "-am", "shrink on main")
        _git(base_repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        _git(base_repo, "checkout", "-q", "feature")

        assert _http_ratchet_failures() == []

    def test_the_base_ref_can_be_overridden(
        self, base_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _git(base_repo, "branch", "release")
        _git(base_repo, "update-ref", "-d", "refs/remotes/origin/main")
        monkeypatch.setenv("KPUBDATA_BASELINE_BASE", "release")
        _write_baseline(
            base_repo / "scripts" / "insecure_http_baseline.txt", [*_BASE_ENTRIES, "entry.new"]
        )

        failures = _http_ratchet_failures()

        assert len(failures) == 1 and "`release`" in failures[0].detail

    def test_a_pull_request_run_compares_against_its_base_branch(
        self, base_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _git(base_repo, "update-ref", "refs/remotes/origin/develop", "HEAD")
        _git(base_repo, "update-ref", "-d", "refs/remotes/origin/main")
        monkeypatch.setenv("GITHUB_BASE_REF", "develop")

        assert verify_mod._baseline_base_ref() == "origin/develop"
        assert _http_ratchet_failures() == []

    def test_a_missing_base_ref_fails_closed(self, base_repo: Path) -> None:
        """A shallow checkout without the base ref cannot tell a removal from
        a swap, so even a pure removal fails — with the fix in the message."""
        _git(base_repo, "update-ref", "-d", "refs/remotes/origin/main")
        _write_baseline(base_repo / "scripts" / "insecure_http_baseline.txt", ["entry.a"])

        failures = _http_ratchet_failures()

        assert len(failures) == 1
        assert "비교할 수 없음" in failures[0].detail
        assert "git fetch origin main" in failures[0].detail
        assert "KPUBDATA_BASELINE_BASE" in failures[0].detail

    def test_without_git_it_fails_closed(
        self, base_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PATH", "")

        failures = _http_ratchet_failures()

        assert len(failures) == 1 and "git" in failures[0].detail
