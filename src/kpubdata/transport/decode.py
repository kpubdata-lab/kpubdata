"""Response decoding helpers: content-type detection plus JSON and XML."""

from __future__ import annotations

import json
import logging
import re
from importlib import import_module

import httpx

from ..exceptions import ParseError

logger = logging.getLogger("kpubdata.transport.decode")


def sniff_body_kind(body: bytes) -> str:
    """Classify a body as ``json``, ``xml`` or ``other`` from a bounded prefix."""
    prefix = body[:256].lstrip(b" \t\r\n\xef\xbb\xbf")
    lowered = prefix.lower()
    if prefix.startswith((b"{", b"[")):
        return "json"
    if lowered.startswith((b"<!doctype html", b"<html", b"<head", b"<body", b"<script")):
        return "other"
    if prefix.startswith(b"<?xml") or lowered.startswith(
        (b"<response", b"<openapi_serviceresponse", b"<result")
    ):
        return "xml"
    return "other"


def detect_content_type(response: httpx.Response) -> str:
    """Classify JSON/XML, sniffing a bounded prefix for ambiguous headers.

    Gateways sometimes return XML errors with text/plain or text/html headers.
    Do not blindly interpret an HTML document as XML, and never log a body
    preview: provider errors can echo credentials (#970).
    """
    header_value_obj = response.headers.get("content-type", "")
    content_type = str(header_value_obj).lower()
    if "json" in content_type:
        return "json"
    if "xml" in content_type:
        return "xml"

    raw_body = getattr(response, "content", None)
    if isinstance(raw_body, bytes):
        sniffed = sniff_body_kind(raw_body)
        if sniffed != "other":
            return sniffed
    logger.debug(
        "Unrecognized content-type, defaulting to 'other'",
        extra={"content_type": content_type},
    )
    return "other"


def decode_json(data: str | bytes) -> object:
    """Decode JSON, raising a clear error when it fails."""
    try:
        payload = data.decode("utf-8-sig") if isinstance(data, bytes) else data
    except UnicodeDecodeError as exc:
        logger.debug(
            "JSON UTF-8 decode failed",
            extra={"byte_length": len(data) if isinstance(data, bytes) else None},
        )
        msg = "Failed to decode JSON bytes as UTF-8"
        raise ParseError(msg) from exc

    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        logger.debug(
            "JSON parse failed",
            extra={
                "char_length": len(payload),
                "line": exc.lineno,
                "column": exc.colno,
            },
        )
        msg = "Failed to decode JSON payload"
        raise ParseError(msg) from exc
    except (ValueError, RecursionError) as exc:
        # json.loads also raises a plain ValueError (an integer longer than
        # the interpreter's digit limit) and RecursionError (nesting too deep).
        logger.debug(
            "JSON parse failed",
            extra={"char_length": len(payload), "error_type": type(exc).__name__},
        )
        msg = "Failed to decode JSON payload"
        raise ParseError(msg) from exc


def decode_xml(data: str | bytes) -> dict[str, object]:
    """Decode XML into a dict.

    Raises:
        ImportError: If ``xmltodict`` is not installed.
        ParseError: If parsing fails.
    """
    try:
        xmltodict = import_module("xmltodict")
    except ImportError as exc:
        msg = (
            "decode_xml requires optional dependency 'xmltodict'. Install with: "
            "pip install kpubdata[xml]"
        )
        raise ImportError(msg) from exc

    try:
        payload: str | bytes = data
        if isinstance(data, bytes):
            # Expat accepts UTF-8/UTF-16 directly but cannot decode all declared
            # multi-byte encodings (such as EUC-KR) on every platform. Decode
            # those with Python's codec registry and remove only the declaration
            # before parsing Unicode text. The response itself is unchanged.
            declared = re.search(
                rb"""^\s*<\?xml\b[^>]{0,180}\bencoding\s*=\s*['"]([A-Za-z0-9._-]{1,40})['"]""",
                data[:256],
                flags=re.IGNORECASE,
            )
            if declared is not None:
                encoding = declared.group(1).decode("ascii")
                if encoding.casefold().replace("_", "-") not in {
                    "utf-8",
                    "utf8",
                    "utf-16",
                    "utf-16le",
                    "utf-16be",
                    "iso-8859-1",
                    "us-ascii",
                }:
                    payload = re.sub(
                        r"^\s*<\?xml[^>]*\?>",
                        "",
                        data.decode(encoding),
                        count=1,
                        flags=re.IGNORECASE,
                    )
        parsed: object = xmltodict.parse(payload)
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "XML parse failed",
            extra={
                "payload_length": len(data),
                "exception_type": type(exc).__name__,
            },
        )
        msg = "Failed to decode XML payload"
        raise ParseError(msg) from exc

    if isinstance(parsed, dict):
        return parsed

    logger.debug(
        "XML payload decoded but root is not a dict",
        extra={"root_type": type(parsed).__name__},
    )
    msg = "XML payload did not decode into a dictionary"
    raise ParseError(msg)


