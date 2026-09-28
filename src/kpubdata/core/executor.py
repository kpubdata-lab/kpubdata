"""Generic Executor — performs dataset queries using declarative specs alone.

Execution layer for the spec system (#378). Interprets the authentication,
parameter, pagination, envelope, and error rules declared by
``kpubdata.core.spec.SpecDefinition`` to produce the same observable behavior
(RecordBatch semantics) as legacy adapters.

Scope (pilot):
- Auth: ``query_param`` (others unimplemented — custom adapters responsible)
- Pagination: ``page_no_rows``, ``none`` (others unimplemented)
- Envelope: ``datago_standard`` (path-based generic extraction — shared by
  data.go.kr family)
- Error: ``header_result_code`` (data.go.kr resultCode standard table)

Layering rule: core does not import providers. Duplicate datago adapter logic
but don't depend on it (verified: tests/unit/core/test_executor.py).
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from types import MappingProxyType
from typing import cast

from kpubdata._hosts import extra_hosts_env_var, host_is_allowed
from kpubdata.config import KPubDataConfig
from kpubdata.core.capability import Operation, PaginationMode, QuerySupport
from kpubdata.core.models import (
    DatasetRef,
    FieldIssue,
    Query,
    RecordBatch,
    SchemaDescriptor,
    ValidationReport,
)
from kpubdata.core.representation import Representation
from kpubdata.core.spec import SpecDefinition
from kpubdata.exceptions import (
    AuthError,
    DatasetNotFoundError,
    InvalidRequestError,
    ProviderResponseError,
    RateLimitError,
    ServiceUnavailableError,
    TransportError,
)
from kpubdata.transport.decode import decode_json, decode_xml, detect_content_type
from kpubdata.transport.http import HttpTransport

logger = logging.getLogger("kpubdata.core.executor")

_AUTH_ERROR_CODES = frozenset({"30", "31", "20", "32"})
_SERVICE_UNAVAILABLE_CODES = frozenset({"01", "02"})
_DEFAULT_PAGE_SIZE = 100
# To avoid importing providers from core, generalize the datago 403 hint.
_FORBIDDEN_HINT = (
    "Provider returned 403. This usually means the specific API has not been activated "
    "(활용신청) for your key. Check the dataset's documentation page for your provider."
)


def _resolve_path(path: str | None, spec: SpecDefinition | None = None) -> str | None:
    """Replace {operation} placeholder in path with the dataset's operation."""
    if path is None:
        return None
    if spec is None:
        return path
    return path.replace("{operation}", spec.endpoint.operation)


def _dot_get(payload: object, path: str | None) -> object | None:
    """Traverse a payload using dot-path notation.

    Numeric segments are treated as array indices (e.g. AJGCF.0.head.0.list_total_count).
    Special path "$" returns the root payload itself (for kosis top-level arrays, etc).
    """
    if path is None:
        return None
    if path == "$":
        return payload
    current: object = payload
    for raw_segment in path.split("."):
        if isinstance(current, dict):
            current = current.get(raw_segment)
        elif isinstance(current, list) and raw_segment.lstrip("-").isdigit():
            index = int(raw_segment)
            current = current[index] if -len(current) <= index < len(current) else None
        else:
            return None
        if current is None:
            return None
    return current


