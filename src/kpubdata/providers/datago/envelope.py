"""data.go.kr response envelope parser."""

from __future__ import annotations

import logging
from typing import NoReturn, cast

from kpubdata.core.models import DatasetRef
from kpubdata.exceptions import (
    AuthError,
    DatasetNotFoundError,
    InvalidRequestError,
    ProviderResponseError,
    RateLimitError,
    ServiceUnavailableError,
)

logger = logging.getLogger("kpubdata.provider.datago")


def _is_success_code(code: str) -> bool:
    """Return True for every data.go.kr resultCode that signals success.

    Different endpoint families spell "no error" with different digit
    counts: "00" (most APIs) and "000" (the RTMS family under
    apis.data.go.kr/1613000). Both, and every numeric variant of zero,
    must count as success.
    """
    try:
        return int(code) == 0
    except ValueError:
        return False


def _is_no_data_code(code: str) -> bool:
    """Return True for data.go.kr's NODATA_ERROR ("03", or 3 where the code is a number).

    It says no record matched the request, not that the call failed, so it is an
    empty result on every path (#470, #787).
    """
    try:
        return int(code) == 3
    except ValueError:
        return False


class DataGoEnvelopeParser:
    """Extract the body and item list from a data.go.kr response envelope."""

    def parse(
        self, payload: dict[str, object], dataset: DatasetRef | None = None
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        """Select the envelope-validation function for the dataset type and extract body/items."""
        dataset_id = dataset.id if dataset is not None else ""
        envelope_style = dataset.raw_metadata.get("envelope_style") if dataset is not None else None

        if envelope_style == "its_flat":
            return self._validate_its_flat_envelope(payload, dataset_id)

        self._raise_for_gateway_error(payload, dataset_id)

        response_obj = payload.get("response")
        if not isinstance(response_obj, dict):
            logger.debug(
                "Datago envelope missing response/body",
                extra={"dataset_id": dataset_id},
            )
            raise ProviderResponseError(
                "Malformed response envelope: missing response",
                provider="datago",
                dataset_id=dataset_id or None,
            )

        response_dict = cast(dict[str, object], response_obj)

        if envelope_style == "gyeonggi_msg":
            return self._validate_gyeonggi_msg_envelope(response_dict, dataset_id)
        return self._validate_standard_envelope(response_dict, dataset_id)

    def parse_odcloud(
        self, payload: dict[str, object], dataset: DatasetRef
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        """Normalize the odcloud response's data array into a record list."""
        data_obj = payload.get("data")
        if data_obj is None:
            return payload, []

        if not isinstance(data_obj, list):
            raise ProviderResponseError(
                "Malformed odcloud response: data must be an array",
                provider="datago",
                dataset_id=dataset.id,
            )

        normalized_items = cast(list[object], data_obj)
        items = [
            cast(dict[str, object], item) for item in normalized_items if isinstance(item, dict)
        ]
        return payload, items

    def _validate_its_flat_envelope(
        self, payload: dict[str, object], dataset_id: str
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        result_code = self._coerce_result_code(payload.get("resultCode"), dataset_id)
        result_msg_raw = payload.get("resultMsg")
        result_msg = (
            result_msg_raw if isinstance(result_msg_raw, str) else "Provider returned error"
        )
        logger.debug(
            "data.go.kr result",
            extra={"result_code": result_code, "result_msg": result_msg, "dataset_id": dataset_id},
        )
        if _is_no_data_code(result_code):
            return payload, []
        if not _is_success_code(result_code):
            self._raise_for_result_code(result_code, result_msg, dataset_id)

        items = self.normalize_items(payload.get("items"))
        return payload, items

    def _validate_standard_envelope(
        self, response_dict: dict[str, object], dataset_id: str
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        header_obj = response_dict.get("header")
        if not isinstance(header_obj, dict):
            raise ProviderResponseError(
                "Malformed response envelope: missing header",
                provider="datago",
                dataset_id=dataset_id or None,
            )

        header_dict = cast(dict[str, object], header_obj)
        result_code = header_dict.get("resultCode")
        if not isinstance(result_code, str):
            raise ProviderResponseError(
                "Malformed response envelope: missing resultCode",
                provider="datago",
                dataset_id=dataset_id or None,
            )

        result_msg_raw = header_dict.get("resultMsg")
        result_msg = (
            result_msg_raw if isinstance(result_msg_raw, str) else "Provider returned error"
        )
        logger.debug(
            "data.go.kr result",
            extra={"result_code": result_code, "result_msg": result_msg, "dataset_id": dataset_id},
        )
        body_obj = response_dict.get("body")
        body_dict: dict[str, object] = (
            cast(dict[str, object], body_obj) if isinstance(body_obj, dict) else {}
        )
        if _is_no_data_code(result_code):
            return body_dict, []
        if not _is_success_code(result_code):
            self._raise_for_result_code(result_code, result_msg, dataset_id)

        items = self.normalize_items(body_dict.get("items"))
        return body_dict, items

    def _validate_gyeonggi_msg_envelope(
        self, response_dict: dict[str, object], dataset_id: str
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        header_obj = response_dict.get("msgHeader")
        if not isinstance(header_obj, dict):
            raise ProviderResponseError(
                "Malformed response envelope: missing msgHeader",
                provider="datago",
                dataset_id=dataset_id or None,
            )

        header_dict = cast(dict[str, object], header_obj)
        result_code = self._coerce_result_code(header_dict.get("resultCode"), dataset_id)
        result_msg_raw = header_dict.get("resultMessage")
        result_msg = (
            result_msg_raw if isinstance(result_msg_raw, str) else "Provider returned error"
        )
        logger.debug(
            "data.go.kr result",
            extra={"result_code": result_code, "result_msg": result_msg, "dataset_id": dataset_id},
        )
        body_obj = response_dict.get("msgBody")
        body_dict: dict[str, object] = (
            cast(dict[str, object], body_obj) if isinstance(body_obj, dict) else {}
        )
        if _is_no_data_code(result_code):
            return body_dict, []
        if not _is_success_code(result_code):
            self._raise_for_result_code(result_code, result_msg, dataset_id)

        items_wrapper = self._extract_gyeonggi_msg_items_wrapper(body_dict)
        items = self.normalize_items(items_wrapper)
        return body_dict, items

    def _coerce_result_code(self, result_code: object, dataset_id: str) -> str:
        if isinstance(result_code, str):
            return result_code
        if isinstance(result_code, int):
            return str(result_code)
        raise ProviderResponseError(
            "Malformed response envelope: missing resultCode",
            provider="datago",
            dataset_id=dataset_id or None,
        )

    def _extract_gyeonggi_msg_items_wrapper(self, body_dict: dict[str, object]) -> object:
        list_values: list[object] = [
            value for value in body_dict.values() if isinstance(value, list)
        ]
        if len(list_values) == 1:
            return list_values[0]
        return body_dict

    def _raise_for_gateway_error(self, payload: dict[str, object], dataset_id: str) -> None:
        """Surface the gateway's own reason when it answered instead of the service.

        When data.go.kr rejects a request before it reaches the service, it
        returns ``OpenAPI_ServiceResponse/cmmMsgHeader`` instead of
        ``<response>`` — unregistered key, expired activation, disallowed
        IP, daily quota exceeded and the like. Before this shape was known,
        it produced a "Malformed response envelope" parse error (no
        ``response`` block) and the actual cause — my key is not registered
        — disappeared. ``returnReasonCode`` uses the same vocabulary as the
        service envelope's ``resultCode``, so it is fed straight into the
        same mapping.
        """
        gateway = payload.get("OpenAPI_ServiceResponse")
        if not isinstance(gateway, dict):
            return
        header = cast(dict[str, object], gateway).get("cmmMsgHeader")
        if not isinstance(header, dict):
            return
        header_dict = cast(dict[str, object], header)

        code_raw = header_dict.get("returnReasonCode")
        if code_raw is None:
            return
        code = str(code_raw).strip()

        # Prefer the human-readable reason: returnAuthMsg is the most
        # specific, falling back to errMsg.
        for key in ("returnAuthMsg", "errMsg"):
            value = header_dict.get(key)
            if isinstance(value, str) and value.strip():
                msg = value.strip()
                break
        else:
            msg = f"data.go.kr gateway rejected the request (returnReasonCode={code})"

        self._raise_for_result_code(code, msg, dataset_id)

    def _raise_for_result_code(self, code: str, msg: str, dataset_id: str) -> NoReturn:
        extra = {"dataset_id": dataset_id, "result_code": code, "result_msg": msg}
        if code in {"30", "31", "20", "32"}:
            logger.debug("Datago API envelope error", extra=extra)
            raise AuthError(msg, provider="datago", provider_code=code)
        if code == "22":
            logger.debug("Datago API envelope error", extra=extra)
            raise RateLimitError(msg, provider="datago", provider_code=code, retryable=False)
        if code == "10":
            logger.debug("Datago API envelope error", extra=extra)
            raise InvalidRequestError(msg, provider="datago", provider_code=code)
        if code == "12":
            logger.debug("Datago API envelope error", extra=extra)
            raise DatasetNotFoundError(
                msg,
                provider="datago",
                provider_code=code,
                dataset_id=dataset_id,
            )
        if code in {"01", "02"}:
            logger.debug("Datago API envelope error", extra=extra)
            raise ServiceUnavailableError(msg, provider="datago", provider_code=code)
        logger.debug("Datago API envelope error", extra=extra)
        raise ProviderResponseError(msg, provider="datago", provider_code=code)

    def normalize_items(self, items_wrapper: object) -> list[dict[str, object]]:
        """Normalize an items/item wrapper into a list of record dicts."""
        if items_wrapper is None:
            return []

        if isinstance(items_wrapper, dict):
            item_value = cast(dict[str, object], items_wrapper).get("item")
            if isinstance(item_value, list):
                normalized_items = cast(list[object], item_value)
                return [
                    cast(dict[str, object], item)
                    for item in normalized_items
                    if isinstance(item, dict)
                ]
            if isinstance(item_value, dict):
                return [cast(dict[str, object], item_value)]
            return []

        if isinstance(items_wrapper, list):
            normalized_items = cast(list[object], items_wrapper)
            return [
                cast(dict[str, object], item) for item in normalized_items if isinstance(item, dict)
            ]

        return []


__all__ = ["DataGoEnvelopeParser"]
