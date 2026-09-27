"""선별된 데이터셋 카탈로그를 포함한 data.go.kr 어댑터."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import cast
from urllib.parse import urlparse

from kpubdata._hosts import host_is_allowed
from kpubdata.config import KPubDataConfig
from kpubdata.core.models import (
    DatasetRef,
    Query,
    RecordBatch,
    SchemaDescriptor,
)
from kpubdata.exceptions import (
    AuthError,
    DatasetNotFoundError,
    InvalidRequestError,
    ParseError,
    ProviderResponseError,
    TransportError,
)
from kpubdata.providers._common import build_schema_from_metadata, coerce_int, load_catalogue
from kpubdata.providers.datago.envelope import DataGoEnvelopeParser
from kpubdata.transport.decode import decode_json, decode_xml, detect_content_type
from kpubdata.transport.http import HttpTransport, TransportConfig

logger = logging.getLogger("kpubdata.provider.datago")

_DATAGO_403_HINT = (
    "data.go.kr returned 403. This usually means the specific API has not been activated "
    "(활용신청) for your key. Visit the dataset's page on https://www.data.go.kr and "
    "click '활용신청'. Approval is usually automatic and becomes active within a few minutes."
)


def _is_allowed_datago_host(host: str) -> bool:
    """Whether the datago credential may be sent to ``host`` (#261).

    The list itself lives in ``kpubdata._hosts`` so that the spec executor reads
    the same one. It used to live here only, which meant ``datago.generic`` was
    guarded while every spec-driven call was not (#519).
    """
    return host_is_allowed("datago", host)


class DataGoAdapter:
    """data.go.kr(공공데이터포털)용 어댑터.

    apis.data.go.kr 엔드포인트 계열에서 지원하는 데이터셋의 선별된 카탈로그를 제공한다.
    """

    requires_api_key: bool = True

    def __init__(
        self,
        *,
        config: KPubDataConfig | None = None,
        transport: HttpTransport | None = None,
        catalogue: Sequence[DatasetRef] | None = None,
    ) -> None:
        """인스턴스가 사용할 내부 상태를 초기화한다."""
        self._config: KPubDataConfig = config or KPubDataConfig()
        transport_config = TransportConfig(
            timeout=self._config.timeout,
            max_retries=self._config.max_retries,
        )
        self._transport: HttpTransport = transport or HttpTransport(transport_config)

        datasets = tuple(catalogue) if catalogue is not None else self._load_default_catalogue()
        self._datasets: tuple[DatasetRef, ...] = datasets
        self._datasets_by_key: dict[str, DatasetRef] = {
            dataset.dataset_key: dataset for dataset in self._datasets
        }
        self._envelope_parser = DataGoEnvelopeParser()

    @property
    def name(self) -> str:
        """정규 Provider 키를 반환한다."""

        return "datago"

    def list_datasets(self) -> list[DatasetRef]:
        """data.go.kr에서 사용 가능한 데이터셋 목록을 반환한다."""

        return list(self._datasets)

    def search_datasets(self, text: str) -> list[DatasetRef]:
        """data.go.kr에서 사용 가능한 데이터셋을 검색한다."""

        needle = text.casefold()
        return [
            dataset
            for dataset in self._datasets
            if needle in dataset.id.casefold() or needle in dataset.name.casefold()
        ]

    def get_dataset(self, dataset_key: str) -> DatasetRef:
        """data.go.kr용 Provider 로컬 데이터셋 키를 해석한다."""

        dataset = self._datasets_by_key.get(dataset_key)
        if dataset is not None:
            return dataset

        logger.debug(
            "Datago dataset not found",
            extra={"dataset_id": f"datago.{dataset_key}", "provider": "datago"},
        )
        raise DatasetNotFoundError(
            f"Dataset not found: datago.{dataset_key}",
            provider="datago",
            dataset_id=f"datago.{dataset_key}",
        )

    def query_records(self, dataset: DatasetRef, query: Query) -> RecordBatch:
        """data.go.kr 데이터셋에서 레코드를 조회한다."""

        if self._is_generic(dataset):
            logger.debug(
                "Datago list called with unsupported operation (generic)",
                extra={"dataset_id": dataset.id},
            )
            raise InvalidRequestError(
                "datago.generic does not support list(); use call_raw with _base_url instead",
                provider="datago",
                dataset_id=dataset.id,
            )

        page = query.page or 1
        page_size = query.page_size or 100
        is_odcloud = self._is_odcloud(dataset)
        logger.debug(
            "datago query_records",
            extra={
                "dataset_id": dataset.id,
                "page": page,
                "page_size": page_size,
                "filter_keys": sorted(query.filters.keys()),
            },
        )

        url = self._build_request_url(dataset)
        params = self._build_base_params(dataset)
        fixed_query_params = self._get_fixed_query_params(dataset)
        params.update(fixed_query_params)
        page_param = "pageNo"
        page_size_param = "numOfRows"
        if is_odcloud:
            # odcloud 계열은 pageNo/numOfRows 대신 메타데이터에 정의된 페이지 파라미터 이름을 쓴다.
            pagination_params = dataset.raw_metadata.get("pagination_params")
            if isinstance(pagination_params, Mapping):
                pagination_params_dict = cast(Mapping[str, object], pagination_params)
                page_param_raw = pagination_params_dict.get("page")
                page_size_param_raw = pagination_params_dict.get("page_size")
                if isinstance(page_param_raw, str) and page_param_raw:
                    page_param = page_param_raw
                if isinstance(page_size_param_raw, str) and page_size_param_raw:
                    page_size_param = page_size_param_raw

        params[page_param] = str(page)
        params[page_size_param] = str(page_size)

        reserved = {params_key.lower() for params_key in params}
        reserved.update({page_param.lower(), page_size_param.lower()})
        for key, raw_value in query.filters.items():
            # 인증키·포맷·페이지 파라미터는 이미 채웠으므로 사용자 필터로 덮어쓰지 않는다.
            if key.lower() not in reserved:
                value: object = raw_value
                params[key] = str(value)
        self._apply_default_filters(params, dataset)
        payload = self._request_and_decode(url, params, dataset.id)
        if is_odcloud:
            body, items = self._envelope_parser.parse_odcloud(payload, dataset)
        else:
            body, items = self._envelope_parser.parse(payload, dataset)

        total_count = coerce_int(body.get("totalCount"), 0)
        if (total_count and page * page_size < total_count) or (
            not total_count and len(items) == page_size
        ):
            # totalCount가 없을 때는 현재 페이지가 꽉 찼는지를 다음 페이지 존재 신호로 사용한다.
            computed_next = page + 1
        else:
            computed_next = None

        if not items:
            logger.debug(
                "Datago envelope: zero items",
                extra={
                    "dataset_id": dataset.id,
                    "page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                },
            )

        return RecordBatch(
            items=items,
            dataset=dataset,
            total_count=total_count if total_count else None,
            next_page=computed_next,
            raw=payload,
        )

    def get_schema(self, dataset: DatasetRef) -> SchemaDescriptor | None:
        """data.go.kr 데이터셋의 스키마 메타데이터를 반환한다.

        가능하면 선별된 카탈로그 메타데이터에서 스키마를 반환한다.
        data.go.kr에는 실시간 스키마 탐색 엔드포인트가 없으므로, 카탈로그에
        명시적으로 선별된 필드 정의가 없는 데이터셋은 ``None``을 반환한다.
        """
        return build_schema_from_metadata(dataset)

    def call_raw(self, dataset: DatasetRef, operation: str, params: dict[str, object]) -> object:
        """data.go.kr 고유 API 작업을 호출한다.

        ``datago.generic``는 선별된 카탈로그에 없는 data.go.kr 엔드포인트를 위한
        raw 전용 비상구다. 정규화, 페이지네이션, 스키마 처리 없이 디코딩된 원시
        응답(dict)을 그대로 반환한다. 호출자는 다음을 전달해야 한다:
          * ``_base_url`` (str, 필수): 작업 이름을 제외한 엔드포인트 기본 URL.
          * ``_envelope`` (bool, 기본값 True): True이면 표준
            ``response.header.resultCode`` 엔벌로프를 검증한다. 실제 bool 값이어야 하며
            문자열/정수는 허용되지 않는다.
          * ``_service_key_param`` (str): service key 파라미터 이름을 재정의한다.
          * ``_format_param`` (str): 응답 형식 파라미터 이름을 재정의한다.

        ``_base_url``이 ``*.data.go.kr`` 호스트를 가리키지 않으면 경고를 기록한다.
        호출은 계속 진행되며, 이는 완화된 점검이다.
        """

        logger.debug(
            "datago call_raw",
            extra={
                "dataset_id": dataset.id,
                "operation": operation,
                "param_keys": sorted(params.keys()),
            },
        )

        is_generic = self._is_generic(dataset)
        if is_generic:
            base_url_override = params.get("_base_url")
            if not isinstance(base_url_override, str) or not base_url_override:
                logger.debug(
                    "Datago.generic missing _base_url in call_raw params",
                    extra={"dataset_id": dataset.id},
                )
                raise InvalidRequestError(
                    "datago.generic requires '_base_url' to be passed in params",
                    provider="datago",
                    dataset_id=dataset.id,
                )
            envelope_flag = params.get("_envelope", True)
            if not isinstance(envelope_flag, bool):
                logger.debug(
                    "Datago.generic '_envelope' must be a bool",
                    extra={"dataset_id": dataset.id},
                )
                raise InvalidRequestError(
                    "datago.generic '_envelope' must be a bool (True or False)",
                    provider="datago",
                    dataset_id=dataset.id,
                )
            validate_envelope = envelope_flag
            service_key_param_override = params.get("_service_key_param")
            format_param_override = params.get("_format_param")

            host = urlparse(base_url_override).hostname or ""
            if not _is_allowed_datago_host(host):
                # 비표준 호스트는 fail-closed로 차단한다(#261) — 호스트만 로그에
                # 남기고 URL 원문은 남기지 않는다(query에 serviceKey가 있을 수 있음).
                logger.warning(
                    "datago.generic blocked non-allowlisted host",
                    extra={
                        "dataset_id": dataset.id,
                        "operation": operation,
                        "host": host,
                    },
                )
                raise InvalidRequestError(
                    "datago.generic only allows data.go.kr hosts"
                    " (extend via KPUBDATA_DATAGO_EXTRA_HOSTS)",
                    provider="datago",
                    dataset_id=dataset.id,
                )

            url = f"{base_url_override.rstrip('/')}/{operation}"
            logger.debug(
                "datago.generic dispatch",
                extra={
                    "dataset_id": dataset.id,
                    "operation": operation,
                    "base_url": base_url_override,
                    "envelope": validate_envelope,
                },
            )
            request_params = self._build_base_params(
                dataset,
                service_key_param_override=(
                    service_key_param_override
                    if isinstance(service_key_param_override, str)
                    else None
                ),
                format_param_override=(
                    format_param_override if isinstance(format_param_override, str) else None
                ),
            )
            service_key_param = (
                service_key_param_override
                if isinstance(service_key_param_override, str) and service_key_param_override
                else str(dataset.raw_metadata.get("service_key_param", "serviceKey"))
            )
            # 제어용 magic key는 소비하고, 실제 Provider 파라미터만 원격 엔드포인트로 전달한다.
            magic_keys = {
                "_base_url",
                "_envelope",
                "_service_key_param",
                "_format_param",
            }
            for key, value in params.items():
                if key in magic_keys or key == service_key_param:
                    continue
                request_params[key] = str(value)

            payload = self._request_and_decode(url, request_params, dataset.id)
            if validate_envelope:
                _ = self._envelope_parser.parse(payload, dataset)
            return payload

        url = self._build_request_url(dataset, operation)
        request_params = self._build_base_params(dataset)

        service_key_param = str(dataset.raw_metadata.get("service_key_param", "serviceKey"))
        for key, value in params.items():
            if key != service_key_param:
                request_params[key] = str(value)
        self._apply_default_filters(request_params, dataset)

        payload = self._request_and_decode(url, request_params, dataset.id)
        if self._is_odcloud(dataset):
            return payload

        _ = self._envelope_parser.parse(payload, dataset)
        return payload

    @staticmethod
    def _is_generic(dataset: DatasetRef) -> bool:
        """데이터셋이 datago.generic 비상구인지 반환한다."""
        return bool(dataset.raw_metadata.get("generic"))

    @staticmethod
    def _is_odcloud(dataset: DatasetRef) -> bool:
        """데이터셋이 odcloud 계열 응답 형식을 쓰는지 반환한다."""
        return dataset.raw_metadata.get("provider_family") == "odcloud"

    @staticmethod
    def _get_fixed_query_params(dataset: DatasetRef) -> dict[str, str]:
        """카탈로그의 operation-fixed 비밀 아닌 query 상수를 반환한다."""
        raw_params = dataset.raw_metadata.get("fixed_query_params")
        if not isinstance(raw_params, Mapping):
            return {}

        forbidden_keys = {"apikey", "authorization", "servicekey"}
        fixed_params: dict[str, str] = {}
        for key, value in raw_params.items():
            if not isinstance(key, str) or not key or key.casefold() in forbidden_keys:
                continue
            fixed_params[key] = str(value)
        return fixed_params

    def _require_api_key(self) -> str:
        """data.go.kr 호출에 사용할 API 키를 설정에서 읽는다."""
        return self._config.require_provider_key("datago")

    def _build_request_url(self, dataset: DatasetRef, operation: str | None = None) -> str:
        """데이터셋 메타데이터와 operation 값으로 호출 URL을 구성한다."""
        base_url_raw = dataset.raw_metadata.get("base_url")
        if not isinstance(base_url_raw, str) or not base_url_raw:
            raise ProviderResponseError(
                "Dataset metadata missing base_url",
                provider="datago",
                dataset_id=dataset.id,
            )
        selected_operation = operation or dataset.raw_metadata.get("default_operation")
        if isinstance(selected_operation, str) and selected_operation:
            return f"{base_url_raw}/{selected_operation}"
        return base_url_raw

    @staticmethod
    def _apply_default_filters(params: dict[str, str], dataset: DatasetRef) -> dict[str, str]:
        """카탈로그 default_filters 중 아직 채워지지 않은 키만 기본값으로 채운다.

        Provider가 요구하는 필수 파라미터(예: 조달청 inqryDiv)를 사용자가 지정하지 않은 경우
        카탈로그에 기록된 기본값으로 채운다. 이미 사용자 필터 등으로 채워진 키는 덮어쓰지 않는다.
        """
        default_filters_raw = dataset.raw_metadata.get("default_filters")
        if not isinstance(default_filters_raw, Mapping):
            return params
        default_filters = cast(Mapping[str, object], default_filters_raw)
        existing_lower = {k.lower() for k in params}
        for key, value in default_filters.items():
            if isinstance(key, str) and key.lower() not in existing_lower:
                params[key] = str(value)
        return params

    def _build_base_params(
        self,
        dataset: DatasetRef,
        *,
        service_key_param_override: str | None = None,
        format_param_override: str | None = None,
    ) -> dict[str, str]:
        """서비스 키와 응답 형식 파라미터를 포함한 기본 쿼리를 만든다."""
        api_key = self._require_api_key()
        service_key_param_raw = (
            service_key_param_override
            if service_key_param_override
            else dataset.raw_metadata.get("service_key_param", "serviceKey")
        )
        format_param_raw = (
            format_param_override
            if format_param_override
            else dataset.raw_metadata.get("format_param", "resultType")
        )
        service_key_param = (
            service_key_param_raw
            if isinstance(service_key_param_raw, str) and service_key_param_raw
            else "serviceKey"
        )
        params: dict[str, str] = {service_key_param: api_key}

        if not self._is_odcloud(dataset):
            format_param = (
                format_param_raw
                if isinstance(format_param_raw, str) and format_param_raw
                else "resultType"
            )
            params[format_param] = "json"

        return params

    def _request_and_decode(
        self, url: str, params: Mapping[str, object], dataset_id: str = ""
    ) -> dict[str, object]:
        """data.go.kr API를 호출하고 응답 본문을 dict로 디코딩한다."""
        string_params = {key: str(value) for key, value in params.items()}
        try:
            response = self._transport.request(
                "GET",
                url,
                params=string_params,
                dataset_id=dataset_id,
                provider="datago",
            )
        except TransportError as exc:
            if self._is_http_403(exc):
                raise AuthError(
                    _DATAGO_403_HINT,
                    provider="datago",
                    dataset_id=dataset_id or None,
                    status_code=403,
                ) from exc
            raise

        try:
            content_type = detect_content_type(response)
            if content_type == "json":
                decoded = decode_json(response.content)
            elif content_type == "xml":
                decoded = decode_xml(response.content)
            else:
                decoded = decode_json(response.content)
        except ParseError as exc:
            exc.provider = "datago"
            logger.debug("Datago response parsing failed", extra={"dataset_id": dataset_id})
            raise
        except ImportError as exc:
            raise ParseError("Failed to parse data.go.kr response", provider="datago") from exc

        if isinstance(decoded, dict):
            return cast(dict[str, object], decoded)

        logger.debug(
            "Datago decoded payload invalid type",
            extra={"dataset_id": dataset_id},
        )
        raise ParseError("Decoded payload is not an object", provider="datago")

    @staticmethod
    def _is_http_403(exc: TransportError) -> bool:
        """TransportError가 HTTP 403 응답에서 나온 것인지 확인한다.

        ``__cause__`` 가 아니라 ``status_code`` 를 본다. transport 는 요청에
        credential 이 실려 있으면 예외 체인을 끊는데(끊지 않으면 httpx 메시지에
        담긴 최종 URL로 키가 샌다), datago 는 키를 ``params`` 로 보내므로 이
        판정이 체인에 의존하면 마스킹이 켜지는 순간 403 힌트가 사라진다.
        """
        return exc.status_code == 403

    @staticmethod
    def _load_default_catalogue() -> tuple[DatasetRef, ...]:
        """패키지에 포함된 data.go.kr 기본 카탈로그를 로드한다."""
        return load_catalogue("kpubdata.providers.datago", "datago")


__all__ = ["DataGoAdapter"]
