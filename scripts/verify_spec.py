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
from datetime import date, datetime, timedelta, timezone
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
#: Ratchet baselines live at ``scripts/*_baseline.txt`` — one naming rule,
#: so the CODEOWNERS pattern and its reverse test (#764) cover every file
#: that lands here. Each baseline may only shrink against the base branch
#: (#766): an entry the base branch does not carry fails verify, which
#: stops both re-growth after a shrink and a one-for-one swap.
#: Fixtures recorded before the spec digest existed (#522), one meta path per
#: line relative to ``FIXTURES_ROOT``. Only these may lack ``spec_sha256`` (#717).
LEGACY_BASELINE = REPO_ROOT / "scripts" / "legacy_evidence_baseline.txt"

#: Specs whose licence says ``allowed`` without the attribution proof (#732).
#: Entries are spec ids (``provider.dataset_key``), one per line.
UNCONFIRMED_TERMS_BASELINE = REPO_ROOT / "scripts" / "unconfirmed_terms_baseline.txt"

#: Specs still sending their service key over plain http:// (#738). Entries
#: are spec ids, one per line. Every one sits on apis.data.go.kr, which the
#: probe in the issue shows answering https with identical envelopes, so an
#: entry leaves by switching schemes — which voids the spec digest and needs
#: a re-record through the Build Dataset workflow.
INSECURE_HTTP_BASELINE = REPO_ROOT / "scripts" / "insecure_http_baseline.txt"


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


def _load_terms_baseline() -> list[str]:
    """Spec ids of the unconfirmed-terms baseline, comments and blanks dropped."""
    if not UNCONFIRMED_TERMS_BASELINE.is_file():
        return []
    entries: list[str] = []
    for line in UNCONFIRMED_TERMS_BASELINE.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if entry and not entry.startswith("#"):
            entries.append(entry)
    return entries


def _terms_violation(spec: SpecDefinition) -> str | None:
    """Why this spec claims a redistribution its terms do not support (#732).

    ``redistribution: allowed`` is what Builder's publish gate reads
    (kpubdata-builder#892); saying it while the terms are unconfirmed
    publishes under conditions nobody checked. The proof of confirmation is
    the ``attribution`` text (#525) — its absence is the violation. None when
    the licence makes no such claim, or proves it.
    """
    lic = spec.license
    if lic is None or lic.redistribution != "allowed":
        return None
    if (lic.attribution or "").strip():
        return None
    return (
        "license.redistribution 이 allowed 인데 license.attribution 이 비어 있다 — "
        "확인되지 않은 이용조건은 재배포 허용이 아니다. 제공기관 페이지에서 이용조건을 "
        "확인해 attribution 을 채우거나 redistribution: unknown 으로 둔다 (#524, #732)"
    )


def _verify_licence_terms(spec: SpecDefinition) -> list[StepResult]:
    """The licence-source step (#732): allowed needs the attribution proof.

    Emitted only where the claim is made without proof — a baseline-listed
    spec passes with a note naming the exemption, an unlisted one fails, and
    a licence that claims nothing (or proves it) emits nothing, so the other
    datasets' verify output stays unchanged.
    """
    violation = _terms_violation(spec)
    if violation is None:
        return []
    if spec.id in _load_terms_baseline():
        return [StepResult(f"라이선스 출처[{spec.id}]", True, "미확인 조건 — baseline 등록 (#732)")]
    return [StepResult(f"라이선스 출처[{spec.id}]", False, violation)]


