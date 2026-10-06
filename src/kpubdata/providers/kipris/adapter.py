"""Korean Intellectual Property Office (KIPI) Patent Family Information open API adapter (#223).

kipo-api.kipi.or.kr patFamInfoSearchService is registered as REST type on the
public data portal and uses serviceKey for authentication. Response shape::

    {"response": {"header": {...}, "body": {"items": {"item": [...]}, ...}}}

- With ``_type=json``, the shape is similar to standard envelope but lacks
  totalCount field (only ``numOfRows``/``pageNo`` available) — page
  calculation falls back to item count. ``pageNo``/``numOfRows`` are sent, and the
  ``pageNo`` the envelope echoes is checked: a page other than the one asked for is
  read as "no such page" (#837).
- Required parameter: ``applicationNumber`` (domestic application number)
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from urllib.parse import urlencode

from kpubdata.config import KPubDataConfig
from kpubdata.core.models import DatasetRef, Query, RecordBatch, SchemaDescriptor
from kpubdata.exceptions import (
    DatasetNotFoundError,
    InvalidRequestError,
    ProviderResponseError,
)
from kpubdata.providers._common import build_schema_from_metadata, load_catalogue
from kpubdata.transport.decode import decode_json
from kpubdata.transport.http import HttpTransport, TransportConfig

logger = logging.getLogger("kpubdata.provider.kipris")

_MAX_PAGE_SIZE = 100
_CATALOGUE_PACKAGE = "kpubdata.providers.kipris"


class KiprisAdapter:
    """Korean Intellectual Property Office patent family search adapter."""

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
        return "kipris"

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
        logger.debug("kipris dataset not found", extra={"dataset_key": dataset_key})
        raise DatasetNotFoundError(
            f"Dataset not found: kipris.{dataset_key}",
            provider="kipris",
            dataset_id=f"kipris.{dataset_key}",
        )

    def query_records(self, dataset: DatasetRef, query: Query) -> RecordBatch:
        page = query.page or 1
        page_size = min(query.page_size or _MAX_PAGE_SIZE, _MAX_PAGE_SIZE)

        required = self._required_filters(dataset)
        missing = [name for name in required if not str(query.filters.get(name, "")).strip()]
        if missing:
            raise InvalidRequestError(
                f"kipris {dataset.dataset_key} queries require filter(s): {', '.join(missing)}",
                provider="kipris",
                dataset_id=dataset.id,
            )

        params: dict[str, str] = {
            "serviceKey": self._require_api_key(),
            "_type": "json",
            "applicationNumber": str(query.filters["applicationNumber"]),
            # The page asked for was never sent (#837): every "next page" was the same
            # request, so a full page made list_all fetch it again until its page limit.
            "pageNo": str(page),
            "numOfRows": str(page_size),
        }

        url = self._build_url(dataset, params)
        payload = self._request_and_decode(url, dataset.id)
        items = self._parse_kipris_envelope(payload, dataset.id)

        # The envelope says which page it is. Whether this service pages at all has not
        # been checked against the provider (#837); if it ignores ``pageNo`` it answers
        # page 1 again, and those rows are not page ``page``'s — there is no such page.
        answered = self._answered_page(payload)
        if answered is not None and answered != page:
            items = []

        # No totalCount available; determine next page by full-page fallback.
        next_page: int | None = None
        if len(items) == page_size:
            next_page = page + 1

        return RecordBatch(
            items=items,
            dataset=dataset,
            # The envelope carries no total. An empty answer is zero rows (#806); for
            # anything else the total is not known — the page's length is not it (#824).
            total_count=None if items else 0,
            next_page=next_page,
            raw=payload,
        )

    def get_schema(self, dataset: DatasetRef) -> SchemaDescriptor | None:
        return build_schema_from_metadata(dataset)

    def call_raw(self, dataset: DatasetRef, operation: str, params: dict[str, object]) -> object:
        logger.debug(
            "kipris call_raw",
            extra={"dataset_id": dataset.id, "operation": operation, "param_keys": sorted(params)},
        )
        service = operation or str(dataset.raw_metadata.get("default_operation", ""))
        if not service:
            raise InvalidRequestError(
                "kipris call_raw requires a non-empty operation",
                provider="kipris",
                dataset_id=dataset.id,
            )
        request_params: dict[str, str] = {
            "serviceKey": self._require_api_key(),
            "_type": "json",
        }
        for key, value in params.items():
            if str(value).strip():
                request_params[str(key)] = str(value)
        url = self._build_url(dataset, request_params, service=service)
        payload = self._request_and_decode(url, dataset.id)
        _ = self._parse_kipris_envelope(payload, dataset.id)
        return payload

    def _require_api_key(self) -> str:
        return self._config.require_provider_key("kipris")

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
        base_url = str(dataset.raw_metadata.get("base_url", ""))
        service_path = service or str(dataset.raw_metadata.get("default_operation", ""))
        return f"{base_url.rstrip('/')}/{service_path}?{urlencode(params, safe='')}"

    def _request_and_decode(self, url: str, dataset_id: str) -> dict[str, object]:
        response = self._transport.request(
            "GET",
            url,
            dataset_id=dataset_id,
            provider="kipris",
            # By value as well as by parameter name (#805): the name is fixed here
            # and on the sensitive list today, and the value holds if that changes.
            secret_values=(self._require_api_key(),),
        )
        decoded: object = decode_json(response.content)
        if not isinstance(decoded, dict):
            raise ProviderResponseError(
                "kipris response is not a JSON object",
                provider="kipris",
                dataset_id=dataset_id,
            )
        return decoded

    @staticmethod
    def _answered_page(payload: Mapping[str, object]) -> int | None:
        """The page number the envelope reports (``response.body.pageNo``), if it does."""
        response = payload.get("response")
        body = response.get("body") if isinstance(response, dict) else None
        value = body.get("pageNo") if isinstance(body, dict) else None
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return None

    def _parse_kipris_envelope(
        self, payload: Mapping[str, object], dataset_id: str
    ) -> list[dict[str, object]]:
        """Extract item list from KIPI envelope (response/body/items/item)."""
        response = payload.get("response")
        if not isinstance(response, dict):
            raise ProviderResponseError(
                "kipris response has no 'response' section",
                provider="kipris",
                dataset_id=dataset_id,
            )
        body = response.get("body")
        if not isinstance(body, dict):
            raise ProviderResponseError(
                "kipris response has no 'body' section",
                provider="kipris",
                dataset_id=dataset_id,
            )
        items_raw = body.get("items")
        if items_raw is None:
            return []
        # Single item may arrive as an object — normalize to list.
        if isinstance(items_raw, dict):
            items_raw = items_raw.get("item")
        if isinstance(items_raw, dict):
            items_raw = [items_raw]
        if not isinstance(items_raw, list):
            return []
        return [item for item in items_raw if isinstance(item, dict)]

    def _load_default_catalogue(self) -> tuple[DatasetRef, ...]:
        return tuple(load_catalogue(_CATALOGUE_PACKAGE, "kipris"))


__all__ = ["KiprisAdapter"]
