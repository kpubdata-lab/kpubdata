"""Phase 2 verification pipeline unit tests-verify record/verify/replay

Live calls recorded separately via make record (integration).
FakeTransport injection deterministically verifies record output files,
verify integrity rules, and replay matching rules.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import cast

import httpx
import pytest

from kpubdata import Client
from kpubdata.core.spec import SpecDefinition
from kpubdata.transport.http import HttpTransport

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
    monkeypatch.setattr(verify_mod, "_base_branch_entries", lambda _p: set(entries))


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


def test_the_baseline_may_not_grow_past_the_base_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _record_apt(tmp_path)
    monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", tmp_path)
    keys = _set_spec_digest(tmp_path, _MISSING)
    _use_baseline(tmp_path, monkeypatch, keys)
    monkeypatch.setattr(verify_mod, "_base_branch_entries", lambda _p: set())

    steps = verify_mod._check_legacy_baseline()

    assert any(not step.passed and "기준 브랜치에 없던 항목" in step.detail for step in steps)


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


def test_the_repository_baseline_is_exactly_the_unbound_fixtures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every tracked fixture without a digest is listed and every listed one
    is tracked and unbound. Sweeps with `git ls-files`, not a hand-written
    path list (AGENTS.md). Growth past the base branch is the check's own
    job now (#766), not this inventory's."""
    monkeypatch.setenv("KPUBDATA_BASELINE_BASE", "HEAD")
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


def test_verify_fails_when_items_path_misses_the_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A recording with a total but no rows fails, even when expected agrees with it."""
    import shutil

    spec_root = tmp_path / "specs"
    shutil.copytree(SPECS_DIR / "datago", spec_root / "datago")
    spec_file = spec_root / "datago" / "apt_trade.yaml"
    text = spec_file.read_text(encoding="utf-8")
    line = next(row for row in text.splitlines() if row.strip().startswith("items_path:"))
    spec_file.write_text(
        text.replace(line, "  items_path: response.body.items.missing"), encoding="utf-8"
    )
    fixtures = tmp_path / "fixtures"
    record_mod.record_dataset(
        "datago.apt_trade",
        fixtures_root=fixtures,
        spec_root=spec_root,
        config=FakeLiveConfig(),
        transport=cast(HttpTransport, cast(object, FakeLiveTransport())),
        recorded_by="test",
    )
    # The snapshot agrees with what the wrong path extracts, as it did for
    # datago.airkorea_forecast: no rows, a positive total.
    for expected_file in (fixtures / "datago" / "apt_trade").glob("*.expected.json"):
        snapshot = json.loads(expected_file.read_text(encoding="utf-8"))
        expected_file.write_text(json.dumps({**snapshot, "items": []}), encoding="utf-8")
    monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", fixtures)
    monkeypatch.setattr(verify_mod, "SPEC_ROOT", spec_root)
    from kpubdata.core.spec import load_spec_file

    steps = verify_mod._verify_fixtures(load_spec_file(spec_file))
    assert any("레코드 추출" in step.name and not step.passed for step in steps)


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
        "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev",
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
            "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev",
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


def _live_record(spec_root: Path, fixtures: Path) -> list[Path]:
    from kpubdata.transport.http import HttpTransport

    live = HttpTransport()
    live.request = FakeLiveTransport().request  # type: ignore[method-assign]
    return record_mod.record_dataset(
        "datago.apt_trade",
        fixtures_root=fixtures,
        spec_root=spec_root,
        config=FakeLiveConfig(),
        transport=live,
        recorded_by="live",
    )


def _spec_root_holding(tmp_path: Path, text: str) -> Path:
    spec_root = tmp_path / "specs"
    (spec_root / "datago").mkdir(parents=True)
    (spec_root / "datago" / "apt_trade.yaml").write_text(text, encoding="utf-8")
    return spec_root


@pytest.mark.parametrize(
    "line",
    [
        'last_verified: "2020-01-01"\n',
        "last_verified: '2020-01-01'\n",
        'last_verified: "2020-01-01"',
        "",
    ],
)
def test_a_live_record_stays_bound_after_the_last_verified_sync(
    line: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The sync after a record must not void the record it just made."""
    spec_root = _spec_root_holding(tmp_path, "id: datago.apt_trade\nstatus: active\n" + line)
    fixtures = tmp_path / "fixtures"

    written = _live_record(spec_root, fixtures)

    assert written
    synced = (spec_root / "datago" / "apt_trade.yaml").read_text(encoding="utf-8")
    assert synced.count("last_verified: ") == 1 and "2020-01-01" not in synced
    monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", fixtures)
    monkeypatch.setattr(verify_mod, "SPEC_ROOT", spec_root)
    binding = _binding_steps(verify_mod._verify_fixtures(_spec("datago.apt_trade")))
    assert binding and all(step.passed for step in binding)


