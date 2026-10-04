"""``Client`` refuses a keyword argument it does not know (#781).

``Client(**extra)`` accepted anything and dropped it, so a typo — or an option the
installed version does not have, such as ``env_keys=False`` on 0.8.0 (#780) — passed for
a setting that was applied.
"""

from __future__ import annotations

from typing import Any

import pytest

from kpubdata.client import Client


def test_a_misspelt_option_is_a_type_error() -> None:
    options: dict[str, Any] = {"timeoutt": 5}

    with pytest.raises(TypeError, match="timeoutt"):
        Client(**options)


def test_an_unknown_option_next_to_known_ones_is_a_type_error() -> None:
    options: dict[str, Any] = {"provider_keys": {}, "bogus_kwarg": 1}

    with pytest.raises(TypeError, match="bogus_kwarg"):
        Client(**options)


def test_from_env_no_longer_forwards_free_form_options() -> None:
    """``from_env(extra=...)`` was the same channel: its dict reached ``Client(**extra)``."""
    options: dict[str, Any] = {"extra": {"timeoutt": 5}}

    with pytest.raises(TypeError, match="extra"):
        Client.from_env(**options)


def test_the_documented_options_are_still_accepted() -> None:
    client = Client(
        provider_keys={"datago": "k"},
        timeout=5.0,
        max_retries=1,
        cache=False,
        cache_ttl_seconds=60,
        env_keys=False,
    )

    assert client._config.timeout == 5.0
    assert client._config.env_fallback is False
