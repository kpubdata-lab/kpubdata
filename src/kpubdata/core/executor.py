"""Generic Executor — 선언적 spec만으로 데이터셋 조회를 수행한다.

spec 시스템(#378)의 실행 계층이다. ``kpubdata.core.spec.SpecDefinition``가
선언한 인증·파라미터·페이지네이션·envelope·에러 규칙을 그대로 해석해
기존 어댑터와 동일한 관찰 가능한 동작(RecordBatch 의미론)을 낸다.

범위(파일럿):
- 인증: ``query_param`` (그 외는 미구현 — 커스텀 어댑터가 담당)
- 페이지네이션: ``page_no_rows``, ``none`` (그 외 미구현)
- envelope: ``datago_standard`` (경로 기반 일반 추출 — data.go.kr 계열 공용)
- 에러: ``header_result_code`` (data.go.kr resultCode 표준 표)

계층 규칙: core는 providers를 import하지 않는다. datago 어댑터의 동작은
복제하되 의존하지 않는다(검증: tests/unit/core/test_executor.py).
"""

from __future__ import annotations

import logging
from types import MappingProxyType
from typing import cast

from kpubdata._hosts import extra_hosts_env_var, host_is_allowed
from kpubdata.config import KPubDataConfig
from kpubdata.core.capability import Operation, PaginationMode, QuerySupport
from kpubdata.core.models import DatasetRef, Query, RecordBatch, SchemaDescriptor
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
# core가 providers를 import하지 않기 위해, datago 403 힌트를 일반화해 재정의한다.
_FORBIDDEN_HINT = (
    "Provider returned 403. This usually means the specific API has not been activated "
    "(활용신청) for your key. Check the dataset's documentation page for your provider."
)


def _resolve_path(path: str | None, spec: SpecDefinition | None = None) -> str | None:
    """경로의 ``{operation}`` 플레이스홀더를 해당 데이터셋의 operation으로 치환한다."""
    if path is None:
        return None
    if spec is None:
        return path
    return path.replace("{operation}", spec.endpoint.operation)


def _dot_get(payload: object, path: str | None) -> object | None:
    """점 경로로 페이로드를 순회한다.

    숫자 세그먼트는 배열 인덱스로 취급한다(예: ``AJGCF.0.head.0.list_total_count``).
    특수 경로 ``$`` 는 루트 페이로드 자체를 반환한다(kosis 최상위 배열 등).
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
    """문자열/정수를 int로 변환한다(불가·불리언은 None)."""
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


def _normalize_item_list(value: object) -> list[dict[str, object]]:
    """items 리프 값을 레코드 dict 목록으로 정규화한다(단일 dict → 1개 리스트)."""
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _apply_transform(value: object, transform: str) -> object:
    """단일 필드 변환을 적용한다(값이 없으면 그대로 반환)."""
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


def _try_cast_field(value: object, field_type: str) -> tuple[bool, object]:
    """선언된 타입으로 캐스팅을 시도하고 (성공 여부, 값)을 반환한다.

    실패해도 원문을 함께 돌려준다 — 호출부가 컬럼 전체를 보고 적용 여부를 정한다
    (``_normalize_fields`` 참조).
    """
    if value is None:
        return True, None
    if field_type == "integer":
        coerced = _to_int(value)
        return (True, coerced) if coerced is not None else (False, value)
    if field_type == "number":
        if isinstance(value, bool):
            return False, value
        if isinstance(value, (int, float)):
            return True, value
        if isinstance(value, str):
            try:
                return True, float(value)
            except ValueError:
                return False, value
        return False, value
    return True, value


def _cast_field(value: object, field_type: str) -> object:
    """선언된 타입으로 캐스팅한다(실패 시 원문을 보존한다)."""
    _, coerced = _try_cast_field(value, field_type)
    return coerced


#: data.go.kr 게이트웨이가 서비스 대신 답할 때 쓰는 봉투. 요청이 서비스에 닿기
#: 전에 거부되면 ``<response>`` 대신 이 모양이 온다 — 등록되지 않은 키, 만료된
#: 활용신청, 허용되지 않은 IP, 일일 한도 초과.
_GATEWAY_ENVELOPE_KEY = "OpenAPI_ServiceResponse"
_GATEWAY_HEADER_KEY = "cmmMsgHeader"


def _gateway_rejection(payload: dict[str, object]) -> tuple[str, str] | None:
    """게이트웨이 거부면 ``(code, message)``, 아니면 None.

    ``returnReasonCode`` 는 서비스 envelope 의 ``resultCode`` 와 같은 어휘를 쓰므로
    같은 매핑에 넘길 수 있다. #478 이 datago **어댑터** 에만 이 분기를 넣었는데,
    spec 우선 경로를 타는 20여 종은 여전히 "응답 envelope에서 에러 코드를 찾을 수
    없습니다" 로 실패했다 — 고칠 수 있는 문제가 파싱 오류로 보였다.
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