@pytest.mark.parametrize(
    "line",
    [
        "last_verified: 2020-01-01\n",
        'last_verified: "2020-01-01"  # checked by hand\n',
        'last_verified: "2020-1-1"\n',
        'last_verified: "2020-01-01"\u2028endpoint: {operation: getEvil}\n',
    ],
)
def test_a_last_verified_line_the_digest_keeps_stops_the_record(
    line: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The sync would rewrite this line and void the record, so nothing is recorded."""
    original = "id: datago.apt_trade\nstatus: active\n" + line
    spec_root = _spec_root_holding(tmp_path, original)
    fixtures = tmp_path / "fixtures"

    written = _live_record(spec_root, fixtures)

    assert written == []
    assert not list(fixtures.rglob("*.json"))
    assert (spec_root / "datago" / "apt_trade.yaml").read_text(encoding="utf-8") == original
    assert 'last_verified: "YYYY-MM-DD"' in capsys.readouterr().out


def test_the_inserted_last_verified_follows_the_top_level_status_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`status: active` inside another value is not the status line."""
    spec_root = _spec_root_holding(
        tmp_path, 'id: datago.apt_trade\nnote: "status: active only on weekdays"\nstatus: active\n'
    )
    fixtures = tmp_path / "fixtures"

    assert _live_record(spec_root, fixtures)

    synced = (spec_root / "datago" / "apt_trade.yaml").read_text(encoding="utf-8")
    assert 'note: "status: active only on weekdays"\nstatus: active\nlast_verified: "' in synced
    monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", fixtures)
    monkeypatch.setattr(verify_mod, "SPEC_ROOT", spec_root)
    binding = _binding_steps(verify_mod._verify_fixtures(_spec("datago.apt_trade")))
    assert binding and all(step.passed for step in binding)


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

    def test_a_one_for_one_swap_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """#766: a swap never moved the count — the set comparison is what stops it."""
        base = [
            "datago.air_station",
            "datago.airkorea_forecast",
            "datago.hospital_info",
            "datago.metro_fare",
            "datago.ocean_buoy",
            "datago.offi_rent",
            "datago.offi_trade",
            "datago.rh_rent",
            "datago.sh_rent",
            "datago.sh_trade",
            "datago.tour_kor_area",
            "datago.tour_kor_festival",
            "datago.tour_kor_keyword",
            "datago.tour_kor_location",
            "datago.ultra_srt_fcst",
            "datago.ultra_srt_ncst",
        ]
        baseline = tmp_path / "terms.txt"
        baseline.write_text("\n".join(base[1:] + ["datago.apt_trade"]) + "\n", encoding="utf-8")
        monkeypatch.setattr(verify_mod, "UNCONFIRMED_TERMS_BASELINE", baseline)
        monkeypatch.setattr(verify_mod, "_base_branch_entries", lambda _p: set(base))

        steps = verify_mod._check_terms_baseline()

        assert any(not step.passed and "기준 브랜치에 없던 항목" in step.detail for step in steps)
        assert any("datago.apt_trade" in step.detail for step in steps if not step.passed)


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


def _unconfirmed_terms_spec(spec_id: str):
    """A real spec whose licence claims redistribution without the attribution text."""
    import dataclasses

    from kpubdata.core.spec import LicenseSpec

    base = _spec(spec_id)
    licence = LicenseSpec(type="공공누리_1유형", redistribution="allowed")
    return dataclasses.replace(base, license=licence)


#: A plain-http base_url, set on a spec by hand: the bundled specs move to https one by
#: one (#893), so no real spec is relied on to still be on http.
_HTTP_URL = "http://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev"


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

        steps = verify_mod._verify_insecure_http(_http_spec("datago.apt_trade", base_url=_HTTP_URL))

        assert len(steps) == 1 and not steps[0].passed
        assert "insecure_http_reason" in steps[0].detail

    def test_a_baseline_listed_spec_passes_with_the_exemption_note(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        baseline = tmp_path / "insecure-http.txt"
        baseline.write_text("datago.apt_trade\n", encoding="utf-8")
        monkeypatch.setattr(verify_mod, "INSECURE_HTTP_BASELINE", baseline)

        steps = verify_mod._verify_insecure_http(_http_spec("datago.apt_trade", base_url=_HTTP_URL))

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

    def test_an_added_entry_fails_after_a_shrink(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """#766: a slot freed by a conversion is not refillable — count ceilings allowed that."""
        base = [
            "datago.air_quality",
            "datago.air_station",
            "datago.airkorea_forecast",
            "datago.apt_rent",
            "datago.apt_trade",
            "datago.hospital_info",
            "datago.metro_fare",
            "datago.ocean_buoy",
            "datago.offi_rent",
            "datago.offi_trade",
            "datago.rh_rent",
            "datago.sh_rent",
            "datago.sh_trade",
            "datago.tour_kor_area",
            "datago.tour_kor_festival",
            "datago.tour_kor_keyword",
            "datago.tour_kor_location",
            "datago.ultra_srt_fcst",
            "datago.ultra_srt_ncst",
            "datago.village_fcst",
            "localdata.bakery",
            "localdata.general_restaurant",
            "localdata.rest_cafe",
        ]
        baseline = tmp_path / "insecure-http.txt"
        baseline.write_text("\n".join(base[:-1] + ["datago.bus_arrival"]) + "\n", encoding="utf-8")
        monkeypatch.setattr(verify_mod, "INSECURE_HTTP_BASELINE", baseline)
        monkeypatch.setattr(verify_mod, "_base_branch_entries", lambda _p: set(base))

        steps = verify_mod._check_insecure_http_baseline()

        assert any(not step.passed and "기준 브랜치에 없던 항목" in step.detail for step in steps)
        assert any("datago.bus_arrival" in step.detail for step in steps if not step.passed)


# ----------------------------------------------------------------------
# baseline ratchets: shrink-only against the base branch (#766)
# ----------------------------------------------------------------------

_TERM_ENTRIES = ["datago.ultra_srt_fcst", "datago.ultra_srt_ncst"]
_HTTP_ENTRIES = ["datago.village_fcst", "datago.apt_trade"]


@pytest.mark.parametrize(
    ("baseline_attr", "check_attr", "entries"),
    [
        pytest.param(
            "UNCONFIRMED_TERMS_BASELINE", "_check_terms_baseline", _TERM_ENTRIES, id="terms"
        ),
        pytest.param(
            "INSECURE_HTTP_BASELINE",
            "_check_insecure_http_baseline",
            _HTTP_ENTRIES,
            id="insecure-http",
        ),
    ],
)
def test_a_pure_removal_passes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    baseline_attr: str,
    check_attr: str,
    entries: list[str],
) -> None:
    """Dropping an entry is the one change a baseline may carry (#766).

    Only the spec-id ratchets run here — the legacy one reads fixture
    metas, which tmp entries do not have; its shrink direction runs
    through the same shared `_check_shrink_only` either way.
    """
    baseline = tmp_path / "baseline.txt"
    baseline.write_text(entries[0] + "\n", encoding="utf-8")
    monkeypatch.setattr(verify_mod, baseline_attr, baseline)
    monkeypatch.setattr(verify_mod, "_base_branch_entries", lambda _p: set(entries))
    if baseline_attr == "INSECURE_HTTP_BASELINE":
        # The real specs move to https one by one (#893); keep the kept entry on http.
        http_specs = [_http_spec(entry, base_url=_HTTP_URL) for entry in entries]
        monkeypatch.setattr(verify_mod, "discover_specs", lambda: http_specs)
    else:
        # The real specs have their terms confirmed one by one (#933); keep the kept
        # entry unconfirmed by hand: allowed, with no attribution text.
        unconfirmed = [_unconfirmed_terms_spec(entry) for entry in entries]
        monkeypatch.setattr(verify_mod, "discover_specs", lambda: unconfirmed)

    steps = getattr(verify_mod, check_attr)()

    assert all(step.passed for step in steps)


@pytest.mark.parametrize(
    "check_attr",
    ["_check_legacy_baseline", "_check_terms_baseline", "_check_insecure_http_baseline"],
)
def test_the_ratchet_fails_closed_when_the_base_cannot_be_read(
    monkeypatch: pytest.MonkeyPatch, check_attr: str
) -> None:
    """A ratchet that cannot see its anchor is not a ratchet (#766)."""
    monkeypatch.setattr(verify_mod, "_base_branch_entries", lambda _p: None)

    steps = getattr(verify_mod, check_attr)()

    assert any(not step.passed and "읽을 수 없다" in step.detail for step in steps)


# ----------------------------------------------------------------------
# the base-ref reader: explicit, never a HEAD fallback (#766 review)
# ----------------------------------------------------------------------


def _base_ref_repo(tmp_path: Path) -> Path:
    """A tiny repository whose HEAD carries one baseline file."""
    import subprocess

    baseline = tmp_path / "scripts" / "insecure_http_baseline.txt"
    baseline.parent.mkdir(parents=True)
    baseline.write_text("# header\ndatago.apt_trade\n", encoding="utf-8")
    for command in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "test@kpubdata.local"],
        ["git", "config", "user.name", "test"],
        ["git", "add", "-A"],
        ["git", "commit", "-qm", "init"],
    ):
        subprocess.run(command, cwd=tmp_path, check=True)
    return tmp_path


