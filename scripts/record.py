"""Fixture recording tool — records validation assets by calling live APIs with spec examples[].

Usage:
    KPUBDATA_DATAGO_API_KEY=... uv run python scripts/record.py datago.apt_trade
    make record DATASET=datago.apt_trade

For each example of the dataset it leaves three files:
- ``{example}.raw.json``      — the sanitized original payload
- ``{example}.meta.json``     — call time, endpoint, params (key excluded),
  hash, and the recording identity
- ``{example}.expected.json`` — snapshot of the normalized result
  (items, total_count)

A fixture without meta fails verification (blocking the path where an
agent fabricates fixtures).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from redact import redact_mapping

from kpubdata.config import KPubDataConfig
from kpubdata.core.executor import (
    SpecExecutor,
    check_payload_error,
    extract_items,
    extract_total_count,
)
from kpubdata.core.models import Query
from kpubdata.core.spec import find_spec, spec_file_digest
from kpubdata.transport.http import HttpTransport

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures"
#: Canonical location of spec file. ``record_dataset`` updates ``last_verified``.
#: Passed as argument so tests don't touch repository source.
SPEC_ROOT = REPO_ROOT / "src" / "kpubdata" / "specs"
_DEFAULT_PAGE_SIZE = 10


def _canon(obj: object) -> str:
    """Canonical JSON serialization for hash comparison (ensure_ascii=False, fixed newlines)."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=1) + "\n"


def _is_live_transport(transport: object) -> bool:
    """Whether this transport uses live network.

    A call with a fake transport injected (a unit test) is not a live call,
    so it must not update the verification date. A call with a real
    ``HttpTransport`` explicitly injected IS live and updates it — the
    criterion is "what was injected", not "whether something was".
    """
    return isinstance(transport, HttpTransport)


