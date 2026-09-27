"""Ministry of Education NEIS open API adapter (#164).

NEIS open API (open.neis.go.kr) uses a unique response shape different from
standard data.go.kr envelope::

    {"mealServiceDietInfo": [
        [{"head": [{"list_total_count": N}, {"RESULT": {"CODE": "INFO-000", ...}}]}],
        [{"head": [{"list_total_count": N}, ...], "row": [ ...items... ]}],
    ]}

- ``INFO-000``: Success, ``INFO-200``: No results (empty batch), ``ERROR-*``: Error
- Authentication uses ``KEY`` query parameter (public data portal API key)
- Pagination via ``pIndex`` (1-based) and ``pSize`` (max 100)
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from urllib.parse import urlencode

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

logger = logging.getLogger("kpubdata.provider.neis")

_MAX_PAGE_SIZE = 100


class NeisAdapter:
    """Ministry of Education NEIS open API adapter."""

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
        return "neis"

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
        logger.debug("NEIS dataset not found", extra={"dataset_key": dataset_key})
        raise DatasetNotFoundError(
            f"Dataset not found: neis.{dataset_key}",
            provider="neis",
            dataset_id=f"neis.{dataset_key}",
        )

    def query_records(self, dataset: DatasetRef, query: Query) -> RecordBatch:
        page = query.page or 1
        page_size = min(query.page_size or _MAX_PAGE_SIZE, _MAX_PAGE_SIZE)
        required = self._required_filters(dataset)
        missing = [name for name in required if not str(query.filters.get(name, "")).strip()]
        if missing:
            raise InvalidRequestError(
                f"NEIS {dataset.dataset_key} queries require filter(s): {', '.join(missing)}",
                provider="neis",
                dataset_id=dataset.id,
            )

        operation = self._default_operation(dataset)
        params: dict[str, str] = {
            "KEY": self._require_api_key(),
            "Type": "json",
            "pIndex": str(page),
            "pSize": str(page_size),
        }
        for key, value in query.filters.items():
            if str(value).strip():
                params[str(key)] = str(value)

        url = f"{dataset.raw_metadata.get('base_url', '')}/{operation}?{urlencode(params)}"
        payload = self._request_and_decode(url, dataset.id)
        items, total_count = self._parse_neis_envelope(payload, operation, dataset.id)

        next_page: int | None = None
        has_more = (total_count and page * page_size < total_count) or (
            not total_count and len(items) == page_size
        )
        if has_more:
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
            "neis call_raw",
            extra={"dataset_id": dataset.id, "operation": operation, "param_keys": sorted(params)},
        )
        if not operation:
            raise InvalidRequestError(
                "NEIS call_raw requires a non-empty operation (e.g. 'mealServiceDietInfo')",
                provider="neis",
                dataset_id=dataset.id,
            )
        request_params: dict[str, str] = {"KEY": self._require_api_key(), "Type": "json"}
        for key, value in params.items():
            if str(value).strip():
                request_params[str(key)] = str(value)
        base_url = dataset.raw_metadata.get("base_url", "")
        url = f"{base_url}/{operation}?{urlencode(request_params)}"
        payload = self._request_and_decode(url, dataset.id)
        _ = self._parse_neis_envelope(payload, operation, dataset.id)
        return payload

    def _require_api_key(self) -> str:
        return self._config.require_provider_key("neis")

    def _default_operation(self, dataset: DatasetRef) -> str:
        return str(dataset.raw_metadata.get("default_operation", ""))

    def _required_filters(self, dataset: DatasetRef) -> tuple[str, ...]:
        raw = dataset.raw_metadata.get("required_query_filters", [])
        if isinstance(raw, (list, tuple)):
            return tuple(str(item) for item in raw)
        return ()

    def _request_and_decode(self, url: str, dataset_id: str) -> dict[str, object]:
        response = self._transport.request("GET", url, dataset_id=dataset_id, provider="neis")
        decoded: object = decode_json(response.content)
        if not isinstance(decoded, dict):
            raise ProviderResponseError(
                "NEIS response is not a JSON object",
                provider="neis",
                dataset_id=dataset_id,
            )
        return decoded

    def _parse_neis_envelope(
        self, payload: Mapping[str, object], operation: str, dataset_id: str
    ) -> tuple[list[dict[str, object]], int]:
        """Extract (items, total_count) from NEIS unique dual-list envelope.

        No results (INFO-200) is normal empty batch operation. Error codes are
        mapped to exceptions (ERROR-290 auth error → AuthError, others →
        ProviderResponseError).
        """
        sections = payload.get(operation)
        if not isinstance(sections, list):
            result = payload.get("RESULT")
            self._raise_for_result(result, dataset_id)
            # Responses with explicit RESULT (e.g., INFO-200 no results) arrive
            # without section — this is normal, not error; treat as empty batch.
            if result is None:
                raise ProviderResponseError(
                    f"NEIS response has no '{operation}' section",
                    provider="neis",
                    dataset_id=dataset_id,
                )
            return [], 0

        total_count = 0
        items: list[dict[str, object]] = []
        for section in sections:
            if not isinstance(section, list):
                continue
            for block in section:
                if not isinstance(block, dict):
                    continue
                head = block.get("head")
                if isinstance(head, list):
                    for entry in head:
                        if isinstance(entry, dict) and isinstance(
                            entry.get("list_total_count"), int
                        ):
                            total_count = entry["list_total_count"]
                row = block.get("row")
                if isinstance(row, list):
                    items.extend(item for item in row if isinstance(item, dict))

        self._raise_for_result(payload.get("RESULT"), dataset_id)
        if not items:
            for section in sections:
                if isinstance(section, list):
                    for block in section:
                        if isinstance(block, dict) and isinstance(block.get("head"), list):
                            for entry in block["head"]:
                                if isinstance(entry, dict) and isinstance(
                                    entry.get("RESULT"), dict
                                ):
                                    self._raise_for_result(entry["RESULT"], dataset_id)
        return items, total_count

    @staticmethod
    def _raise_for_result(result: object, dataset_id: str) -> None:
        if not isinstance(result, dict):
            return
        code = str(result.get("CODE", ""))
        if code in ("", "INFO-000"):
            return
        message = str(result.get("MESSAGE", ""))
        if code == "INFO-200":
            return  # No results — caller treats as empty batch
        if code == "ERROR-290":
            raise AuthError(
                f"NEIS authentication failed: {message}",
                provider="neis",
                dataset_id=dataset_id,
            )
        raise ProviderResponseError(
            f"NEIS API error {code}: {message}",
            provider="neis",
            dataset_id=dataset_id,
        )

    def _load_default_catalogue(self) -> tuple[DatasetRef, ...]:
        return tuple(load_catalogue("kpubdata.providers.neis", "neis"))


__all__ = ["NeisAdapter"]
