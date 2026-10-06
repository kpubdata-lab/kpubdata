"""KPubData Python module.

This file contains the implementation at ``src/kpubdata/providers/seoul/adapter.py``.
Key classes and functions are part of the public API, transport layer,
or provider adapter.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast
from urllib.parse import quote

from kpubdata.config import KPubDataConfig
from kpubdata.core.models import DatasetRef, Query, RecordBatch, SchemaDescriptor
from kpubdata.exceptions import (
    DatasetNotFoundError,
    InvalidRequestError,
    ParseError,
    ProviderResponseError,
)
from kpubdata.providers._common import build_schema_from_metadata, coerce_int, load_catalogue
from kpubdata.providers.seoul.envelope import validate_envelope
from kpubdata.transport.decode import decode_json
from kpubdata.transport.http import HttpTransport, TransportConfig


class SeoulAdapter:
    """Compute or query values related to SeoulAdapter."""

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
        return "seoul"

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

        raise DatasetNotFoundError(
            f"Dataset not found: seoul.{dataset_key}",
            provider="seoul",
            dataset_id=f"seoul.{dataset_key}",
        )

    def query_records(self, dataset: DatasetRef, query: Query) -> RecordBatch:
        """Query records by calling Seoul API."""
        page_no = query.page or 1
        page_size = query.page_size or 100
        self._validate_pagination(page_no, page_size, dataset.id)

        path_params = self._require_path_params(dataset, query.filters)
        start_index = (page_no - 1) * page_size + 1
        end_index = page_no * page_size
        url = self._build_request_url(
            dataset,
            operation=None,
            start_index=start_index,
            end_index=end_index,
            path_params=path_params,
        )

        payload = self._request_and_decode(url, dataset.id)
        service_name = self._service_name(dataset, operation=None)
        body, items = validate_envelope(payload, service_name, dataset)
        total_count = coerce_int(body.get("list_total_count"), len(items))
        next_page = page_no + 1 if total_count > 0 and end_index < total_count else None

        return RecordBatch(
            items=items,
            dataset=dataset,
            # Zero is the provider's answer (INFO-200, no data), not a missing count (#806).
            total_count=total_count,
            next_page=next_page,
            raw=payload,
        )

    def get_schema(self, dataset: DatasetRef) -> SchemaDescriptor | None:
        """Return schema information of the dataset."""
        return build_schema_from_metadata(dataset)

    def call_raw(self, dataset: DatasetRef, operation: str, params: dict[str, object]) -> object:
        """Call Seoul API directly and return raw response."""
        page_no = self._int_param(params, "page_no", 1)
        page_size = self._int_param(params, "page_size", 100)
        self._validate_pagination(page_no, page_size, dataset.id)

        start_index = self._int_param(params, "start_index", 0)
        end_index = self._int_param(params, "end_index", 0)
        if start_index <= 0 or end_index <= 0:
            start_index = (page_no - 1) * page_size + 1
            end_index = page_no * page_size

        path_params = self._require_path_params(dataset, params)
        url = self._build_request_url(
            dataset,
            operation=operation,
            start_index=start_index,
            end_index=end_index,
            path_params=path_params,
        )
        payload = self._request_and_decode(url, dataset.id)
        _ = validate_envelope(payload, self._service_name(dataset, operation=operation), dataset)
        return payload

    def _validate_pagination(self, page_no: int, page_size: int, dataset_id: str) -> None:
        """Validate Seoul API pagination format."""
        if page_no < 1:
            raise InvalidRequestError(
                "Seoul API page_no must be >= 1",
                provider="seoul",
                dataset_id=dataset_id,
            )
        if page_size < 1:
            raise InvalidRequestError(
                "Seoul API page_size must be >= 1",
                provider="seoul",
                dataset_id=dataset_id,
            )
        if page_size > 1000:
            raise InvalidRequestError(
                "Seoul API page_size must be <= 1000",
                provider="seoul",
                dataset_id=dataset_id,
            )

    def _require_api_key(self) -> str:
        """Read required API key or raise exception."""
        return self._config.require_provider_key("seoul")

    def _build_request_url(
        self,
        dataset: DatasetRef,
        *,
        operation: str | None,
        start_index: int,
        end_index: int,
        path_params: Mapping[str, str],
    ) -> str:
        """Build Seoul API request URL."""
        base_url = self._require_dataset_metadata(dataset, "base_url")
        service_name = self._service_name(dataset, operation=operation)
        path_suffix = "/".join(quote(value, safe="") for value in path_params.values())
        base_path = (
            f"{base_url}/{self._require_api_key()}/json/{service_name}/{start_index}/{end_index}"
        )
        if path_suffix:
            return f"{base_path}/{path_suffix}"
        return base_path

    def _service_name(self, dataset: DatasetRef, operation: str | None) -> str:
        """Return service name for dataset."""
        if operation is not None and operation:
            return operation
        return self._require_dataset_metadata(dataset, "default_operation")

    def _request_and_decode(self, url: str, dataset_id: str) -> dict[str, object]:
        """Compute or query values related to request and decode."""
        # seoul passes API key as URL path segment (#354) — transport can mask it in logs/exception
        # URLs so it passes the actual key.
        response = self._transport.request(
            "GET",
            url,
            dataset_id=dataset_id,
            provider="seoul",
            secret_values=(self._config.require_provider_key("seoul"),),
        )

        try:
            decoded: object = decode_json(response.content)
        except ParseError as exc:
            exc.provider = "seoul"
            raise

        if isinstance(decoded, dict):
            return cast(dict[str, object], decoded)
        raise ParseError(
            "Decoded payload is not an object", provider="seoul", dataset_id=dataset_id
        )

    def _require_path_params(
        self,
        dataset: DatasetRef,
        params: Mapping[str, object],
    ) -> dict[str, str]:
        """Read required path parameters."""
        resolved: dict[str, str] = {}
        for param_name in self._required_path_param_names(dataset):
            value = params.get(param_name)
            if isinstance(value, str) and value:
                resolved[param_name] = value
                continue
            raise InvalidRequestError(
                f"Seoul API requires path parameter '{param_name}'",
                provider="seoul",
                dataset_id=dataset.id,
            )
        return resolved

    def _required_path_param_names(self, dataset: DatasetRef) -> tuple[str, ...]:
        """Return required path parameter names."""
        raw = dataset.raw_metadata.get("required_path_params")
        if not isinstance(raw, list):
            raise ProviderResponseError(
                "Dataset metadata missing required_path_params",
                provider="seoul",
                dataset_id=dataset.id,
            )

        names: list[str] = []
        for value in cast(list[object], raw):
            if isinstance(value, str) and value:
                names.append(value)
        return tuple(names)

    def _require_dataset_metadata(self, dataset: DatasetRef, key: str) -> str:
        """Read required field from dataset metadata."""
        value = dataset.raw_metadata.get(key)
        if isinstance(value, str) and value:
            return value
        raise ProviderResponseError(
            f"Dataset metadata missing {key}",
            provider="seoul",
            dataset_id=dataset.id,
        )

    @staticmethod
    def _int_param(params: Mapping[str, object], key: str, default: int) -> int:
        """Extract integer parameter or return default."""
        coerced = coerce_int(params.get(key), default)
        return coerced if coerced > 0 else default

    @staticmethod
    def _load_default_catalogue() -> tuple[DatasetRef, ...]:
        """Load and return default catalog."""
        return load_catalogue("kpubdata.providers.seoul", "seoul")


__all__ = ["SeoulAdapter"]
