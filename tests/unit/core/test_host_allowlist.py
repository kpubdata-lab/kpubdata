"""The executor must not send a provider credential to an unlisted host (#519).

These are negative tests: what matters is that the credential never leaves, not
that a nice error appears. They deliberately do not use the ``_allow_fixture_hosts``
autouse fixture's widening for the host under test.

The shape being guarded against is a spec that names one host and a different
provider's credential. ``providers/datago/adapter.py`` already refused that for
``datago.generic``; the spec executor did not, so every spec-driven call was
unguarded while one override path was covered.
"""

from __future__ import annotations

import httpx
import pytest

from kpubdata._hosts import PROVIDER_ALLOWED_HOSTS, host_is_allowed, hosts_for
from kpubdata.config import KPubDataConfig
from kpubdata.core.executor import SpecExecutor
from kpubdata.core.models import Query
from kpubdata.core.spec import SpecDefinition, from_mapping
from kpubdata.exceptions import InvalidRequestError

_SECRET = "the-project-service-key"


def _spec(
    *,
    base_url: str = "https://apis.data.go.kr/svc",
    auth_type: str = "query_param",
    path_template: str | None = None,
    provider: str = "datago",
    provider_key: str = "datago",
) -> SpecDefinition:
    auth: dict[str, object] = {"type": auth_type}
    if auth_type == "query_param":
        auth["param_name"] = "serviceKey"
    elif auth_type == "path_segment":
        auth["param_name"] = "__path_key__"
    if auth_type != "none":
        auth["provider_key"] = provider_key
    endpoint: dict[str, object] = {"base_url": base_url, "operation": "getList"}
    if path_template is not None:
        endpoint["path_template"] = path_template
    return from_mapping(
        {
            "id": f"{provider}.host_gate",
            "provider": provider,
            "title": "host gate",
            "endpoint": endpoint,
            "auth": auth,
            "source": {"url": "https://www.data.go.kr"},
            "response": {
                "format": "json",
                "envelope": "datago_standard",
                "items_path": "response.body.items",
                "error": {
                    "style": "header_result_code",
                    "code_path": "response.header.resultCode",
                    "ok_values": ["00", "000"],
                },
            },
            "pagination": {
                "type": "page_no_rows",
                "page_param": "pageNo",
                "size_param": "numOfRows",
            },
        }
    )


class _RefusingTransport:
    """Any request reaching here means the gate failed to stop it."""

    def request(self, *args: object, **kwargs: object) -> httpx.Response:
        raise AssertionError(f"the credential left the process: {args} {kwargs}")


def _executor(*, keys: dict[str, str] | None = None) -> SpecExecutor:
    provider_keys = {"datago": _SECRET, "bok": _SECRET} if keys is None else keys
    return SpecExecutor(
        transport=_RefusingTransport(),  # type: ignore[arg-type]
        config=KPubDataConfig(provider_keys=provider_keys),
    )


@pytest.fixture(autouse=True)
def _no_widening(monkeypatch: pytest.MonkeyPatch) -> None:
    """Undo the directory-level widening; these tests assert the default gate."""
    for provider in ("datago", "test", "bok"):
        monkeypatch.delenv(f"KPUBDATA_{provider.upper()}_EXTRA_HOSTS", raising=False)


class TestTheCredentialNeverReachesAnUnlistedHost:
    def test_query_param_auth_is_refused(self) -> None:
        with pytest.raises(InvalidRequestError) as caught:
            _executor().build_params(_spec(base_url="https://attacker.example/api"), Query())
        assert _SECRET not in str(caught.value)

    def test_path_segment_auth_is_refused(self) -> None:
        """``path_segment`` puts the key straight into the URL, so it matters most."""
        spec = _spec(
            base_url="https://attacker.example",
            auth_type="path_segment",
            path_template="{base_url}/{key}/json/{operation}",
        )
        with pytest.raises(InvalidRequestError) as caught:
            _executor().build_params(spec, Query())
        assert _SECRET not in str(caught.value)

    def test_the_refusal_happens_before_the_key_is_read(self) -> None:
        """A config with no key at all must still refuse on the host, not on the
        missing key -- proof that the order is host check first."""
        executor = _executor(keys={})
        with pytest.raises(InvalidRequestError, match="allowlist"):
            executor.build_params(_spec(base_url="https://attacker.example/api"), Query())

    def test_a_path_template_cannot_smuggle_its_own_host(self) -> None:
        """``base_url`` passes the gate but the template names somewhere else.

        ``build_params`` only sees ``base_url``, so this is the case the second
        check in ``_request`` exists for.
        """
        spec = _spec(
            base_url="https://apis.data.go.kr",
            auth_type="path_segment",
            path_template="https://attacker.example/{key}/{operation}",
        )
        executor = _executor()
        params = executor.build_params(spec, Query())
        with pytest.raises(InvalidRequestError, match="allowlist"):
            executor._request(spec, params)

    def test_a_lookalike_domain_is_refused(self) -> None:
        with pytest.raises(InvalidRequestError):
            _executor().build_params(
                _spec(base_url="https://apis.data.go.kr.evil.example"), Query()
            )

    def test_another_providers_host_is_refused(self) -> None:
        """A bok credential may not go to a data.go.kr host, or the reverse."""
        with pytest.raises(InvalidRequestError):
            _executor().build_params(
                _spec(base_url="https://ecos.bok.or.kr", provider="datago", provider_key="datago"),
                Query(),
            )


class TestTheGateDoesNotBlockLegitimateCalls:
    def test_a_listed_host_passes(self) -> None:
        params = _executor().build_params(_spec(), Query())
        assert params["serviceKey"] == _SECRET

    def test_auth_none_is_not_gated(self) -> None:
        """No credential is attached, so there is nothing to leak."""
        spec = _spec(base_url="https://anything.example", auth_type="none")
        assert "serviceKey" not in _executor().build_params(spec, Query())

    def test_the_environment_variable_widens_the_list(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("KPUBDATA_DATAGO_EXTRA_HOSTS", "gateway.internal")
        params = _executor().build_params(_spec(base_url="https://gateway.internal/api"), Query())
        assert params["serviceKey"] == _SECRET


class TestTheListItself:
    def test_an_unknown_provider_is_fail_closed(self) -> None:
        assert hosts_for("no-such-provider") == frozenset()
        assert not host_is_allowed("no-such-provider", "https://apis.data.go.kr")

    def test_no_wildcard_entry_exists(self) -> None:
        """A bare ``.`` or ``*`` entry would match everything."""
        for provider, hosts in PROVIDER_ALLOWED_HOSTS.items():
            for host in hosts:
                assert host not in (".", "*", ""), f"{provider} has a catch-all entry"
                assert "*" not in host, f"{provider}: {host} looks like a wildcard"

    def test_suffix_entries_cover_the_bare_domain(self) -> None:
        assert host_is_allowed("datago", "data.go.kr")
        assert host_is_allowed("datago", "apis.data.go.kr")

    @pytest.mark.parametrize("value", ["", "   ", "not a url", "https://"])
    def test_unparseable_values_are_refused(self, value: str) -> None:
        assert not host_is_allowed("datago", value)
