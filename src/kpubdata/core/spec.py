"""Declarative dataset spec loader — converts YAML definitions to validated dataclass.

Read layer for the spec system (#378). Dataset definitions live in
``src/kpubdata/specs/{provider}/{dataset_key}.yaml``; ``specs/schema.json``
is the contract. Generic Executor (``kpubdata.core.executor``) performs
queries using only outputs from this module.

Design principles:
- Full schema validation is handled by ``scripts/validate_spec.py`` (jsonschema);
  this module performs only minimal runtime structure validation (minimize dependencies).
- Unknown keys are not rejected; preserved in ``raw_metadata`` for forward compatibility.
"""

from __future__ import annotations

import copy
import hashlib
import re
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path

import yaml

from kpubdata.core.status import SpecStatus
from kpubdata.exceptions import InvalidRequestError

# Enum sets kept in sync with schema.json (runtime structure validation).
_AUTH_TYPES = frozenset({"query_param", "path_segment", "oauth_exchange", "none"})
_PAGINATION_TYPES = frozenset(
    {"page_no_rows", "page_display", "pindex_psize", "index_range", "date_window", "none"}
)
_FORMATS = frozenset({"json", "xml", "geojson"})
_ENVELOPES = frozenset(
    {
        "datago_standard",
        "datago_gyeonggi_msg",
        "datago_its_flat",
        "datago_odcloud",
        "localdata_rows",
        "semas_rows",
        "lofin_head_row",
        "neis_double_list",
        "kipris_items",
        "seoul_service_row",
        "bok_statistic_row",
        "kosis_top_array",
        "law_item_key",
        "korean_channel",
        "fds_row",
    }
)
_ERROR_STYLES = frozenset(
    {"header_result_code", "result_code", "status_code", "err_cd", "err_field", "http_status"}
)
_STATUSES = frozenset(status.value for status in SpecStatus)


@dataclass(slots=True, frozen=True)
class SourceRef:
    """Original document source information."""

    url: str | None = None
    doc_version: str | None = None
    verified_at: date | None = None


@dataclass(slots=True, frozen=True)
class FormatParamSpec:
    """Response format selection parameter (data.go.kr family: dataType/_type/resultType, etc)."""

    name: str
    values: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class EndpointSpec:
    """Endpoint assembly information."""

    base_url: str
    operation: str
    method: str = "GET"
    format_param: FormatParamSpec | None = None
    path_template: str | None = None
    insecure_http_reason: str | None = None


@dataclass(slots=True, frozen=True)
class AuthSpec:
    """Authentication method declaration."""

    type: str
    param_name: str | None = None
    provider_key: str | None = None


@dataclass(slots=True, frozen=True)
class ParamSpec:
    """Data filter parameter declaration."""

    name: str
    type: str = "string"
    alias: str | None = None
    required: bool = False
    enum: tuple[str, ...] = ()
    description: str | None = None
    example: str | int | float | None = None
    max_age_days: int | None = None

    @property
    def exposed_name(self) -> str:
        """Name exposed to library filters (alias prioritized)."""
        return self.alias or self.name


@dataclass(slots=True, frozen=True)
class ErrorSpec:
    """Response error representation declaration."""

    style: str
    code_path: str | None = None
    ok_values: tuple[str | int, ...] = ()


@dataclass(slots=True, frozen=True)
class ResponseSpec:
    """Response format, envelope, path declaration."""

    format: str
    envelope: str
    items_path: str | None = None
    total_count_path: str | None = None
    error: ErrorSpec = field(default_factory=lambda: ErrorSpec(style="http_status"))


@dataclass(slots=True, frozen=True)
class PaginationSpec:
    """Pagination method declaration."""

    type: str
    page_param: str | None = None
    size_param: str | None = None
    max_size: int | None = None
    start_index_base: int | None = None


