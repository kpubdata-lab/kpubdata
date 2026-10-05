"""KPubData Python module.

This file contains the implementation at ``src/kpubdata/providers/lofin/adapter.py``.
Key classes and functions are part of the public API, transport layer,
or provider adapter.
"""

from __future__ import annotations

import logging
import ssl
from collections.abc import Mapping, Sequence
from typing import NoReturn, cast
from urllib.parse import quote

from kpubdata.config import KPubDataConfig
from kpubdata.core.models import DatasetRef, Query, RecordBatch, SchemaDescriptor
from kpubdata.exceptions import (
    AuthError,
    DatasetNotFoundError,
    ParseError,
    ProviderResponseError,
)
from kpubdata.providers._common import (
    build_schema_from_metadata,
    coerce_int,
    load_catalogue,
    reported_total,
)
from kpubdata.transport.decode import decode_json
from kpubdata.transport.http import HttpTransport, TransportConfig, TransportRequirements

logger = logging.getLogger("kpubdata.provider.lofin")


def _lofin_ssl_context() -> ssl.SSLContext:
    """Create SSL context compatible with LOFIN server.

    Certificate verification is enabled. Previously, verification was disabled
    entirely with ``check_hostname = False`` and ``verify_mode = CERT_NONE`` —
    but since API keys travel with this request, a MITM attacker who swaps
    certificates also gets the key. The README only noted it as "SSL settings
    auto-adjusted".

    Actually only cipher relaxation was needed. Direct verification on
    2026-09-25 of www.lofin365.go.kr shows::

        Default context (full verification)    OK  TLSv1.3  TLS_AES_256_GCM_SHA384
        Verification ON + SECLEVEL=1           OK  TLSv1.3  TLS_AES_256_GCM_SHA384
        Issuer CN = Sectigo Public Server Authentication CA OV R36
        subject   = lofin365.go.kr

    Public CA issued a proper certificate and connects via TLSv1.3 — there was
    never reason to disable verification, and even less so now. ``SECLEVEL=1``
    is retained because this function exists from when the server offered only
    TLSv1.2 and AES256-SHA256, so some nodes may still do that — relaxing cipher
    floor is completely different from not verifying the peer.
    """
    ctx = ssl.create_default_context()
    ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
    return ctx