class SpecExecutor:
    """spec 정의를 해석해 조회를 실행하는 Provider 비종속 실행기."""

    def __init__(self, transport: HttpTransport, config: KPubDataConfig) -> None:
        """전송 계층과 설정을 주입받아 실행기를 초기화한다."""
        self._transport = transport
        self._config = config

    # ------------------------------------------------------------------
    # 요청 조립
    # ------------------------------------------------------------------

    def _resolve_format_value(self, spec: SpecDefinition, format_hint: str | None) -> str | None:
        """format_hint에 해당하는 포맷 파라미터 값을 spec에서 해석한다."""
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
        """인증·포맷·페이지네이션·필터를 조립한 쿼리 파라미터를 만든다.

        예외:
            InvalidRequestError: 파라미터 이름이 선언되지 않은 페이지네이션 방식인 경우.
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
            # 키는 URL 경로(path_template의 {key})로 싣는다 — 쿼리에서는 제거된다.
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
            # lofin(pIndex/pSize, 1-기반)·law(page/display) — 쿼리 파라미터 방식
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
            # bok/seoul 계열 — start/end가 URL 경로에 들어간다(path_template {{start}}/{{end}}).
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
            # 인증·포맷·페이지 파라미터는 이미 채웠으므로 사용자 필터로 덮어쓰지 않는다.
            if key.lower() in reserved:
                continue
            provider_name = alias_map.get(key, key)
            params[provider_name] = str(raw_value)

        return params

    # ------------------------------------------------------------------
    # 전송·디코딩
    # ------------------------------------------------------------------

    def build_url(
        self,
        spec: SpecDefinition,
        page: int = 1,
        page_size: int = _DEFAULT_PAGE_SIZE,
        api_key: str = "",
    ) -> str:
        """spec 엔드포인트 URL을 조립한다.

        ``endpoint.path_template``이 있으면 ``{key}``·``{operation}``·``{start}``·``{end}``
        플레이스홀더를 치환한다(bok/seoul 계열의 경로 내 키·범위). 없으면
        ``{base}/{operation}`` 기본 형태를 쓴다.
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

    def _request(self, spec: SpecDefinition, params: dict[str, str]) -> dict[str, object]:
        """spec 엔드포인트로 GET 요청을 보내고 디코딩된 dict를 반환한다.

        예외:
            AuthError: 전송 계층 403의 경우(활용신청 힌트 포함).
            ProviderResponseError: 디코딩 결과가 dict가 아닌 경우.
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
            # ``exc.status_code`` 로 본다. ``__cause__`` 를 보던 시절에는 키가
            # 섞인 요청에서 transport 가 체인을 끊으면(그래야 한다) 403 판정이
            # 통째로 사라졌다 — 키 마스킹과 403 힌트가 서로를 무효화했다.
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
            return decoded
        msg = f"{spec.id}: 응답 페이로드가 객체가 아닙니다({type(decoded).__name__})."
        raise ProviderResponseError(msg, provider=spec.provider, dataset_id=spec.id)

    # ------------------------------------------------------------------
    # envelope·에러 매핑
    # ------------------------------------------------------------------

    def _require_supported_envelope(self, spec: SpecDefinition) -> None:
        """파일럿 범위 밖 envelope를 명확히 거부한다."""
        if spec.response.envelope != "datago_standard":
            msg = (
                f"{spec.id}: envelope={spec.response.envelope!r}은(는) "
                "아직 spec 실행기가 지원하지 않습니다."
            )
            raise NotImplementedError(msg)

    def _raise_for_code(self, spec: SpecDefinition, code: str, message: str) -> None:
        """모듈 함수에 위임한다 — 같은 규칙이 두 벌 있으면 반드시 갈라진다."""
        raise_for_code(spec, code, message)

    def _check_error(self, spec: SpecDefinition, payload: dict[str, object]) -> None:
        """모듈 함수에 위임한다.

        예전에는 같은 판정을 여기서 따로 구현했고, 그 사본에는 모듈 쪽에만
        추가된 네 가지가 빠져 있었다 — ``err_field`` style(kosis), code_path 의
        ``{operation}`` 치환(lofin 계열), KorService 류의 최상단 ``resultCode``
        폴백, ``resultMsg``/``errMsg`` 메시지 폴백.

        그 결과 ``make verify`` 는 모듈 함수를 쓰고 실제 실행은 이 메서드를 써서,
        **verify 통과가 실행 경로를 검증한다는 보장이 없었다.** kosis 처럼
        code 체계가 없는 provider 는 성공 응답에도 "에러 코드를 찾을 수
        없습니다" 로 실패했다.
        """
        check_payload_error(spec, payload)

    def _extract_items(
        self, spec: SpecDefinition, payload: dict[str, object]
    ) -> list[dict[str, object]]:
        """모듈 함수에 위임한다.

        사본에는 ``neis_double_list`` envelope, ``{operation}`` 치환, 루트를
        가리키는 ``$``(kosis 최상위 배열)가 모두 빠져 있었다 — 그 provider 들은
        verify 를 통과하면서 실행 시에는 빈 목록을 돌려줬다.
        """
        return extract_items(spec, payload)

    def _extract_total_count(self, spec: SpecDefinition, payload: dict[str, object]) -> int | None:
        """total_count_path 규칙으로 총건수를 추출한다(없으면 None)."""
        raw = _dot_get(payload, spec.response.total_count_path)
        coerced = _to_int(raw)
        return coerced if coerced else None

    # ------------------------------------------------------------------
    # 정규화
    # ------------------------------------------------------------------

    def _normalize_fields(
        self, spec: SpecDefinition, items: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        """fields[] 선언이 있을 때만 rename·transform·캐스팅을 적용한다.

        캐스팅은 **컬럼 단위로 전부 성공할 때만** 적용한다. 행마다 따로 판단하면
        같은 컬럼에 캐스팅된 값과 원문이 섞여, 소비자가 표 형태로 다룰 때 타입이
        깨진다 — 예컨대 실거래가의 ``aptDong`` 은 대부분 ``"105"`` 지만 일부 행에는
        동 이름(``"현대뜨레비앙"``)이 들어와, 행 단위 캐스팅은 int와 str이 공존하는
        컬럼을 만든다. 한 값이라도 캐스팅에 실패하면 그 컬럼은 원문 그대로 둔다 —
        spec의 타입 선언이 실제 데이터와 어긋나더라도 downstream이 깨지지 않는다.
        """
        if not spec.fields:
            return items

        # 1단계: rename과 transform만 적용한다(캐스팅은 컬럼 전체를 본 뒤에).
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

        # 2단계: 컬럼 단위 캐스팅 — 전부 성공할 때만 반영한다.
        for field in spec.fields:
            casts: list[tuple[dict[str, object], object]] = []
            castable = True
            for record in staged:
                if field.name not in record:
                    continue
                succeeded, coerced = _try_cast_field(record[field.name], field.type)
                if not succeeded:
                    castable = False
                    break
                casts.append((record, coerced))
            if not castable:
                logger.debug(
                    "leaving column uncast: a value does not match the declared type",
                    extra={"dataset_id": spec.id, "field": field.name, "type": field.type},
                )
                continue
            for record, coerced in casts:
                record[field.name] = coerced

        return staged

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------

    def query(
        self,
        spec: SpecDefinition,
        dataset: DatasetRef,
        query: Query,
        format_hint: str | None = None,
    ) -> RecordBatch:
        """spec에 따라 조회를 실행해 RecordBatch를 반환한다."""
        self._require_supported_envelope(spec)
        params = self.build_params(spec, query, format_hint=format_hint)
        payload = self._request(spec, params)
        self._check_error(spec, payload)

        items = self._normalize_fields(spec, self._extract_items(spec, payload))
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

        return RecordBatch(
            items=items,
            dataset=dataset,
            total_count=total_count,
            next_page=next_page,
            raw=payload,
        )

    def fetch(
        self,
        spec: SpecDefinition,
        query: Query,
        format_hint: str | None = None,
    ) -> tuple[dict[str, str], dict[str, object]]:
        """요청 파라미터와 디코딩된 원본 페이로드를 함께 반환한다(record용).

        query와 달리 envelope 해석·정규화를 수행하지 않는다 — 기록 도구가
        raw/expected를 각자 저장하기 위한 저수준 진입점이다.
        """
        self._require_supported_envelope(spec)
        params = self.build_params(spec, query, format_hint=format_hint)
        payload = self._request(spec, params)
        return params, payload

    def request_raw(
        self,
        spec: SpecDefinition,
        params: dict[str, object],
        format_hint: str | None = None,
    ) -> dict[str, object]:
        """envelope 해석 없이 디코딩된 원본 페이로드를 반환한다(raw 비상구)."""
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
        return self._request(spec, string_params)


def raise_for_code(spec: SpecDefinition, code: str, message: str) -> None:
    """에러 코드를 표준 예외로 매핑한다(data.go.kr resultCode 표준 표)."""
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
    """에러 코드 경로를 검사하고 실패 코드면 예외를 발생시킨다(record·verify 공용)."""
    error = spec.response.error
    # 게이트웨이가 서비스 대신 답했으면 선언된 code_path 를 찾아봐야 없다.
    # builder 의 verify 와 record 가 이 함수를 쓰므로 여기도 같이 본다.
    gateway = _gateway_rejection(payload)
    if gateway is not None:
        raise_for_code(spec, gateway[0], gateway[1])
    if error.style == "err_field":
        # kosis류: 코드 체계가 없고 err 필드 존재 자체가 실패를 뜻한다.
        err_raw = payload.get("err")
        if isinstance(err_raw, (str, dict)):
            raise ProviderResponseError(
                f"{spec.id}: Provider 오류 응답: {str(err_raw)[:200]}",
                provider=spec.provider,
                dataset_id=spec.id,
            )
        return
    raw_code = _dot_get(payload, _resolve_path(error.code_path, spec))
    # 폴백: 한국관광공사 KorService류는 에러를 envelope 밖 최상단 resultCode로
    # 평면 반환한다(성공은 정상 envelope). 선언 경로에 없으면 최상단을 확인한다.
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
    """spec의 items_path 규칙으로 레코드 목록을 추출한다(record·verify 공용).

    - ``{operation}`` 플레이스홀더 지원(lofin 계열: ``{operation}.1.row``)
    - ``$`` 는 루트(kosis 최상위 배열)
    - envelope ``neis_double_list`` 는 블록별 row를 병합한다
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
    """NEIS 이중 리스트 envelope: ``{operation}[].row`` 블록을 모두 병합한다."""
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
    """spec의 total_count_path 규칙으로 총건수를 추출한다(없으면 None)."""
    resolved = _resolve_path(spec.response.total_count_path, spec)
    raw = _dot_get(payload, resolved)
    coerced = _to_int(raw)
    return coerced if coerced else None