@dataclass(slots=True, frozen=True)
class FieldSpec:
    """Single field declaration with normalization rules."""

    name: str
    type: str
    source_name: str | None = None
    unit: str | None = None
    transform: str | None = None
    description: str | None = None
    #: What the value means, apart from how it is stored (ADR 0006, #651).
    semantic_kind: str | None = None
    #: Display name; maps to ``FieldDescriptor.title``.
    title: str | None = None
    #: Display format hint; maps to ``FieldConstraints.format``.
    format: str | None = None


#: ``semantic_kind`` → the storage types it allows (ADR 0006 section 2).
SEMANTIC_KIND_TYPES: dict[str, frozenset[str]] = {
    "code": frozenset({"string"}),
    "measure": frozenset({"integer", "number"}),
    "date": frozenset({"string"}),
    "period": frozenset({"string"}),
    "text": frozenset({"string"}),
    "flag": frozenset({"boolean"}),
}
#: Transforms that turn text into numbers. A code keeps its source string.
_NUMERIC_TRANSFORMS = frozenset({"to_int", "to_float", "strip_comma"})


def field_conflicts(field: dict[str, object]) -> list[str]:
    """Contradictions between a field's meaning and its storage (ADR 0006 section 5).

    A field that declares no ``semantic_kind`` is not checked, so existing specs pass.
    Shared by the loader and ``scripts/validate_spec.py``.
    """
    name = field.get("name")
    kind = field.get("semantic_kind")
    field_type = field.get("type") or "string"
    problems: list[str] = []
    if kind is None:
        return problems
    allowed = SEMANTIC_KIND_TYPES.get(str(kind))
    if allowed is None:
        return [f"fields.{name}: unknown semantic_kind {kind!r} ({sorted(SEMANTIC_KIND_TYPES)})"]
    if field_type not in allowed:
        problems.append(
            f"fields.{name}: semantic_kind {kind!r} needs type {sorted(allowed)}, "
            f"not {field_type!r}"
        )
    if kind == "code" and field.get("transform") in _NUMERIC_TRANSFORMS:
        problems.append(
            f"fields.{name}: a code keeps its source string; transform "
            f"{field.get('transform')!r} makes it a number"
        )
    if field.get("unit") and kind != "measure":
        problems.append(f"fields.{name}: unit belongs to a measure, not a {kind!r}")
    return problems


@dataclass(slots=True, frozen=True)
class ExampleSpec:
    """Call example declaration (shared by record/smoke/example generation)."""

    name: str
    description: str | None = None
    params: dict[str, str | int | float] = field(default_factory=dict)
    page: int | None = None
    page_size: int | None = None
    format: str | None = None


@dataclass(slots=True, frozen=True)
class LicenseSpec:
    """Data usage permission conditions declaration (#525).

    redistribution: allowed / non_commercial / forbidden / unknown.
    Default None means unknown — not knowing must not read as permission.
    attribution: the exact attribution text to display (not just a flag).
    quota: rate limit or traffic cap description from the provider.
    pii_columns: column names that may contain personally identifiable information.
    """

    type: str | None = None
    commercial_use: bool | None = None
    attribution_required: bool | None = None
    modification_allowed: bool | None = None
    note: str | None = None
    redistribution: str | None = None
    attribution: str | None = None
    quota: str | None = None
    pii_columns: tuple[str, ...] = ()


def reported_license(licence: LicenseSpec | None) -> LicenseSpec | None:
    """A spec's licence as a dataset reference reports it (#812).

    ``redistribution: allowed`` counts only with the ``attribution`` text that shows the
    terms were read from the provider's page (#525). A spec that says ``allowed`` without
    it — the ones frozen in ``scripts/unconfirmed_terms_baseline.txt`` (#732) — reports
    ``unknown``: a term nobody confirmed must not read as permission (#785), to someone
    using kpubdata directly as much as to Builder.

    The spec file keeps what it declares, so the baseline ratchet still counts it; only
    what is reported changes. The other terms already restrict and pass through.
    """
    if licence is None or licence.redistribution != "allowed":
        return licence
    if (licence.attribution or "").strip():
        return licence
    return replace(licence, redistribution="unknown")


