"""``SENSITIVE_PARAM_KEYS`` is public, and it is the list the transport masks with (#782).

Builder redacts its own record of a request and kept a second list for it, which had
drifted: ``key``, ``oc``, ``consumer_key`` and ``consumer_secret`` were missing. A public
name is only useful if it is the same object the transport uses.
"""

from __future__ import annotations

import kpubdata
import kpubdata.transport
from kpubdata.transport import _sensitive, cache, http, replay

#: Names a release has shipped. Removing one is a breaking change; add new names here.
_SHIPPED = frozenset(
    {
        "servicekey",
        "service_key",
        "api_key",
        "apikey",
        "token",
        "authorization",
        "secret",
        "password",
        "key",
        "oc",
        "accesstoken",
        "consumer_key",
        "consumer_secret",
    }
)


def test_the_list_is_importable_from_the_public_modules() -> None:
    assert "SENSITIVE_PARAM_KEYS" in kpubdata.__all__
    assert "SENSITIVE_PARAM_KEYS" in kpubdata.transport.__all__
    assert kpubdata.SENSITIVE_PARAM_KEYS is kpubdata.transport.SENSITIVE_PARAM_KEYS


def test_it_is_the_list_the_transport_masks_with() -> None:
    public = kpubdata.SENSITIVE_PARAM_KEYS

    assert public is _sensitive.SENSITIVE_PARAM_KEYS
    assert http.SENSITIVE_PARAM_KEYS is public
    assert cache.SENSITIVE_PARAM_KEYS is public
    assert replay.SENSITIVE_PARAM_KEYS is public


def test_no_shipped_name_is_removed_and_names_are_casefolded() -> None:
    public = kpubdata.SENSITIVE_PARAM_KEYS

    assert isinstance(public, frozenset)
    assert sorted(_SHIPPED - public) == []
    assert all(name == name.casefold() for name in public)
