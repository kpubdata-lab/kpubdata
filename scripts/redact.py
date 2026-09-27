"""Response redaction — ensures sensitive values don't remain in fixtures.

Before record.py saves, replaces the following in the original payload
and parameters:
- The literal API key value (exactly as read from configuration)
- Email addresses
- Korean phone numbers (010-1234-5678, 02-123-4567 and the like)
"""

from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\b(?:0\d{1,2}-\d{3,4}-\d{4}|01\d{8,9})\b")
_REDACTED = "[REDACTED]"


def redact_string(value: str, secrets: tuple[str, ...] = ()) -> str:
    """Substitute sensitive values in string."""
    result = value
    for secret in secrets:
        if secret:
            result = result.replace(secret, _REDACTED)
    result = _EMAIL_RE.sub(_REDACTED, result)
    result = _PHONE_RE.sub(_REDACTED, result)
    return result


def redact_mapping(data: dict[str, object], secrets: tuple[str, ...] = ()) -> dict[str, object]:
    """Recursively traverse mapping and return copy with sanitized string values.

    Entries whose key name is a sensitive parameter (serviceKey etc.) have
    the whole value replaced.
    """
    sensitive_keys = {"servicekey", "service_key", "apikey", "api_key", "key", "token", "secret"}
    redacted: dict[str, object] = {}
    for key, value in data.items():
        if isinstance(value, str):
            if key.strip().lower() in sensitive_keys:
                redacted[key] = _REDACTED
            else:
                redacted[key] = redact_string(value, secrets)
        elif isinstance(value, dict):
            redacted[key] = redact_mapping(value, secrets)
        elif isinstance(value, list):
            redacted[key] = _redact_list(value, secrets)
        else:
            redacted[key] = value
    return redacted


def _redact_list(values: list[object], secrets: tuple[str, ...]) -> list[object]:
    """Recursively clean list contents."""
    result: list[object] = []
    for value in values:
        if isinstance(value, str):
            result.append(redact_string(value, secrets))
        elif isinstance(value, dict):
            result.append(redact_mapping(value, secrets))
        elif isinstance(value, list):
            result.append(_redact_list(value, secrets))
        else:
            result.append(value)
    return result


__all__ = ["redact_mapping", "redact_string"]
