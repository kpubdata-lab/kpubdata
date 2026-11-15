"""Test module for conftest configuration.

Defines test scenarios and helper functions in ``tests/integration/conftest.py``.
Verifies core flows, exceptions, and edge cases to prevent regressions and validate
the public contract.
"""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest

from kpubdata.client import Client
from kpubdata.config import KPubDataConfig
from kpubdata.exceptions import ConfigError


def _require_provider_key(provider: str, *, fallback_to: str | None = None) -> str:
    """Use the SDK's actual credential lookup rules for live-test prerequisites.

    Having a key is not proof that a specific upstream service has approved it.
    """
    try:
        return KPubDataConfig().require_provider_key(provider, fallback_to=fallback_to)
    except ConfigError:
        names = [f"KPUBDATA_{provider.upper()}_API_KEY"]
        if fallback_to is not None:
            names.append(f"KPUBDATA_{fallback_to.upper()}_API_KEY")
        pytest.skip(f"No credential for {provider}: set {' or '.join(names)}")


@pytest.fixture(scope="session")
def require_datago_key() -> str:
    """
    Require data.go.kr API key fixture.

    Returns:
        str: API key from environment or raises skip if not set.

    Raises:
        pytest.skip: If KPUBDATA_DATAGO_API_KEY is not set.
    """
    key = os.getenv("KPUBDATA_DATAGO_API_KEY", "")
    if not key:
        pytest.skip("KPUBDATA_DATAGO_API_KEY not set")
    return key


@pytest.fixture
def require_realestate_key() -> Generator[None, None, None]:
    """
    Require real-estate scope approval on API key fixture.

    Returns:
        Generator[None, None, None]: Yields after checking approval flag.

    Raises:
        pytest.skip: If KPUBDATA_DATAGO_REALESTATE_ENABLED is not "1".
    """
    if os.environ.get("KPUBDATA_DATAGO_REALESTATE_ENABLED") != "1":
        pytest.skip(
            "Set KPUBDATA_DATAGO_REALESTATE_ENABLED=1 once "
            + "국토부 RTMS APIs have been 활용신청 approved on this key"
        )
    yield


@pytest.fixture(scope="session")
def require_bok_key() -> str:
    """
    Require Bank of Korea API key fixture.

    Returns:
        str: API key from environment or raises skip if not set.

    Raises:
        pytest.skip: If KPUBDATA_BOK_API_KEY is not set.
    """
    key = os.getenv("KPUBDATA_BOK_API_KEY", "")
    if not key:
        pytest.skip("KPUBDATA_BOK_API_KEY not set")
    return key


@pytest.fixture(scope="session")
def require_kosis_key() -> str:
    """
    Require KOSIS (Korean Statistical Information System) API key fixture.

    Returns:
        str: API key from environment or raises skip if not set.

    Raises:
        pytest.skip: If KPUBDATA_KOSIS_API_KEY is not set.
    """
    key = os.getenv("KPUBDATA_KOSIS_API_KEY", "")
    if not key:
        pytest.skip("KPUBDATA_KOSIS_API_KEY not set")
    return key


@pytest.fixture(scope="session")
def require_lofin_key() -> str:
    """
    Require LOFIN (Local Finance 365) API key fixture.

    Returns:
        str: API key from environment or raises skip if not set.

    Raises:
        pytest.skip: If KPUBDATA_LOFIN_API_KEY is not set.
    """
    key = os.getenv("KPUBDATA_LOFIN_API_KEY", "")
    if not key:
        pytest.skip("KPUBDATA_LOFIN_API_KEY not set")
    return key


@pytest.fixture(scope="session")
def require_localdata_key() -> str:
    """
    Require LocalData API key fixture.

    Returns:
        str: API key from environment or raises skip if not set.

    Raises:
        pytest.skip: If KPUBDATA_LOCALDATA_API_KEY is not set.
    """
    return _require_provider_key("localdata", fallback_to="datago")


@pytest.fixture(scope="session")
def require_seoul_key() -> str:
    """
    Require Seoul Open Data API key fixture.

    Returns:
        str: API key from environment or raises skip if not set.

    Raises:
        pytest.skip: If KPUBDATA_SEOUL_API_KEY is not set.
    """
    key = os.getenv("KPUBDATA_SEOUL_API_KEY", "")
    if not key:
        pytest.skip("KPUBDATA_SEOUL_API_KEY not set")
    return key


@pytest.fixture(scope="session")
def require_semas_key() -> str:
    """
    Require SEMAS API key fixture.

    Returns:
        str: API key from environment or raises skip if not set.

    Raises:
        pytest.skip: If KPUBDATA_SEMAS_API_KEY is not set.
    """
    return _require_provider_key("semas", fallback_to="datago")


@pytest.fixture(scope="session")
def require_sgis_key() -> str:
    """
    Require SGIS (Spatial Information Platform) API key fixture.

    Returns:
        str: API key from environment or raises skip if not set.

    Raises:
        pytest.skip: If KPUBDATA_SGIS_API_KEY is not set.
    """
    key = os.getenv("KPUBDATA_SGIS_API_KEY", "")
    if not key:
        pytest.skip("KPUBDATA_SGIS_API_KEY not set")
    return key


@pytest.fixture(scope="session")
def live_client() -> Client:
    """
    Create a live Client fixture for integration tests.

    Returns:
        Client: Initialized client using environment variables.

    Raises:
        pytest.skip: If no API keys are set.
    """
    config = KPubDataConfig()
    if not any(
        config.get_provider_key(provider)
        for provider in (
            "datago", "bok", "kosis", "lofin", "localdata", "seoul",
            "semas", "sgis", "neis", "fds", "law", "kipris", "korean",
        )
    ):
        pytest.skip("No provider credentials configured")
    return Client.from_env()
