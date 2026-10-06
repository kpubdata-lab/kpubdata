"""Tell whether a response that arrived as HTTP 200 is really a refusal.

Many Korean public APIs report failure in the body envelope rather than in the
HTTP status -- quota exceeded (``22``), unregistered key (``30``) and gateway
refusals all arrive as 200. The transport used to cache on the status code
alone, so a momentary quota overrun froze into a 24-hour outage. That cache
propagated into builder's Bronze fetch as well, which meant a scheduled build
could publish empty data as a "success".

**The check is deliberately conservative.** The transport does not know the
spec, so it can see neither ``code_path`` nor ``ok_values``; all it does here is
look for widely used envelope shapes at fixed positions. When no code is visible,
or the body does not parse, the answer is "unknown" and the response is cached
as before.

The asymmetry is why it leans that way: a false positive costs one extra cache
miss, while a false negative reuses a wrong response for a day.

XML is matched with a regular expression over the tags. Parsing it would require
the optional extra (``kpubdata[xml]``), and deciding whether to cache cannot be
made to depend on that.
"""

from __future__ import annotations

import json
import re

#: Codes read as success. Same vocabulary as the executor's check
#: (``ok_values``, or the integer 0).
_SUCCESS_CODES = frozenset({"00", "000", "0"})

#: Envelope code paths at fixed positions. The first one found wins.
_JSON_CODE_PATHS: tuple[tuple[str, ...], ...] = (
    # The gateway answered instead of the service (unregistered key, quota, ...)
    ("OpenAPI_ServiceResponse", "cmmMsgHeader", "returnReasonCode"),
    # The standard data.go.kr service envelope
    ("response", "header", "resultCode"),
    # KorService-style APIs (Korea Tourism Organization): top level, outside
    # any envelope
    ("resultCode",),
)

_XML_CODE_TAGS = ("returnReasonCode", "resultCode")
_XML_CODE_PATTERN = re.compile(
    rb"<(?:\w+:)?(" + b"|".join(t.encode() for t in _XML_CODE_TAGS) + rb")>([^<]{0,32})</",
    re.IGNORECASE,
)


def _is_failure_code(code: str) -> bool:
    code = code.strip()
    if not code:
        return False
    if code in _SUCCESS_CODES:
        return False
    try:
        return int(code) != 0
    except ValueError:
        # A non-numeric code is not judged -- it is vocabulary we do not know.
        return False


def _json_code(body: bytes) -> str | None:
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    for path in _JSON_CODE_PATHS:
        node: object = payload
        for key in path:
            if not isinstance(node, dict):
                node = None
                break
            node = node.get(key)
        if isinstance(node, str | int) and not isinstance(node, bool):
            return str(node)
    return None


# --- The ``RESULT`` / ``CODE`` family (#838) ---
#
# Seoul Open Data, BOK ECOS, NEIS and LOFIN answer with ``RESULT: {CODE, MESSAGE}`` and
# codes that are words, not numbers: ``INFO-000`` is success, ``INFO-200`` is "no data"
# — an ordinary empty answer — and the rest of the list below are refusals. The numeric
# check above could not read any of them, so an invalid-key or server-error answer was
# cached like a success.
#
# Only codes these providers' own adapters treat as errors are listed (seoul/envelope.py,
# bok, neis and lofin adapters). A code outside the list is still not judged.

#: A refusal by name: the key is invalid, restricted, or the request or server failed.
_RESULT_FAILURE_CODES = frozenset({"INFO-100", "INFO-300", "INFO-400", "INFO-500", "ERROR"})
#: ``ERROR-290``, ``ERROR-300``, ``ERROR-500`` …: every numbered error of the family.
_RESULT_ERROR_PATTERN = re.compile(r"ERROR-\d{1,4}")

_XML_RESULT_PATTERN = re.compile(rb"<RESULT>\s*<CODE>([^<]{0,32})</CODE>", re.IGNORECASE)


def _is_result_failure(code: str) -> bool:
    code = code.strip().upper()
    return code in _RESULT_FAILURE_CODES or _RESULT_ERROR_PATTERN.fullmatch(code) is not None


def _code_of_result(result: object) -> str | None:
    """``CODE`` of one ``RESULT`` value: a mapping, or a list holding one (LOFIN)."""
    if isinstance(result, list) and result:
        result = result[0]
    if not isinstance(result, dict):
        return None
    # Seoul's top-level form names the field ``RESULT.CODE``.
    code = result.get("CODE", result.get("RESULT.CODE"))
    return code if isinstance(code, str) else None


def _json_result_code(body: bytes) -> str | None:
    """The family's code at the two places an error answer carries it: a top-level
    ``RESULT``, or the ``RESULT`` of the one service object (Seoul)."""
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    code = _code_of_result(payload.get("RESULT"))
    if code is not None:
        return code
    for value in payload.values():
        if isinstance(value, dict):
            code = _code_of_result(value.get("RESULT"))
            if code is not None:
                return code
    return None


def is_upstream_error_envelope(body: bytes, content_type: str) -> bool:
    """Whether this 200 response is really a refusal. True only when certain."""
    kind = content_type.split(";", 1)[0].strip().casefold()
    if "json" in kind:
        code = _json_code(body)
        if code is not None:
            return _is_failure_code(code)
        result_code = _json_result_code(body)
        return result_code is not None and _is_result_failure(result_code)
    if "xml" in kind:
        match = _XML_CODE_PATTERN.search(body)
        if match is not None:
            return _is_failure_code(match.group(2).decode("ascii", "ignore"))
        result = _XML_RESULT_PATTERN.search(body)
        return result is not None and _is_result_failure(result.group(1).decode("ascii", "ignore"))
    return False


__all__ = ["is_upstream_error_envelope"]