@dataclass(slots=True, frozen=True)
class SpecDefinition:
    """Validated dataset spec definition."""

    id: str
    provider: str
    title: str
    endpoint: EndpointSpec
    auth: AuthSpec
    response: ResponseSpec
    pagination: PaginationSpec
    status: str = "active"
    description: str | None = None
    source: SourceRef | None = None
    params: tuple[ParamSpec, ...] = ()
    fields: tuple[FieldSpec, ...] = ()
    examples: tuple[ExampleSpec, ...] = ()
    last_verified: date | None = None
    license: LicenseSpec | None = None
    raw_metadata: dict[str, object] = field(default_factory=dict)

    @property
    def dataset_key(self) -> str:
        """Provider-local dataset key (last segment of id)."""
        return self.id.split(".", 1)[1] if "." in self.id else self.id


def _parse_date(value: object, problems: list[str], label: str) -> date | None:
    """Convert ISO YYYY-MM-DD string to date (record failure in problems list)."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            problems.append(f"{label}은(는) YYYY-MM-DD 형식이어야 합니다: {value!r}")
            return None
    problems.append(f"{label}은(는) 문자열 또는 null이어야 합니다: {type(value).__name__}")
    return None


#: What each KOGL (Korea Open Government License) type forbids: commercial use for types 2 and 4,
#: modification for types 3 and 4. Type 1 forbids neither (#719). Every type requires
#: attribution (docs/policy/terms-matrix.md), so none may waive it (#725).
_KOGL_FORBIDS: dict[str, tuple[bool, bool]] = {
    "공공누리_1유형": (False, False),
    "공공누리_2유형": (True, False),
    "공공누리_3유형": (False, True),
    "공공누리_4유형": (True, True),
}


def licence_conflicts(licence: Mapping[str, object]) -> list[str]:
    """Contradictions between a licence's KOGL type and its own flags (#719, #725).

    A consumer may read either the type or the flags, so a spec that says
    "type 3, modification allowed" tells two readers two different things.
    Refused: an explicit ``commercial_use: true`` under types 2 and 4, an
    explicit ``modification_allowed: true`` under types 3 and 4, and an
    explicit ``attribution_required: false`` under any KOGL type. A flag left
    undeclared, or a value of the wrong type (reported separately by its
    parser), says nothing here. A type that is not a KOGL type is not checked.

    Shared by the loader and ``scripts/validate_spec.py``.
    """
    licence_type = licence.get("type")
    if not isinstance(licence_type, str) or licence_type not in _KOGL_FORBIDS:
        return []
    no_commercial, no_modification = _KOGL_FORBIDS[licence_type]
    problems: list[str] = []
    if no_commercial and licence.get("commercial_use") is True:
        problems.append(
            f"license.commercial_use is true, but {licence_type} forbids commercial use"
        )
    if no_modification and licence.get("modification_allowed") is True:
        problems.append(
            f"license.modification_allowed is true, but {licence_type} forbids modification"
        )
    if licence.get("attribution_required") is False:
        problems.append(
            f"license.attribution_required is false, but {licence_type} requires attribution"
        )
    return problems


def insecure_http_problem(base_url: str | None, insecure_http_reason: str | None) -> str | None:
    """Why this endpoint sends its credentials over plain http:// (#738).

    The service key rides the query string, so over http:// anyone on the
    network path reads it.     https is the fix — the one host every http
    spec uses (apis.data.go.kr) answers it with identical envelopes, and
    the reproducible record (commands and raw envelopes for all 16
    service paths behind the baseline) sits as a comment on #738
    (2026-10-01). A provider that genuinely cannot serve https says why
    in ``insecure_http_reason``. None when the scheme is already https,
    the reason is written down, or there is nothing to judge.

    Shared by ``scripts/verify_spec.py`` and ``scripts/validate_spec.py``.
    """
    if base_url is None or not base_url.startswith("http://"):
        return None
    if (insecure_http_reason or "").strip():
        return None
    return (
        "endpoint.base_url 이 http:// 인데 endpoint.insecure_http_reason 이 비어 있다 — "
        "서비스 키가 쿼리로 실리는 요청을 평문으로 보내면 경로의 누구나 키를 볼 수 "
        "있다. https 로 바꾸고 재기록하거나, 제공기관이 https 를 지원하지 않는다면 "
        "그 사유를 insecure_http_reason 에 적는다 (#738)"
    )


def _parse_license(raw: object, problems: list[str]) -> LicenseSpec | None:
    """Convert license section to LicenseSpec."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        problems.append("license는 객체여야 합니다.")
        return None

    def _str_field(key: str) -> str | None:
        val = raw.get(key)
        if val is None:
            return None
        if not isinstance(val, str):
            problems.append(f"license.{key}은(는) 문자열이어야 합니다: {type(val).__name__}")
            return None
        return val

    def _bool_field(key: str) -> bool | None:
        val = raw.get(key)
        if val is None:
            return None
        if not isinstance(val, bool):
            problems.append(f"license.{key}은(는) boolean이어야 합니다: {type(val).__name__}")
            return None
        return val

    redistribution = _str_field("redistribution")
    if redistribution is not None and redistribution not in (
        "allowed",
        "non_commercial",
        "forbidden",
        "unknown",
    ):
        problems.append(
            f"license.redistribution must be one of "
            f"allowed/non_commercial/forbidden/unknown: {redistribution!r}"
        )
        redistribution = None

    pii_raw = raw.get("pii_columns")
    pii_columns: tuple[str, ...] = ()
    if pii_raw is not None:
        if isinstance(pii_raw, list) and all(isinstance(c, str) for c in pii_raw):
            pii_columns = tuple(pii_raw)
        else:
            problems.append("license.pii_columns은 문자열 리스트여야 합니다.")

    license_type = _str_field("type")
    commercial_use = _bool_field("commercial_use")
    attribution_required = _bool_field("attribution_required")
    modification_allowed = _bool_field("modification_allowed")
    problems.extend(
        licence_conflicts(
            {
                "type": license_type,
                "commercial_use": commercial_use,
                "attribution_required": attribution_required,
                "modification_allowed": modification_allowed,
            }
        )
    )

    return LicenseSpec(
        type=license_type,
        commercial_use=commercial_use,
        attribution_required=attribution_required,
        modification_allowed=modification_allowed,
        note=_str_field("note"),
        redistribution=redistribution,
        attribution=_str_field("attribution"),
        quota=_str_field("quota"),
        pii_columns=pii_columns,
    )


