"""Phase 2 verification pipeline unit tests-verify record/verify/replay

Live calls recorded separately via make record (integration).
FakeTransport injection deterministically verifies record output files,
verify integrity rules, and replay matching rules.
"""

from __future__ import annotations

import importlib.util
import json
import sys
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


def test_verify_passes_legacy_evidence_without_a_spec_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fixtures recorded before the digest existed stay valid — retrofitting
    them is the issue's non-goal, so absence reports, not fails."""
    _record_apt(tmp_path)
    monkeypatch.setattr(verify_mod, "FIXTURES_ROOT", tmp_path)
    meta_path = next((tmp_path / "datago" / "apt_trade").glob("*.meta.json"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    del meta["spec_sha256"]
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8",
    )

    steps = verify_mod._verify_fixtures(_spec("datago.apt_trade"))

    assert all(step.passed for step in steps)
    binding = [step for step in steps if "spec 결속" in step.name]
    assert binding and "legacy" in binding[0].detail


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
