# Environment variables — KPubData SDK

This page documents the **current implemented names**. It is for users of the
standalone Python SDK. The names here are not a proposal to rename your existing
settings: a separate post-MVP issue, [#988](https://github.com/kpubdata-lab/kpubdata/issues/988),
covers possible readability improvements and backward-compatible migration.

## Provider API credentials

Set only keys for providers you actually use. Each provider or service can
require its own registration or API-specific approval: **a key that exists is
not proof the dataset is authorized or verified**.

| Provider | Current environment variable | Credential source / note |
| --- | --- | --- |
| `datago` | `KPUBDATA_DATAGO_API_KEY` | [Public Data Portal](https://www.data.go.kr); dataset-specific activation may be required |
| `localdata`, `semas` | `KPUBDATA_DATAGO_API_KEY` (shared default) | These adapters first honor their own `KPUBDATA_LOCALDATA_API_KEY` / `KPUBDATA_SEMAS_API_KEY` override, then fall back to the data.go.kr key |
| `neis` | `KPUBDATA_NEIS_API_KEY` | [NEIS Open API](https://open.neis.go.kr/portal/guide/apiGuidePage.do); **not** a data.go.kr shared-key fallback |
| `fds` | `KPUBDATA_FDS_API_KEY` | [Food Safety Korea Open API](https://www.foodsafetykorea.go.kr/api/howToUseApi.do); **not** a data.go.kr shared-key fallback |
| `bok` | `KPUBDATA_BOK_API_KEY` | [Bank of Korea ECOS](https://ecos.bok.or.kr/api/) |
| `kosis` | `KPUBDATA_KOSIS_API_KEY` | KOSIS |
| `seoul` | `KPUBDATA_SEOUL_API_KEY` | Seoul Open Data |
| `sgis` | `KPUBDATA_SGIS_API_KEY` + `KPUBDATA_SGIS_CONSUMER_SECRET` | The first value is SGIS's consumer key; both values are required for the default two-part token exchange |
| `law`, `kipris`, `korean` | `KPUBDATA_LAW_API_KEY`, `KPUBDATA_KIPRIS_API_KEY`, `KPUBDATA_KOREAN_API_KEY` | Each provider's own credential issuer |
| `krx` | None | This optional backend does not require an SDK API key |

**LOFIN exception:** `docs/providers/lofin.md` describes an independently
issued `KPUBDATA_LOFIN_API_KEY`, but the current
`LofinAdapter._require_api_key()` reads the `datago` key instead. These
credentials must **not** be assumed interchangeable. [Issue #986](https://github.com/kpubdata-lab/kpubdata/issues/986)
tracks verification and correction. Do not run a credentialed LOFIN live test
until the issuer, endpoint, and adapter behavior have been reconciled.

### Lookup order

For ordinary providers, the runtime checks these values in order:

1. An explicit `Client(provider_keys={"provider": "..."})` entry.
2. `KPUBDATA_<PROVIDER>_API_KEY`.
3. The legacy `<PROVIDER>_API_KEY` variable.

For `localdata` and `semas`, after their provider-specific lookup fails,
the SDK falls back to `datago` using its own normal lookup order. An explicit
provider-specific key wins over the shared key. This is the existing behavior,
not a new cross-provider secret-sharing feature.

`Client(provider_keys={...}, env_keys=False)` disables **all** environment
credential fallback, including the SGIS consumer secret. Use this mode for
requests where the supplied key must never be replaced with a service
operator's ambient credential. A local test relying on environment variables
must not be mistaken for verification of another user's key.

## Other SDK settings

| Name | Meaning | Current value and default |
| --- | --- | --- |
| `KPUBDATA_CACHE` | Enable the response cache when using `Client.from_env()` | `1` enables; otherwise off by default |
| `KPUBDATA_CACHE_DIR` | Local response-cache directory | Optional; only used when cache is enabled via the environment |
| `KPUBDATA_CACHE_TTL` | Cache lifetime **in seconds** | Integer, default `86400` (24 hours) |

The API constructor has corresponding explicit arguments such as
`cache_ttl_seconds`. The environment variable retains its current
`KPUBDATA_CACHE_TTL` name for compatibility. See
[cache usage](caching.md) and [CLI options](cli.md).

## Verification-only variables

- `KPUBDATA_DATAGO_REALESTATE_ENABLED=1` is an **integration-test opt-in**
  flag. Set it only after the particular real-estate service has approved the
  operator's API key. It does **not** grant permission.
- `KPUBDATA_MODE=replay` is used by the recorded-response examples and
  verification tooling; it is not a switch that guarantees every ordinary
  `Client` call is offline.
- CI secrets and GitHub Actions settings are operational controls, not extra
  required SDK user configuration. See
  [live-provider verification](LIVE_PROBE.md) for their distinct scope.

**Safety:** Never print credential values for a configuration check, include
keys in screenshots or logs, or commit a real `.env` file. A successful
fixture/replay run is not evidence that a real provider accepted the key.
Current real-API test arrangements are tracked in
[#887](https://github.com/kpubdata-lab/kpubdata/issues/887).