def _parse_params(raw: object, problems: list[str]) -> tuple[ParamSpec, ...]:
    """Convert params[] section to ParamSpec tuple."""
    if raw is None:
        return ()
    if not isinstance(raw, list):
        problems.append("params는 리스트여야 합니다.")
        return ()
    parsed: list[ParamSpec] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            problems.append(f"params[{index}]은(는) 객체여야 합니다.")
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name:
            problems.append(f"params[{index}].name은(는) 비어 있지 않은 문자열이어야 합니다.")
            continue
        enum_raw = item.get("enum") or []
        if not isinstance(enum_raw, list):
            problems.append(f"params[{index}].enum은(는) 리스트여야 합니다.")
            enum_raw = []
        raw_max_age = item.get("max_age_days")
        parsed.append(
            ParamSpec(
                name=name,
                type=item.get("type", "string") if isinstance(item.get("type"), str) else "string",
                alias=item.get("alias") if isinstance(item.get("alias"), str) else None,
                required=bool(item.get("required", False)),
                enum=tuple(v for v in enum_raw if isinstance(v, str)),
                description=item.get("description")
                if isinstance(item.get("description"), str)
                else None,
                example=item.get("example")
                if isinstance(item.get("example"), (str, int, float))
                else None,
                max_age_days=raw_max_age
                if isinstance(raw_max_age, int) and not isinstance(raw_max_age, bool)
                else None,
            )
        )
    return tuple(parsed)


def _section(data: dict[str, object], key: str) -> dict[str, object]:
    """Return subsection as dict from mapping (empty dict if missing/wrong type)."""
    value = data.get(key)
    if isinstance(value, dict):
        return dict(value)
    return {}