def record_dataset(
    dataset_id: str,
    *,
    fixtures_root: Path = FIXTURES_ROOT,
    spec_root: Path = SPEC_ROOT,
    config: KPubDataConfig | None = None,
    transport: HttpTransport | None = None,
    recorded_by: str | None = None,
) -> list[Path]:
    """Record all examples via live call and save 3 fixture files.

    Raises:
        SystemExit: No spec, or no key (with a human-readable notice).
    """
    spec = find_spec(dataset_id)
    if spec is None:
        print(f"오류: spec을 찾을 수 없습니다: {dataset_id}")
        return []

    resolved_config = config or KPubDataConfig.from_env()
    resolved_transport = transport or HttpTransport()
    executor = SpecExecutor(resolved_transport, resolved_config)

    provider_key = spec.auth.provider_key or spec.provider
    api_key = resolved_config.get_provider_key(provider_key)
    if api_key is None:
        print(
            f"오류: {provider_key} API 키가 없습니다. "
            f"KPUBDATA_{provider_key.upper()}_API_KEY 를 설정하세요."
        )
        return []

    out_dir = fixtures_root / spec.provider / spec.dataset_key
    out_dir.mkdir(parents=True, exist_ok=True)

    # Evidence binding (#522): the spec content this record executed, and —
    # when the environment says so — the commit and the run that executed it.
    # `spec_file_digest` ignores the last_verified line this function syncs
    # below, so that sync does not void the record it just made.
    spec_path = spec_root / spec.provider / f"{spec.dataset_key}.yaml"
    spec_sha = spec_file_digest(spec_path)
    run_binding: dict[str, str] = {}
    commit = os.environ.get("KPUBDATA_RECORD_COMMIT") or os.environ.get("GITHUB_SHA")
    if commit:
        run_binding["record_commit"] = commit
    run_ref = os.environ.get("KPUBDATA_RECORD_RUN") or os.environ.get("GITHUB_RUN_ID")
    if run_ref:
        run_binding["run_ref"] = run_ref

    written: list[Path] = []
    for example in spec.examples:
        query = Query(
            filters=dict(example.params),
            page=example.page or 1,
            page_size=example.page_size or _DEFAULT_PAGE_SIZE,
        )
        params, payload = executor.fetch(spec, query, format_hint=example.format)
        check_payload_error(spec, payload)

        safe_params = redact_mapping(params, secrets=(api_key,))
        safe_payload = redact_mapping(payload, secrets=(api_key,))
        # expected extracted from same source as sanitized raw — verify replays sanitized
        # so pair must match (reflects phone number etc. substitutions).
        items = extract_items(spec, safe_payload)
        total = extract_total_count(spec, safe_payload)
        payload_text = _canon(safe_payload)

        raw_path = out_dir / f"{example.name}.raw.json"
        meta_path = out_dir / f"{example.name}.meta.json"
        expected_path = out_dir / f"{example.name}.expected.json"

        meta = {
            "dataset_id": spec.id,
            "example": example.name,
            "recorded_at": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
            "endpoint": f"{spec.endpoint.base_url.rstrip('/')}/{spec.endpoint.operation}",
            "params": safe_params,
            "format": example.format or spec.response.format,
            "response_sha256": hashlib.sha256(payload_text.encode("utf-8")).hexdigest(),
            "spec_sha256": spec_sha,
            "recorded_by": recorded_by
            or os.environ.get("KPUBDATA_RECORDER")
            or ("ci" if os.environ.get("CI") else "human"),
        }
        meta.update(run_binding)

        raw_path.write_text(payload_text, encoding="utf-8")
        meta_path.write_text(_canon(meta), encoding="utf-8")
        expected_path.write_text(_canon({"items": items, "total_count": total}), encoding="utf-8")
        written.extend([raw_path, meta_path, expected_path])
        shown = raw_path.relative_to(REPO_ROOT) if raw_path.is_relative_to(REPO_ROOT) else raw_path
        print(f"기록: {shown} ({len(items)}건, total={total})")

    # Record success → sync spec's last_verified to today (verification date reliability).
    #
    # Write only after checking both:
    #
    # 1) Path: use ``spec_root``. Previously, even when ``fixtures_root`` was passed as tmp,
    #    spec path was fixed to REPO_ROOT only, so unit tests modified repository source.
    # 2) Live call check: records from fake transport are not "live API final verification date".
    #    ``last_verified`` is the source for SUPPORTED_DATA.md, docs/status.md, README tables
    #    "re-verify if >90 days" rule hangs here — if tests update it, that rule
    #    no longer holds.
    if _is_live_transport(resolved_transport) and spec_path.is_file():
        text = spec_path.read_text(encoding="utf-8")
        today = datetime.now(tz=timezone.utc).date().isoformat()
        if re.search(r"^last_verified:", text, re.MULTILINE):
            text = re.sub(
                r"^last_verified:.*$", f'last_verified: "{today}"', text, flags=re.MULTILINE
            )
        else:
            text = text.replace("status: active", f'status: active\nlast_verified: "{today}"', 1)
        spec_path.write_text(text, encoding="utf-8")

    # Clean up old fixtures for examples removed from spec (tool hygiene — not manual edit)
    declared = {example.name for example in spec.examples}
    for stale in out_dir.glob("*.raw.json"):
        stale_name = stale.name.removesuffix(".raw.json")
        if stale_name not in declared:
            for suffix in (".raw.json", ".meta.json", ".expected.json"):
                (out_dir / f"{stale_name}{suffix}").unlink(missing_ok=True)
            print(f"정리: 낡은 예제 fixture {stale_name}")

    return written


def _spec_ids() -> list[str]:
    """Return bundle spec id list."""
    from kpubdata.core.spec import discover_specs

    return [spec.id for spec in discover_specs()]


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="spec examples 실호출 fixture 기록")
    parser.add_argument("dataset", nargs="?", help="데이터셋 id (예: datago.apt_trade)")
    parser.add_argument("--list", action="store_true", help="기록 가능한 spec id 나열")
    args = parser.parse_args(argv)

    if args.list or not args.dataset:
        for spec_id in _spec_ids():
            print(spec_id)
        return 0

    written = record_dataset(args.dataset)
    return 0 if written else 1


if __name__ == "__main__":
    sys.exit(main())
