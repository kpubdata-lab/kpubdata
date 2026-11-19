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


__all__ = ["decode_json", "decode_xml", "detect_content_type"]
