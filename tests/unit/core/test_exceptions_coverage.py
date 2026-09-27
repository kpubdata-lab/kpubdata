"""Test module.

This file ``tests/unit/core/test_exceptions_coverage.py`` defines test scenarios and helper objects.
For regression prevention and public contract validation verify core flows, exceptions, and edge conditions.
"""

from __future__ import annotations

from kpubdata.exceptions import PublicDataError


# Explains scenario for: test public data error repr includes retryable flag.
def test_public_data_error_repr_includes_retryable_flag() -> None:
    """
    Verify: test public data error repr includes retryable flag scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    error = PublicDataError("retry me", retryable=True)

    assert "retryable=True" in repr(error)
