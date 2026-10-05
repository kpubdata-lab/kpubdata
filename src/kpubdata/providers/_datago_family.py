"""Shared implementation for data.go.kr family provider adapters.

``localdata`` and ``semas`` use the same data.go.kr auth, envelope, and
pagination contract. Originally two 375-line adapter copies existed; comparing
them by normalizing name strings yielded **0 lines of code difference** — only
comments and formatting varied.

This duplication caused real regressions. The data.go.kr ``"03"`` (NODATA_ERROR)
branch, which treats it as a normal response (no matching data), existed in semas
but not localdata, causing filtered queries with no results to raise exceptions
only in localdata (#470). There was no documentation that fixes must be applied
to both.

New providers using the same contract inherit by specifying ``provider_name``
and catalogue package only.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import ClassVar, NoReturn, cast

from kpubdata.config import KPubDataConfig
from kpubdata.core.models import DatasetRef, Query, RecordBatch, SchemaDescriptor
from kpubdata.exceptions import (
    AuthError,
    DatasetNotFoundError,
    InvalidRequestError,
    ParseError,
    ProviderResponseError,
    RateLimitError,
    ServiceUnavailableError,
)
from kpubdata.providers._common import (
    build_schema_from_metadata,
    load_catalogue,
    reported_total,
)
from kpubdata.transport.decode import decode_json, decode_xml, detect_content_type
from kpubdata.transport.http import HttpTransport, TransportConfig

#: Module-level logger. Instances use per-provider logger via ``self._logger``
#: to avoid breaking operator filtering by ``kpubdata.provider.localdata``.
logger = logging.getLogger("kpubdata.provider.datago_family")


def _is_success_code(code: str) -> bool:
    """Return whether code is a success code."""
    try:
        return int(code) == 0
    except ValueError:
        return False


class DataGoFamilyAdapter:
    """Shared implementation for data.go.kr family adapters.

    Subclasses specify only ``provider_name`` and ``catalogue_package``.
    """

    #: Provider identifier used in logs, exceptions, and credential resolution.
    provider_name: ClassVar[str]
    #: Package path containing default catalogue.json.
    catalogue_package: ClassVar[str]

    requires_api_key: bool = True

    def __init__(
        self,
        *,
        config: KPubDataConfig | None = None,
        transport: HttpTransport | None = None,
        catalogue: Sequence[DatasetRef] | None = None,
    ) -> None:
        """Initialize instance internal state."""
        # Per-provider logger. Shared implementation but logs must be
        # per-provider.
        self._logger = logging.getLogger(f"kpubdata.provider.{self.provider_name}")
        #: Display name used in log messages ("Localdata", "Semas").
        self._label = self.provider_name.capitalize()
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

    @property
    def name(self) -> str:
        """Return computed or retrieved name-related value."""
        return self.provider_name

    def list_datasets(self) -> list[DatasetRef]:
        """Return computed or retrieved list-datasets value."""
        return list(self._datasets)

    def search_datasets(self, text: str) -> list[DatasetRef]:
        """Return computed or retrieved search-datasets value."""
        needle = text.casefold()
        return [
            dataset
            for dataset in self._datasets
            if needle in dataset.id.casefold() or needle in dataset.name.casefold()
        ]

    def get_dataset(self, dataset_key: str) -> DatasetRef:
        """Return dataset."""
        dataset = self._datasets_by_key.get(dataset_key)
        if dataset is not None:
            return dataset

        self._logger.debug(
            f"{self._label} dataset not found",
            extra={
                "dataset_id": f"{self.provider_name}.{dataset_key}",
                "provider": self.provider_name,
            },
        )
        raise DatasetNotFoundError(
            f"Dataset not found: {self.provider_name}.{dataset_key}",
            provider=self.provider_name,
            dataset_id=f"{self.provider_name}.{dataset_key}",
        )

    def query_records(self, dataset: DatasetRef, query: Query) -> RecordBatch:
        """Execute query_records operation."""
        page = query.page or 1
        page_size = query.page_size or 100
        self._logger.debug(
            f"{self.provider_name} query_records",
            extra={
                "dataset_id": dataset.id,
                "page": page,
                "page_size": page_size,
                "filter_keys": sorted(query.filters.keys()),
            },
        )

        url = self._build_request_url(dataset)
        params = self._build_base_params(dataset)
        params["pageNo"] = str(page)
        params["numOfRows"] = str(page_size)

        reserved = {params_key.lower() for params_key in params}
        reserved.update({"pageno", "numofrows"})
        for key, raw_value in query.filters.items():
            if key.lower() not in reserved:
                value: object = raw_value
                params[key] = str(value)

        payload = self._request_and_decode(url, params, dataset.id)

        body, items = self._validate_envelope(payload, dataset.id)
        reported_count = reported_total(body.get("totalCount"))
        # Paging treats "no count" and zero alike: only a positive count bounds it.
        total_count = reported_count or 0
        if (total_count and page * page_size < total_count) or (
            not total_count and len(items) == page_size
        ):
            computed_next = page + 1
        else:
            computed_next = None

        if not items:
            self._logger.debug(
                f"{self._label} envelope: zero items",
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
            total_count=reported_count,
            next_page=computed_next,
            raw=payload,
        )

    def get_schema(self, dataset: DatasetRef) -> SchemaDescriptor | None:
        """Return schema."""
        return build_schema_from_metadata(dataset)

    def call_raw(self, dataset: DatasetRef, operation: str, params: dict[str, object]) -> object:
        """Return computed or retrieved call-raw value."""
        self._logger.debug(
            f"{self.provider_name} call_raw",
            extra={
                "dataset_id": dataset.id,
                "operation": operation,
                "param_keys": sorted(params.keys()),
            },
        )
        url = self._build_request_url(dataset, operation)
        request_params = self._build_base_params(dataset)

        service_key_param = str(dataset.raw_metadata.get("service_key_param", "serviceKey"))
        for key, value in params.items():
            if key != service_key_param:
                request_params[key] = str(value)

        payload = self._request_and_decode(url, request_params, dataset.id)
        _ = self._validate_envelope(payload, dataset.id)
        return payload

    def _require_api_key(self) -> str:
        """Read data.go.kr API key; raise on missing.

        localdata, semas, and lofin adapters all share the data.go.kr
        authentication system, managed by a single provider key ("datago")
        by design.
        """
        # Check own name first. This family uses data.go.kr credentials,
        # but requiring "datago" immediately would silently ignore the
        # KPUBDATA_<PROVIDER>_API_KEY guidance in README.
        return self._config.require_provider_key(self.provider_name, fallback_to="datago")

    def _build_request_url(self, dataset: DatasetRef, operation: str | None = None) -> str:
        """Build and return request URL."""
        base_url_raw = dataset.raw_metadata.get("base_url")
        if not isinstance(base_url_raw, str) or not base_url_raw:
            self._logger.debug(
                f"{self._label} dataset metadata missing base_url",
                extra={"dataset_id": dataset.id},
            )
            raise ProviderResponseError(
                "Dataset metadata missing base_url",
                provider=self.provider_name,
                dataset_id=dataset.id,
            )

        selected_operation = operation or dataset.raw_metadata.get("default_operation")
        if isinstance(selected_operation, str) and selected_operation:
            return f"{base_url_raw.rstrip('/')}/{selected_operation}"
        return base_url_raw

    def _build_base_params(self, dataset: DatasetRef) -> dict[str, str]:
        """Build and return base parameters."""
        api_key = self._require_api_key()
        service_key_param_raw = dataset.raw_metadata.get("service_key_param", "serviceKey")
        format_param_raw = dataset.raw_metadata.get("format_param", "type")
        service_key_param = (
            service_key_param_raw
            if isinstance(service_key_param_raw, str) and service_key_param_raw
            else "serviceKey"
        )
        format_param = (
            format_param_raw if isinstance(format_param_raw, str) and format_param_raw else "type"
        )
        return {service_key_param: api_key, format_param: "json"}

    def _request_and_decode(
        self, url: str, params: Mapping[str, object], dataset_id: str
    ) -> dict[str, object]:
        """Request and decode return value."""
        string_params = {key: str(value) for key, value in params.items()}
        response = self._transport.request(
            "GET",
            url,
            params=string_params,
            dataset_id=dataset_id,
            provider=self.provider_name,
        )

        try:
            content_type = detect_content_type(response)
            if content_type == "json":
                decoded = decode_json(response.content)
            elif content_type == "xml":
                decoded = decode_xml(response.content)
            else:
                decoded = decode_json(response.content)
        except ParseError as exc:
            exc.provider = self.provider_name
            self._logger.debug(
                f"{self._label} response parsing failed", extra={"dataset_id": dataset_id}
            )
            raise
        except ImportError as exc:
            raise ParseError(
                f"Failed to parse {self.provider_name} response", provider=self.provider_name
            ) from exc

        if isinstance(decoded, dict):
            return cast(dict[str, object], decoded)

        self._logger.debug(
            f"{self._label} decoded payload invalid type", extra={"dataset_id": dataset_id}
        )
        raise ParseError("Decoded payload is not an object", provider=self.provider_name)

    def _validate_envelope(
        self, payload: dict[str, object], dataset_id: str = ""
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        """Validate envelope format and extract required values."""
        response_obj = payload.get("response")
        if not isinstance(response_obj, dict):
            raise ProviderResponseError(
                "Malformed response envelope: missing response",
                provider=self.provider_name,
                dataset_id=dataset_id or None,
            )

        response_dict = cast(dict[str, object], response_obj)

        header_obj = response_dict.get("header")
        if not isinstance(header_obj, dict):
            raise ProviderResponseError(
                "Malformed response envelope: missing header",
                provider=self.provider_name,
                dataset_id=dataset_id or None,
            )

        header_dict = cast(dict[str, object], header_obj)
        result_code = header_dict.get("resultCode")
        if not isinstance(result_code, str):
            raise ProviderResponseError(
                "Malformed response envelope: missing resultCode",
                provider=self.provider_name,
                dataset_id=dataset_id or None,
            )

        result_msg_raw = header_dict.get("resultMsg")
        result_msg = (
            result_msg_raw if isinstance(result_msg_raw, str) else "Provider returned error"
        )
        self._logger.debug(
            f"{self.provider_name} result",
            extra={"result_code": result_code, "result_msg": result_msg, "dataset_id": dataset_id},
        )
        body_obj = response_dict.get("body")
        body_dict: dict[str, object] = (
            cast(dict[str, object], body_obj) if isinstance(body_obj, dict) else {}
        )

        # data.go.kr "03" (NODATA_ERROR) is a normal response — it means
        # no matching data exists, not that the call failed. Without this
        # branch, filtered queries with no results commonly raise exceptions.
        # semas handled this from the start; localdata was missing it (#470).
        if result_code == "03":
            return body_dict, []
        if not _is_success_code(result_code):
            self._raise_for_result_code(result_code, result_msg, dataset_id)

        items = self._normalize_items(body_dict.get("items"))
        return body_dict, items

    def _raise_for_result_code(self, code: str, msg: str, dataset_id: str) -> NoReturn:
        """Raise exception for result code."""
        if code in {"30", "31", "20", "32"}:
            raise AuthError(msg, provider=self.provider_name, provider_code=code)
        if code == "22":
            raise RateLimitError(
                msg, provider=self.provider_name, provider_code=code, retryable=False
            )
        if code == "10":
            raise InvalidRequestError(msg, provider=self.provider_name, provider_code=code)
        if code == "12":
            raise DatasetNotFoundError(
                msg,
                provider=self.provider_name,
                provider_code=code,
                dataset_id=dataset_id,
            )
        if code in {"01", "02"}:
            raise ServiceUnavailableError(msg, provider=self.provider_name, provider_code=code)
        raise ProviderResponseError(msg, provider=self.provider_name, provider_code=code)

    def _normalize_items(self, items_wrapper: object) -> list[dict[str, object]]:
        """Normalize and return items."""
        if items_wrapper is None:
            return []

        if isinstance(items_wrapper, dict):
            item_value = cast(dict[str, object], items_wrapper).get("item")
            if isinstance(item_value, list):
                normalized_items = cast(list[object], item_value)
                return [
                    cast(dict[str, object], item)
                    for item in normalized_items
                    if isinstance(item, dict)
                ]
            if isinstance(item_value, dict):
                return [cast(dict[str, object], item_value)]
            if "item" in items_wrapper or not items_wrapper:
                # ``item`` key with non-list/dict value means empty response.
                # (XML ``<items><item/></items>`` becomes ``{"item": None}``).
                # Empty dict is the same. Promoting both as single records
                # creates **phantom rows** — that happened in #470, causing
                # regression.
                return []
            # Non-empty dict without wrapping is a single record. Dropping to
            # [] causes same-shaped responses to differ per-provider (0 vs 1
            # record) — #470.
            return [cast(dict[str, object], items_wrapper)]

        if isinstance(items_wrapper, list):
            normalized_items = cast(list[object], items_wrapper)
            return [
                cast(dict[str, object], item) for item in normalized_items if isinstance(item, dict)
            ]

        return []

    def _load_default_catalogue(self) -> tuple[DatasetRef, ...]:
        """Load and return default catalogue from subclass-specified package."""
        return load_catalogue(self.catalogue_package, self.provider_name)


__all__ = ["DataGoFamilyAdapter"]
