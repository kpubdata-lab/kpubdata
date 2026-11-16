"""Credential-gating checks for opt-in live integration tests (#986)."""

from __future__ import annotations

import pytest

from tests.integration.conftest import _require_provider_key


@pytest.fixture(autouse=True)
def _remove_ambient_test_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep local credentials from leaking into fixture-gating tests."""
    for provider in ("DATAGO", "LOCALDATA", "SEMAS", "NEIS", "FDS", "LOFIN"):
        monkeypatch.delenv(f"KPUBDATA_{provider}_API_KEY", raising=False)
        monkeypatch.delenv(f"{provider}_API_KEY", raising=False)


@pytest.mark.parametrize("provider", ["localdata", "semas"])
def test_datago_key_can_enable_shared_family_fixture(
    monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    """The fixture must not skip when the SDK would use the shared key."""
    monkeypatch.setenv("KPUBDATA_DATAGO_API_KEY", "shared-placeholder")

    assert _require_provider_key(provider, fallback_to="datago") == "shared-placeholder"


@pytest.mark.parametrize("provider", ["localdata", "semas"])
def test_provider_specific_key_wins_over_shared_key(
    monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    """A provider override takes precedence over the shared portal key."""
    monkeypatch.setenv("KPUBDATA_DATAGO_API_KEY", "shared-placeholder")
    monkeypatch.setenv(f"KPUBDATA_{provider.upper()}_API_KEY", "own-placeholder")

    assert _require_provider_key(provider, fallback_to="datago") == "own-placeholder"


def test_legacy_key_name_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    """A legacy environment alias follows the existing SDK fallback order."""
    monkeypatch.setenv("LOCALDATA_API_KEY", "legacy-placeholder")

    assert _require_provider_key("localdata", fallback_to="datago") == "legacy-placeholder"


@pytest.mark.parametrize("provider", ["neis", "fds"])
def test_unrelated_portal_key_does_not_satisfy_provider(
    monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    """NEIS and FDS must never treat the data.go.kr key as their own."""
    monkeypatch.setenv("KPUBDATA_DATAGO_API_KEY", "do-not-send")

    with pytest.raises(pytest.skip.Exception) as captured:
        _require_provider_key(provider)

    message = str(captured.value)
    assert f"KPUBDATA_{provider.upper()}_API_KEY" in message
    assert "do-not-send" not in message


def test_missing_shared_key_skips_without_disclosing_a_value() -> None:
    """Missing credentials do not count as a successful real-provider test."""
    with pytest.raises(pytest.skip.Exception) as captured:
        _require_provider_key("localdata", fallback_to="datago")

    message = str(captured.value)
    assert "KPUBDATA_LOCALDATA_API_KEY" in message
    assert "KPUBDATA_DATAGO_API_KEY" in message


def test_lofin_live_fixture_accepts_legacy_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """A runtime-supported LOFIN credential must not silently skip live checks."""
    from tests.integration.conftest import require_lofin_key

    monkeypatch.setenv("LOFIN_API_KEY", "lofin-placeholder")
    monkeypatch.setenv("KPUBDATA_DATAGO_API_KEY", "unrelated-placeholder")

    try:
        key = require_lofin_key.__wrapped__()
    except pytest.skip.Exception as exc:
        pytest.fail(f"Runtime-supported key incorrectly skipped: {exc}")
    assert key == "lofin-placeholder"