def test_without_a_configured_ref_it_is_none_even_though_head_carries_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No KPUBDATA_BASELINE_BASE → None. HEAD must not substitute (#766
    review): in a pull request's CI it holds the PR's own baseline, and
    the ratchet would compare the file against itself."""
    root = _base_ref_repo(tmp_path)
    monkeypatch.setattr(verify_mod, "REPO_ROOT", root)
    monkeypatch.delenv("KPUBDATA_BASELINE_BASE", raising=False)

    assert verify_mod._base_branch_entries(root / "scripts" / "insecure_http_baseline.txt") is None


def test_an_unresolvable_ref_is_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _base_ref_repo(tmp_path)
    monkeypatch.setattr(verify_mod, "REPO_ROOT", root)
    monkeypatch.setenv("KPUBDATA_BASELINE_BASE", "origin/main")

    assert verify_mod._base_branch_entries(root / "scripts" / "insecure_http_baseline.txt") is None


def test_a_resolved_ref_without_the_file_is_the_empty_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bootstrap rule: a baseline the ref does not carry starts from
    the empty set, so its creating change counts every entry as an
    addition (#766)."""
    root = _base_ref_repo(tmp_path)
    monkeypatch.setattr(verify_mod, "REPO_ROOT", root)
    monkeypatch.setenv("KPUBDATA_BASELINE_BASE", "HEAD")

    assert (
        verify_mod._base_branch_entries(root / "scripts" / "unconfirmed_terms_baseline.txt")
        == set()
    )


