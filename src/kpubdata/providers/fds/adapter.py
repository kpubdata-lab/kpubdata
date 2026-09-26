"""Adapter for the Ministry of Food and Drug Safety (FDS) open API (#165).

식약처 open API(\`openapi.foodsafetykorea.go.kr\`) does not use the standard
data.go.kr envelope; the whole request lives in the URL path::

    http://openapi.foodsafetykorea.go.kr/api/{KEY}/{serviceId}/{dataType}/{startIdx}/{endIdx}

- The API key is a **path segment**, not a query parameter, so it has to be
  masked by value (#354)
- Pagination is a 1-based \`startIdx\`/\`endIdx\` range
- Errors look like \`{"code": "INFO-100", "message": ...}\`; \`code == "000"\`
  means success
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import cast
from urllib.parse import quote

from kpubdata.config import KPubDataConfig
from kpubdata.core.models import DatasetRef, Query, RecordBatch, SchemaDescriptor
from kpubdata.exceptions import (
    AuthError,
    DatasetNotFoundError,
    InvalidRequestError,
    ProviderResponseError,
)
from kpubdata.providers._common import build_schema_from_metadata, load_catalogue
from kpubdata.transport.decode import decode_json
from kpubdata.transport.http import HttpTransport, TransportConfig

logger = logging.getLogger("kpubdata.provider.fds")

_MAX_PAGE_SIZE = 1000
_CATALOGUE_PACKAGE = "kpubdata.providers.fds"


class FdsAdapter:
    """Adapter for the Ministry of Food and Drug Safety open API."""

    requires_api_key: bool = True

    def __init__(
        self,
        *,
        config: KPubDataConfig | None = None,
        transport: HttpTransport | None = None,
        catalogue: Sequence[DatasetRef] | None = None,
    ) -> None:
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
        return "fds"

    def list_datasets(self) -> list[DatasetRef]:
        return list(self._datasets)

    def search_datasets(self, text: str) -> list[DatasetRef]:
        needle = text.casefold()
        return [
            dataset
            for dataset in self._datasets
            if needle in dataset.id.casefold() or needle in dataset.name.casefold()
        ]

    def get_dataset(self, dataset_key: str) -> DatasetRef:
        dataset = self._datasets_by_key.get(dataset_key)
        if dataset is not None:
            return dataset
        logger.debug("FDS dataset not found", extra={"dataset_key": dataset_key})
        raise DatasetNotFoundError(
            f"Dataset not found: fds.{dataset_key}",
            provider="fds",
            dataset_id=f"fds.{dataset_key}",
        )

    def query_records(self, dataset: DatasetRef, query: Query) -> RecordBatch:
        page = query.page or 1
        page_size = min(query.page_size or _MAX_PAGE_SIZE, _MAX_PAGE_SIZE)
        start_idx = (page - 1) * page_size + 1
        end_idx = page * page_size

        url = self._build_request_url(dataset, start_idx, end_idx, filters=query.filters)
        payload = self._request_and_decode(url, dataset.id)
        service = str(dataset.raw_metadata.get("default_operation", ""))
        items, total_count = self._parse_fds_envelope(payload, dataset.id, service)

        next_page: int | None = None
        if total_count and end_idx < total_count or not total_count and len(items) == page_size:
            next_page = page + 1

        return RecordBatch(
            items=items,
            dataset=dataset,
            total_count=total_count if total_count else None,
            next_page=next_page,
            raw=payload,
        )

    def get_schema(self, dataset: DatasetRef) -> SchemaDescriptor | None:
        return build_schema_from_metadata(dataset)

    def call_raw(self, dataset: DatasetRef, operation: str, params: dict[str, object]) -> object:
        logger.debug(
            "fds call_raw",
            extra={"dataset_id": dataset.id, "operation": operation, "param_keys": sorted(params)},
        )
        service = operation or str(dataset.raw_metadata.get("default_operation", ""))
        if not service:
            raise InvalidRequestError(
                "FDS call_raw requires a non-empty service name",
                provider="fds",
                dataset_id=dataset.id,
            )
        start_idx = self._int_param(params, "start_idx", 1)
        end_idx = self._int_param(params, "end_idx", 10)
        filters = {
            k: v for k, v in params.items() if k not in ("start_idx", "end_idx") and str(v).strip()
        }
        url = self._build_request_url(dataset, start_idx, end_idx, service=service, filters=filters)
        payload = self._request_and_decode(url, dataset.id)
        _ = self._parse_fds_envelope(payload, dataset.id, service)
        return payload

    def _require_api_key(self) -> str:
        return self._config.require_provider_key("fds")

    def _build_request_url(
        self,
        dataset: DatasetRef,
        start_idx: int,
        end_idx: int,
        *,
        service: str | None = None,
        filters: Mapping[str, object] | None = None,
    ) -> str:
        base_url = str(
            dataset.raw_metadata.get("base_url", "http://openapi.foodsafetykorea.go.kr/api")
        )
        service_id = service or str(dataset.raw_metadata.get("default_operation", ""))
        key = quote(self._require_api_key(), safe="")
        url = f"{base_url.rstrip('/')}/{key}/{service_id}/json/{start_idx}/{end_idx}"
        extra = {k: str(v) for k, v in (filters or {}).items() if str(v).strip()}
        if extra:
            from urllib.parse import urlencode

            url = f"{url}?{urlencode(extra)}"
        return url

    def _request_and_decode(self, url: str, dataset_id: str) -> dict[str, object]:
        # The key sits in the URL path, so log masking needs the literal value
        # rather than a parameter name (#354).
        response = self._transport.request(
            "GET",
            url,
            dataset_id=dataset_id,
            provider="fds",
            secret_values=(self._require_api_key(),),
        )
        decoded: object = decode_json(response.content)
        if not isinstance(decoded, dict):
            raise ProviderResponseError(
                "FDS response is not a JSON object",
                provider="fds",
                dataset_id=dataset_id,
            )
        return decoded

    def _parse_fds_envelope(
        self, payload: Mapping[str, object], dataset_id: str, service: str | None = None
    ) -> tuple[list[dict[str, object]], int]:
        """Extract ``(items, total_count)`` from an FDS response.

        Shape observed against the live API on 2026-08-26, called with an invalid
        key: the top-level key is the service name, for example ``I1200``, and
        under it come ``RESULT.CODE``/``RESULT.MSG`` plus the list. ``"000"``
        means success, ``INFO-100`` an authentication failure. The published docs
        give both ``body`` and ``row`` as candidate list keys for the success
        shape, so both are tried -- a safe fallback until a working key confirms
        which one it is.
        """
        section: Mapping[str, object] | None = None
        if service and isinstance(payload.get(service), dict):
            section = cast(Mapping[str, object], payload[service])
        elif len(payload) == 1:
            only = next(iter(payload.values()))
            if isinstance(only, dict):
                section = cast(Mapping[str, object], only)
        if section is None:
            raise ProviderResponseError(
                "FDS response has no service section",
                provider="fds",
                dataset_id=dataset_id,
            )

        result = section.get("RESULT")
        if isinstance(result, dict):
            code = str(result.get("CODE", ""))
            message = str(result.get("MSG", ""))
            if code not in ("", "000"):
                if code == "INFO-100":
                    raise AuthError(
                        f"FDS authentication failed: {message}",
                        provider="fds",
                        dataset_id=dataset_id,
                    )
                raise ProviderResponseError(
                    f"FDS API error {code}: {message}",
                    provider="fds",
                    dataset_id=dataset_id,
                )

        total_count = 0
        total_raw = section.get("total_count")
        if isinstance(total_raw, str) and total_raw.isdigit():
            total_count = int(total_raw)
        elif isinstance(total_raw, int):
            total_count = total_raw

        items: list[dict[str, object]] = []
        for list_key in ("body", "row", "items"):
            rows = section.get(list_key)
            if isinstance(rows, list):
                items.extend(item for item in rows if isinstance(item, dict))
                break
        return items, total_count

    @staticmethod
    def _int_param(params: Mapping[str, object], name: str, default: int) -> int:
        raw = params.get(name, default)
        if isinstance(raw, (str, int)) and not isinstance(raw, bool):
            try:
                return int(raw)
            except ValueError:
                return default
        return default

    def _load_default_catalogue(self) -> tuple[DatasetRef, ...]:
        return tuple(load_catalogue(_CATALOGUE_PACKAGE, "fds"))


__all__ = ["FdsAdapter"]
