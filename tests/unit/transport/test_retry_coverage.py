"""Test module.

This file ``tests/unit/transport/test_retry_coverage.py`` defines test scenarios and helper objects.
For regression prevention and public contract validation verify core flows, exceptions, and edge conditions.
"""

from __future__ import annotations

import pytest

from kpubdata.transport.retry import with_retry


# Explains scenario for: test with retry rejects negative backoff factor.
def test_with_retry_rejects_negative_backoff_factor() -> None:
    """
    Verify: test with retry rejects negative backoff factor scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    with pytest.raises(ValueError, match="backoff_factor"):
        _ = with_retry(lambda: 1, backoff_factor=-0.1)


# test with retry unreachable state raises runtime error Explains scenario validated by test.
def test_with_retry_unreachable_state_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    test with retry unreachable state raises runtime error Verify scenario.

    Args:
        monkeypatch (pytest.MonkeyPatch): input value provided by caller.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    import kpubdata.transport.retry as retry_module

    monkeypatch.setattr(retry_module, "range", lambda *_args: [], raising=False)

    with pytest.raises(RuntimeError, match="unreachable retry state"):
        _ = with_retry(lambda: 1)
