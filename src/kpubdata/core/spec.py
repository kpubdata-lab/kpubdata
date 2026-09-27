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

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

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
_STATUSES = frozenset({"active", "deprecated", "broken", "unstable"})


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
    """Data usage permission conditions declaration."""

    type: str | None = None
    commercial_use: bool | None = None
    attribution_required: bool | None = None
    modification_allowed: bool | None = None
    note: str | None = None


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

    return LicenseSpec(
        type=_str_field("type"),
        commercial_use=_bool_field("commercial_use"),
        attribution_required=_bool_field("attribution_required"),
        modification_allowed=_bool_field("modification_allowed"),
        note=_str_field("note"),
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
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        msg = f"spec YAML 파싱 실패: {path}"
        raise InvalidRequestError(msg) from exc
    if not isinstance(data, dict):
        msg = f"spec 루트는 매핑이어야 합니다: {path}"
        raise InvalidRequestError(msg)
    return from_mapping(data)


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


def discover_specs(root: Path | None = None) -> list[SpecDefinition]:
    """Load all specs from specs directory.

    If root is omitted, discovers from the in-package ``kpubdata/specs/``.
    schema.json is not YAML so it's naturally excluded.
    """
    target = _default_specs_dir() if root is None else root
    if not target.is_dir():
        return []
    return [load_spec_file(path) for path in _iter_yaml_files(target)]


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
    "spec_index",
]
