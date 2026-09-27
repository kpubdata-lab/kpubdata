"""도달성 프로브 — 키 하나로 전 데이터셋을 분류하고 활용신청 목록을 만든다 (#499).

데이터셋 추가에서 **사람만 할 수 있는 단계는 data.go.kr 활용신청** 하나다. 그런데
어느 데이터셋이 신청을 기다리는지가 ``SUPPORTED_DATA.md`` 비고란 텍스트에만 있어서,
에이전트는 spec 작업을 시작한 **뒤에야** 403 으로 알게 된다. 되돌릴 작업을 먼저 하는
셈이다.

이 모듈은 그 판정을 앞으로 당긴다 — 데이터셋마다 1회 호출해 분류한다. 분류
어휘는 ``PROBE_STATUSES`` 이고, 예전 네 갈래보다 넓다: **폐기와 일시 장애를
구분하지 못하면 한도 초과가 폐기로 읽혀** 기다리면 되는 것을 포기하라고 알려
준다 (#514).

``batch_record.py`` 와 같은 fast-fail 전송 설정을 쓴다(timeout 15s·재시도 0) —
실패 데이터셋이 전체를 늦추지 않아야 하고, 여기서는 실패가 정상 결과다.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from kpubdata.config import KPubDataConfig
from kpubdata.core.models import DatasetRef, Query
from kpubdata.core.spec import SpecDefinition, discover_specs, find_spec
from kpubdata.exceptions import (
    AuthError,
    DatasetNotFoundError,
    InvalidRequestError,
    ParseError,
    PublicDataError,
    RateLimitError,
    ServiceUnavailableError,
    TransportError,
    TransportTimeoutError,
)
from kpubdata.transport.http import HttpTransport, TransportConfig

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_PATH = REPO_ROOT / "docs" / "status" / "key-scope.json"

#: 프로브 전송 설정. 실패가 정상 결과이므로 빠르게 포기한다.
PROBE_TIMEOUT_SECONDS = 15
PROBE_RETRIES = 0

#: Probe outcomes (#514). The earlier four-way split could not tell a retired
#: dataset from a transient outage, so a quota overrun read as retirement --
#: which told a user to give up on something they only needed to wait for.
#:
#: ``application_required`` also covers what would be "awaiting approval".
#: data.go.kr returns the same access-denied code whether no application was ever
#: made or one is pending, and no documented code distinguishes them, so inventing
#: the distinction would mean guessing. Splitting them later needs a record of
#: submitted applications, which does not exist yet.
PROBE_STATUSES: tuple[str, ...] = (
    "available",
    "auth_unknown",
    "application_required",
    "params_invalid",
    "rate_limited",
    "temporarily_unavailable",
    "network_error",
    "insufficient_metadata",
    "retired",
)

ProbeStatus = str

#: data.go.kr standard result codes, as mapped in ``core/executor.py``.
#: ``raise_for_code`` already turns these into typed exceptions, so the codes are
#: read off ``provider_code`` rather than re-deriving them from the body.
_CODE_STATUS: Mapping[str, ProbeStatus] = {
    "01": "temporarily_unavailable",
    "02": "temporarily_unavailable",
    "10": "params_invalid",
    "12": "retired",  # NO_OPENAPI_SERVICE -- the service is not there
    "20": "application_required",  # SERVICE_ACCESS_DENIED
    "22": "rate_limited",  # quota exceeded -- reachable, so not an application matter
    "30": "application_required",  # SERVICE_KEY_IS_NOT_REGISTERED
    "31": "application_required",  # expired
    "32": "auth_unknown",  # UNREGISTERED_IP -- the key is fine, the caller is not
}


@dataclass(frozen=True)
class ProbeResult:
    """데이터셋 하나의 도달성 판정."""

    dataset_id: str
    service_id: str
    status: ProbeStatus
    probed_at: str
    detail: str = ""


def service_id_of(spec: SpecDefinition) -> str:
    """이 데이터셋이 속한 data.go.kr 서비스 식별자.

    ``base_url`` 의 마지막 경로 세그먼트다 — 활용신청은 **데이터셋이 아니라 서비스
    단위**로 한다. 예컨대 ``ArpltnInforInqireSvc`` 하나를 신청하면 대기질 관련
    데이터셋 셋이 함께 풀린다. 데이터셋 단위로 나열하면 세 번 신청해야 하는 것처럼
    보인다.
    """
    base_url = getattr(spec.endpoint, "base_url", "") or ""
    path = urlsplit(base_url).path.rstrip("/")
    return path.rsplit("/", 1)[-1] if path else ""


def classify(error: BaseException | None) -> tuple[ProbeStatus, str]:
    """Map a call outcome onto one of ``PROBE_STATUSES``.

    The provider result code is consulted first where there is one. ``executor``
    already maps the data.go.kr table onto typed exceptions and records the code
    on ``provider_code``, and the code carries more than the exception type does
    -- a 403 can mean "not applied for" (30) or "your IP is not registered" (32),
    and those need different advice.

    Where no code is available the exception type decides. Subclass order matters:
    ``RateLimitError`` and ``TransportTimeoutError`` both subclass
    ``TransportError``, so checking the base first would bury them. A quota
    overrun previously classified as retirement, which told a user to abandon
    something they only had to wait for.
    """
    if error is None:
        return "available", ""
    detail = f"{type(error).__name__}: {str(error)[:120]}"

    code = getattr(error, "provider_code", None)
    if isinstance(code, str) and code.strip() in _CODE_STATUS:
        return _CODE_STATUS[code.strip()], detail

    # Narrowest first. RateLimitError and TransportTimeoutError are
    # TransportError subclasses.
    if isinstance(error, RateLimitError):
        return "rate_limited", detail
    if isinstance(error, TransportTimeoutError):
        return "network_error", detail
    if isinstance(error, AuthError):
        return "application_required", detail
    if isinstance(error, InvalidRequestError):
        return "params_invalid", detail
    if isinstance(error, DatasetNotFoundError):
        return "retired", detail
    if isinstance(error, ServiceUnavailableError):
        return "temporarily_unavailable", detail
    if isinstance(error, ParseError):
        # The endpoint answered with something undecodable. That is not a
        # reachability verdict, and calling it retired would be wrong.
        return "insufficient_metadata", detail
    if isinstance(error, TransportError):
        status = getattr(error, "status_code", None)
        if status == 403:
            return "application_required", detail
        if status == 400:
            return "params_invalid", detail
        if status == 429:
            return "rate_limited", detail
        if isinstance(status, int) and 500 <= status < 600:
            return "temporarily_unavailable", detail
        if status is None:
            # No HTTP exchange completed: DNS, TLS, connection refused.
            return "network_error", detail
        return "temporarily_unavailable", detail
    return "network_error", detail


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _missing_credential(spec: SpecDefinition, config: KPubDataConfig) -> str | None:
    """The provider whose key is absent, or None when nothing is needed."""
    if spec.auth.type == "none":
        return None
    provider = spec.auth.provider_key or spec.provider
    # ``get_provider_key`` returns None rather than raising, so no guard is
    # needed -- ``require_provider_key`` is the one that raises.
    return None if config.get_provider_key(provider) else provider


def probe_dataset(
    dataset_id: str,
    *,
    config: KPubDataConfig | None = None,
    transport: HttpTransport | None = None,
) -> ProbeResult | None:
    """데이터셋 하나를 1회 호출해 분류한다. spec 이 없으면 None."""
    spec = find_spec(dataset_id)
    if spec is None:
        return None

    resolved_config = config or KPubDataConfig.from_env()

    # Stop before calling when there is no key to call with. Sending a request
    # that is certain to fail costs the provider a request against the quota and
    # tells us nothing -- and it would come back as application_required, which
    # is the wrong advice: nothing needs applying for, a key needs configuring.
    missing = _missing_credential(spec, resolved_config)
    if missing is not None:
        return ProbeResult(
            dataset_id=spec.id,
            service_id=service_id_of(spec),
            status="auth_unknown",
            probed_at=_now(),
            detail=f"no credential configured for provider {missing!r}",
        )

    resolved_transport = transport or HttpTransport(
        config=TransportConfig(timeout=PROBE_TIMEOUT_SECONDS, max_retries=PROBE_RETRIES, cache=None)
    )
    from kpubdata.core.executor import SpecExecutor

    executor = SpecExecutor(config=resolved_config, transport=resolved_transport)
    example = spec.examples[0] if spec.examples else None
    query = (
        Query(filters=dict(example.params), page=example.page, page_size=example.page_size)
        if example
        else Query()
    )

    error: BaseException | None = None
    try:
        _ = executor.query(spec, _ref_for(spec), query)
    except PublicDataError as exc:
        error = exc
    except Exception as exc:  # noqa: BLE001 — 프로브는 모든 실패를 분류해야 한다
        error = exc

    status, detail = classify(error)
    return ProbeResult(
        dataset_id=spec.id,
        service_id=service_id_of(spec),
        status=status,
        probed_at=_now(),
        detail=detail,
    )


def _ref_for(spec: SpecDefinition) -> DatasetRef:
    """executor 가 요구하는 최소 DatasetRef."""
    from kpubdata.core.models import DatasetRef
    from kpubdata.core.representation import Representation

    return DatasetRef(
        id=spec.id,
        provider=spec.provider,
        dataset_key=spec.dataset_key,
        name=getattr(spec, "title", None) or spec.id,
        representation=Representation.API_JSON,
    )


def probe_all(
    *,
    provider: str | None = None,
    dataset_id: str | None = None,
    config: KPubDataConfig | None = None,
    transport: HttpTransport | None = None,
) -> list[ProbeResult]:
    """대상 데이터셋 전체를 프로브한다."""
    if dataset_id:
        one = probe_dataset(dataset_id, config=config, transport=transport)
        return [one] if one else []

    results: list[ProbeResult] = []
    for spec in discover_specs():
        if provider and spec.provider != provider:
            continue
        one = probe_dataset(spec.id, config=config, transport=transport)
        if one is not None:
            results.append(one)
    return results


def render_apply_report(results: list[ProbeResult]) -> str:
    """활용신청 체크리스트. **서비스 단위로 묶는다.**

    묶는 것이 이 보고서의 요점이다 — 데이터셋 단위로 나열하면 같은 서비스를 여러 번
    신청해야 하는 것처럼 보인다.
    """
    pending = [r for r in results if r.status == "application_required"]
    if not pending:
        return "# 활용신청 대기\n\n없습니다.\n"

    groups: dict[str, list[ProbeResult]] = {}
    for result in pending:
        groups.setdefault(result.service_id, []).append(result)

    lines = [
        "# 활용신청 대기",
        "",
        f"서비스 {len(groups)}건을 신청하면 데이터셋 {len(pending)}종이 풀립니다.",
        "",
    ]
    for service, items in sorted(groups.items()):
        lines.append(f"## {service or '(서비스 식별 불가)'}")
        lines.append("")
        lines.append(
            f"- 데이터셋 {len(items)}종: " + ", ".join(sorted(i.dataset_id for i in items))
        )
        lines.append("- 신청: https://www.data.go.kr/ 에서 위 서비스명을 검색해 활용신청")
        lines.append("")
    return "\n".join(lines)


def merge_with_existing(results: list[ProbeResult], path: Path) -> list[ProbeResult]:
    """Fold ``results`` into whatever the report already holds.

    Probing one dataset with ``--dataset`` used to overwrite the report with a
    single row, discarding every other verdict. The point of the report is the
    whole picture, and rebuilding it means calling every provider again.

    Rows for the same ``dataset_id`` are replaced by the new verdict; everything
    else is kept.
    """
    existing: dict[str, ProbeResult] = {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        payload = None
    if isinstance(payload, dict):
        for row in payload.get("results", []):
            if not isinstance(row, dict) or "dataset_id" not in row:
                continue
            try:
                existing[str(row["dataset_id"])] = ProbeResult(
                    dataset_id=str(row["dataset_id"]),
                    service_id=str(row.get("service_id", "")),
                    status=str(row.get("status", "")),
                    probed_at=str(row.get("probed_at", "")),
                    detail=str(row.get("detail", "")),
                )
            except (TypeError, ValueError):
                continue
    for result in results:
        existing[result.dataset_id] = result
    return sorted(existing.values(), key=lambda r: r.dataset_id)


def write_report(results: list[ProbeResult], path: Path = DEFAULT_REPORT_PATH) -> Path:
    """Write the report atomically.

    A crash midway through a plain ``write_text`` leaves a truncated JSON file,
    and the next run reads it as "no previous verdicts" -- so a partial write
    silently erases the report it was extending.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "probed_at": _now(),
        "results": [asdict(r) for r in sorted(results, key=lambda r: r.dataset_id)],
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    temporary = path.with_name(f"{path.name}.tmp")
    try:
        temporary.write_text(rendered, encoding="utf-8")
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return path


def summarize(results: list[ProbeResult]) -> dict[str, int]:
    """분류별 개수."""
    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    return counts
