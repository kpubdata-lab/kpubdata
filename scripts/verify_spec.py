"""Dataset verification orchestrator — the substance of `make verify`.

Steps (any failure exits 1):
1. Spec schema/id/duplicate checks (delegates to
   scripts/validate_spec.py)
2. Fixture integrity — raw/meta/expected all present + hashes match, and
   bound to the current spec digest unless listed in the frozen legacy
   baseline (scripts/legacy_evidence_baseline.txt, #717)
3. Replay contract — raw → envelope validation → items/total extraction
   matches expected

Usage:
    uv run python scripts/verify_spec.py                     # all specs
    uv run python scripts/verify_spec.py --dataset datago.apt_trade
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from kpubdata.core.spec import (
    SpecDefinition,
    discover_specs,
    find_spec,
    spec_file_digest,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures"
SPEC_ROOT = REPO_ROOT / "src" / "kpubdata" / "specs"
#: Fixtures recorded before the spec digest existed (#522), one meta path per
#: line relative to ``FIXTURES_ROOT``. Only these may lack ``spec_sha256`` (#717).
LEGACY_BASELINE = REPO_ROOT / "scripts" / "legacy_evidence_baseline.txt"
#: Size of the baseline when it was frozen (#717). The ratchet lets it shrink,
#: never grow: a new fixture without a digest is not legacy, it is unbound.
LEGACY_CEILING = 28


@dataclass
class StepResult:
    """Single verification stage result."""

    name: str
    passed: bool
    detail: str = ""


@dataclass
class DatasetVerifyResult:
    """Verification result per dataset."""

    dataset_id: str
    steps: list[StepResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """All stages passed."""
        return all(step.passed for step in self.steps)


def _canon_bytes(data: object) -> str:
    """Canonical JSON serialization for hash comparison (same rules as record.py)."""
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=1) + "\n"


def _load_legacy_baseline() -> list[str]:
    """Entries of the legacy evidence baseline, comments and blank lines dropped.

    A missing file is an empty baseline: every fixture then needs a digest.
    """
    if not LEGACY_BASELINE.is_file():
        return []
    entries: list[str] = []
    for line in LEGACY_BASELINE.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if entry and not entry.startswith("#"):
            entries.append(entry)
    return entries


def _check_legacy_baseline() -> list[StepResult]:
    """Hold the legacy baseline to its ratchet (#717).

    The baseline may only shrink. It fails when it grows past its frozen size,
    repeats an entry, or keeps an entry that no longer exists or that now
    carries ``spec_sha256`` — a stale entry is a hole a new fixture could use.
    """
    entries = _load_legacy_baseline()
    results: list[StepResult] = []
    name = "legacy baseline"
    if len(entries) > LEGACY_CEILING:
        results.append(
            StepResult(
                name,
                passed=False,
                detail=(
                    f"baseline {len(entries)}개 > 동결 크기 {LEGACY_CEILING}개 — "
                    "legacy 목록은 줄기만 한다. 새 fixture 는 `make record` 로 기록"
                ),
            )
        )
    duplicates = sorted({entry for entry in entries if entries.count(entry) > 1})
    if duplicates:
        results.append(StepResult(name, passed=False, detail=f"중복 항목: {', '.join(duplicates)}"))
    for entry in sorted(set(entries)):
        meta_path = FIXTURES_ROOT / entry
        if not meta_path.is_file():
            results.append(
                StepResult(
                    f"{name}[{entry}]",
                    passed=False,
                    detail="fixture 가 더 이상 없음 — baseline 에서 이 줄을 삭제",
                )
            )
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if "spec_sha256" in meta:
            results.append(
                StepResult(
                    f"{name}[{entry}]",
                    passed=False,
                    detail=(
                        "spec_sha256 필드가 있음 — 더 이상 legacy 가 아니다. "
                        "baseline 에서 이 줄을 삭제"
                    ),
                )
            )
    if not results:
        results.append(StepResult(name, passed=True, detail=f"{len(entries)}개"))
    return results


def _fixture_key(meta_path: Path) -> str:
    """A meta path as the baseline names it: relative to ``FIXTURES_ROOT``."""
    return meta_path.relative_to(FIXTURES_ROOT).as_posix()


def _verify_fixtures(spec: SpecDefinition) -> list[StepResult]:
    """Verify fixture integrity + replay contract."""
    results: list[StepResult] = []
    legacy = frozenset(_load_legacy_baseline())
    out_dir = FIXTURES_ROOT / spec.provider / spec.dataset_key
    if not out_dir.is_dir() or not list(out_dir.glob("*.raw.json")):
        shown = out_dir.relative_to(REPO_ROOT) if out_dir.is_relative_to(REPO_ROOT) else out_dir
        results.append(
            StepResult(
                "fixture 존재",
                passed=False,
                detail=(f"fixture 없음: {shown} — `make record DATASET={spec.id}` 로 생성"),
            )
        )
        return results

    for raw_path in sorted(out_dir.glob("*.raw.json")):
        example = raw_path.name.removesuffix(".raw.json")
        meta_path = raw_path.with_name(f"{example}.meta.json")
        expected_path = raw_path.with_name(f"{example}.expected.json")

        # 2-a. All 3 types exist
        missing = [path.name for path in (raw_path, meta_path, expected_path) if not path.is_file()]
        if missing:
            results.append(
                StepResult(
                    f"fixture[{example}] 3종 존재",
                    passed=False,
                    detail=f"누락: {', '.join(missing)} (메타 없는 fixture는 검증 불가)",
                )
            )
            continue

        # 2-b. Hash match (block agent from fabricating fixtures)
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(_canon_bytes(payload).encode("utf-8")).hexdigest()
        if digest != meta.get("response_sha256"):
            results.append(
                StepResult(
                    f"fixture[{example}] 해시 일치",
                    passed=False,
                    detail="meta의 response_sha256과 raw 내용이 불일치 — fixture가 기록 후 수정됨",
                )
            )
            continue

        # 2-c. Spec binding (#522): evidence recorded against a spec digest
        # that no longer matches the file is void — the spec changed after
        # recording. Legacy is decided by the frozen baseline, not by the
        # field being absent (#717): only a listed fixture whose meta has no
        # `spec_sha256` key passes unbound. A deleted key, `null` or "" on any
        # other fixture fails, so a one-line meta edit cannot unbind evidence.
        binding = f"fixture[{example}] spec 결속"
        recorded_spec = meta.get("spec_sha256")
        if isinstance(recorded_spec, str) and recorded_spec:
            current_spec = spec_file_digest(SPEC_ROOT / spec.provider / f"{spec.dataset_key}.yaml")
            if current_spec != recorded_spec:
                results.append(
                    StepResult(
                        binding,
                        passed=False,
                        detail=(
                            "spec이 기록 후 변경됨 — 증거 무효. "
                            f"`make record DATASET={spec.id}` 로 재기록"
                        ),
                    )
                )
                continue
            results.append(StepResult(binding, passed=True, detail=recorded_spec[:12]))
        elif "spec_sha256" not in meta and _fixture_key(meta_path) in legacy:
            results.append(
                StepResult(
                    binding,
                    passed=True,
                    detail="spec_sha256 없음 — legacy baseline 증거 (TRUST-04)",
                )
            )
        else:
            state = "없음" if "spec_sha256" not in meta else f"{recorded_spec!r}"
            results.append(
                StepResult(
                    binding,
                    passed=False,
                    detail=(
                        f"spec_sha256 {state} — legacy baseline 밖의 fixture 는 spec 결속이 "
                        f"필수. `make record DATASET={spec.id}` 로 재기록"
                    ),
                )
            )
            continue

        # 3. replay contract — changing spec fields should fail at this stage
        from kpubdata.core.executor import check_payload_error, extract_items, extract_total_count

        try:
            check_payload_error(spec, payload)
            items = extract_items(spec, payload)
            total = extract_total_count(spec, payload)
        except Exception as exc:  # noqa: BLE001 — verifier collects all failures as results
            results.append(
                StepResult(f"replay[{example}] envelope 검사", passed=False, detail=str(exc))
            )
            continue

        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        if items != expected.get("items") or total != expected.get("total_count"):
            results.append(
                StepResult(
                    f"replay[{example}] 정규화 일치",
                    passed=False,
                    detail=(
                        f"expected 불일치: items {len(items)}건/total={total} vs 스냅샷 "
                        f"{len(expected.get('items', []))}건/total={expected.get('total_count')}"
                    ),
                )
            )
            continue

        lost = _lost_leading_zeros(spec, items)
        if lost:
            results.append(
                StepResult(
                    f"replay[{example}] 코드값 보존",
                    passed=False,
                    detail=(
                        "normalization drops leading zeros — declare these as string (#613): "
                        + ", ".join(lost)
                    ),
                )
            )
            continue

        results.append(StepResult(f"fixture[{example}] + replay", passed=True))

    return results


_CODE_VALUE = re.compile(r"^0\d+$")


def _lost_leading_zeros(spec: SpecDefinition, items: list[dict[str, object]]) -> list[str]:
    """Fields whose zero-led code values ("06102") do not survive normalization.

    The replay above compares values *before* normalization, so a cast that turns
    "06102" into 6102 passed it (#613). This compares what users receive.
    """
    from kpubdata.core.executor import normalize_items

    normalized = normalize_items(spec, items)
    lost: dict[str, str] = {}
    for raw, out in zip(items, normalized, strict=True):
        for declared in spec.fields:
            if declared.transform or declared.name in lost:
                continue
            value = raw.get(declared.source_name or declared.name)
            received = out.get(declared.name)
            if isinstance(value, str) and _CODE_VALUE.match(value) and received != value:
                lost[declared.name] = f"{declared.name} ({value!r} -> {received!r})"
    return sorted(lost.values())


def run_verify(dataset_id: str | None = None) -> int:
    """Run verification on all (or single) specs and return exit code."""
    specs: list[SpecDefinition]
    if dataset_id:
        spec = find_spec(dataset_id)
        if spec is None:
            print(f"오류: spec을 찾을 수 없습니다: {dataset_id}")
            return 1
        specs = [spec]
    else:
        specs = discover_specs()

    # 1. Delegate schema validation
    validate = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "validate_spec.py")],
        check=False,
        capture_output=True,
        text=True,
    )
    print(validate.stdout.rstrip())
    if validate.returncode != 0:
        if validate.stderr:
            print(validate.stderr.rstrip())
        return 1

    # specs with unstable/broken status skip fixture/example verification —
    # case where fixture creation is impossible (e.g., usage request not approved).
    skippable = frozenset({"unstable", "broken"})

    # 2-c'. The legacy baseline itself (#717) — checked once per run, because a
    # stale entry is a hole whichever dataset is being verified.
    baseline_steps = _check_legacy_baseline()
    baseline_passed = all(step.passed for step in baseline_steps)
    print(f"[{'통과' if baseline_passed else '실패'}] legacy evidence baseline")
    for step in baseline_steps:
        if not step.passed:
            print(f"  오류({step.name}): {step.detail}")

    failed_any = not baseline_passed
    for spec in specs:
        if not dataset_id and spec.status in skippable:
            print(f"[건너뜀] {spec.id} (status={spec.status})")
            continue
        result = DatasetVerifyResult(dataset_id=spec.id)
        result.steps.extend(_verify_fixtures(spec))
        result.steps.append(_run_example_script(spec))
        result.steps.append(_run_live_schema_diff(spec))

        status = "통과" if result.passed else "실패"
        print(f"[{status}] {spec.id}")
        for step in result.steps:
            if not step.passed:
                print(f"  오류({step.name}): {step.detail}")
        failed_any = failed_any or not result.passed

    total = len(specs)
    print(f"검증 결과: {total}개 데이터셋, {'실패 있음' if failed_any else '전체 통과'}")
    return 1 if failed_any else 0


def _run_live_schema_diff(spec: SpecDefinition) -> StepResult:
    """Perform live schema diff when LIVE=1 (ignore value changes, compare structure only)."""
    import os

    if os.environ.get("LIVE") != "1":
        return StepResult("live 스키마 diff", passed=True, detail="건너뜀(LIVE=1 아님)")

    from kpubdata.config import KPubDataConfig
    from kpubdata.core.executor import SpecExecutor, check_payload_error, extract_items
    from kpubdata.core.models import Query
    from kpubdata.core.spec import ExampleSpec
    from kpubdata.transport.http import HttpTransport

    out_dir = FIXTURES_ROOT / spec.provider / spec.dataset_key
    meta_paths = sorted(out_dir.glob("*.meta.json"))
    if not meta_paths:
        return StepResult("live 스키마 diff", passed=True, detail="fixture 없음 — 건너뜀")

    meta = json.loads(meta_paths[0].read_text(encoding="utf-8"))
    example_name = str(meta.get("example", "default"))
    example = next(
        (ex for ex in spec.examples if ex.name == example_name),
        spec.examples[0] if spec.examples else ExampleSpec(name=example_name),
    )
    query = Query(
        filters=dict(example.params),
        page=example.page or 1,
        page_size=example.page_size or 10,
    )
    executor = SpecExecutor(HttpTransport(), KPubDataConfig.from_env())
    try:
        params, payload = executor.fetch(spec, query, format_hint=example.format)
        check_payload_error(spec, payload)
        live_items = extract_items(spec, payload)
    except Exception as exc:  # noqa: BLE001 — LIVE verification collects failures as results
        return StepResult("live 스키마 diff", passed=False, detail=f"실호출 실패: {str(exc)[:120]}")

    expected = json.loads((out_dir / f"{example_name}.expected.json").read_text(encoding="utf-8"))
    fixture_keys = (
        {k for item in expected.get("items", []) for k in item} if expected.get("items") else set()
    )
    live_keys = {k for item in live_items for k in item} if live_items else set()
    added = sorted(live_keys - fixture_keys)
    removed = sorted(fixture_keys - live_keys)
    if added or removed:
        detail = f"스키마 diff — 추가: {added or '없음'} / 제거: {removed or '없음'}"
        return StepResult("live 스키마 diff", passed=False, detail=detail)
    return StepResult("live 스키마 diff", passed=True, detail=f"구조 일치({len(live_keys)}필드)")


def _run_example_script(spec: SpecDefinition) -> StepResult:
    """Run example script in replay mode (verification stage 4)."""
    import os
    import subprocess

    script = REPO_ROOT / "examples" / spec.provider / f"{spec.dataset_key}.py"
    if not script.is_file():
        return StepResult(
            "examples 실행",
            passed=False,
            detail=(f"예제 스크립트 없음: {script} — examples/README.md 규약(#379 2.3)"),
        )
    env = {**os.environ, "KPUBDATA_MODE": "replay"}
    proc = subprocess.run(
        [sys.executable, str(script)],
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-3:]
        return StepResult(
            "examples 실행",
            passed=False,
            detail="replay 실행 실패: " + " / ".join(tail),
        )
    return StepResult("examples 실행", passed=True)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="spec 데이터셋 검증 (make verify)")
    parser.add_argument("--dataset", help="단일 데이터셋 id (예: datago.apt_trade)")
    args = parser.parse_args(argv)
    return run_verify(args.dataset)


if __name__ == "__main__":
    sys.exit(main())
