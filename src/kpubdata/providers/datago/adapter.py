"""data.go.kr adapter with a curated dataset catalogue."""

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
    """Adapter for data.go.kr (the Korean public-data portal).

    Provides a curated catalogue of the datasets supported by the
    apis.data.go.kr endpoint family.
    """

    requires_api_key: bool = True

    def __init__(
        self,
        *,
        config: KPubDataConfig | None = None,
        transport: HttpTransport | None = None,
        catalogue: Sequence[DatasetRef] | None = None,
    ) -> None:
        """Initialize the internal state for the instance."""
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
        """Return the canonical provider key."""

        return "datago"

    def list_datasets(self) -> list[DatasetRef]:
        """Return the datasets available on data.go.kr."""

        return list(self._datasets)

    def search_datasets(self, text: str) -> list[DatasetRef]:
        """Search the datasets available on data.go.kr."""

        needle = text.casefold()
        return [
            dataset
            for dataset in self._datasets
            if needle in dataset.id.casefold() or needle in dataset.name.casefold()
        ]

    def get_dataset(self, dataset_key: str) -> DatasetRef:
        """Resolve a provider-local dataset key for data.go.kr."""

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
        """Query records from a data.go.kr dataset."""

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
            # odcloud-family services use the page-parameter names defined in
            # metadata instead of pageNo/numOfRows.
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
            # The auth key, format and page parameters are already filled —
            # user filters must not overwrite them.
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
            # Without totalCount, a full current page is the signal that a next
            # page exists.
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
        """Return schema metadata for a data.go.kr dataset.

        Returns a schema from the curated catalogue metadata when possible.
        data.go.kr has no live schema-discovery endpoint, so datasets whose
        catalogue entry carries no explicitly curated field definitions
        return ``None``.
        """
        return build_schema_from_metadata(dataset)

    def call_raw(self, dataset: DatasetRef, operation: str, params: dict[str, object]) -> object:
        """Call a data.go.kr-specific API operation.

        ``datago.generic`` is a raw-only escape hatch for data.go.kr
        endpoints absent from the curated catalogue. It returns the decoded
        raw response (dict) as-is, with no normalization, pagination or
        schema handling. The caller must pass:
          * ``_base_url`` (str, required): endpoint base URL without the
            operation name.
          * ``_envelope`` (bool, default True): when True, validates the
            standard ``response.header.resultCode`` envelope. Must be an
            actual bool — strings/integers are rejected.
          * ``_service_key_param`` (str): overrides the service key
            parameter name.
          * ``_format_param`` (str): overrides the response format
            parameter name.

        When ``_base_url`` does not point at a ``*.data.go.kr`` host, a
        warning is logged. The call proceeds — this is a relaxed check.
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
                # Non-allowlisted hosts are blocked fail-closed (#261) — only the
                # host is logged, never the raw URL (the query may carry the
                # serviceKey).
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
            # Consume the control magic keys and forward only real provider
            # parameters to the remote endpoint.
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
        """Return whether the dataset is the datago.generic escape hatch."""
        return bool(dataset.raw_metadata.get("generic"))

    @staticmethod
    def _is_odcloud(dataset: DatasetRef) -> bool:
        """Return whether the dataset uses an odcloud-family response shape."""
        return dataset.raw_metadata.get("provider_family") == "odcloud"

    @staticmethod
    def _get_fixed_query_params(dataset: DatasetRef) -> dict[str, str]:
        """Return the catalogue's non-secret, operation-fixed query constants."""
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
        """Read the API key for data.go.kr calls from configuration."""
        return self._config.require_provider_key("datago")

    def _build_request_url(self, dataset: DatasetRef, operation: str | None = None) -> str:
        """Build the call URL from dataset metadata and the operation value."""
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
        """Fill only the not-yet-provided catalogue default_filters keys with defaults.

        When the user did not specify a required provider parameter (e.g.
        the procurement-office inqryDiv), it is filled from the default
        recorded in the catalogue. Keys already provided (via user filters
        and the like) are not overwritten.
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
        """Build the base query including the service key and format parameters."""
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

    def _secret_values(self) -> tuple[str, ...]:
        """The configured service key, for value-based masking; empty when none is set."""
        key = self._config.get_provider_key("datago")
        return (key,) if key else ()

    def _request_and_decode(
        self, url: str, params: Mapping[str, object], dataset_id: str = ""
    ) -> dict[str, object]:
        """Call the data.go.kr API and decode the response body into a dict."""
        string_params = {key: str(value) for key, value in params.items()}
        try:
            response = self._transport.request(
                "GET",
                url,
                params=string_params,
                dataset_id=dataset_id,
                provider="datago",
                # ``datago.generic`` lets the caller name the key parameter
                # (``_service_key_param``); under a name the sensitive-name list
                # lacks, only the value tells the transport what to mask (#805).
                secret_values=self._secret_values(),
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
        """Return whether the TransportError came from an HTTP 403 response.

        Looks at ``status_code``, not ``__cause__``. The transport breaks
        the exception chain when a request carries credentials (otherwise
        the key leaks through the final URL embedded in the httpx message),
        and datago sends its key in ``params`` — so if this verdict relied
        on the chain, the 403 hint would vanish the moment masking turns
        on.
        """
        return exc.status_code == 403

    @staticmethod
    def _load_default_catalogue() -> tuple[DatasetRef, ...]:
        """Load the bundled default data.go.kr catalogue."""
        return load_catalogue("kpubdata.providers.datago", "datago")


__all__ = ["DataGoAdapter"]
