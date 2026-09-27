"""Unit test module.

tests/unit/test_config_coverage.py`` Defines test scenarios and helper objects.
Verifies core flows, exceptions, and edge conditions for regression prevention and public contract validation.
"""

from __future__ import annotations

import os
from unittest.mock import patch

from kpubdata.config import KPubDataConfig


# test from env skips empty values Describes scenario being tested.
def test_from_env_skips_empty_values() -> None:
    """
    test from env skips empty values Verifies scenario.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    env = {
        "KPUBDATA_DATAGO_API_KEY": "datago-key",
        "KPUBDATA_EMPTY_API_KEY": "",
    }
    with patch.dict(os.environ, env, clear=False):
        config = KPubDataConfig.from_env()

    assert config.provider_keys["datago"] == "datago-key"
    assert "empty" not in config.provider_keys


# test from env provider overrides require string pairs and non empty values Describes scenario being tested.
def test_from_env_provider_overrides_require_string_pairs_and_non_empty_values() -> None:
    """
    test from env provider overrides require string pairs and non empty values Verifies scenario.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    env = {"KPUBDATA_DATAGO_API_KEY": "scanned-key"}
    overrides: dict[object, object] = {
        "Data-Go": "override-key",
        "blank": "",
        "nonstr": 123,
        999: "value",
    }
    with patch.dict(os.environ, env, clear=False):
        config = KPubDataConfig.from_env(provider_keys=overrides)

    assert config.provider_keys["data-go"] == "override-key"
    assert "blank" not in config.provider_keys
    assert "nonstr" not in config.provider_keys
    assert "999" not in config.provider_keys


# test get provider key uses case insensitive explicit fallback Describes scenario being tested.
def test_get_provider_key_uses_case_insensitive_explicit_fallback() -> None:
    """
    test get provider key uses case insensitive explicit fallback Verifies scenario.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    config = KPubDataConfig(provider_keys={"DaTaGo": "explicit-key"})

    assert config.get_provider_key("datago") == "explicit-key"