def _get_str(section: dict[str, object], key: str) -> str | None:
    """Extract non-empty string value from section (None if condition unmet)."""
    value = section.get(key)
    if isinstance(value, str) and value:
        return value
    return None


def from_mapping(data: dict[str, object]) -> SpecDefinition:
    """Convert mapping following schema structure to validated SpecDefinition.

    Args:
        data: Spec definition as a dictionary (usually from parsed YAML).

    Raises:
        InvalidRequestError: If there are any structural issues (missing required fields,
            enum mismatch, id mismatch, etc). All problems are bundled into one message.
    """
    problems: list[str] = []

    spec_id = _get_str(data, "id")
    provider = _get_str(data, "provider")
    title = _get_str(data, "title")
    if spec_id is None:
        problems.append("id은(는) 비어 있지 않은 문자열이어야 합니다.")
    if provider is None:
        problems.append("provider은(는) 비어 있지 않은 문자열이어야 합니다.")
    if title is None:
        problems.append("title은(는) 비어 있지 않은 문자열이어야 합니다.")

    endpoint_raw = _section(data, "endpoint")
    path_template = _get_str(endpoint_raw, "path_template")
    insecure_http_reason = _get_str(endpoint_raw, "insecure_http_reason")
    base_url = _get_str(endpoint_raw, "base_url")
    if base_url is None:
        problems.append("endpoint.base_url은(는) 비어 있지 않은 문자열이어야 합니다.")
    operation = _get_str(endpoint_raw, "operation")
    if operation is None:
        problems.append("endpoint.operation은(는) 비어 있지 않은 문자열이어야 합니다.")
    method = _get_str(endpoint_raw, "method") or "GET"
    if method not in {"GET", "POST"}:
        problems.append(f"endpoint.method는 GET 또는 POST여야 합니다: {method!r}")
    format_param: FormatParamSpec | None = None
    fp_raw = _section(endpoint_raw, "format_param")
    fp_name = _get_str(fp_raw, "name")
    if fp_raw and fp_name is None:
        problems.append("endpoint.format_param.name은(는) 비어 있지 않은 문자열이어야 합니다.")
    if fp_name is not None:
        values_raw = _section(fp_raw, "values")
        format_param = FormatParamSpec(
            name=fp_name,
            values={k: v for k, v in values_raw.items() if isinstance(v, str)},
        )
    endpoint = (
        EndpointSpec(
            base_url=base_url or "",
            operation=operation or "",
            method=method,
            format_param=format_param,
            path_template=path_template,
            insecure_http_reason=insecure_http_reason,
        )
        if base_url and operation
        else None
    )

    auth_raw = _section(data, "auth")
    auth_type = _get_str(auth_raw, "type")
    auth: AuthSpec | None = None
    if auth_type is None:
        problems.append("auth.type는 필수입니다.")
    elif auth_type not in _AUTH_TYPES:
        problems.append(f"auth.type는 {_sorted(_AUTH_TYPES)} 중 하나여야 합니다: {auth_type!r}")
        auth = AuthSpec(type=auth_type)
    else:
        auth = AuthSpec(
            type=auth_type,
            param_name=_get_str(auth_raw, "param_name"),
            provider_key=_get_str(auth_raw, "provider_key"),
        )

    response_raw = _section(data, "response")
    resp_format = _get_str(response_raw, "format")
    envelope = _get_str(response_raw, "envelope")
    response: ResponseSpec | None = None
    if resp_format is None:
        problems.append("response.format는 필수입니다.")
    elif resp_format not in _FORMATS:
        problems.append(
            f"response.format는 {_sorted(_FORMATS)} 중 하나여야 합니다: {resp_format!r}"
        )
    if envelope is None:
        problems.append("response.envelope는 필수입니다.")
    elif envelope not in _ENVELOPES:
        problems.append(
            f"response.envelope는 {_sorted(_ENVELOPES)} 중 하나여야 합니다: {envelope!r}"
        )
    error_raw = _section(response_raw, "error")
    error_style = _get_str(error_raw, "style")
    if error_style is None:
        problems.append("response.error.style는 필수입니다.")
    elif error_style not in _ERROR_STYLES:
        allowed_styles = _sorted(_ERROR_STYLES)
        problems.append(
            f"response.error.style는 {allowed_styles} 중 하나여야 합니다: {error_style!r}"
        )
    if resp_format and envelope and error_style:
        ok_values_raw = error_raw.get("ok_values")
        ok_values = (
            tuple(v for v in ok_values_raw if isinstance(v, (str, int)) and not isinstance(v, bool))
            if isinstance(ok_values_raw, list)
            else ()
        )
        response = ResponseSpec(
            format=resp_format,
            envelope=envelope,
            items_path=_get_str(response_raw, "items_path"),
            total_count_path=_get_str(response_raw, "total_count_path"),
            error=ErrorSpec(
                style=error_style, code_path=_get_str(error_raw, "code_path"), ok_values=ok_values
            ),
        )

    pagination_raw = _section(data, "pagination")
    pg_type = _get_str(pagination_raw, "type")
    pagination: PaginationSpec | None = None
    if pg_type is None:
        problems.append("pagination.type는 필수입니다.")
    elif pg_type not in _PAGINATION_TYPES:
        allowed_pg = _sorted(_PAGINATION_TYPES)
        problems.append(f"pagination.type는 {allowed_pg} 중 하나여야 합니다: {pg_type!r}")
    else:
        max_size_obj = pagination_raw.get("max_size")
        if max_size_obj is not None and (
            isinstance(max_size_obj, bool) or not isinstance(max_size_obj, int) or max_size_obj < 1
        ):
            problems.append("pagination.max_size는 1 이상의 정수여야 합니다.")
            max_size_obj = None
        start_base = pagination_raw.get("start_index_base")
        pagination = PaginationSpec(
            type=pg_type,
            page_param=_get_str(pagination_raw, "page_param"),
            size_param=_get_str(pagination_raw, "size_param"),
            max_size=max_size_obj if isinstance(max_size_obj, int) else None,
            start_index_base=start_base if isinstance(start_base, int) else None,
        )

    status = _get_str(data, "status") or "active"
    if status not in _STATUSES:
        problems.append(f"status는 {_sorted(_STATUSES)} 중 하나여야 합니다: {status!r}")

    if spec_id is not None and "." not in spec_id:
        problems.append(f"id는 '{{provider}}.{{dataset_key}}' 형식이어야 합니다: {spec_id!r}")
    if spec_id is not None and provider is not None and "." in spec_id:
        id_prefix = spec_id.split(".", 1)[0]
        if id_prefix != provider:
            problems.append(f"id 접두사({id_prefix})가 provider 필드({provider})와 불일치합니다.")

    source_raw = _section(data, "source")
    fields_list = data.get("fields")
    examples_list = data.get("examples")

    # These three parsers record in problems but return None for the value.
    # Previously they were called inside SpecDefinition constructor arguments,
    # after the `if problems: raise` check already passed, so recorded problems
    # were discarded entirely — a value like last_verified: "2026-13-45" became
    # None silently, indistinguishable from unverified specs. Call them before the check.
    source_verified_at = _parse_date(source_raw.get("verified_at"), problems, "source.verified_at")
    params_parsed = _parse_params(data.get("params"), problems)
    last_verified = _parse_date(data.get("last_verified"), problems, "last_verified")
    license_parsed = _parse_license(data.get("license"), problems)
    if isinstance(fields_list, list):
        for item in fields_list:
            if isinstance(item, dict):
                problems.extend(field_conflicts(dict(item)))

    if problems:
        raise InvalidRequestError(
            "데이터셋 spec 구조 검증 실패: " + " | ".join(problems),
            provider=provider,
            dataset_id=spec_id,
        )

    fields_parsed: list[FieldSpec] = []
    if isinstance(fields_list, list):
        for item in fields_list:
            if not isinstance(item, dict):
                continue
            item_dict: dict[str, object] = dict(item)
            name = _get_str(item_dict, "name")
            if name is None:
                continue
            type_value = _get_str(item_dict, "type") or "string"
            fields_parsed.append(
                FieldSpec(
                    name=name,
                    type=type_value,
                    source_name=_get_str(item_dict, "source_name"),
                    unit=_get_str(item_dict, "unit"),
                    transform=_get_str(item_dict, "transform"),
                    description=_get_str(item_dict, "description"),
                    semantic_kind=_get_str(item_dict, "semantic_kind"),
                    title=_get_str(item_dict, "title"),
                    format=_get_str(item_dict, "format"),
                )
            )

    examples_parsed: list[ExampleSpec] = []
    if isinstance(examples_list, list):
        for item in examples_list:
            if not isinstance(item, dict):
                continue
            ex_dict: dict[str, object] = dict(item)
            name = _get_str(ex_dict, "name")
            if name is None:
                continue
            params_raw = ex_dict.get("params")
            params = (
                {
                    k: v
                    for k, v in dict(params_raw).items()
                    if isinstance(k, str)
                    and isinstance(v, (str, int, float))
                    and not isinstance(v, bool)
                }
                if isinstance(params_raw, dict)
                else {}
            )
            page_obj = ex_dict.get("page")
            size_obj = ex_dict.get("page_size")
            examples_parsed.append(
                ExampleSpec(
                    name=name,
                    description=_get_str(ex_dict, "description"),
                    params=params,
                    page=page_obj
                    if isinstance(page_obj, int) and not isinstance(page_obj, bool)
                    else None,
                    page_size=(
                        size_obj
                        if isinstance(size_obj, int) and not isinstance(size_obj, bool)
                        else None
                    ),
                    format=_get_str(ex_dict, "format"),
                )
            )

    assert endpoint is not None  # noqa: S101 — always exists after validation passes above
    assert auth is not None  # noqa: S101
    assert response is not None  # noqa: S101
    assert pagination is not None  # noqa: S101

    return SpecDefinition(
        id=spec_id or "",
        provider=provider or "",
        title=title or "",
        endpoint=endpoint,
        auth=auth,
        response=response,
        pagination=pagination,
        status=status,
        description=_get_str(data, "description"),
        source=SourceRef(
            url=_get_str(source_raw, "url"),
            doc_version=_get_str(source_raw, "doc_version"),
            verified_at=source_verified_at,
        ),
        params=params_parsed,
        fields=tuple(fields_parsed),
        examples=tuple(examples_parsed),
        last_verified=last_verified,
        license=license_parsed,
        raw_metadata=dict(data),
    )


