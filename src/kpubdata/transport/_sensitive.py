"""The one canonical list of parameter and header names treated as credentials.

This list used to exist in three copies -- 13 names in ``http.py``, 9 in
``cache.py``, 8 in ``replay.py``. Nobody had written down that adding a name
meant editing all three, so they drifted, and ``cache.py`` ended up without
sgis's ``consumer_secret``. A name that is missing from the list goes into the
cache key **verbatim** rather than as a fingerprint.

Names match exactly, not as substrings. Treating ``key`` as a substring would
mask ordinary parameters such as ``district_code`` and leave the logs useless.
"""

from __future__ import annotations

#: Holds casefolded names only; the comparison side casefolds as well.
SENSITIVE_PARAM_KEYS: frozenset[str] = frozenset(
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
        # law (National Law Information Center) sends its API key as the "OC"
        # parameter. The name does not look like a credential, so it was missing
        # from the masking list and the key stayed in clear text in the URL that
        # exception messages carry.
        "oc",
        # sgis (Statistical Geographic Information Service) uses OAuth-style
        # names. Matching is exact, so each one has to be listed.
        "accesstoken",
        "consumer_key",
        "consumer_secret",
    }
)

__all__ = ["SENSITIVE_PARAM_KEYS"]
