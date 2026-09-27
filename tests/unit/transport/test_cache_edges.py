"""``ResponseCache`` edge case regression tests (#454).

Cache is a layer where bugs go silent — even with wrong key or TTL returning stale/other responses
the caller looks normal. Here we focus not on normal round-trips but on **what cache must NOT return
from**(expiration, corruption, format mismatch)and **what keys must distinguish**are pinned.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from kpubdata.transport.cache import ResponseCache, make_cache_key


def _write_raw(cache: ResponseCache, key: str, payload: object) -> Path:
    """Bypass validation to write cache file directly (for simulating corrupted entries)."""
    path = cache.base_dir / f"{key}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _entry(
    *, body: bytes = b"cached", created_at: float = 1_000.0, ttl: float = 60.0
) -> dict[str, object]:
    return {
        "created_at": created_at,
        "ttl_seconds": ttl,
        "body_b64": base64.b64encode(body).decode("ascii"),
    }


# --- TTL boundary --------------------------------------------------------------


def test_entry_is_served_before_its_ttl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache = ResponseCache(base_dir=tmp_path)
    _ = _write_raw(cache, "k", _entry(created_at=1_000.0, ttl=60.0))

    monkeypatch.setattr("kpubdata.transport.cache.time.time", lambda: 1_059.0)
    assert cache.get("k") == (b"cached", "")


def test_entry_expires_exactly_at_its_ttl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Boundary is closed — at created_at + ttl is already expired."""
    cache = ResponseCache(base_dir=tmp_path)
    path = _write_raw(cache, "k", _entry(created_at=1_000.0, ttl=60.0))

    monkeypatch.setattr("kpubdata.transport.cache.time.time", lambda: 1_060.0)
    assert cache.get("k") is None
    # Expired entries are deleted on read — not left on disk.
    assert not path.exists()


def test_zero_ttl_entry_is_never_served(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache = ResponseCache(base_dir=tmp_path)
    cache.set("k", b"cached", ttl_seconds=0)
    assert cache.get("k") is None


def test_negative_ttl_entry_is_never_served(tmp_path: Path) -> None:
    """Negative TTL is NOT 'infinite validity' but immediate expiration."""
    cache = ResponseCache(base_dir=tmp_path)
    _ = _write_raw(cache, "k", _entry(ttl=-1.0))
    assert cache.get("k") is None


# --- Corrupted entries ---------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "payload"),
    [
        ("not-a-mapping", ["created_at", 1.0]),
        ("missing-body", {"created_at": 1.0, "ttl_seconds": 60.0}),
        ("body-not-a-string", {"created_at": 1.0, "ttl_seconds": 60.0, "body_b64": 12}),
        ("created-at-not-a-number", {"created_at": "now", "ttl_seconds": 60.0, "body_b64": "eA=="}),
        ("ttl-not-a-number", {"created_at": 1.0, "ttl_seconds": "forever", "body_b64": "eA=="}),
    ],
)
def test_malformed_entry_is_dropped_not_served(tmp_path: Path, name: str, payload: object) -> None:
    """Malformed entries treated as miss without Raises, file deleted."""
    cache = ResponseCache(base_dir=tmp_path)
    path = _write_raw(cache, name, payload)

    assert cache.get(name) is None
    assert not path.exists()


def test_unparsable_json_entry_is_a_miss(tmp_path: Path) -> None:
    cache = ResponseCache(base_dir=tmp_path)
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")

    assert cache.get("broken") is None


def test_non_base64_body_is_a_miss(tmp_path: Path) -> None:
    """If body_b64 is not base64, swallow decode Raises return miss."""
    cache = ResponseCache(base_dir=tmp_path)
    _ = _write_raw(
        cache, "k", {"created_at": 1.0, "ttl_seconds": 10**9, "body_b64": "!!!not-base64!!!"}
    )
    assert cache.get("k") is None


# --- clear / clear_expired -------------------------------------------------


def test_clear_removes_every_entry(tmp_path: Path) -> None:
    cache = ResponseCache(base_dir=tmp_path)
    cache.set("a", b"1", ttl_seconds=600)
    cache.set("b", b"2", ttl_seconds=600)

    cache.clear()

    assert cache.get("a") is None
    assert cache.get("b") is None
    assert list(tmp_path.glob("*.json")) == []


def test_clear_on_a_missing_directory_is_a_noop(tmp_path: Path) -> None:
    cache = ResponseCache(base_dir=tmp_path / "never-created")
    cache.clear()
    cache.clear_expired()


