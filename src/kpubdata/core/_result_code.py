"""Reading a data.go.kr ``resultCode`` the same way on every path (#843).

The spec executor, the datago adapter and the shared datago-family adapter each read
the code themselves: one compared it to ``"03"``, another to the number 3, and two
refused a code the provider sent as a JSON number. The same answer was an empty
result on one path and an error on another.
"""

from __future__ import annotations

_NO_DATA = 3


def result_code_text(raw: object) -> str | None:
    """Return the code as text, or None when the value is not a code.

    A code arrives as a string, or as a number where the provider answers in JSON.
    """
    if isinstance(raw, str):
        return raw
    if isinstance(raw, int) and not isinstance(raw, bool):
        return str(raw)
    return None


def is_no_data_code(code: str) -> bool:
    """Return True for NODATA_ERROR, however the provider wrote the number 3.

    ``"03"``, ``"3"`` and ``"003"`` are the same code, as ``"00"`` and ``"000"`` are
    the same success. It says no record matched, not that the call failed (#470, #787).
    """
    try:
        return int(code) == _NO_DATA
    except ValueError:
        return False
