"""Adapter for the National Institute of Korean Language dictionary API (#222).

stdict open API(\`stdict.korean.go.kr/api\`) does not use the standard data.go.kr
envelope; it has a shape of its own::

    {"channel": {
        "title": "...", "link": "...", "total": "50", "start": "1", "num": "10",
        "item": [{"target_code": "...", "word": "...", "sense": [...], ...}],
    }}

- Authentication uses the \`key\` query parameter, issued on the stdict site
- Errors arrive in the JSON body as \`statusCode\` (\`"000"\` means success)
- Pagination uses \`start\`/\`num\` (1-based start index, page size, max 100)
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

logger = logging.getLogger("kpubdata.provider.korean")

_MAX_PAGE_SIZE = 100
_CATALOGUE_PACKAGE = "kpubdata.providers.korean"


class KoreanAdapter:
    """Adapter for the National Institute of Korean Language dictionary."""

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
        return "korean"

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
        logger.debug("korean dataset not found", extra={"dataset_key": dataset_key})
        raise DatasetNotFoundError(
            f"Dataset not found: korean.{dataset_key}",
            provider="korean",
            dataset_id=f"korean.{dataset_key}",
        )

    def query_records(self, dataset: DatasetRef, query: Query) -> RecordBatch:
        page = query.page or 1
        page_size = min(query.page_size or _MAX_PAGE_SIZE, _MAX_PAGE_SIZE)

        required = self._required_filters(dataset)
        missing = [name for name in required if not str(query.filters.get(name, "")).strip()]
        if missing:
            raise InvalidRequestError(
                f"korean {dataset.dataset_key} queries require filter(s): {', '.join(missing)}",
                provider="korean",
                dataset_id=dataset.id,
            )

        params: dict[str, str] = {
            "key": self._require_api_key(),
            "type_search": "search",
            "req_type": "json",
            "start": str((page - 1) * page_size + 1),
            "num": str(page_size),
        }
        for key, value in query.filters.items():
            if str(value).strip():
                params[str(key)] = str(value)

        url = self._build_url(dataset, params)
        payload = self._request_and_decode(url, dataset.id)
        items, total_count = self._parse_stdict_envelope(payload, dataset.id)

        next_page: int | None = None
        if total_count and page * page_size < total_count:
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
            "korean call_raw",
            extra={"dataset_id": dataset.id, "operation": operation, "param_keys": sorted(params)},
        )
        service = operation or str(dataset.raw_metadata.get("default_operation", ""))
        if not service:
            raise InvalidRequestError(
                "korean call_raw requires a non-empty operation (e.g. 'search.do')",
                provider="korean",
                dataset_id=dataset.id,
            )
        request_params: dict[str, str] = {
            "key": self._require_api_key(),
            "type_search": "search",
            "req_type": "json",
        }
        for key, value in params.items():
            if str(value).strip():
                request_params[str(key)] = str(value)
        url = self._build_url(dataset, request_params, service=service)
        payload = self._request_and_decode(url, dataset.id)
        _ = self._parse_stdict_envelope(payload, dataset.id)
        return payload

    def _require_api_key(self) -> str:
        return self._config.require_provider_key("korean")

    def _required_filters(self, dataset: DatasetRef) -> tuple[str, ...]:
        raw = dataset.raw_metadata.get("required_query_filters", [])
        if isinstance(raw, (list, tuple)):
            return tuple(str(item) for item in raw)
        return ()

    def _build_url(
        self,
        dataset: DatasetRef,
        params: Mapping[str, str],
        *,
        service: str | None = None,
    ) -> str:
        base_url = str(dataset.raw_metadata.get("base_url", "https://stdict.korean.go.kr/api"))
        service_path = service or str(dataset.raw_metadata.get("default_operation", "search.do"))
        return f"{base_url.rstrip('/')}/{service_path}?{urlencode(params)}"

    def _request_and_decode(self, url: str, dataset_id: str) -> dict[str, object]:
        response = self._transport.request(
            "GET",
            url,
            dataset_id=dataset_id,
            provider="korean",
        )
        decoded: object = decode_json(response.content)
        if not isinstance(decoded, dict):
            raise ProviderResponseError(
                "korean response is not a JSON object",
                provider="korean",
                dataset_id=dataset_id,
            )
        return decoded

    def _parse_stdict_envelope(
        self, payload: Mapping[str, object], dataset_id: str
    ) -> tuple[list[dict[str, object]], int]:
        """Extract ``(items, total_count)`` from the stdict channel envelope.

        A polysemous headword carries several \`sense\` entries. They are
        flattened to one record per sense, because headword plus definition is
        the unit callers work with. Errors map from \`statusCode\`; \`019\`
        is an authentication failure and becomes AuthError.
        """
        status_code = payload.get("statusCode")
        if isinstance(status_code, str) and status_code != "000":
            message = str(payload.get("statusMessage", ""))
            if status_code in ("019", "020", "021"):
                raise AuthError(
                    f"stdict authentication failed ({status_code}): {message}",
                    provider="korean",
                    dataset_id=dataset_id,
                )
            raise ProviderResponseError(
                f"stdict API error {status_code}: {message}",
                provider="korean",
                dataset_id=dataset_id,
            )

        channel = payload.get("channel")
        if not isinstance(channel, dict):
            raise ProviderResponseError(
                "stdict response has no 'channel' section",
                provider="korean",
                dataset_id=dataset_id,
            )

        total_count = 0
        total_raw = channel.get("total")
        if isinstance(total_raw, str) and total_raw.isdigit():
            total_count = int(total_raw)
        elif isinstance(total_raw, int):
            total_count = total_raw

        items: list[dict[str, object]] = []
        raw_items = channel.get("item")
        if isinstance(raw_items, list):
            for entry in raw_items:
                if not isinstance(entry, dict):
                    continue
                senses = entry.get("sense")
                if isinstance(senses, list):
                    for sense in senses:
                        if isinstance(sense, dict):
                            items.append({**entry, "sense": sense})
                else:
                    items.append(entry)
        return items, total_count

    def _load_default_catalogue(self) -> tuple[DatasetRef, ...]:
        return tuple(load_catalogue(_CATALOGUE_PACKAGE, "korean"))


__all__ = ["KoreanAdapter"]