class LofinAdapter:
    """Compute or query values related to LofinAdapter."""

    requires_api_key: bool = True

    transport_requirements: TransportRequirements = TransportRequirements(
        ssl_context_factory=_lofin_ssl_context,
    )

    def __init__(
        self,
        *,
        config: KPubDataConfig | None = None,
        transport: HttpTransport | None = None,
        catalogue: Sequence[DatasetRef] | None = None,
    ) -> None:
        """Initialize instance state."""
        self._config: KPubDataConfig = config or KPubDataConfig()
        if transport is not None:
            self._transport: HttpTransport = transport
        else:
            ssl_ctx = _lofin_ssl_context()
            transport_config = TransportConfig(
                timeout=self._config.timeout,
                max_retries=self._config.max_retries,
                ssl_context=ssl_ctx,
            )
            self._transport = HttpTransport(transport_config)

        datasets = tuple(catalogue) if catalogue is not None else self._load_default_catalogue()
        self._datasets: tuple[DatasetRef, ...] = datasets
        self._datasets_by_key: dict[str, DatasetRef] = {
            dataset.dataset_key: dataset for dataset in self._datasets
        }

    @property
    def name(self) -> str:
        """Return provider name."""
        return "lofin"

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
            "LOFIN dataset not found",
            extra={"dataset_id": f"lofin.{dataset_key}", "provider": "lofin"},
        )
        raise DatasetNotFoundError(
            f"Dataset not found: lofin.{dataset_key}",
            provider="lofin",
            dataset_id=f"lofin.{dataset_key}",
        )

    def query_records(self, dataset: DatasetRef, query: Query) -> RecordBatch:
        """Query records by calling LOFIN API."""
        page = query.page or 1
        page_size = query.page_size or 100
        logger.debug(
            "lofin query_records",
            extra={
                "dataset_id": dataset.id,
                "page": page,
                "page_size": page_size,
                "filter_keys": sorted(query.filters.keys()),
            },
        )

        url = self._build_request_url(
            dataset, page=page, page_size=page_size, filters=query.filters
        )
        payload = self._request_and_decode(url, dataset.id)

        body, items = self._validate_envelope(payload, dataset)

        reported_count = reported_total(body.get("list_total_count"))
        # Paging treats "no count" and zero alike: only a positive count bounds it.
        total_count = reported_count or 0
        if (total_count and page * page_size < total_count) or (
            not total_count and len(items) == page_size
        ):
            computed_next = page + 1
        else:
            computed_next = None

        if not items:
            logger.debug(
                "LOFIN envelope: zero items",
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
        """Return schema information of the dataset."""
        return build_schema_from_metadata(dataset)

    def call_raw(self, dataset: DatasetRef, operation: str, params: dict[str, object]) -> object:
        """Call LOFIN API directly and return raw response."""
        _ = operation
        logger.debug(
            "lofin call_raw",
            extra={
                "dataset_id": dataset.id,
                "operation": operation,
                "param_keys": sorted(params.keys()),
            },
        )
        page = self._int_param(params, "pIndex", self._int_param(params, "page", 1))
        page_size = self._int_param(params, "pSize", self._int_param(params, "page_size", 100))
        extra_keys = {"pIndex", "page", "pSize", "page_size"}
        filters = {k: v for k, v in params.items() if k not in extra_keys}

        url = self._build_request_url(dataset, page=page, page_size=page_size, filters=filters)
        payload = self._request_and_decode(url, dataset.id)
        _ = self._validate_envelope(payload, dataset)
        return payload

    def _require_api_key(self) -> str:
        """Read public data portal (data.go.kr) API key or raise exception.

        localdata, semas, and lofin adapters all share the data.go.kr
        authentication system and are intentionally managed under a single
        provider_key ("datago").
        """
        return self._config.require_provider_key("datago")

    def _build_request_url(
        self,
        dataset: DatasetRef,
        *,
        page: int,
        page_size: int,
        filters: dict[str, object] | None = None,
    ) -> str:
        """Build LOFIN API request URL."""
        base_url_raw = dataset.raw_metadata.get("base_url")
        if not isinstance(base_url_raw, str) or not base_url_raw:
            logger.debug(
                "LOFIN dataset metadata missing base_url",
                extra={"dataset_id": dataset.id},
            )
            raise ProviderResponseError(
                "Dataset metadata missing base_url",
                provider="lofin",
                dataset_id=dataset.id,
            )

        dataset_code = self._require_dataset_metadata(dataset, "api_code")
        api_key = self._require_api_key()
        safe_page = page if page > 0 else 1
        safe_page_size = page_size if page_size > 0 else 100
        url = (
            f"{base_url_raw}/{dataset_code}"
            f"?Key={api_key}&Type=json&pIndex={safe_page}&pSize={safe_page_size}"
        )
        if filters:
            for key, value in filters.items():
                url += f"&{key}={quote(str(value), safe='')}"
        return url

    def _request_and_decode(self, url: str, dataset_id: str = "") -> dict[str, object]:
        """Send HTTP GET request to LOFIN API and decode."""
        response = self._transport.request(
            "GET",
            url,
            dataset_id=dataset_id,
            provider="lofin",
            # By value as well as by parameter name (#805): the name is fixed here
            # and on the sensitive list today, and the value holds if that changes.
            secret_values=(self._require_api_key(),),
        )

        try:
            decoded_obj: object = decode_json(response.content)
        except ValueError as exc:
            logger.debug("LOFIN response parsing failed", extra={"dataset_id": dataset_id})
            raise ParseError("Failed to parse LOFIN response", provider="lofin") from exc

        if isinstance(decoded_obj, dict):
            payload = cast(dict[str, object], decoded_obj)
            self._raise_for_top_level_result(payload, dataset_id)
            return payload

        logger.debug("LOFIN decoded payload invalid type", extra={"dataset_id": dataset_id})
        raise ParseError("Decoded payload is not an object", provider="lofin")

    def _validate_envelope(
        self, payload: dict[str, object], dataset: DatasetRef
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        """Validate LOFIN API response envelope format."""
        dataset_code = self._require_dataset_metadata(dataset, "api_code")
        body_obj = payload.get(dataset_code)
        if not isinstance(body_obj, list) or not body_obj:
            raise ProviderResponseError(
                f"Malformed response envelope: missing {dataset_code}",
                provider="lofin",
                dataset_id=dataset.id,
            )

        body_list = cast(list[object], body_obj)
        first_entry = body_list[0]
        if not isinstance(first_entry, dict):
            raise ProviderResponseError(
                f"Malformed response envelope: invalid {dataset_code} body",
                provider="lofin",
                dataset_id=dataset.id,
            )

        head_entry = cast(dict[str, object], first_entry)
        head_obj = head_entry.get("head")
        if not isinstance(head_obj, list) or not head_obj:
            legacy_body = cast(dict[str, object], first_entry)
            self._raise_for_result(legacy_body, dataset.id)
            items = self._normalize_rows(legacy_body.get("row"))
            return legacy_body, items

        head_items = cast(list[object], head_obj)
        metadata: dict[str, object] = {}
        result_payload: Mapping[str, object] | None = None
        for head_item in head_items:
            if not isinstance(head_item, dict):
                continue
            head_dict = cast(dict[str, object], head_item)
            if "list_total_count" in head_dict:
                metadata["list_total_count"] = head_dict.get("list_total_count")
            if "RESULT" in head_dict:
                result_obj = head_dict.get("RESULT")
                if isinstance(result_obj, Mapping):
                    result_payload = cast(Mapping[str, object], result_obj)

        if result_payload is None:
            raise ProviderResponseError(
                f"Malformed response envelope: missing {dataset_code} RESULT",
                provider="lofin",
                dataset_id=dataset.id,
            )

        self._raise_for_result({"RESULT": dict(result_payload)}, dataset.id)

        rows_entry = body_list[1] if len(body_list) > 1 else None
        rows_wrapper: object = None
        if isinstance(rows_entry, dict):
            rows_dict = cast(dict[str, object], rows_entry)
            rows_wrapper = rows_dict.get("row")

        items = self._normalize_rows(rows_wrapper)
        return metadata, items

    def _raise_for_top_level_result(self, payload: Mapping[str, object], dataset_id: str) -> None:
        """Check LOFIN top-level result field."""
        result_obj = payload.get("RESULT")
        if not isinstance(result_obj, list):
            return

        result_list = cast(list[object], result_obj)
        if not result_list:
            return

        first_result = result_list[0]
        if not isinstance(first_result, Mapping):
            return

        self._raise_for_result(
            {"RESULT": dict(cast(Mapping[str, object], first_result))}, dataset_id
        )

    def _raise_for_result(self, payload: Mapping[str, object], dataset_id: str) -> None:
        """Check LOFIN result field and raise on error."""
        result_obj = payload.get("RESULT")
        if not isinstance(result_obj, dict):
            return

        result_dict = cast(dict[str, object], result_obj)
        code_raw = result_dict.get("CODE")
        message_raw = result_dict.get("MESSAGE")
        code = code_raw if isinstance(code_raw, str) else "ERROR-000"
        message = message_raw if isinstance(message_raw, str) else "Provider returned error"
        logger.debug(
            "LOFIN result",
            extra={"result_code": code, "result_msg": message, "dataset_id": dataset_id},
        )

        if code == "INFO-000":
            return
        if code == "INFO-200":
            return

        self._raise_for_result_code(code, message, dataset_id)

    def _raise_for_result_code(self, code: str, msg: str, dataset_id: str) -> NoReturn:
        """Analyze LOFIN error code and raise exception."""
        if code in {"ERROR-290", "ERROR-300"}:
            raise AuthError(
                msg, provider="lofin", provider_code=code, dataset_id=dataset_id or None
            )
        if code.startswith("ERROR-"):
            raise ProviderResponseError(
                msg,
                provider="lofin",
                provider_code=code,
                dataset_id=dataset_id or None,
            )
        raise ProviderResponseError(
            msg,
            provider="lofin",
            provider_code=code,
            dataset_id=dataset_id or None,
        )

    def _require_dataset_metadata(self, dataset: DatasetRef, key: str) -> str:
        """Read required field from dataset metadata."""
        value = dataset.raw_metadata.get(key)
        if isinstance(value, str) and value:
            return value
        raise ProviderResponseError(
            f"Dataset metadata missing {key}",
            provider="lofin",
            dataset_id=dataset.id,
        )

    def _normalize_rows(self, rows_wrapper: object) -> list[dict[str, object]]:
        """Normalize LOFIN API response rows field."""
        if rows_wrapper is None:
            return []
        if isinstance(rows_wrapper, list):
            rows = cast(list[object], rows_wrapper)
            return [cast(dict[str, object], item) for item in rows if isinstance(item, dict)]
        if isinstance(rows_wrapper, dict):
            return [cast(dict[str, object], rows_wrapper)]
        return []

    @classmethod
    def _int_param(cls, params: Mapping[str, object], key: str, default: int) -> int:
        """Extract integer parameter or return default."""
        value = params.get(key)
        coerced = coerce_int(value, default)
        return coerced if coerced > 0 else default

    @staticmethod
    def _load_default_catalogue() -> tuple[DatasetRef, ...]:
        """Load and return default catalog."""
        return load_catalogue("kpubdata.providers.lofin", "lofin")


__all__ = ["LofinAdapter"]