def _message_path(code_path: str | None) -> str | None:
    """resultCode 경로에서 대응하는 resultMsg 경로를 유추한다."""
    if not code_path:
        return None
    segments = code_path.split(".")
    segments[-1] = "resultMsg"
    return ".".join(segments)


def _spec_request_parameters(spec: SpecDefinition) -> tuple[MappingProxyType[str, object], ...]:
    """spec params를 catalogue ``request_parameters``와 같은 형태로 변환한다 (#375).

    ``query_support.filterable_fields`` 는 "필터 가능한 이름"만 알려줄 뿐이라,
    소비자(Builder/Studio)는 어떤 파라미터가 **필수**인지, 무슨 값을 넣어야 하는지
    알 수 없었다. spec에는 그 정보가 이미 있으므로 그대로 노출한다.

    catalogue 엔트리의 ``request_parameters``(#374)와 키 이름을 맞춰
    소비자가 두 경로를 한 가지 형태로 읽을 수 있게 한다. ``name`` 은 호출 시
    실제로 넘기는 이름(alias 우선)이고, 원 API 파라미터 이름은 ``api_name`` 으로
    따로 싣는다 — 둘이 다를 때 사용자가 넘겨야 하는 쪽은 언제나 ``name`` 이다.
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
    """SpecDefinition을 catalogue와 동일한 의미론의 DatasetRef로 변환한다."""
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
        # 언제 기준의 명세인지 — 소비자가 메타데이터의 신선도를 판단할 수 있게 한다.
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
    """하나의 Provider 분량 spec 묶음을 ProviderAdapter 프로토콜로 노출한다.

    레지스트리 통합 전 파일럿용: 기존 어댑터와 동일한 인터페이스를 제공하되
    spec 실행기가 조회를 수행한다. call_raw는 항상 원본 페이로드를 반환한다.
    """

    def __init__(self, provider: str, specs: list[SpecDefinition], executor: SpecExecutor) -> None:
        """Provider 식별자·spec 목록·실행기로 어댑터를 초기화한다."""
        self._provider = provider
        self._specs = {spec.dataset_key: spec for spec in specs if spec.provider == provider}
        self._executor = executor
        self.requires_api_key: bool = any(spec.auth.type != "none" for spec in self._specs.values())

    @property
    def name(self) -> str:
        """Provider 식별자를 반환한다."""
        return self._provider

    def list_datasets(self) -> list[DatasetRef]:
        """보유한 spec 전체를 DatasetRef로 반환한다."""
        return [build_spec_dataset_ref(spec) for spec in self._specs.values()]

    def search_datasets(self, text: str) -> list[DatasetRef]:
        """id·제목·설명에 대한 부분 문자열 검색 결과를 반환한다."""
        needle = text.lower()
        return [
            build_spec_dataset_ref(spec)
            for spec in self._specs.values()
            if needle in spec.id.lower()
            or needle in spec.title.lower()
            or (spec.description is not None and needle in spec.description.lower())
        ]

    def get_dataset(self, dataset_key: str) -> DatasetRef:
        """Provider 로컬 키로 DatasetRef를 해석한다.

        예외:
            DatasetNotFoundError: 알 수 없는 키인 경우.
        """
        spec = self._specs.get(dataset_key)
        if spec is None:
            msg = f"Unknown dataset key for spec adapter: {self._provider}.{dataset_key}"
            raise DatasetNotFoundError(msg, provider=self._provider)
        return build_spec_dataset_ref(spec)

    def query_records(self, dataset: DatasetRef, query: Query) -> RecordBatch:
        """spec 실행기로 정규 목록 질의를 실행한다."""
        spec = self._specs.get(dataset.dataset_key)
        if spec is None:
            msg = f"Unknown dataset key for spec adapter: {dataset.id}"
            raise DatasetNotFoundError(msg, provider=self._provider, dataset_id=dataset.id)
        return self._executor.query(spec, dataset, query)

    def get_schema(self, dataset: DatasetRef) -> SchemaDescriptor | None:
        """아직 스키마 메타데이터를 지원하지 않는다(정직한 선언)."""
        return None

    def call_raw(self, dataset: DatasetRef, operation: str, params: dict[str, object]) -> object:
        """원본 페이로드를 반환하는 raw 비상구를 보장한다."""
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