def test_a_resolved_ref_reads_its_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _base_ref_repo(tmp_path)
    monkeypatch.setattr(verify_mod, "REPO_ROOT", root)
    monkeypatch.setenv("KPUBDATA_BASELINE_BASE", "HEAD")

    entries = verify_mod._base_branch_entries(root / "scripts" / "insecure_http_baseline.txt")

    assert entries == {"datago.apt_trade"}


# ----------------------------------------------------------------------
# broken/unstable specs: live steps skipped, offline integrity kept
# ----------------------------------------------------------------------


def _status_spec(status: str, **endpoint_changes: object) -> SpecDefinition:
    """apt_trade under another status, its endpoint optionally changed."""
    import dataclasses

    spec = _http_spec("datago.apt_trade", **endpoint_changes) if endpoint_changes else None
    return dataclasses.replace(spec or _spec("datago.apt_trade"), status=status)


def _run_full_verify(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    spec: object,
    *,
    example_ok: bool = True,
) -> tuple[int, list[str]]:
    """Run `make verify` over one spec, offline: the schema subprocess and the
    once-per-run baselines are stubbed, and the example step is recorded."""
    import subprocess
    from types import SimpleNamespace

    ran: list[str] = []

    def fake_example(target: object) -> object:
        ran.append(getattr(target, "id", ""))
        detail = "" if example_ok else "replay 실행 실패: example broken"
        return verify_mod.StepResult("examples 실행", passed=example_ok, detail=detail)

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(verify_mod, "subprocess", SimpleNamespace(run=fake_run))
    monkeypatch.setattr(verify_mod, "discover_specs", lambda: [spec])
    monkeypatch.setattr(verify_mod, "_check_legacy_baseline", lambda: [])
    monkeypatch.setattr(verify_mod, "_check_terms_baseline", lambda: [])
    monkeypatch.setattr(verify_mod, "_check_insecure_http_baseline", lambda: [])
    monkeypatch.setattr(verify_mod, "_run_example_script", fake_example)
    empty = tmp_path / "empty-baseline.txt"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setattr(verify_mod, "INSECURE_HTTP_BASELINE", empty)
    monkeypatch.setattr(verify_mod, "UNCONFIRMED_TERMS_BASELINE", empty)
    monkeypatch.delenv("LIVE", raising=False)
    return verify_mod.run_verify(), ran


