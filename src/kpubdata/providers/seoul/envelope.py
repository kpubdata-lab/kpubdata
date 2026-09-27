"""Seoul API response envelope parser."""

from __future__ import annotations

from typing import NoReturn, cast

from kpubdata.core.models import DatasetRef
from kpubdata.exceptions import AuthError, InvalidRequestError, ProviderResponseError

_SUCCESS_CODE = "INFO-000"
_EMPTY_CODE = "INFO-200"


def validate_envelope(
    payload: dict[str, object],
    service_name: str,
    dataset: DatasetRef,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    if "code" in payload and "message" in payload and service_name not in payload:
        code_raw = payload.get("code")
        message_raw = payload.get("message")
        code = code_raw if isinstance(code_raw, str) else "ERROR-UNKNOWN"
        message = message_raw if isinstance(message_raw, str) else "Provider returned error"
        _raise_for_result_code(code, message, dataset.id)

    envelope_key = _envelope_key(payload, service_name, dataset)
    if dataset.raw_metadata.get("top_level_result") is True:
        result_obj = payload.get("RESULT")
        if not isinstance(result_obj, dict):
            raise ProviderResponseError(
                "Malformed response envelope: missing RESULT",
                provider="seoul",
                dataset_id=dataset.id,
            )
        result = cast(dict[str, object], result_obj)
        code_raw = result.get("RESULT.CODE")
        message_raw = result.get("RESULT.MESSAGE")
        code = code_raw if isinstance(code_raw, str) else "ERROR-UNKNOWN"
        message = message_raw if isinstance(message_raw, str) else "Provider returned error"
        if code == _SUCCESS_CODE:
            return payload, _normalize_rows(payload.get(envelope_key))
        if code == _EMPTY_CODE:
            return payload, []
        _raise_for_result_code(code, message, dataset.id)

    body_obj = payload.get(envelope_key)
    if not isinstance(body_obj, dict):
        raise ProviderResponseError(
            f"Malformed response envelope: missing {envelope_key}",
            provider="seoul",
            dataset_id=dataset.id,
        )

    body = cast(dict[str, object], body_obj)
    result_obj = body.get("RESULT")
    if not isinstance(result_obj, dict):
        raise ProviderResponseError(
            "Malformed response envelope: missing RESULT",
            provider="seoul",
            dataset_id=dataset.id,
        )

    result = cast(dict[str, object], result_obj)
    code_raw = result.get("CODE")
    message_raw = result.get("MESSAGE")
    code = code_raw if isinstance(code_raw, str) else "ERROR-UNKNOWN"
    message = message_raw if isinstance(message_raw, str) else "Provider returned error"

    if code == _SUCCESS_CODE:
        return body, _normalize_rows(body.get("row"))
    if code == _EMPTY_CODE:
        return body, []

    _raise_for_result_code(code, message, dataset.id)


def _envelope_key(payload: dict[str, object], service_name: str, dataset: DatasetRef) -> str:
    override = dataset.raw_metadata.get("envelope_key")
    if isinstance(override, str) and override and override in payload:
        return override
    return service_name


def _raise_for_result_code(code: str, message: str, dataset_id: str) -> NoReturn:
    if code in {"INFO-100", "INFO-300"}:
        raise AuthError(message, provider="seoul", provider_code=code, dataset_id=dataset_id)
    if code in {"INFO-400", "ERROR-300", "ERROR-301", "ERROR-310", "ERROR-336"}:
        raise InvalidRequestError(
            message,
            provider="seoul",
            provider_code=code,
            dataset_id=dataset_id,
        )
    if code in {"INFO-500", "ERROR-500", "ERROR-600", "ERROR-601"}:
        raise ProviderResponseError(
            message,
            provider="seoul",
            provider_code=code,
            dataset_id=dataset_id,
        )
    raise ProviderResponseError(
        message,
        provider="seoul",
        provider_code=code,
        dataset_id=dataset_id,
    )


def _normalize_rows(rows: object) -> list[dict[str, object]]:
    if rows is None:
        return []
    if isinstance(rows, list):
        row_items = cast(list[object], rows)
        return [cast(dict[str, object], item) for item in row_items if isinstance(item, dict)]
    if isinstance(rows, dict):
        return [cast(dict[str, object], rows)]
    return []