def _base_branch_entries(baseline: Path) -> set[str] | None:
    """Entry set of a baseline file on the base branch (#766).

    ``origin/main`` is the base of a pull request; ``HEAD`` is the base in
    the Build Dataset runner, which verifies uncommitted edits on main.
    None when neither can be read — the caller fails closed, because a
    ratchet that cannot see its anchor is not a ratchet. A baseline outside
    the repository (tests point the constant at a tmp file) has no git base
    either: None, for the same reason.
    """
    try:
        relative = baseline.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return None
    for ref in (f"origin/main:{relative}", f"HEAD:{relative}"):
        show = subprocess.run(
            ["git", "show", ref],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if show.returncode == 0:
            return {
                line.strip()
                for line in show.stdout.splitlines()
                if line.strip() and not line.strip().startswith("#")
            }
    return None


def _check_shrink_only(name: str, baseline: Path, entries: list[str]) -> list[StepResult]:
    """A baseline may only lose entries the base branch still carries (#766).

    The first ratchets compared counts against frozen ceilings, so a list
    that had shrunk could grow back — filling the freed slots with exactly
    the violations the ratchet exists to stop — and a one-for-one swap
    never moved the count at all. The anchor is the base branch's entry
    set: anything it does not carry is new, and new fails.
    """
    base = _base_branch_entries(baseline)
    if base is None:
        return [
            StepResult(
                name,
                passed=False,
                detail=(
                    "기준 브랜치(origin/main)의 baseline 항목을 읽을 수 없다 — "
                    "래칫의 기준점을 확인할 수 없으면 통과할 수 없다"
                ),
            )
        ]
    added = sorted(set(entries) - base)
    if added:
        return [
            StepResult(
                name,
                passed=False,
                detail=(
                    f"기준 브랜치에 없던 항목이 더해졌다: {', '.join(added)} — "
                    "목록은 줄기만 한다 (교체도 추가다)"
                ),
            )
        ]
    return []


def _check_terms_baseline() -> list[StepResult]:
    """Hold the unconfirmed-terms baseline to its ratchet (#732).

    Like the legacy evidence baseline (#717), it may only shrink: a listed
    spec stops needing the exemption exactly when its terms are confirmed or
    the claim is withdrawn, and a stale entry left behind is a hole a new
    pull request could hide behind. An entry naming no discovered spec is
    stale too.
    """
    entries = _load_terms_baseline()
    name = "unconfirmed terms baseline"
    results: list[StepResult] = _check_shrink_only(name, UNCONFIRMED_TERMS_BASELINE, entries)
    duplicates = sorted({entry for entry in entries if entries.count(entry) > 1})
    if duplicates:
        results.append(StepResult(name, passed=False, detail=f"중복 항목: {', '.join(duplicates)}"))
    by_id = {spec.id: spec for spec in discover_specs()}
    for entry in sorted(set(entries)):
        spec = by_id.get(entry)
        if spec is None:
            results.append(
                StepResult(
                    f"{name}[{entry}]",
                    passed=False,
                    detail="spec 이 더 이상 없음 — baseline 에서 이 줄을 삭제",
                )
            )
            continue
        if _terms_violation(spec) is None:
            results.append(
                StepResult(
                    f"{name}[{entry}]",
                    passed=False,
                    detail="더 이상 위반이 아님 — baseline 에서 이 줄을 삭제",
                )
            )
    return results


def _load_insecure_http_baseline() -> list[str]:
    """Spec ids of the insecure-http baseline, comments and blanks dropped."""
    if not INSECURE_HTTP_BASELINE.is_file():
        return []
    entries: list[str] = []
    for line in INSECURE_HTTP_BASELINE.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if entry and not entry.startswith("#"):
            entries.append(entry)
    return entries


def _insecure_http_violation(spec: SpecDefinition) -> str | None:
    """Why this spec sends its credentials over plain http:// (#738).

    The service key rides the query string, so over http:// anyone on the
    network path reads it. https is the fix — the one host every http spec
    uses (apis.data.go.kr) answers it with the same envelopes (probe in the
    issue). A provider that genuinely cannot serve https says why in
    ``endpoint.insecure_http_reason``. None when the scheme is already
    https, or the reason is written down.
    """
    endpoint = spec.endpoint
    if endpoint is None or not endpoint.base_url.startswith("http://"):
        return None
    if (endpoint.insecure_http_reason or "").strip():
        return None
    return (
        "endpoint.base_url 이 http:// 인데 endpoint.insecure_http_reason 이 비어 있다 — "
        "서비스 키가 쿼리로 실리는 요청을 평문으로 보내면 경로의 누구나 키를 볼 수 "
        "있다. https 로 바꾸고 재기록하거나, 제공기관이 https 를 지원하지 않는다면 "
        "그 사유를 insecure_http_reason 에 적는다 (#738)"
    )


def _verify_insecure_http(spec: SpecDefinition) -> list[StepResult]:
    """The transport-security step (#738): plain http needs its reason.

    Emitted only where the key would cross in the clear — a baseline-listed
    spec passes with a note naming the exemption, an unlisted one fails, and
    an https base_url (or one with the reason written down) emits nothing,
    so the other datasets' verify output stays unchanged.
    """
    violation = _insecure_http_violation(spec)
    if violation is None:
        return []
    if spec.id in _load_insecure_http_baseline():
        return [StepResult(f"전송 보안[{spec.id}]", True, "평문 HTTP — baseline 등록 (#738)")]
    return [StepResult(f"전송 보안[{spec.id}]", False, violation)]


def _check_insecure_http_baseline() -> list[StepResult]:
    """Hold the insecure-http baseline to its ratchet (#738).

    Like the two baselines above, it may only shrink: a listed spec stops
    needing the exemption exactly when it switches to https or writes the
    reason down, and a stale entry left behind is a hole a new pull request
    could hide behind. An entry naming no discovered spec is stale too.
    """
    entries = _load_insecure_http_baseline()
    name = "insecure http baseline"
    results: list[StepResult] = _check_shrink_only(name, INSECURE_HTTP_BASELINE, entries)
    duplicates = sorted({entry for entry in entries if entries.count(entry) > 1})
    if duplicates:
        results.append(StepResult(name, passed=False, detail=f"중복 항목: {', '.join(duplicates)}"))
    by_id = {spec.id: spec for spec in discover_specs()}
    for entry in sorted(set(entries)):
        spec = by_id.get(entry)
        if spec is None:
            results.append(
                StepResult(
                    f"{name}[{entry}]",
                    passed=False,
                    detail="spec 이 더 이상 없음 — baseline 에서 이 줄을 삭제",
                )
            )
            continue
        if _insecure_http_violation(spec) is None:
            results.append(
                StepResult(
                    f"{name}[{entry}]",
                    passed=False,
                    detail="더 이상 위반이 아님 — baseline 에서 이 줄을 삭제",
                )
            )
    return results


def _check_legacy_baseline() -> list[StepResult]:
    """Hold the legacy baseline to its ratchet (#717).

    The baseline may only shrink. It fails when it adds an entry the base
    branch does not carry (#766), repeats an entry, or keeps an entry that
    no longer exists or that now carries ``spec_sha256`` — a stale entry is
    a hole a new fixture could use.
    """
    entries = _load_legacy_baseline()
    name = "legacy baseline"
    results: list[StepResult] = _check_shrink_only(name, LEGACY_BASELINE, entries)
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


def _parse_date_value(value: object) -> date | None:
    """Parse an example parameter value as a date (YYYYMMDD or YYYY-MM-DD)."""
    text = str(value).strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _kst_today() -> date:
    """Today on the Seoul calendar — the provider serves Korean time."""
    return datetime.now(timezone(timedelta(hours=9))).date()


def _verify_example_recency(spec: SpecDefinition, today: date | None = None) -> list[StepResult]:
    """Examples whose date parameter left the provider's window fail as expired (#734).

    KMA-family APIs answer only recent issues — roughly a day for the nowcast,
    three for the short-term forecast — so a fixed example date goes stale in
    days and every live call after that reports a generic params_invalid
    (#731). A spec declares the window per parameter (``max_age_days``); verify
    then fails on an expired example *before* the live call does, naming the
    cause and the refresh route. A date past today fails too — a future issue
    does not answer yet, the #731 morning trap. Parameters without a declared
    window emit nothing, so the step appears only where the contract exists.
    """
    results: list[StepResult] = []
    resolved = today if today is not None else _kst_today()
    for param in spec.params:
        if param.max_age_days is None:
            continue
        for example in spec.examples:
            if param.exposed_name not in example.params:
                continue
            raw = example.params[param.exposed_name]
            step = f"예제 최신성[{example.name}]"
            value_date = _parse_date_value(raw)
            if value_date is None:
                results.append(
                    StepResult(
                        step,
                        False,
                        f"{param.exposed_name}={raw!r}을(를) 날짜로 읽을 수 없습니다"
                        " — max_age_days는 날짜 값 파라미터에만 둔다",
                    )
                )
                continue
            if value_date > resolved:
                results.append(
                    StepResult(
                        step,
                        False,
                        f"{param.exposed_name}={value_date}는 미래 발표다 — 아직 응답하지 않는다",
                    )
                )
                continue
            age = (resolved - value_date).days
            if age > param.max_age_days:
                results.append(
                    StepResult(
                        step,
                        False,
                        f"{param.exposed_name}={value_date}이(가) 만료 창"
                        f"({param.max_age_days}일)을 넘었다({age}일) — 실호출 불가(만료)."
                        f" dataset-request 워크플로 또는 `make record DATASET={spec.id}`"
                        "(으)로 갱신",
                    )
                )
                continue
            results.append(
                StepResult(
                    step,
                    True,
                    f"{param.exposed_name}={value_date} ({age}일/창 {param.max_age_days}일)",
                )
            )
    return results


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

    # 2-e'. The unconfirmed-terms baseline itself (#732) — same once-per-run
    # ratchet reasoning as the legacy baseline above.
    terms_steps = _check_terms_baseline()
    terms_passed = all(step.passed for step in terms_steps)
    print(f"[{'통과' if terms_passed else '실패'}] unconfirmed terms baseline")
    for step in terms_steps:
        if not step.passed:
            print(f"  오류({step.name}): {step.detail}")

    # 2-f'. The insecure-http baseline itself (#738) — same once-per-run
    # ratchet reasoning as the two baselines above.
    http_steps = _check_insecure_http_baseline()
    http_passed = all(step.passed for step in http_steps)
    print(f"[{'통과' if http_passed else '실패'}] insecure http baseline")
    for step in http_steps:
        if not step.passed:
            print(f"  오류({step.name}): {step.detail}")

    failed_any = not baseline_passed or not terms_passed or not http_passed
    for spec in specs:
        if not dataset_id and spec.status in skippable:
            print(f"[건너뜀] {spec.id} (status={spec.status})")
            continue
        result = DatasetVerifyResult(dataset_id=spec.id)
        result.steps.extend(_verify_fixtures(spec))
        result.steps.extend(_verify_example_recency(spec))
        result.steps.extend(_verify_licence_terms(spec))
        result.steps.extend(_verify_insecure_http(spec))
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