def _tamper_raw(fixtures: Path) -> None:
    raw_file = next((fixtures / "datago" / "apt_trade").glob("*.raw.json"))
    payload = json.loads(raw_file.read_text(encoding="utf-8"))
    payload["response"]["body"]["totalCount"] = "999"
    raw_file.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=1) + "\n", encoding="utf-8"
    )


@pytest.mark.parametrize("status", ["broken", "unstable"])
class TestSkippableStatusKeepsOfflineChecks:
    """`status: broken` must not dodge verification (AGENTS.md): only the steps
    that need a working dataset are skipped."""

    def test_a_tampered_fixture_digest_fails(
        self, status: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fixtures = tmp_path / "fixtures"
        _record_apt(fixtures)
        _tamper_raw(fixtures)
        monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", fixtures)

        code, _ran = _run_full_verify(monkeypatch, tmp_path, _status_spec(status))

        assert code == 1

    def test_unjustified_plain_http_fails_the_transport_check(
        self,
        status: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        fixtures = tmp_path / "fixtures"
        _record_apt(fixtures)
        monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", fixtures)
        spec = _status_spec(status, base_url=_HTTP_URL)

        code, _ran = _run_full_verify(monkeypatch, tmp_path, spec)

        assert code == 1
        assert "전송 보안[datago.apt_trade]" in capsys.readouterr().out

    def test_unconfirmed_terms_fail_the_licence_check(
        self, status: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import dataclasses

        fixtures = tmp_path / "fixtures"
        _record_apt(fixtures)
        monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", fixtures)
        spec = dataclasses.replace(_unconfirmed_terms_spec("datago.apt_trade"), status=status)

        code, _ran = _run_full_verify(monkeypatch, tmp_path, spec)

        assert code == 1

    def test_a_failing_example_is_still_skipped(
        self,
        status: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The intended skip: the example (and recency, live diff) needs the dataset."""
        fixtures = tmp_path / "fixtures"
        _record_apt(fixtures)
        monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", fixtures)

        code, ran = _run_full_verify(monkeypatch, tmp_path, _status_spec(status), example_ok=False)

        assert code == 0
        assert ran == []
        assert f"status={status}" in capsys.readouterr().out

    def test_no_fixtures_at_all_is_allowed(
        self, status: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A dataset whose recording is impossible (application pending) has none."""
        monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", tmp_path / "no-fixtures")

        code, ran = _run_full_verify(monkeypatch, tmp_path, _status_spec(status))

        assert code == 0
        assert ran == []

    def test_an_orphan_meta_without_its_raw_fails(
        self, status: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Deleting the raw file cannot turn recorded evidence into 'no fixtures'."""
        fixtures = tmp_path / "fixtures"
        _record_apt(fixtures)
        for raw_file in (fixtures / "datago" / "apt_trade").glob("*.raw.json"):
            raw_file.unlink()
        monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", fixtures)

        code, _ran = _run_full_verify(monkeypatch, tmp_path, _status_spec(status))

        assert code == 1


class TestActiveStatusUnchanged:
    def test_a_failing_example_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        fixtures = tmp_path / "fixtures"
        _record_apt(fixtures)
        monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", fixtures)

        code, ran = _run_full_verify(
            monkeypatch, tmp_path, _status_spec("active"), example_ok=False
        )

        assert code == 1
        assert ran == ["datago.apt_trade"]

    def test_a_clean_spec_passes_and_runs_its_example(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fixtures = tmp_path / "fixtures"
        _record_apt(fixtures)
        monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", fixtures)

        code, ran = _run_full_verify(monkeypatch, tmp_path, _status_spec("active"))

        assert code == 0
        assert ran == ["datago.apt_trade"]

    def test_missing_fixtures_still_fail(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", tmp_path / "no-fixtures")

        code, _ran = _run_full_verify(monkeypatch, tmp_path, _status_spec("active"))

        assert code == 1

    def test_a_tampered_fixture_digest_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fixtures = tmp_path / "fixtures"
        _record_apt(fixtures)
        _tamper_raw(fixtures)
        monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", fixtures)

        code, _ran = _run_full_verify(monkeypatch, tmp_path, _status_spec("active"))

        assert code == 1


# ----------------------------------------------------------------------
# spec binding tolerates a change confined to the status line (#1117)
# ----------------------------------------------------------------------


def _spec_root_with(tmp_path: Path, edit: Callable[[str], str]) -> Path:
    """Copy apt_trade.yaml under tmp_path, passing its text through ``edit``."""
    source = (Path(verify_mod.SPEC_ROOT) / "datago" / "apt_trade.yaml").read_text(encoding="utf-8")
    assert source.count("\nstatus: active\n") == 1
    spec_root = tmp_path / "specs"
    (spec_root / "datago").mkdir(parents=True)
    (spec_root / "datago" / "apt_trade.yaml").write_text(edit(source), encoding="utf-8")
    return spec_root


def _as_status(status: str) -> Callable[[str], str]:
    return lambda text: text.replace("\nstatus: active\n", f"\nstatus: {status}\n")


@pytest.mark.parametrize("status", ["broken", "unstable", "deprecated"])
def test_a_status_only_change_keeps_the_evidence_bound(
    status: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Marking a recorded spec broken must not void its fixtures."""
    _record_apt(tmp_path)
    monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", tmp_path)
    monkeypatch.setattr(verify_mod, "SPEC_ROOT", _spec_root_with(tmp_path, _as_status(status)))

    steps = verify_mod._verify_fixtures(_spec("datago.apt_trade"))

    binding = _binding_steps(steps)
    assert binding and all(step.passed for step in binding)
    assert all("기록 당시 status: active" in step.detail for step in binding)
    assert all(step.passed for step in steps)


def test_a_status_change_with_any_other_edit_still_voids_the_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _record_apt(tmp_path)
    monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", tmp_path)
    spec_root = _spec_root_with(
        tmp_path, lambda text: _as_status("broken")(text) + "\n# a field changed too\n"
    )
    monkeypatch.setattr(verify_mod, "SPEC_ROOT", spec_root)

    steps = verify_mod._verify_fixtures(_spec("datago.apt_trade"))

    binding = _binding_steps(steps)
    assert binding and not any(step.passed for step in binding)
    assert all("재기록" in step.detail for step in binding)


def test_a_spec_with_two_status_lines_gets_no_tolerance(tmp_path: Path) -> None:
    """With two top-level status lines, substituting both could match a recording
    that differs in more than one line, so neither is tolerated."""
    from kpubdata.core.spec import spec_file_digest

    source = (Path(verify_mod.SPEC_ROOT) / "datago" / "apt_trade.yaml").read_text(encoding="utf-8")
    recorded_path = tmp_path / "recorded.yaml"
    recorded_path.write_text(source + "status: active\n", encoding="utf-8")
    recorded = spec_file_digest(recorded_path)
    assert recorded is not None
    current = tmp_path / "apt_trade.yaml"
    current.write_text(_as_status("broken")(source) + "status: broken\n", encoding="utf-8")

    assert verify_mod._status_recorded_under(current, recorded) is None


@pytest.mark.parametrize("brk", ["\x85", "\u2028", "\u2029"])
@pytest.mark.parametrize("status", ["broken", "active"])
def test_a_key_hidden_on_the_status_line_voids_the_evidence(
    brk: str, status: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """YAML starts a new line at these characters, so the text after one can
    redefine the endpoint; the status tolerance must not cover it."""
    _record_apt(tmp_path)
    monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", tmp_path)
    injected = "endpoint: {base_url: 'https://evil.example/x', operation: getEvil}"
    spec_root = _spec_root_with(
        tmp_path,
        lambda text: text.replace("\nstatus: active\n", f"\nstatus: {status}{brk}{injected}\n"),
    )
    monkeypatch.setattr(verify_mod, "SPEC_ROOT", spec_root)

    steps = verify_mod._verify_fixtures(_spec("datago.apt_trade"))

    binding = _binding_steps(steps)
    assert binding and not any(step.passed for step in binding)


@pytest.mark.parametrize(
    "line", ['status: "broken"', "status: broken  # dataset down", "status: 'broken'"]
)
def test_only_a_bare_status_value_is_tolerated(
    line: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _record_apt(tmp_path)
    monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", tmp_path)
    spec_root = _spec_root_with(
        tmp_path, lambda text: text.replace("\nstatus: active\n", f"\n{line}\n")
    )
    monkeypatch.setattr(verify_mod, "SPEC_ROOT", spec_root)

    steps = verify_mod._verify_fixtures(_spec("datago.apt_trade"))

    assert not any(step.passed for step in _binding_steps(steps))


def test_an_unchanged_spec_reports_no_status_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _record_apt(tmp_path)
    monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", tmp_path)

    steps = verify_mod._verify_fixtures(_spec("datago.apt_trade"))

    binding = _binding_steps(steps)
    assert binding and all(step.passed and "status" not in step.detail for step in binding)


def test_a_recorded_spec_marked_broken_passes_a_full_verify(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The draft PR's reproducer: a recorded spec flipped to broken, its example
    failing. Offline checks pass on the old evidence; the example is skipped."""
    fixtures = tmp_path / "fixtures"
    _record_apt(fixtures)
    monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", fixtures)
    monkeypatch.setattr(verify_mod, "SPEC_ROOT", _spec_root_with(tmp_path, _as_status("broken")))

    code, ran = _run_full_verify(monkeypatch, tmp_path, _status_spec("broken"), example_ok=False)

    assert code == 0
    assert ran == []


def test_spec_statuses_match_the_schema() -> None:
    schema = json.loads(
        (REPO_ROOT / "src" / "kpubdata" / "specs" / "schema.json").read_text(encoding="utf-8")
    )
    assert set(verify_mod.SPEC_STATUSES) == set(schema["properties"]["status"]["enum"])