def test_clear_expired_keeps_live_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Only delete expired — Deleting valid entries makes cache useless."""
    cache = ResponseCache(base_dir=tmp_path)
    _ = _write_raw(cache, "stale", _entry(body=b"old", created_at=0.0, ttl=1.0))
    _ = _write_raw(cache, "fresh", _entry(body=b"new", created_at=0.0, ttl=10**9))

    monkeypatch.setattr("kpubdata.transport.cache.time.time", lambda: 1_000.0)
    cache.clear_expired()

    assert cache.get("stale") is None
    assert cache.get("fresh") == (b"new", "")


def test_clear_expired_drops_malformed_entries(tmp_path: Path) -> None:
    """Undecidable entries are also cleanup targets — to not remain forever eating disk."""
    cache = ResponseCache(base_dir=tmp_path)
    path = _write_raw(cache, "junk", {"nothing": "useful"})

    cache.clear_expired()

    assert not path.exists()


def test_clear_expired_ignores_unrelated_files(tmp_path: Path) -> None:
    cache = ResponseCache(base_dir=tmp_path)
    stray = tmp_path / "README.txt"
    stray.write_text("not a cache entry", encoding="utf-8")

    cache.clear()
    cache.clear_expired()

    assert stray.exists()


# --- Cache key ---------------------------------------------------------------


def test_key_is_stable_across_parameter_order() -> None:
    """dict order must not affect key — same request must be same entry."""
    first = make_cache_key("GET", "https://x.test/r", {"a": "1", "b": "2"}, None)
    second = make_cache_key("GET", "https://x.test/r", {"b": "2", "a": "1"}, None)
    assert first == second


def test_key_ignores_method_and_parameter_name_casing() -> None:
    assert make_cache_key("get", "https://x.test/r", {"Page": "1"}, None) == make_cache_key(
        "GET", "https://x.test/r", {"page": "1"}, None
    )


def test_key_separates_different_urls_methods_and_values() -> None:
    base = make_cache_key("GET", "https://x.test/r", {"page": "1"}, None)
    assert base != make_cache_key("GET", "https://x.test/other", {"page": "1"}, None)
    assert base != make_cache_key("POST", "https://x.test/r", {"page": "1"}, None)
    assert base != make_cache_key("GET", "https://x.test/r", {"page": "2"}, None)


def test_key_treats_absent_and_empty_parameters_as_one_request() -> None:
    """None and {} are same request — do not split into different entries halving cache."""
    assert make_cache_key("GET", "https://x.test/r", None, None) == make_cache_key(
        "GET", "https://x.test/r", {}, None
    )


def test_key_never_contains_the_credential(tmp_path: Path) -> None:
    """key becomes filename — raw credential must not remain in disk path (#263)."""
    secret = "super-secret-service-key"
    key = make_cache_key("GET", "https://x.test/r", {"serviceKey": secret}, None)
    assert secret not in key
    assert len(key) == 32


def test_key_isolates_header_credentials() -> None:
    """Different Authorization header = different entry even for same URL."""
    first = make_cache_key("GET", "https://x.test/r", None, {"Authorization": "Bearer a"})
    second = make_cache_key("GET", "https://x.test/r", None, {"Authorization": "Bearer b"})
    assert first != second


def test_key_handles_non_string_parameter_values() -> None:
    """Numeric/boolean params normalized to string, key generated without Raises."""
    key = make_cache_key("GET", "https://x.test/r", {"page": 1, "all": True}, None)
    assert len(key) == 32
    assert key == make_cache_key("GET", "https://x.test/r", {"page": "1", "all": "True"}, None)


# --- Failure-swallowing path ----------------------------------------------------
#
# Cache is auxiliary layer — If disk misbehaves caller must not die.
# tests below are "do not expose Raises outward"are pinned.


def test_set_failure_does_not_raise(tmp_path: Path) -> None:
    """If base_dir is file, mkdir fails — must fail silently."""
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")
    cache = ResponseCache(base_dir=blocked)

    cache.set("k", b"payload", ttl_seconds=60)

    assert cache.get("k") is None


def test_clear_failure_does_not_raise(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache = ResponseCache(base_dir=tmp_path)
    cache.set("k", b"payload", ttl_seconds=60)

    def exploding_glob(self: Path, pattern: str) -> object:
        raise OSError("glob failed")

    monkeypatch.setattr(Path, "glob", exploding_glob)

    cache.clear()
    cache.clear_expired()


def test_clear_expired_survives_one_unreadable_entry(tmp_path: Path) -> None:
    """Cleanup must continue for remaining entries even if one cannot be read."""
    cache = ResponseCache(base_dir=tmp_path)
    # If directory named .json, read_text raises IsADirectoryError.
    (tmp_path / "unreadable.json").mkdir()
    stale = _write_raw(cache, "stale", _entry(created_at=0.0, ttl=1.0))

    cache.clear_expired()

    assert (tmp_path / "unreadable.json").exists()
    # Check if expired entry disappeared from disk. ``cache.get`` cleanup is mid-operation
    # even if stopped, by real clock already expired returns None, proves nothing.
    assert not stale.exists()


def test_delete_failure_still_reports_a_miss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """even if cannot delete expired entry, still does not return value."""
    cache = ResponseCache(base_dir=tmp_path)
    _ = _write_raw(cache, "k", _entry(created_at=0.0, ttl=1.0))

    def exploding_unlink(self: Path, missing_ok: bool = False) -> None:
        raise OSError("unlink failed")

    monkeypatch.setattr(Path, "unlink", exploding_unlink)

    assert cache.get("k") is None


# --- default cache directory ----------------------------------------------------


def test_default_dir_follows_xdg_cache_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", "/tmp/xdg-probe")
    assert ResponseCache().base_dir == Path("/tmp/xdg-probe/kpubdata/responses")


def test_default_dir_falls_back_to_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/home/probe")))
    assert ResponseCache().base_dir == Path("/home/probe/.cache/kpubdata/responses")


def test_empty_xdg_cache_home_falls_back_to_home(monkeypatch: pytest.MonkeyPatch) -> None:
    """empty string must be treated like 'not configured' — do not create cache at root."""
    monkeypatch.setenv("XDG_CACHE_HOME", "")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/home/probe")))
    assert ResponseCache().base_dir == Path("/home/probe/.cache/kpubdata/responses")


def test_a_cache_entry_is_written_atomically(tmp_path: Path) -> None:
    """partially written file read as complete entry yields broken value until expiration."""
    import os

    from kpubdata.transport.cache import ResponseCache

    cache = ResponseCache(tmp_path)
    seen: list[tuple[str, str]] = []
    real_replace = os.replace

    def _record(src: object, dst: object) -> None:
        seen.append((str(src), str(dst)))
        real_replace(src, dst)  # type: ignore[arg-type]

    with patch("kpubdata.transport.cache.os.replace", _record):
        cache.set("k", b"body", ttl_seconds=60)

    assert seen and seen[0][0].endswith(".tmp")
    assert cache.get("k") == (b"body", "")