def load_spec_file(path: Path) -> SpecDefinition:
    """Read YAML spec file and convert to validated SpecDefinition.

    Args:
        path: Path to the YAML spec file.

    Raises:
        InvalidRequestError: If YAML parsing fails or root is not a mapping.
    """
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=_SafeLoader)
    except yaml.YAMLError as exc:
        msg = f"spec YAML 파싱 실패: {path}"
        raise InvalidRequestError(msg) from exc
    if not isinstance(data, dict):
        msg = f"spec 루트는 매핑이어야 합니다: {path}"
        raise InvalidRequestError(msg)
    return from_mapping(data)


#: libyaml's safe loader when PyYAML was built with it, the pure-Python one otherwise.
#: Both resolve the same YAML 1.1 types; the C one parses the bundled specs ten times
#: faster.
_SafeLoader: type[yaml.SafeLoader] = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def _default_specs_dir() -> Path:
    """Return bundled specs directory path.

    Interpreted as a relative path from this module file (src/kpubdata/core/spec.py).
    We don't use importlib.resources because: (1) it conflicts with global
    import mocking in existing tests (test_client_transport_requirements), and
    (2) it works identically across filesystem deployments (dev checkout,
    site-packages, wheel). Zipimport-loaded special environments are not supported
    (honest limitation).
    """
    return Path(__file__).resolve().parent.parent / "specs"