def _to_int(value: object) -> int | None:
    """Convert string/integer to int (skip bool; return None on failure)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


#: Numeric null markers — after whitespace trimming, these count as None for
#: integer/number casting and do NOT block all-or-nothing fallback (#461).
#: "-" is a very common Korean public-data missing-value marker.  String fields
#: are unaffected: "-" can carry meaning there, so null recognition is scoped
#: to numeric casting.
_DEFAULT_NULL_MARKERS: frozenset[str] = frozenset({"", "-"})

#: Valid thousands-separator pattern (e.g. "1,200", "12,345,678", "-1,200.5").
#: Malformed grouping like "12,34" does NOT match and will fail the cast.
_GROUPED_NUMERIC_RE = re.compile(r"^[+-]?\d{1,3}(,\d{3})*(\.\d+)?$")


def _normalize_numeric_lexeme(value: object) -> object:
    """Normalize a string for numeric casting (#461).

    Steps (in order):
    1. Trim surrounding whitespace.
    2. Map null markers ("", "-") to None — these are cast successes.
    3. Remove thousands separators only when the grouping is valid.
    4. For integer fields, accept integral decimal strings like "3.0" → 3.

    Units ("85㎡"), arbitrary text, and malformed grouping are left as-is
    so they still trigger all-or-nothing fallback.
    """
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if stripped in _DEFAULT_NULL_MARKERS:
        return None
    if _GROUPED_NUMERIC_RE.match(stripped):
        stripped = stripped.replace(",", "")
    return stripped


#: Exact integer-string patterns — plain digits or integral decimals like "3.0".
#: Rejects scientific notation ("1e3"), NaN/inf, and non-integral decimals (#461).
_PLAIN_INTEGER_RE = re.compile(r"^[+-]?\d+$")
_INTEGRAL_DECIMAL_RE = re.compile(r"^[+-]?\d+\.0+$")


def _try_cast_field(value: object, field_type: str) -> tuple[bool, object]:
    """Attempt cast to declared type; return (success, value).

    Even on failure, return the original value—caller examines the entire column
    to decide whether to apply the result (see _normalize_fields).
    """
    if value is None:
        return True, None
    if field_type in ("integer", "number"):
        normalized = _normalize_numeric_lexeme(value)
        if normalized is None:
            return True, None
        value = normalized
    if field_type == "integer":
        if isinstance(value, bool):
            return False, value
        if isinstance(value, int):
            return True, value
        if isinstance(value, float):
            return (True, int(value)) if value.is_integer() else (False, value)
        if isinstance(value, str):
            # Exact string parsing — no float() round-trip, which would
            # silently corrupt large integers like 9007199254740993 (#461).
            if _PLAIN_INTEGER_RE.match(value):
                return True, int(value)
            if _INTEGRAL_DECIMAL_RE.match(value):
                return True, int(value.split(".")[0])
            return False, value
        return False, value
    if field_type == "number":
        if isinstance(value, bool):
            return False, value
        if isinstance(value, (int, float)):
            return True, value
        if isinstance(value, str):
            # Reject NaN/inf — they are not valid normalized public-data values.
            if value.lower() in ("nan", "inf", "-inf", "+inf", "infinity", "-infinity"):
                return False, value
            if "e" in value.lower():
                return False, value
            try:
                return True, float(value)
            except ValueError:
                return False, value
        return False, value
    return True, value


def _normalize_item_list(value: object) -> list[dict[str, object]]:
    """Normalize items leaf value to record dict list (single dict → 1-item list)."""
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _apply_transform(value: object, transform: str) -> object:
    """Apply single-field transformation (return as-is if no value)."""
    if value is None:
        return None
    if isinstance(value, str) and transform == "strip_comma":
        return value.replace(",", "")
    if (
        isinstance(value, str)
        and transform == "date_yyyymmdd"
        and len(value) == 8
        and value.isdigit()
    ):
        return f"{value[:4]}-{value[4:6]}-{value[6:]}"
    if (
        isinstance(value, str)
        and transform == "date_yyyymm"
        and len(value) == 6
        and value.isdigit()
    ):
        return f"{value[:4]}-{value[4:]}"
    return value


def _cast_field(value: object, field_type: str) -> object:
    """Cast to declared type (preserve original if cast fails)."""
    _, coerced = _try_cast_field(value, field_type)
    return coerced


#: The envelope returned by data.go.kr gateway when it rejects before reaching
#: the service. Instead of the service's <response>, this shape arrives when
#: rejected (unregistered key, expired activation request, disallowed IP, quota exceeded).
_GATEWAY_ENVELOPE_KEY = "OpenAPI_ServiceResponse"
_GATEWAY_HEADER_KEY = "cmmMsgHeader"


def _gateway_rejection(payload: dict[str, object]) -> tuple[str, str] | None:
    """Return (code, message) if gateway rejection, else None.

    returnReasonCode uses the same vocabulary as service envelope's resultCode,
    so it can use the same mapping. #478 added this branch only to the datago
    adapter, but ~20 datasets on the spec-first path still failed with
    "error code not found in response envelope". What could be fixed was seen
    as a parse error.
    """
    gateway = payload.get(_GATEWAY_ENVELOPE_KEY)
    if not isinstance(gateway, dict):
        return None
    header = cast(dict[str, object], gateway).get(_GATEWAY_HEADER_KEY)
    if not isinstance(header, dict):
        return None
    header_dict = cast(dict[str, object], header)
    raw_code = header_dict.get("returnReasonCode")
    if raw_code is None:
        return None
    for key in ("returnAuthMsg", "errMsg"):
        value = header_dict.get(key)
        if isinstance(value, str) and value.strip():
            return str(raw_code).strip(), value.strip()
    return (
        str(raw_code).strip(),
        f"data.go.kr gateway rejected the request (returnReasonCode={raw_code})",
    )


def _build_provenance(
    response: object, params: dict[str, str], spec: SpecDefinition
) -> dict[str, object]:
    """Build standardized provenance metadata for RecordBatch.meta (#479).

    Fail-closed: if masking fails for any field, that field is omitted entirely
    rather than leaking the unmasked value.
    """
    from kpubdata.transport._sensitive import SENSITIVE_PARAM_KEYS

    provenance: dict[str, object] = {}

    # fetched_at — UTC ISO-8601
    provenance["fetched_at"] = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")

    # content_sha256 — hash of the raw response bytes
    content = getattr(response, "content", None)
    if content is not None and isinstance(content, bytes):
        provenance["content_sha256"] = hashlib.sha256(content).hexdigest()

    # content_type — declared or inferred
    ct = getattr(response, "headers", None)
    if ct is not None:
        declared = ct.get("content-type", "")
        if declared:
            provenance["content_type"] = declared.split(";")[0].strip()

    # cached — whether this came from the response cache
    cached = getattr(response, "_from_cache", None)
    if cached is not None:
        provenance["cached"] = bool(cached)
    else:
        provenance["cached"] = False

    # url — masked, fail-closed (omit if we cannot safely mask)
    url = str(getattr(response, "url", ""))
    if url:
        try:
            safe_url = url
            for key, value in params.items():
                if key.casefold() in SENSITIVE_PARAM_KEYS and value:
                    safe_url = safe_url.replace(value, "[REDACTED]")
            provenance["url"] = safe_url
        except Exception:
            pass  # fail-closed: omit rather than leak

    # params — masked, fail-closed
    try:
        safe_params = {
            k: ("[REDACTED]" if k.casefold() in SENSITIVE_PARAM_KEYS else v)
            for k, v in params.items()
        }
        provenance["params"] = safe_params
    except Exception:
        pass  # fail-closed: omit rather than leak

    return provenance


class SpecExecutor:
    """Provider-agnostic executor that interprets spec to execute queries."""

    def __init__(self, transport: HttpTransport, config: KPubDataConfig) -> None:
        """Initialize the executor with transport and config injection."""
        self._transport = transport
        self._config = config

    # ------------------------------------------------------------------
    # Request assembly
    # ------------------------------------------------------------------

    def _resolve_format_value(self, spec: SpecDefinition, format_hint: str | None) -> str | None:
        """Resolve format parameter value from spec matching format_hint."""
        format_param = spec.endpoint.format_param
        if format_param is None or not format_param.name:
            return None
        hint = format_hint or spec.response.format
        if format_param.values:
            return format_param.values.get(hint)
        return hint

    def _require_allowed_host(self, spec: SpecDefinition, url_or_host: str) -> None:
        """Refuse before a credential is assembled for a host we do not trust.

        A spec names both the host to call and the credential to attach, and
        nothing verified that the two belonged together (#519). The check has to
        run *before* the key is read, not before the request is sent: once the
        key is in the parameter dict it can reach a log, an exception message or
        a retry.
        """
        credential_owner = spec.auth.provider_key or spec.provider
        if host_is_allowed(credential_owner, url_or_host):
            return
        # The message names the provider and the variable that widens the list,
        # but never the host's credential.
        msg = (
            f"{spec.id}: refusing to send the {credential_owner!r} credential to "
            f"a host that is not on its allowlist. Set "
            f"{extra_hosts_env_var(credential_owner)} if this host is legitimate."
        )
        raise InvalidRequestError(msg, provider=spec.provider, dataset_id=spec.id)

    def build_params(
        self, spec: SpecDefinition, query: Query, format_hint: str | None = None
    ) -> dict[str, str]:
        """Assemble auth, format, pagination, and filters into query parameters.

        Args:
            spec: The dataset spec definition.
            query: The user query.
            format_hint: Optional format override.

        Raises:
            InvalidRequestError: If pagination mode lacks required param name.
        """
        params: dict[str, str] = {}

        if spec.auth.type != "none":
            # Before any credential is read. ``path_template`` can name a host
            # of its own without going through ``base_url``, so the resolved URL
            # is checked again in ``_request``.
            self._require_allowed_host(spec, spec.endpoint.base_url)

        if spec.auth.type == "query_param":
            if not spec.auth.param_name:
                msg = f"{spec.id}: auth.query_param 방식은 param_name 선언이 필요합니다."
                raise InvalidRequestError(msg, provider=spec.provider, dataset_id=spec.id)
            provider_key = spec.auth.provider_key or spec.provider
            params[spec.auth.param_name] = self._config.require_provider_key(provider_key)
        elif spec.auth.type == "path_segment":
            # Key is placed in URL path (path_template {key}) — removed from query.
            template = spec.endpoint.path_template or ""
            if "{key}" not in template:
                msg = f"{spec.id}: path_segment 인증은 path_template의 {{key}}가 필요합니다."
                raise InvalidRequestError(msg, provider=spec.provider, dataset_id=spec.id)
            params[spec.auth.param_name or "__path_key__"] = self._config.require_provider_key(
                spec.auth.provider_key or spec.provider
            )
        elif spec.auth.type != "none":
            msg = (
                f"{spec.id}: auth.type={spec.auth.type!r}은(는) 아직 spec 실행기가 "
                "지원하지 않습니다."
            )
            raise NotImplementedError(msg)

        format_value = self._resolve_format_value(spec, format_hint)
        format_param = spec.endpoint.format_param
        if format_param is not None and format_param.name and format_value is not None:
            params[format_param.name] = format_value

        page = query.page or 1
        page_size = query.page_size or _DEFAULT_PAGE_SIZE
        if spec.pagination.max_size is not None:
            page_size = min(page_size, spec.pagination.max_size)
        if spec.pagination.type == "page_no_rows":
            page_param = spec.pagination.page_param or "pageNo"
            size_param = spec.pagination.size_param or "numOfRows"
            params[page_param] = str(page)
            params[size_param] = str(page_size)
        elif spec.pagination.type in {"pindex_psize", "page_display"}:
            # lofin(pIndex/pSize, 1-based)·law(page/display) — query parameter style
            defaults: dict[str, tuple[str, str, int, int]] = {
                "pindex_psize": ("pIndex", "pSize", 1, 100),
                "page_display": ("page", "display", 1, 20),
            }
            default_page_p, default_size_p, default_page, default_size = defaults[
                spec.pagination.type
            ]
            page_param = spec.pagination.page_param or default_page_p
            size_param = spec.pagination.size_param or default_size_p
            params[page_param] = str(query.page or default_page)
            params[size_param] = str(query.page_size or default_size)
        elif spec.pagination.type == "index_range":
            # BOK/Seoul family — start/end go in URL path (path_template {{start}}/{{end}}).
            if not spec.endpoint.path_template:
                msg = f"{spec.id}: index_range 페이지네이션은 path_template이 필요합니다."
                raise InvalidRequestError(msg, provider=spec.provider, dataset_id=spec.id)
        elif spec.pagination.type != "none":
            msg = (
                f"{spec.id}: pagination.type={spec.pagination.type!r}은(는) "
                "아직 spec 실행기가 지원하지 않습니다."
            )
            raise NotImplementedError(msg)

        reserved = {key.lower() for key in params}
        alias_map = {param.exposed_name: param.name for param in spec.params}
        for key, raw_value in query.filters.items():
            # Auth, format, pagination params already filled; don't override with user filters.
            if key.lower() in reserved:
                continue
            provider_name = alias_map.get(key, key)
            params[provider_name] = str(raw_value)

        return params

    # ------------------------------------------------------------------
    # Transport and decoding
    # ------------------------------------------------------------------

    def build_url(
        self,
        spec: SpecDefinition,
        page: int = 1,
        page_size: int = _DEFAULT_PAGE_SIZE,
        api_key: str = "",
    ) -> str:
        """Assemble spec endpoint URL.

        If ``endpoint.path_template`` exists, replace {key}, {operation}, {start}, {end}
        placeholders (for BOK/Seoul family path-based keys and ranges). Otherwise use
        the default {base}/{operation} form.
        """
        template = spec.endpoint.path_template
        if template:
            start_index = spec.pagination.start_index_base or 1
            start = (page - 1) * page_size + start_index
            end = start + page_size - 1
            return template.format(
                base_url=spec.endpoint.base_url.rstrip("/"),
                key=api_key,
                operation=spec.endpoint.operation,
                start=start,
                end=end,
            )
        return f"{spec.endpoint.base_url.rstrip('/')}/{spec.endpoint.operation.lstrip('/')}"

    def _request(
        self, spec: SpecDefinition, params: dict[str, str]
    ) -> tuple[dict[str, object], dict[str, object]]:
        """Send GET request to spec endpoint and return decoded dict.

        Args:
            spec: The dataset spec.
            params: Request parameters.

        Raises:
            AuthError: On transport 403 (with activation request hint).
            ProviderResponseError: If decoded result is not a dict.
        """
        page_part = params.get(spec.pagination.page_param or "", "1")
        size_part = params.get(spec.pagination.size_param or "", str(_DEFAULT_PAGE_SIZE))
        url = self.build_url(
            spec,
            page=_to_int(page_part) or 1,
            page_size=_to_int(size_part) or _DEFAULT_PAGE_SIZE,
            api_key=params.get(spec.auth.param_name or "", "")
            if spec.auth.type == "path_segment"
            else "",
        )
        if spec.auth.type != "none":
            # ``path_template`` is free-form and can embed a host that
            # ``base_url`` never mentions, which would walk past the check in
            # ``build_params``. Re-check what will actually be requested (#519).
            self._require_allowed_host(spec, url)
        if spec.auth.type == "path_segment":
            params = {k: v for k, v in params.items() if k != (spec.auth.param_name or "")}
        try:
            response = self._transport.request(
                "GET",
                url,
                params=params,
                dataset_id=spec.id,
                provider=spec.provider,
            )
        except TransportError as exc:
            # Check exc.status_code. When we relied on __cause__, if transport broke
            # the chain on mixed-key requests (as it should), the 403 determination
            # vanished entirely — key masking and 403 hint defeated each other.
            if exc.status_code == 403:
                raise AuthError(
                    _FORBIDDEN_HINT,
                    provider=spec.provider,
                    dataset_id=spec.id,
                    status_code=403,
                ) from exc
            raise
        try:
            content_type = detect_content_type(response)
            if content_type == "xml":
                decoded: object = decode_xml(response.content)
            else:
                decoded = decode_json(response.content)
        except ImportError as exc:
            msg = "XML 응답을 파싱하려면 선택 의존성이 필요합니다: pip install kpubdata[xml]"
            raise InvalidRequestError(msg, provider=spec.provider, dataset_id=spec.id) from exc

        if isinstance(decoded, dict):
            provenance = _build_provenance(response, params, spec)
            return decoded, provenance
        msg = f"{spec.id}: 응답 페이로드가 객체가 아닙니다({type(decoded).__name__})."
        raise ProviderResponseError(msg, provider=spec.provider, dataset_id=spec.id)

    # ------------------------------------------------------------------
    # Envelope and error mapping
    # ------------------------------------------------------------------

    def _require_supported_envelope(self, spec: SpecDefinition) -> None:
        """Explicitly reject envelopes outside pilot scope."""
        if spec.response.envelope != "datago_standard":
            msg = (
                f"{spec.id}: envelope={spec.response.envelope!r}은(는) "
                "아직 spec 실행기가 지원하지 않습니다."
            )
            raise NotImplementedError(msg)

    def _raise_for_code(self, spec: SpecDefinition, code: str, message: str) -> None:
        """Delegate to module function — if same rule exists twice, they must diverge."""
        raise_for_code(spec, code, message)

    def _check_error(self, spec: SpecDefinition, payload: dict[str, object]) -> None:
        """Delegate to module function.

        Previously, the same logic was implemented separately here, and the copy
        missed four enhancements that exist in the module only: err_field style
        (kosis), {operation} substitution in code_path (lofin family), KorService
        top-level resultCode fallback, and resultMsg/errMsg message fallback.

        As a result, ``make verify`` used the module function while actual execution
        used this method—verify passing did not guarantee the execution path worked.
        Providers without a code system like kosis failed on success responses saying
        "error code not found in envelope".
        """
        check_payload_error(spec, payload)

    def _extract_items(
        self, spec: SpecDefinition, payload: dict[str, object]
    ) -> list[dict[str, object]]:
        """Delegate to module function.

        The copy lacked neis_double_list envelope, {operation} substitution, and $
        (root for kosis top-level array) — those providers passed verify but returned
        empty lists at runtime.
        """
        return extract_items(spec, payload)

    def _extract_total_count(self, spec: SpecDefinition, payload: dict[str, object]) -> int | None:
        """Extract total count using spec's total_count_path rule (None if absent)."""
        raw = _dot_get(payload, spec.response.total_count_path)
        coerced = _to_int(raw)
        return coerced if coerced else None

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def _stage_fields(
        self, spec: SpecDefinition, items: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        """Stage 1 only: rename + transform (no casting) (#481)."""
        if not spec.fields:
            return items
        staged: list[dict[str, object]] = []
        for item in items:
            record: dict[str, object] = dict(item)
            for field in spec.fields:
                source_name = field.source_name or field.name
                if source_name not in record:
                    continue
                record[field.name] = _apply_transform(record[source_name], field.transform or "")
                if source_name != field.name:
                    record.pop(source_name, None)
            staged.append(record)
        return staged

    def _finalize_casting(
        self, spec: SpecDefinition, staged: list[dict[str, object]]
    ) -> tuple[list[dict[str, object]], ValidationReport]:
        """Stage 2 only: column-level all-or-nothing casting (#481, #572).

        Returns (items_with_casting_applied, validation_report).
        """
        if not spec.fields:
            return staged, ValidationReport()

        issues: list[FieldIssue] = []
        declared_names = {f.name for f in spec.fields}

        # Detect undeclared keys (spec drift) from the first record.
        if staged:
            undeclared = set(staged[0].keys()) - declared_names
            for key in sorted(undeclared):
                issues.append(FieldIssue(field=key, kind="undeclared"))

        for field in spec.fields:
            casts: list[tuple[dict[str, object], object]] = []
            failed_count = 0
            sample_failures: list[str] = []
            castable = True
            found_in_any = False
            for record in staged:
                if field.name not in record:
                    continue
                found_in_any = True
                raw_value = record[field.name]
                succeeded, coerced = _try_cast_field(raw_value, field.type)
                if not succeeded:
                    castable = False
                    failed_count += 1
                    if len(sample_failures) < 3:
                        sample_failures.append(repr(raw_value)[:60])
                    continue
                casts.append((record, coerced))
            if not found_in_any:
                issues.append(
                    FieldIssue(field=field.name, kind="missing", declared_type=field.type)
                )
                continue
            if not castable:
                issues.append(
                    FieldIssue(
                        field=field.name,
                        kind="uncastable",
                        declared_type=field.type,
                        failed_count=failed_count,
                        sample_values=tuple(sample_failures),
                    )
                )
                logger.debug(
                    "leaving column uncast: a value does not match the declared type",
                    extra={"dataset_id": spec.id, "field": field.name, "type": field.type},
                )
                continue
            for record, coerced in casts:
                record[field.name] = coerced

        report = ValidationReport(issues=tuple(issues))
        if not report.ok:
            logger.info(
                "normalization validation issues",
                extra={"dataset_id": spec.id, "issue_count": len(issues)},
            )
        return staged, report

    def _normalize_fields(
        self, spec: SpecDefinition, items: list[dict[str, object]]
    ) -> tuple[list[dict[str, object]], ValidationReport]:
        """Apply rename/transform/casting only when a fields[] declaration exists.

        Casting applies **per column, and only when every value succeeds**.
        Deciding row by row would mix cast values with originals in one
        column, breaking the type for consumers working in tabular form —
        for example, the apartment-trade ``aptDong`` is mostly ``"105"`` but
        some rows carry a dong *name* (a Korean neighborhood string), so
        row-wise casting would produce a column where int and str coexist.
        If even one value fails to cast, the column stays as-is — even when
        the spec's type declaration disagrees with the real data,
        downstream does not break.

        Returns (normalized_items, cast_fallback_diagnostics) — the second
        element lists fields that stayed string despite a numeric/typed
        declaration (#461).
        """
        if not spec.fields:
            return items, ValidationReport()
        staged = self._stage_fields(spec, items)
        return self._finalize_casting(spec, staged)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def query(
        self,
        spec: SpecDefinition,
        dataset: DatasetRef,
        query: Query,
        format_hint: str | None = None,
    ) -> RecordBatch:
        """Execute the query per spec and return a RecordBatch."""
        self._require_supported_envelope(spec)
        params = self.build_params(spec, query, format_hint=format_hint)
        payload, provenance = self._request(spec, params)
        self._check_error(spec, payload)

        items, validation = self._normalize_fields(spec, self._extract_items(spec, payload))
        total_count = self._extract_total_count(spec, payload)

        page = query.page or 1
        page_size = query.page_size or _DEFAULT_PAGE_SIZE
        if spec.pagination.max_size is not None:
            page_size = min(page_size, spec.pagination.max_size)
        has_next = (total_count and page * page_size < total_count) or (
            not total_count and len(items) == page_size
        )
        next_page = page + 1 if has_next else None

        if not items:
            logger.debug("Spec executor: zero items", extra={"dataset_id": spec.id, "page": page})

        meta: dict[str, object] = {"provenance": provenance}
        return RecordBatch(
            items=items,
            dataset=dataset,
            total_count=total_count,
            next_page=next_page,
            meta=meta,
            validation=validation,
            raw=payload,
        )

    def fetch(
        self,
        spec: SpecDefinition,
        query: Query,
        format_hint: str | None = None,
    ) -> tuple[dict[str, str], dict[str, object]]:
        """Return the request parameters together with the decoded raw payload (for recording).

        Unlike query, this performs no envelope interpretation or
        normalization — a low-level entry point so recording tools can store
        raw/expected themselves.
        """
        self._require_supported_envelope(spec)
        params = self.build_params(spec, query, format_hint=format_hint)
        payload, _provenance = self._request(spec, params)
        return params, payload

    def request_raw(
        self,
        spec: SpecDefinition,
        params: dict[str, object],
        format_hint: str | None = None,
    ) -> dict[str, object]:
        """Return the decoded raw payload without envelope interpretation (raw escape hatch)."""
        string_params: dict[str, str] = {key: str(value) for key, value in params.items()}
        if spec.auth.type == "query_param" and spec.auth.param_name:
            provider_key = spec.auth.provider_key or spec.provider
            string_params.setdefault(
                spec.auth.param_name, self._config.require_provider_key(provider_key)
            )
        format_value = self._resolve_format_value(spec, format_hint)
        format_param = spec.endpoint.format_param
        if format_param is not None and format_param.name and format_value is not None:
            string_params.setdefault(format_param.name, format_value)
        payload, _provenance = self._request(spec, string_params)
        return payload


def raise_for_code(spec: SpecDefinition, code: str, message: str) -> None:
    """Map error code to standard exception (data.go.kr resultCode standard table)."""
    if code in _AUTH_ERROR_CODES:
        raise AuthError(message, provider=spec.provider, dataset_id=spec.id, provider_code=code)
    if code == "22":
        raise RateLimitError(
            message, provider=spec.provider, dataset_id=spec.id, provider_code=code, retryable=False
        )
    if code == "10":
        raise InvalidRequestError(
            message, provider=spec.provider, dataset_id=spec.id, provider_code=code
        )
    if code == "12":
        raise DatasetNotFoundError(
            message, provider=spec.provider, dataset_id=spec.id, provider_code=code
        )
    if code in _SERVICE_UNAVAILABLE_CODES:
        raise ServiceUnavailableError(
            message, provider=spec.provider, dataset_id=spec.id, provider_code=code
        )
    raise ProviderResponseError(
        message, provider=spec.provider, dataset_id=spec.id, provider_code=code
    )


def check_payload_error(spec: SpecDefinition, payload: dict[str, object]) -> None:
    """Check error code path and raise if failure code (shared by record/verify).

    If gateway rejected instead of service, declared code_path won't exist.
    Both builder's verify and record use this function, so check it too.
    """
    error = spec.response.error
    gateway = _gateway_rejection(payload)
    if gateway is not None:
        raise_for_code(spec, gateway[0], gateway[1])
    if error.style == "err_field":
        # kosis family: no code system; err field presence itself means failure.
        err_raw = payload.get("err")
        if isinstance(err_raw, (str, dict)):
            raise ProviderResponseError(
                f"{spec.id}: Provider 오류 응답: {str(err_raw)[:200]}",
                provider=spec.provider,
                dataset_id=spec.id,
            )
        return
    raw_code = _dot_get(payload, _resolve_path(error.code_path, spec))
    # Fallback: Korean Tourism Organization KorService returns errors at top-level
    # resultCode outside envelope (success uses normal envelope). If declared path
    # missing, check top-level.
    if raw_code is None and isinstance(payload.get("resultCode"), (str, int)):
        raw_code = payload.get("resultCode")
    if isinstance(raw_code, str):
        code = raw_code
    elif isinstance(raw_code, int) and not isinstance(raw_code, bool):
        code = str(raw_code)
    else:
        msg = f"{spec.id}: 응답 envelope에서 에러 코드를 찾을 수 없습니다({error.code_path!r})."
        raise ProviderResponseError(msg, provider=spec.provider, dataset_id=spec.id)

    ok_strings = {str(value) for value in error.ok_values}
    code_as_int = _to_int(code)
    is_success = code in ok_strings or (code_as_int == 0)
    if is_success:
        return

    raw_message = _dot_get(payload, _resolve_path(_message_path(error.code_path), spec))
    if not isinstance(raw_message, str) or not raw_message:
        raw_message = payload.get("resultMsg")
    if not isinstance(raw_message, str) or not raw_message:
        raw_message = payload.get("errMsg")
    message = (
        raw_message if isinstance(raw_message, str) and raw_message else "Provider returned error"
    )
    raise_for_code(spec, code, message)


def extract_items(spec: SpecDefinition, payload: dict[str, object]) -> list[dict[str, object]]:
    """Extract record list using spec's items_path rule (shared by record/verify).

    Supports:
    - {operation} placeholder (lofin family: {operation}.1.row)
    - $ for root (kosis top-level array)
    - neis_double_list envelope merges row blocks per operation
    """
    if spec.response.envelope == "neis_double_list":
        return _extract_neis_rows(spec, payload)
    resolved = _resolve_path(spec.response.items_path, spec) or ""
    if resolved == "$":
        return _normalize_item_list(payload)
    if "." in resolved:
        container_path, leaf = resolved.rsplit(".", 1)
    else:
        container_path, leaf = "", resolved
    container = _dot_get(payload, container_path) if container_path else payload
    if container is None:
        return []
    value = container.get(leaf) if isinstance(container, dict) else None
    return _normalize_item_list(value)


def _extract_neis_rows(spec: SpecDefinition, payload: dict[str, object]) -> list[dict[str, object]]:
    """NEIS double-list envelope: merge all {operation}[].row blocks."""
    blocks = payload.get(spec.endpoint.operation)
    rows: list[dict[str, object]] = []
    if not isinstance(blocks, list):
        return rows
    for block in blocks:
        if not isinstance(block, dict):
            continue
        row_value = block.get("row")
        if isinstance(row_value, list):
            rows.extend(item for item in row_value if isinstance(item, dict))
        elif isinstance(row_value, dict):
            rows.append(row_value)
    return rows


def extract_total_count(spec: SpecDefinition, payload: dict[str, object]) -> int | None:
    """Extract total count using spec's total_count_path rule (None if absent)."""
    resolved = _resolve_path(spec.response.total_count_path, spec)
    raw = _dot_get(payload, resolved)
    coerced = _to_int(raw)
    return coerced if coerced else None


def _message_path(code_path: str | None) -> str | None:
    """Infer corresponding resultMsg path from resultCode path."""
    if not code_path:
        return None
    segments = code_path.split(".")
    segments[-1] = "resultMsg"
    return ".".join(segments)


def _spec_request_parameters(spec: SpecDefinition) -> tuple[MappingProxyType[str, object], ...]:
    """Convert spec params to catalog request_parameters format (#375).

    query_support.filterable_fields only names "filterable" fields, so consumers
    (Builder/Studio) couldn't tell which parameters are **required** or what values
    to use. Spec already has this info; expose it directly.

    Match catalog entry request_parameters (#374) key names so consumers can read
    both paths in one format. name is the calling name (alias first); original API
    param goes in api_name separately — when they differ, name is what users pass.
    """
    parameters: list[MappingProxyType[str, object]] = []
    for param in spec.params:
        entry: dict[str, object] = {
            "name": param.exposed_name,
            "required": param.required,
            "type": param.type,
        }
        if param.alias:
            entry["api_name"] = param.name
        if param.description:
            entry["description"] = param.description
        if param.example is not None:
            entry["example"] = param.example
        if param.enum:
            entry["enum"] = list(param.enum)
        parameters.append(MappingProxyType(entry))
    return tuple(parameters)


def build_spec_dataset_ref(spec: SpecDefinition) -> DatasetRef:
    """Convert SpecDefinition to DatasetRef with catalog-equivalent semantics."""
    paginated = spec.pagination.type in {"page_no_rows", "page_display", "pindex_psize"}
    query_support = QuerySupport(
        pagination=PaginationMode.OFFSET if paginated else PaginationMode.NONE,
        filterable_fields=frozenset(param.exposed_name for param in spec.params),
        max_page_size=spec.pagination.max_size,
    )
    raw_metadata: dict[str, object] = {}
    request_parameters = _spec_request_parameters(spec)
    if request_parameters:
        raw_metadata["request_parameters"] = request_parameters
    if spec.source is not None and spec.source.verified_at:
        # Spec basis date — lets consumers judge metadata freshness.
        raw_metadata["verified_at"] = spec.source.verified_at
    return DatasetRef(
        id=spec.id,
        provider=spec.provider,
        dataset_key=spec.dataset_key,
        name=spec.title,
        representation=Representation.API_JSON,
        operations=frozenset({Operation.LIST, Operation.RAW}),
        query_support=query_support,
        description=spec.description,
        tags=(spec.provider, "spec"),
        source_url=spec.source.url if spec.source else None,
        raw_metadata=MappingProxyType(raw_metadata),
    )


class SpecDatasetAdapter:
    """Expose one Provider's spec bundle as ProviderAdapter protocol.

    Pilot version before registry integration: provides same interface as
    built-in adapters but spec executor performs queries. call_raw always
    returns the raw payload.
    """

    def __init__(self, provider: str, specs: list[SpecDefinition], executor: SpecExecutor) -> None:
        """Initialize the adapter with provider ID, spec list, and executor."""
        self._provider = provider
        self._specs = {spec.dataset_key: spec for spec in specs if spec.provider == provider}
        self._executor = executor
        self.requires_api_key: bool = any(spec.auth.type != "none" for spec in self._specs.values())

    @property
    def name(self) -> str:
        """Return the Provider identifier."""
        return self._provider

    def list_datasets(self) -> list[DatasetRef]:
        """Return all held specs as DatasetRef."""
        return [build_spec_dataset_ref(spec) for spec in self._specs.values()]

    def search_datasets(self, text: str) -> list[DatasetRef]:
        """Return substring search results in id, title, description."""
        needle = text.lower()
        return [
            build_spec_dataset_ref(spec)
            for spec in self._specs.values()
            if needle in spec.id.lower()
            or needle in spec.title.lower()
            or (spec.description is not None and needle in spec.description.lower())
        ]

    def get_dataset(self, dataset_key: str) -> DatasetRef:
        """Resolve a provider-local key into a DatasetRef.

        Raises:
            DatasetNotFoundError: The key is unknown.
        """
        spec = self._specs.get(dataset_key)
        if spec is None:
            msg = f"Unknown dataset key for spec adapter: {self._provider}.{dataset_key}"
            raise DatasetNotFoundError(msg, provider=self._provider)
        return build_spec_dataset_ref(spec)

    def query_records(self, dataset: DatasetRef, query: Query) -> RecordBatch:
        """Run a canonical list query through the spec executor."""
        spec = self._specs.get(dataset.dataset_key)
        if spec is None:
            msg = f"Unknown dataset key for spec adapter: {dataset.id}"
            raise DatasetNotFoundError(msg, provider=self._provider, dataset_id=dataset.id)
        return self._executor.query(spec, dataset, query)

    def query_records_all(
        self, dataset: DatasetRef, query: Query, *, max_pages: int | None = None
    ) -> list[RecordBatch]:
        """Multi-page query with global column casting (#481).

        Collects all pages first, then applies all-or-nothing column casting
        once across the full result set. This prevents mixed types when
        page 1 casts a column but page 2 cannot.
        """
        spec = self._specs.get(dataset.dataset_key)
        if spec is None:
            msg = f"Unknown dataset key for spec adapter: {dataset.id}"
            raise DatasetNotFoundError(msg, provider=self._provider, dataset_id=dataset.id)

        effective_max = max_pages if max_pages is not None else 1000
        all_staged: list[dict[str, object]] = []
        page_boundaries: list[int] = []
        total_count: int | None = None
        page = query.page or 1
        page_size = query.page_size or _DEFAULT_PAGE_SIZE

        while len(page_boundaries) < effective_max:
            self._executor._require_supported_envelope(spec)
            params = self._executor.build_params(spec, query, format_hint=None)
            payload, _prov = self._executor._request(spec, params)
            self._executor._check_error(spec, payload)

            items = self._executor._extract_items(spec, payload)
            staged = self._executor._stage_fields(spec, items)
            all_staged.extend(staged)
            page_boundaries.append(len(staged))

            tc = self._executor._extract_total_count(spec, payload)
            if total_count is None:
                total_count = tc

            has_next = (tc and page * page_size < tc) or (not tc and len(staged) == page_size)
            if not has_next:
                break
            page += 1
            query = Query(filters=query.filters, page=page, page_size=query.page_size)

        # Global casting decision across all pages (#481).
        finalized, validation = self._executor._finalize_casting(spec, all_staged)

        result: list[RecordBatch] = []
        start = 0
        for batch_len in page_boundaries:
            page_items = finalized[start : start + batch_len]
            result.append(
                RecordBatch(
                    items=page_items,
                    dataset=dataset,
                    total_count=total_count,
                    next_page=None,
                    validation=validation,
                    raw=None,
                )
            )
            start += batch_len
        return result

    def get_schema(self, dataset: DatasetRef) -> SchemaDescriptor | None:
        """Schema metadata is not supported yet (an honest declaration)."""
        return None

    def call_raw(self, dataset: DatasetRef, operation: str, params: dict[str, object]) -> object:
        """Guarantee the raw escape hatch returning the original payload."""
        spec = self._specs.get(dataset.dataset_key)
        if spec is None:
            msg = f"Unknown dataset key for spec adapter: {dataset.id}"
            raise DatasetNotFoundError(msg, provider=self._provider, dataset_id=dataset.id)
        return self._executor.request_raw(spec, params)


__all__ = [
    "SpecDatasetAdapter",
    "SpecExecutor",
    "build_spec_dataset_ref",
    "check_payload_error",
    "extract_items",
    "extract_total_count",
    "raise_for_code",
]
