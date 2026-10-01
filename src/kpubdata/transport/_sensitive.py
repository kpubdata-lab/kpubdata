"""The one canonical list of parameter and header names treated as credentials.

This list used to exist in three copies -- 13 names in ``http.py``, 9 in
``cache.py``, 8 in ``replay.py``. Nobody had written down that adding a name
meant editing all three, so they drifted, and ``cache.py`` ended up without
sgis's ``consumer_secret``. A name that is missing from the list goes into the
cache key **verbatim** rather than as a fingerprint.

Names match exactly, not as substrings. Treating ``key`` as a substring would
mask ordinary parameters such as ``district_code`` and leave the logs useless.

Names are also not the whole story: a provider can send its key under a name
nobody listed (DART's ``crtfc_key``), so masking by name alone leaks the value.
``_secret_forms`` turns the actual secret values into every form they can take,
for the value-based masking that catches those (#737).
"""

from __future__ import annotations

from urllib.parse import quote, quote_plus

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


def _secret_forms(secrets: tuple[str, ...]) -> tuple[str, ...]:
    """Each secret as sent and as it can appear percent-encoded in a URL (#612).

    data.go.kr keys carry ``+``, ``/`` and ``=``; the response URL holds them as
    ``%2B``, ``%2F`` and ``%3D``, so matching only the plain text misses them.
    Longest first, so a longer form is replaced before a shorter prefix of it.
    """
    forms: set[str] = set()
    for secret in secrets:
        if not secret:
            continue
        forms.update({secret, quote(secret, safe=""), quote_plus(secret, safe="")})
    return tuple(sorted(forms, key=len, reverse=True))


__all__ = ["SENSITIVE_PARAM_KEYS"]
