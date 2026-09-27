"""File-based cache storing response bodies on disk with TTL expiration."""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import logging
import os
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path
from typing import TypedDict, cast

from kpubdata.transport._sensitive import SENSITIVE_PARAM_KEYS

logger = logging.getLogger("kpubdata.transport")


class _CachePayload(TypedDict, total=False):
    """Serialized payload structure stored in cache files.

    Args:
        created_at: Unix timestamp when payload was created.
        ttl_seconds: Time-to-live in seconds.
        body_b64: Base64-encoded response body.
        content_type: Content-Type header at storage time. Previous versions
            stored only the body, so cache hits re-inferred the type and JSON
            could decode XML responses — the same request yielded different
            results depending on cache state.
    """

    created_at: float
    ttl_seconds: float
    body_b64: str
    content_type: str


_REDACTED_VALUE = "[REDACTED]"


class ResponseCache:
    """HTTP response body cache on disk with TTL expiration."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        """Initialize the default response cache directory."""
        self._base_dir: Path = Path(base_dir) if base_dir is not None else _default_cache_dir()

    @property
    def base_dir(self) -> Path:
        """Return the base directory where cache files are stored."""
        return self._base_dir

    def get(self, key: str) -> tuple[bytes, str] | None:
        """Read cache entry and return ``(body, content_type)`` if valid.

        Returning content_type together is essential. Without it, cache hits
        would re-infer the type and JSON could decode XML responses, so the
        same request could yield different results depending on cache state.
        Old entries without stored type return empty string to preserve backward
        compatibility (caller re-infers as before).
        """
        payload_path = self._payload_path(key)
        try:
            if not payload_path.exists():
                return None
            payload = _load_payload(payload_path)
            if payload is None:
                self._delete_entry(key)
                return None
            if _is_expired(payload):
                self._delete_entry(key)
                return None
            body_b64 = payload.get("body_b64")
            if body_b64 is None:
                self._delete_entry(key)
                return None
            stored_type = payload.get("content_type")
            return (
                base64.b64decode(body_b64.encode("ascii")),
                stored_type if isinstance(stored_type, str) else "",
            )
        except Exception as exc:
            logger.debug(
                "transport cache read failed",
                extra={
                    "cache_key": key,
                    "path": str(payload_path),
                    "exception_type": type(exc).__name__,
                },
            )
            return None

    def set(self, key: str, value: bytes, ttl_seconds: int, content_type: str = "") -> None:
        """Cache response bytes, TTL, and Content-Type to a file."""
        payload_path = self._payload_path(key)
        try:
            payload_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "created_at": time.time(),
                "ttl_seconds": ttl_seconds,
                "body_b64": base64.b64encode(value).decode("ascii"),
                "content_type": content_type,
            }
            # Write to temp file then replace. Direct write can leave
            # incomplete files that are read as valid cache entries, and that
            # broken value persists until expiration.
            fd, tmp_name = tempfile.mkstemp(dir=payload_path.parent, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(json.dumps(payload, separators=(",", ":")))
                os.replace(tmp_name, payload_path)
            except BaseException:
                with contextlib.suppress(OSError):
                    os.unlink(tmp_name)
                raise
        except Exception as exc:
            logger.debug(
                "transport cache write failed",
                extra={
                    "cache_key": key,
                    "path": str(payload_path),
                    "exception_type": type(exc).__name__,
                },
            )

    def clear(self) -> None:
        """Delete all stored cache entries."""
        try:
            if not self._base_dir.exists():
                return
            for payload_path in self._base_dir.glob("*.json"):
                payload_path.unlink(missing_ok=True)
        except Exception as exc:
            logger.debug(
                "transport cache clear failed",
                extra={"path": str(self._base_dir), "exception_type": type(exc).__name__},
            )

    def clear_expired(self) -> None:
        """Find and delete expired cache entries only."""
        try:
            if not self._base_dir.exists():
                return
            for payload_path in self._base_dir.glob("*.json"):
                try:
                    payload = _load_payload(payload_path)
                    if payload is None or _is_expired(payload):
                        payload_path.unlink(missing_ok=True)
                except Exception as exc:
                    logger.debug(
                        "transport cache cleanup entry failed",
                        extra={
                            "path": str(payload_path),
                            "exception_type": type(exc).__name__,
                        },
                    )
        except Exception as exc:
            logger.debug(
                "transport cache cleanup failed",
                extra={"path": str(self._base_dir), "exception_type": type(exc).__name__},
            )

    def _payload_path(self, key: str) -> Path:
        """Return the JSON file path for a cache key."""
        return self._base_dir / f"{key}.json"

    def _delete_entry(self, key: str) -> None:
        """Silently delete a cache file."""
        try:
            self._payload_path(key).unlink(missing_ok=True)
        except Exception as exc:
            logger.debug(
                "transport cache delete failed",
                extra={
                    "cache_key": key,
                    "path": str(self._payload_path(key)),
                    "exception_type": type(exc).__name__,
                },
            )


def make_cache_key(
    method: str,
    url: str,
    params: Mapping[str, object] | None,
    headers_subset: Mapping[str, object] | None,
) -> str:
    """Build a stable cache key from method, URL, params, and headers."""
    normalized_payload = {
        "method": method.upper(),
        "url": url,
        "params": _normalize_mapping(params),
        "headers": _normalize_mapping(headers_subset),
    }
    digest = hashlib.sha256(
        json.dumps(normalized_payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return digest[:32]


def _default_cache_dir() -> Path:
    """Determine the default cache path from env vars and home directory."""
    xdg_cache_home = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache_home:
        return Path(xdg_cache_home) / "kpubdata" / "responses"
    return Path.home() / ".cache" / "kpubdata" / "responses"


def _normalize_mapping(values: Mapping[str, object] | None) -> list[tuple[str, str]]:
    """Normalize mapping into sortable key-value list with fingerprinted credentials.

    Sensitive values (credentials) use sha256 fingerprints instead of plaintext
    (#263) — no plaintext appears in cache keys and caches are isolated per
    credential. If all keys used a constant, different credentials would share
    cache entries, polluting with responses from previous users.
    """
    if values is None:
        return []

    normalized_items: list[tuple[str, str]] = []
    for key, value in values.items():
        text = str(value)
        if key.casefold() in SENSITIVE_PARAM_KEYS:
            normalized_value = _credential_fingerprint(text)
        else:
            normalized_value = text
        normalized_items.append((key.casefold(), normalized_value))
    normalized_items.sort()
    return normalized_items


def _credential_fingerprint(value: str) -> str:
    """Return a one-way fingerprint for credentials in cache keys (#263)."""
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"{_REDACTED_VALUE}:sha256:{digest[:16]}"


def _is_expired(payload: _CachePayload) -> bool:
    """Check if cache payload is expired or malformed."""
    created_at = payload.get("created_at")
    ttl_seconds = payload.get("ttl_seconds")
    if not isinstance(created_at, int | float) or not isinstance(ttl_seconds, int | float):
        return True
    if ttl_seconds < 0:
        return True
    return time.time() >= created_at + ttl_seconds


def _load_payload(payload_path: Path) -> _CachePayload | None:
    """Read and validate a cache JSON file as a payload dict."""
    raw_payload = cast(object, json.loads(payload_path.read_text(encoding="utf-8")))
    if not isinstance(raw_payload, dict):
        return None
    payload = cast(_CachePayload, cast(object, raw_payload))
    body_b64 = payload.get("body_b64")
    created_at = payload.get("created_at")
    ttl_seconds = payload.get("ttl_seconds")
    if not isinstance(body_b64, str):
        return None
    if not isinstance(created_at, int | float) or not isinstance(ttl_seconds, int | float):
        return None
    return payload


__all__ = ["ResponseCache", "make_cache_key"]
