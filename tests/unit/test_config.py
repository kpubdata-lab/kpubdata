"""Tests for config management."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.exceptions import ConfigError


class TestKPubDataConfig:
    """
    TestKPubDataConfig Class encapsulating related operations.

    This class in ``tests/unit/test_config.py`` module manages TestKPubDataConfigstate and behavior.
    Key methods: test_explicit_key, test_missing_key_returns_none, test_require_key_raises, test_env_kpubdata_prefix, test_env_fallback_prefix.

    Attributes:
        Properties defined in constructor and class body are reused as shared context by methods.
    """

    # test explicit key Describes scenario being tested.
    def test_explicit_key(self) -> None:
        """
        test explicit key Verifies scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        cfg = KPubDataConfig(provider_keys={"datago": "mykey"})
        assert cfg.get_provider_key("datago") == "mykey"

    # test missing key returns none Describes scenario being tested.
    def test_missing_key_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        test missing key returns none Verifies scenario.

        Args:
            monkeypatch (pytest.MonkeyPatch): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        monkeypatch.delenv("KPUBDATA_DATAGO_API_KEY", raising=False)
        monkeypatch.delenv("DATAGO_API_KEY", raising=False)
        cfg = KPubDataConfig()
        assert cfg.get_provider_key("datago") is None

    # test require key raises Describes scenario being tested.
    def test_require_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        test require key raises Verifies scenario.

        Args:
            monkeypatch (pytest.MonkeyPatch): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        monkeypatch.delenv("KPUBDATA_DATAGO_API_KEY", raising=False)
        monkeypatch.delenv("DATAGO_API_KEY", raising=False)
        cfg = KPubDataConfig()
        with pytest.raises(ConfigError, match="Missing provider API key"):
            cfg.require_provider_key("datago")

    # test env kpubdata prefix Describes scenario being tested.
    def test_env_kpubdata_prefix(self) -> None:
        """
        test env kpubdata prefix Verifies scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        cfg = KPubDataConfig()
        with patch.dict(os.environ, {"KPUBDATA_SEOUL_API_KEY": "envkey"}):
            assert cfg.get_provider_key("seoul") == "envkey"

    # test env fallback prefix Describes scenario being tested.
    def test_env_fallback_prefix(self) -> None:
        """
        test env fallback prefix Verifies scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        cfg = KPubDataConfig()
        with patch.dict(os.environ, {"SEOUL_API_KEY": "fallback"}, clear=False):
            # Only if KPUBDATA_ not set
            result = cfg.get_provider_key("seoul")
            assert result is not None

    # test explicit takes precedence Describes scenario being tested.
    def test_explicit_takes_precedence(self) -> None:
        """
        test explicit takes precedence Verifies scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        cfg = KPubDataConfig(provider_keys={"seoul": "explicit"})
        with patch.dict(os.environ, {"KPUBDATA_SEOUL_API_KEY": "envkey"}):
            assert cfg.get_provider_key("seoul") == "explicit"

    # test from env Describes scenario being tested.
    def test_from_env(self) -> None:
        """
        test from env Verifies scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        env = {"KPUBDATA_DATAGO_API_KEY": "k1", "KPUBDATA_SEOUL_API_KEY": "k2"}
        with patch.dict(os.environ, env, clear=False):
            cfg = KPubDataConfig.from_env()
            assert "datago" in cfg.provider_keys
            assert "seoul" in cfg.provider_keys

    # test repr no secrets Describes scenario being tested.
    def test_repr_no_secrets(self) -> None:
        """
        test repr no secrets Verifies scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        cfg = KPubDataConfig(provider_keys={"datago": "secret123"})
        r = repr(cfg)
        assert "secret123" not in r
        assert "datago" in r
