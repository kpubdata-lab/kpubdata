"""KPubData Python module.

This file contains the implementation at
``src/kpubdata/providers/sgis/adapter.py``.
Key classes and functions serve as public API, transport layer, or provider
adapter.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import NoReturn, Protocol, cast

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
from kpubdata.providers._common import build_schema_from_metadata, load_catalogue
from kpubdata.providers.sgis.auth import SgisAuthClient, _extract_err_code
from kpubdata.transport.decode import decode_json
from kpubdata.transport.http import HttpTransport, TransportConfig

_SGIS_PROVIDER = "sgis"
_BASE_URL = "https://sgisapi.kostat.go.kr/OpenAPI3"


def _token_of(params: Mapping[str, str]) -> tuple[str, ...]:
    """The access token a request carries, for value-based masking (#805)."""
    token = params.get("accessToken")
    return (token,) if token else ()


class _AuthClient(Protocol):
    """Protocol for AuthClient to compute or retrieve values."""

    def get_access_token(self, *, force_refresh: bool = False) -> str: ...

    def invalidate(self) -> None: ...


class SgisAdapter:
    """SgisAdapter to compute or retrieve values."""

    requires_api_key: bool = True

    def __init__(
        self,
        *,
        config: KPubDataConfig | None = None,
        transport: HttpTransport | None = None,
        catalogue: Sequence[DatasetRef] | None = None,
        auth_client: _AuthClient | None = None,
    ) -> None:
        """Initialize internal state for this adapter instance."""
        self._config: KPubDataConfig = config or KPubDataConfig()
        transport_config = TransportConfig(
            timeout=self._config.timeout,
            max_retries=self._config.max_retries,
        )
        self._transport: HttpTransport = transport or HttpTransport(transport_config)
        self._auth: _AuthClient = auth_client or SgisAuthClient(
            config=self._config,
            transport=self._transport,
        )

        datasets = tuple(catalogue) if catalogue is not None else self._load_default_catalogue()
        self._datasets: tuple[DatasetRef, ...] = datasets
        self._datasets_by_key: dict[str, DatasetRef] = {
            dataset.dataset_key: dataset for dataset in self._datasets
        }

    @property
    def name(self) -> str:
        """Return the provider name."""
        return _SGIS_PROVIDER

    def list_datasets(self) -> list[DatasetRef]:
        """Return the list of available datasets."""
        return list(self._datasets)

    def search_datasets(self, text: str) -> list[DatasetRef]:
        """Search datasets by text."""
        needle = text.casefold()
        return [
            dataset
            for dataset in self._datasets
            if needle in dataset.id.casefold() or needle in dataset.name.casefold()
        ]

    def get_dataset(self, dataset_key: str) -> DatasetRef:
        """Return a dataset by key."""
        dataset = self._datasets_by_key.get(dataset_key)
        if dataset is not None:
            return dataset

        raise DatasetNotFoundError(
            f"Dataset not found: {_SGIS_PROVIDER}.{dataset_key}",
            provider=_SGIS_PROVIDER,
            dataset_id=f"{_SGIS_PROVIDER}.{dataset_key}",
        )

    def query_records(self, dataset: DatasetRef, query: Query) -> RecordBatch:
        """Perform record query."""
        endpoint = self._dataset_endpoint(dataset)
        request_params = self._build_boundary_params(dataset, query.filters)
        payload = self._request_geojson(
            endpoint=endpoint, params=request_params, dataset_id=dataset.id
        )

        features_obj = payload.get("features")
        if not isinstance(features_obj, list):
            raise ProviderResponseError(
                "SGIS boundary response missing features list",
                provider=_SGIS_PROVIDER,
                dataset_id=dataset.id,
            )

        features = cast(list[object], features_obj)
        items = [
            self._normalize_feature(cast(dict[str, object], feature))
            for feature in features
            if isinstance(feature, dict)
        ]

        return RecordBatch(items=items, dataset=dataset, total_count=len(items), raw=payload)

    def get_schema(self, dataset: DatasetRef) -> SchemaDescriptor | None:
        """Return schema for dataset."""
        return build_schema_from_metadata(dataset)

    def call_raw(self, dataset: DatasetRef, operation: str, params: dict[str, object]) -> object:
        """Call raw operation."""
        endpoint = self._resolve_raw_endpoint(dataset, operation)
        request_params: dict[str, str] = {}
        for key, value in params.items():
            request_params[key] = str(value)

        if "accessToken" not in request_params:
            request_params["accessToken"] = self._auth.get_access_token()

        return self._request_geojson(
            endpoint=endpoint, params=request_params, dataset_id=dataset.id
        )

    def _resolve_raw_endpoint(self, dataset: DatasetRef, operation: str) -> str:
        """Resolve raw endpoint from configuration and defaults."""
        if operation == "list":
            return self._dataset_endpoint(dataset)
        if operation.startswith("http://") or operation.startswith("https://"):
            raise InvalidRequestError(
                "SGIS call_raw operation must be an endpoint path, not a full URL",
                provider=_SGIS_PROVIDER,
                dataset_id=dataset.id,
                operation=operation,
            )
        return operation.lstrip("/")

    def _build_boundary_params(
        self, dataset: DatasetRef, filters: Mapping[str, object]
    ) -> dict[str, str]:
        """Build and return boundary parameters."""
        params: dict[str, str] = {
            "year": str(dataset.raw_metadata.get("default_year", "2023")),
        }
        adm_cd_default = dataset.raw_metadata.get("default_adm_cd")
        if isinstance(adm_cd_default, str):
            params["adm_cd"] = adm_cd_default

        low_search_default = dataset.raw_metadata.get("default_low_search")
        if isinstance(low_search_default, int):
            params["low_search"] = str(low_search_default)
        elif isinstance(low_search_default, str):
            params["low_search"] = low_search_default

        for key, value in filters.items():
            params[key] = str(value)

        params["accessToken"] = self._auth.get_access_token()
        return params

    def _request_geojson(
        self,
        *,
        endpoint: str,
        params: Mapping[str, str],
        dataset_id: str,
    ) -> dict[str, object]:
        """Request GeoJSON and return decoded payload."""
        url = self._make_url(endpoint)
        response = self._transport.request(
            "GET",
            url,
            params=dict(params),
            secret_values=_token_of(params),
        )

        try:
            decoded = decode_json(response.content)
        except ParseError as exc:
            exc.provider = _SGIS_PROVIDER
            exc.dataset_id = dataset_id
            raise

        if not isinstance(decoded, dict):
            raise ProviderResponseError(
                "SGIS response must be a JSON object",
                provider=_SGIS_PROVIDER,
                dataset_id=dataset_id,
            )
        payload = cast(dict[str, object], decoded)

        try:
            self._raise_for_err_code(payload, dataset_id)
        except AuthError:
            self._auth.invalidate()
            refreshed = dict(params)
            refreshed["accessToken"] = self._auth.get_access_token(force_refresh=True)
            response_retry = self._transport.request(
                "GET",
                url,
                params=refreshed,
                secret_values=_token_of(refreshed),
            )
            decoded_retry = decode_json(response_retry.content)
            if not isinstance(decoded_retry, dict):
                raise ProviderResponseError(
                    "SGIS response must be a JSON object",
                    provider=_SGIS_PROVIDER,
                    dataset_id=dataset_id,
                ) from None
            payload_retry = cast(dict[str, object], decoded_retry)
            self._raise_for_err_code(payload_retry, dataset_id)
            return payload_retry

        return payload

    def _normalize_feature(self, feature: Mapping[str, object]) -> dict[str, object]:
        """Normalize feature and return result."""
        properties_obj = feature.get("properties")
        properties = (
            cast(dict[str, object], properties_obj) if isinstance(properties_obj, dict) else {}
        )
        item: dict[str, object] = dict(properties)

        geometry_obj = feature.get("geometry")
        if isinstance(geometry_obj, dict):
            item["geometry"] = cast(dict[str, object], geometry_obj)

        feature_type = feature.get("type")
        if isinstance(feature_type, str):
            item["feature_type"] = feature_type
        return item

    def _raise_for_err_code(self, payload: Mapping[str, object], dataset_id: str) -> None:
        """Raise exception for error code."""
        err_code = _extract_err_code(payload)
        if err_code is None or err_code == 0:
            return

        message_obj = payload.get("errMsg")
        message = message_obj if isinstance(message_obj, str) and message_obj else "SGIS API error"
        self._raise_for_code(err_code, message, dataset_id)

    def _raise_for_code(self, err_code: int, message: str, dataset_id: str) -> NoReturn:
        """Raise exception for specific error code."""
        provider_code = str(err_code)
        if err_code in {-100}:
            raise ProviderResponseError(
                message,
                provider=_SGIS_PROVIDER,
                provider_code=provider_code,
                dataset_id=dataset_id,
            )
        if err_code in {-401, -402, -403}:
            raise AuthError(
                message,
                provider=_SGIS_PROVIDER,
                provider_code=provider_code,
                dataset_id=dataset_id,
            )
        if err_code in {-413, -414}:
            raise InvalidRequestError(
                message,
                provider=_SGIS_PROVIDER,
                provider_code=provider_code,
                dataset_id=dataset_id,
            )
        if err_code in {-429}:
            raise RateLimitError(
                message,
                provider=_SGIS_PROVIDER,
                provider_code=provider_code,
                dataset_id=dataset_id,
                retryable=False,
            )
        if err_code <= -500:
            raise ServiceUnavailableError(
                message,
                provider=_SGIS_PROVIDER,
                provider_code=provider_code,
                dataset_id=dataset_id,
            )
        raise ProviderResponseError(
            message,
            provider=_SGIS_PROVIDER,
            provider_code=provider_code,
            dataset_id=dataset_id,
        )

    def _dataset_endpoint(self, dataset: DatasetRef) -> str:
        """Return dataset endpoint from metadata."""
        endpoint_obj = dataset.raw_metadata.get("endpoint")
        if isinstance(endpoint_obj, str) and endpoint_obj:
            return endpoint_obj
        raise ProviderResponseError(
            "Dataset metadata missing endpoint",
            provider=_SGIS_PROVIDER,
            dataset_id=dataset.id,
        )

    @staticmethod
    def _make_url(endpoint: str) -> str:
        """Generate and return URL from endpoint."""
        return f"{_BASE_URL}/{endpoint.lstrip('/')}"

    @staticmethod
    def _load_default_catalogue() -> tuple[DatasetRef, ...]:
        """Load and return default catalogue."""
        return load_catalogue("kpubdata.providers.sgis", _SGIS_PROVIDER)


__all__ = ["SgisAdapter"]
