"""Batch recorder — records all specs from a provider in fast-fail mode and collects results.

Usage:
    uv run python scripts/batch_record.py --provider localdata [--limit N]

- Transport settings: 15s timeout, zero retries (failing datasets must not
  slow the batch)
- Result: the success/failure list is written as JSON to
  ``tests/fixtures/batch-record-{provider}.json``
- Failures (required params, retirement, permissions) are normal results —
  skipped and classified into the backlog
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from record import record_dataset

from kpubdata.config import KPubDataConfig
from kpubdata.core.spec import discover_specs
from kpubdata.transport.http import HttpTransport, TransportConfig

REPO_ROOT = Path(__file__).resolve().parents[1]


def batch_record(provider: str, *, limit: int | None = None) -> dict[str, list[str]]:
    """Record all specs from provider and return success/failure summary."""
    config = KPubDataConfig.from_env()
    fast_transport = HttpTransport(config=TransportConfig(timeout=15, max_retries=0, cache=None))
    specs = [spec for spec in discover_specs() if spec.provider == provider]
    if limit is not None:
        specs = specs[:limit]

    ok: list[str] = []
    failed: list[list[str]] = []
    for spec in specs:
        try:
            written = record_dataset(
                spec.id, config=config, transport=fast_transport, recorded_by="batch-agent"
            )
            if written:
                ok.append(spec.id)
            else:
                failed.append([spec.id, "키 없음"])
        except Exception as exc:  # noqa: BLE001 — batch collects all failures
            failed.append([spec.id, f"{type(exc).__name__}: {str(exc)[:120]}"])
            print(f"실패 {spec.id}: {type(exc).__name__}: {str(exc)[:100]}")

    summary = {"ok": ok, "failed": failed}
    out = REPO_ROOT / "tests" / "fixtures" / f"batch-record-{provider}.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[{provider}] 성공 {len(ok)} / 실패 {len(failed)} → {out.relative_to(REPO_ROOT)}")
    return summary


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Provider 단위 배치 녹화")
    parser.add_argument("--provider", required=True)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args(argv)
    summary = batch_record(args.provider, limit=args.limit)
    return 0 if summary["ok"] or not summary["failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