#: A gateway refusal is a few hundred bytes; anything far larger is not one.
_GATEWAY_ENVELOPE_MAX_BYTES = 8192
#: The whole document: an optional declaration, then exactly
#: ``<OpenAPI_ServiceResponse><cmmMsgHeader>`` holding only flat, attribute-free
#: text elements. ``&`` is refused outright, so no entity or character
#: reference is ever expanded, and a DOCTYPE cannot appear anywhere.
#: XML whitespace only: Python's ``\s`` also matches Unicode separators that
#: an XML parser would reject between elements.
_GATEWAY_WS = r"[ \t\r\n]*"
#: Element text: no markup, no reference, and none of the control characters
#: XML 1.0 forbids, so a body ``decode_xml`` would refuse is not read here either.
_GATEWAY_TEXT = r"[^<&\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]"
_GATEWAY_ENVELOPE = re.compile(
    r"\A\ufeff?(?:<\?xml[^<>]{0,200}\?>)?"
    + _GATEWAY_WS
    + r"<OpenAPI_ServiceResponse>"
    + _GATEWAY_WS
    + r"<cmmMsgHeader>"
    + _GATEWAY_WS
    + r"((?:<([A-Za-z_]{1,40})>"
    + _GATEWAY_TEXT
    + r"{0,2048}</\2>"
    + _GATEWAY_WS
    + r"|<[A-Za-z_]{1,40}[ \t\r\n]?/>"
    + _GATEWAY_WS
    + r")*)</cmmMsgHeader>"
    + _GATEWAY_WS
    + r"</OpenAPI_ServiceResponse>"
    + _GATEWAY_WS
    + r"\Z"
)
_GATEWAY_FIELD = re.compile(
    r"<([A-Za-z_]{1,40})>(" + _GATEWAY_TEXT + r"*)</\1>|<([A-Za-z_]{1,40})[ \t\r\n]?/>"
)


def decode_gateway_envelope(data: bytes) -> dict[str, object] | None:
    """Read a data.go.kr gateway refusal without ``xmltodict``; ``None`` for anything else.

    The gateway answers a rejected key with ``OpenAPI_ServiceResponse/cmmMsgHeader``
    XML even on JSON endpoints, so on a base install the refusal used to surface as
    "install the xml extra" instead of the auth or quota error it is (#1101). This
    recognises that one envelope with a bounded, anchored regular expression and
    returns the dict ``decode_xml`` would, so the existing gateway mapping reads it.
    """
    if len(data) > _GATEWAY_ENVELOPE_MAX_BYTES:
        return None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    envelope = _GATEWAY_ENVELOPE.match(text)
    if envelope is None:
        return None
    header: dict[str, object] = {}
    for field in _GATEWAY_FIELD.finditer(envelope.group(1)):
        name = field.group(1) or field.group(3)
        if name in header:
            # xmltodict would turn a repeated element into a list; do not guess.
            return None
        # An XML parser normalises line endings to a bare newline.
        value = (field.group(2) or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        header[name] = value or None
    return {"OpenAPI_ServiceResponse": {"cmmMsgHeader": header}}


__all__ = ["decode_json", "decode_xml", "detect_content_type"]