def _iter_yaml_files(root: Path) -> list[Path]:
    """Recursively traverse directory and return *.yaml/*.yml files as sorted list."""
    files = [*root.rglob("*.yaml"), *root.rglob("*.yml")]
    return sorted(files)


#: The specs shipped in the package, parsed once per process and directory (#822). The
#: files do not change while the process runs, and a client read all of them again for
#: every provider it resolved.
_bundled_specs: dict[Path, tuple[SpecDefinition, ...]] = {}
_bundled_specs_lock = threading.Lock()


def _load_specs(target: Path) -> list[SpecDefinition]:
    return [load_spec_file(path) for path in _iter_yaml_files(target)]


def discover_specs(root: Path | None = None) -> list[SpecDefinition]:
    """Load all specs from specs directory.

    If root is omitted, discovers from the in-package ``kpubdata/specs/``.
    schema.json is not YAML so it's naturally excluded.

    The in-package specs are read and validated once per process; every call gets its
    own copy, so a caller that changes what it was given changes nothing for the next
    (a spec is frozen, but holds dictionaries). A directory passed as ``root`` is read
    on every call: its files are the caller's and may change between calls.
    """
    if root is not None:
        return _load_specs(root) if root.is_dir() else []
    return copy.deepcopy(list(_shared_bundled_specs()))


