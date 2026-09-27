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
    key = os.getenv("KPUBDATA_LOCALDATA_API_KEY", "")
    if not key:
        pytest.skip("KPUBDATA_LOCALDATA_API_KEY not set")
    return key


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
    key = os.getenv("KPUBDATA_SEMAS_API_KEY", "")
    if not key:
        pytest.skip("KPUBDATA_SEMAS_API_KEY not set")
    return key


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
    if not any(
        os.getenv(name, "")
        for name in (
            "KPUBDATA_DATAGO_API_KEY",
            "KPUBDATA_BOK_API_KEY",
            "KPUBDATA_KOSIS_API_KEY",
            "KPUBDATA_LOFIN_API_KEY",
            "KPUBDATA_LOCALDATA_API_KEY",
            "KPUBDATA_SEOUL_API_KEY",
            "KPUBDATA_SEMAS_API_KEY",
            "KPUBDATA_SGIS_API_KEY",
        )
    ):
        pytest.skip("No API keys set")
    return Client.from_env()
