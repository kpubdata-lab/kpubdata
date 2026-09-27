"""Replay transport: serve recorded fixtures instead of calling the live API.

``HttpTransport.request`` delegates here when ``KPUBDATA_MODE=replay`` is set.

Interception is deliberately narrow. A request is matched only when its
``dataset_id`` and URL appear in the fixture index as a (dataset, endpoint)
pair. Everything else returns ``None`` and falls through to the live path --
intercepting globally would break unrelated transport unit tests.

- Fixture root: ``KPUBDATA_REPLAY_DIR`` (default: ``./tests/fixtures``)
- Match key: the endpoint plus every parameter except the authentication ones
- A registered pair whose parameters do not match fails with a "make record"
  hint. No invented responses -- deterministic verification only.
- Development and CI only. An installed environment has no fixtures, so leaving
  the variable unset is the default.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

from kpubdata.exceptions import InvalidRequestError
from kpubdata.transport._sensitive import SENSITIVE_PARAM_KEYS

_DEFAULT_ROOT = Path("tests") / "fixtures"
# Authentication parameters differ per environment, so they stay out of the match
# key. _sensitive holds the canonical list of their names.

_IndexEntry = tuple[str, str, str, Path]


def _iter_index(root: Path) -> list[_IndexEntry]:
    """Walk the fixture index as ``(dataset_id, example, endpoint, meta path)``."""
    index: list[_IndexEntry] = []
    for meta_path in sorted(root.rglob("*.meta.json")):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        index.append(
            (
                str(meta.get("dataset_id", "?")),
                str(meta.get("example", "?")),
                str(meta.get("endpoint", "")),
                meta_path,
            )
        )
    return index


def _signature(params: dict[str, str] | None) -> dict[str, str]:
    """Build a lowercase key signature with the sensitive parameters removed."""
    return {
        key.lower(): value
        for key, value in (params or {}).items()
        if key.lower() not in SENSITIVE_PARAM_KEYS
    }


def replay_response(
    method: str,
    url: str,
    *,
    params: dict[str, str] | None = None,
    dataset_id: str | None = None,
    provider: str | None = None,
) -> httpx.Response | None:
    """Serve a recorded response for a registered (dataset, endpoint) request.

    Returns:
        The recorded response on a match, or None when this request is not ours
        to intercept, in which case the caller falls through to the live API.

    Raises:
        InvalidRequestError: The pair is registered but no recording matches the
            parameters.
    """
    root = Path(os.environ.get("KPUBDATA_REPLAY_DIR", str(_DEFAULT_ROOT)))
    index = _iter_index(root) if root.is_dir() else []

    if dataset_id is None or (dataset_id, url) not in {
        (dataset, endpoint) for dataset, _, endpoint, _ in index
    }:
        return None

    signature = _signature(params)
    candidates: list[tuple[str, str, Path]] = []
    for dataset, example, endpoint, meta_path in index:
        if endpoint != url:
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta_params = _signature(
            {str(key): str(value) for key, value in dict(meta.get("params", {})).items()}
        )
        if meta_params == signature:
            raw_path = meta_path.with_name(meta_path.name.replace(".meta.json", ".raw.json"))
            if raw_path.is_file():
                candidates.append((dataset, example, raw_path))

    if not candidates:
        available = sorted({f"{did}.{ex}" for did, ex, _, _ in index})
        hint = f" — Available: {', '.join(available[:10])}" if available else ""
        msg = (
            f"replay match failed: {dataset_id} ({method} {url}, params={signature}). "
            f"Use `make record DATASET=...` to record fixture first{hint}"
        )
        raise InvalidRequestError(msg, provider=provider, dataset_id=dataset_id)

    dataset, example, raw_path = candidates[0]
    payload_text = raw_path.read_text(encoding="utf-8")
    response = httpx.Response(
        status_code=200,
        content=payload_text.encode("utf-8"),
        headers={"content-type": "application/json"},
        request=httpx.Request(method, url),
    )
    response.extensions["kpubdata_replay"] = {"dataset_id": dataset, "example": example}
    return response


__all__ = ["replay_response"]