def _shared_bundled_specs() -> tuple[SpecDefinition, ...]:
    """Return the parsed in-package specs themselves, not a copy.

    The objects are shared by every caller: a caller copies what it keeps before it
    hands it on. ``discover_specs()`` copies all of them; a caller that needs a few
    copies only those.
    """
    target = _default_specs_dir()
    cached = _bundled_specs.get(target)
    if cached is None:
        with _bundled_specs_lock:
            cached = _bundled_specs.get(target)
            if cached is None:
                if not target.is_dir():
                    return ()
                cached = tuple(_load_specs(target))
                _bundled_specs[target] = cached
    return cached


def _forget_bundled_specs() -> None:
    """Drop the parsed in-package specs, so the next call reads the files again."""
    with _bundled_specs_lock:
        _bundled_specs.clear()


def spec_index(root: Path | None = None) -> dict[str, SpecDefinition]:
    """Return id → SpecDefinition dictionary."""
    return {spec.id: spec for spec in discover_specs(root)}


def find_spec(
    dataset_key: str, provider: str | None = None, root: Path | None = None
) -> SpecDefinition | None:
    """Find spec by "provider.key" or bare key (None if not found)."""
    for spec in discover_specs(root):
        if spec.id == dataset_key:
            return spec
        bare_key_match = "." not in dataset_key and spec.dataset_key == dataset_key
        if bare_key_match and (provider is None or spec.provider == provider):
            return spec
    return None


#: The one line the recorder rewrites after a successful record (#522).
_LAST_VERIFIED_LINE = re.compile(r"^last_verified:.*$\n?", re.MULTILINE)


def spec_file_digest(path: Path) -> str | None:
    """Digest a spec file's pipeline-relevant content (#522).

    Evidence binding hashes what the recorder executed, so the digest must
    stay stable across the one rewrite the recorder itself performs after
    recording: ``record.py`` syncs ``last_verified`` to the record date —
    provenance, not pipeline. Those lines are dropped before hashing; any
    other change moves the digest and voids evidence recorded against the
    old spec. None when the file cannot be read.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    normalized = _LAST_VERIFIED_LINE.sub("", text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _sorted(values: frozenset[str]) -> str:
    """Convert enum set to human-readable choice string."""
    return "|".join(sorted(values))


__all__ = [
    "AuthSpec",
    "EndpointSpec",
    "ErrorSpec",
    "ExampleSpec",
    "FieldSpec",
    "FormatParamSpec",
    "LicenseSpec",
    "PaginationSpec",
    "ParamSpec",
    "ResponseSpec",
    "SourceRef",
    "SpecDefinition",
    "discover_specs",
    "find_spec",
    "from_mapping",
    "load_spec_file",
    "spec_file_digest",
    "spec_index",
]
