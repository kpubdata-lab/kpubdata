"""KPubData Python module.

This file contains the implementation at ``src/kpubdata/providers/kosis/adapter.py``.
Key classes and functions are part of the public API, transport layer,
or provider adapter.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import cast
from urllib.parse import urlencode

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
)
from kpubdata.providers._common import build_schema_from_metadata, load_catalogue
from kpubdata.transport.decode import decode_json
from kpubdata.transport.http import HttpTransport, TransportConfig

logger = logging.getLogger("kpubdata.provider.kosis")

_KOSIS_DEFAULT_QUERY_PARAM_KEYS: tuple[str, ...] = (
    "objL1",
    "objL2",
    "objL3",
    "objL4",
    "objL5",
    "objL6",
    "objL7",
    "objL8",
    "itmId",
    "prdSe",
    "newEstPrdCnt",
    "prdInterval",
)


class KosisAdapter:
    """KOSIS adapter.

    Query merge rule: dataset default_query_params < query.filters (caller priority).
    """

    requires_api_key: bool = True

    def __init__(
        self,
        *,
        config: KPubDataConfig | None = None,
        transport: HttpTransport | None = None,
        catalogue: Sequence[DatasetRef] | None = None,
    ) -> None:
        """Initialize instance state."""
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
        """Return provider name."""
        return "kosis"

    def list_datasets(self) -> list[DatasetRef]:
        """Return all datasets provided by this adapter."""
        return list(self._datasets)

    def search_datasets(self, text: str) -> list[DatasetRef]:
        """Search datasets."""
        needle = text.casefold()
        return [
            dataset
            for dataset in self._datasets
            if needle in dataset.id.casefold() or needle in dataset.name.casefold()
        ]

    def get_dataset(self, dataset_key: str) -> DatasetRef:
        """Return the dataset for the given key."""
        dataset = self._datasets_by_key.get(dataset_key)
        if dataset is not None:
            return dataset

        logger.debug(
            "KOSIS dataset not found",
            extra={"dataset_id": f"kosis.{dataset_key}", "provider": "kosis"},
        )
        raise DatasetNotFoundError(
            f"Dataset not found: kosis.{dataset_key}",
            provider="kosis",
            dataset_id=f"kosis.{dataset_key}",
        )

    def query_records(self, dataset: DatasetRef, query: Query) -> RecordBatch:
        """Query records by calling KOSIS API."""
        _page_size = query.page_size or 100
        logger.debug(
            "kosis query_records",
            extra={
                "dataset_id": dataset.id,
                "page": query.page,
                "page_size": _page_size,
                "start_date": query.start_date,
                "end_date": query.end_date,
                "filter_keys": sorted(query.filters.keys()),
            },
        )
        url = self._build_request_url(dataset, query)
        payload = self._request_and_decode(url, dataset.id)
        items = self._extract_items(payload, dataset.id)

        if not items:
            logger.debug(
                "KOSIS envelope: zero items",
                extra={
                    "dataset_id": dataset.id,
                    "page": query.page,
                    "page_size": _page_size,
                    "total_count": len(items),
                },
            )

        return RecordBatch(
            items=items,
            dataset=dataset,
            total_count=len(items),
            next_page=None,
            raw=payload,
        )

    def get_schema(self, dataset: DatasetRef) -> SchemaDescriptor | None:
        """Return schema information of the dataset."""
        return build_schema_from_metadata(dataset)

    def call_raw(self, dataset: DatasetRef, operation: str, params: dict[str, object]) -> object:
        """Call KOSIS API directly and return raw response."""
        logger.debug(
            "kosis call_raw",
            extra={
                "dataset_id": dataset.id,
                "operation": operation,
                "param_keys": sorted(params.keys()),
            },
        )
        url = self._build_raw_url(dataset, operation, params)
        payload = self._request_and_decode(url, dataset.id)
        if isinstance(payload, dict):
            self._raise_for_error_payload(cast(dict[str, object], payload), dataset.id)
        return payload

    def _require_api_key(self) -> str:
        """Read required API key or raise exception."""
        return self._config.require_provider_key("kosis")

    def _build_request_url(self, dataset: DatasetRef, query: Query) -> str:
        """Build KOSIS API request URL."""
        start_date = query.start_date
        end_date = query.end_date
        if not isinstance(start_date, str) or not start_date:
            logger.debug(
                "KOSIS invalid query: missing start_date", extra={"dataset_id": dataset.id}
            )
            raise InvalidRequestError(
                "KOSIS queries require start_date",
                provider="kosis",
                dataset_id=dataset.id,
            )
        if not isinstance(end_date, str) or not end_date:
            raise InvalidRequestError(
                "KOSIS queries require end_date",
                provider="kosis",
                dataset_id=dataset.id,
            )

        filters: dict[str, object] = dict(query.filters)
        params = self._build_base_params(dataset)
        params["startPrdDe"] = start_date
        params["endPrdDe"] = end_date

        reserved = {key.casefold() for key in params}
        for key in _KOSIS_DEFAULT_QUERY_PARAM_KEYS:
            if key in filters:
                params[key] = str(filters.pop(key))

        for key, value in filters.items():
            if key.casefold() not in reserved:
                params[key] = str(value)

        return self._compose_url(dataset, params)

    def _build_raw_url(
        self,
        dataset: DatasetRef,
        operation: str,
        params: Mapping[str, object],
    ) -> str:
        """Build KOSIS API raw request URL."""
        request_params = self._build_base_params(dataset)
        selected_operation = operation.strip()
        if selected_operation and selected_operation != "statisticsParameterData":
            request_params["operation"] = selected_operation
        for key, value in params.items():
            if key != "apiKey":
                request_params[key] = str(value)
        return self._compose_url(dataset, request_params)

    def _build_base_params(self, dataset: DatasetRef) -> dict[str, str]:
        """Build default query parameters."""
        api_key = self._require_api_key()
        org_id = self._require_dataset_metadata(dataset, "org_id")
        tbl_id = self._require_dataset_metadata(dataset, "tbl_id")
        params = {
            "apiKey": api_key,
            "format": "json",
            "jsonVD": "Y",
            "orgId": org_id,
            "tblId": tbl_id,
        }
        default_query_params = self._get_default_query_params(dataset)
        if default_query_params:
            params.update(default_query_params)
        else:
            params.update(
                {
                    "objL1": "ALL",
                    "objL2": "ALL",
                    "itmId": "ALL",
                    "prdSe": "M",
                }
            )
        return params

    @staticmethod
    def _get_default_query_params(dataset: DatasetRef) -> dict[str, str]:
        """Return merged default query params."""
        raw_defaults = dataset.raw_metadata.get("default_query_params")
        if not isinstance(raw_defaults, Mapping):
            return {}
        typed_defaults = cast(Mapping[str, object], raw_defaults)

        default_query_params: dict[str, str] = {}
        for key in _KOSIS_DEFAULT_QUERY_PARAM_KEYS:
            value = typed_defaults.get(key)
            if value is not None:
                default_query_params[key] = str(value)
        return default_query_params

    def _compose_url(self, dataset: DatasetRef, params: Mapping[str, str]) -> str:
        """Compose KOSIS URL from dataset and query."""
        base_url = self._require_dataset_metadata(dataset, "base_url")
        query_string = urlencode(params)
        return f"{base_url}?{query_string}"

    def _request_and_decode(self, url: str, dataset_id: str) -> object:
        """Send HTTP GET request to KOSIS API and decode."""
        response = self._transport.request("GET", url, dataset_id=dataset_id, provider="kosis")

        try:
            decoded: object = decode_json(response.content)
        except ParseError as exc:
            exc.provider = "kosis"
            logger.debug("KOSIS response parsing failed", extra={"dataset_id": dataset_id})
            raise

        if isinstance(decoded, list):
            return cast(list[object], decoded)
        if isinstance(decoded, dict):
            return cast(dict[str, object], decoded)

        logger.debug("KOSIS response parsing failed", extra={"dataset_id": dataset_id})
        raise ParseError("Decoded payload is neither an object nor an array", provider="kosis")

    def _extract_items(self, payload: object, dataset_id: str) -> list[dict[str, object]]:
        """Extract items from KOSIS API response."""
        if isinstance(payload, dict):
            self._raise_for_error_payload(cast(dict[str, object], payload), dataset_id)

        if not isinstance(payload, list):
            logger.debug(
                "KOSIS envelope malformed: expected array payload",
                extra={"dataset_id": dataset_id},
            )
            raise ProviderResponseError(
                "Malformed KOSIS response: expected array payload",
                provider="kosis",
                dataset_id=dataset_id,
            )

        payload_items = cast(list[object], payload)
        return [cast(dict[str, object], item) for item in payload_items if isinstance(item, dict)]

    def _raise_for_error_payload(self, payload: Mapping[str, object], dataset_id: str) -> None:
        """Check KOSIS API error response and raise exception."""
        code_raw = payload.get("err")
        if code_raw is None:
            return  # "err" field missing = success response
        message_raw = payload.get("errMsg")
        code = code_raw if isinstance(code_raw, str) else None
        message = message_raw if isinstance(message_raw, str) else "KOSIS returned an error"

        logger.debug(
            "KOSIS API envelope error",
            extra={"dataset_id": dataset_id, "code": code, "message": message},
        )

        if code == "30":
            raise AuthError(
                message,
                provider="kosis",
                dataset_id=dataset_id,
                provider_code=code,
                detail=dict(payload),
            )
        if code == "10":
            raise InvalidRequestError(
                message,
                provider="kosis",
                dataset_id=dataset_id,
                provider_code=code,
                detail=dict(payload),
            )
        raise ProviderResponseError(
            message,
            provider="kosis",
            dataset_id=dataset_id,
            provider_code=code,
            detail=dict(payload),
        )

    @staticmethod
    def _require_dataset_metadata(dataset: DatasetRef, field_name: str) -> str:
        """Read required field from dataset metadata."""
        value = dataset.raw_metadata.get(field_name)
        if isinstance(value, str) and value:
            return value
        raise ProviderResponseError(
            f"Dataset metadata missing {field_name}",
            provider="kosis",
            dataset_id=dataset.id,
        )

    @staticmethod
    def _load_default_catalogue() -> tuple[DatasetRef, ...]:
        """Load and return default catalog."""
        return load_catalogue("kpubdata.providers.kosis", "kosis")


__all__ = ["KosisAdapter"]
