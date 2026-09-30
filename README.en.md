# KPubData

**Korean public data, ready to query.**

> A standalone Python SDK for accessing Korean public data. KPubData installs and runs on its own, without any other project.
>
> Related projects:
>
> - [KPubData Builder](https://github.com/yeongseon/kpubdata-builder) — builds and manages reproducible datasets and tables on top of KPubData
> - [KPubData Studio](https://github.com/yeongseon/kpubdata-studio) — a visual workspace for KPubData Builder

[한국어](./README.md)

Every Korean public-data API authenticates differently, answers in a different shape
and paginates its own way. KPubData absorbs those differences in adapters so one
Python interface reaches all of them. It is **an SDK that uses your own official API
key**, so it neither holds nor redistributes the data.

<!-- BEGIN: datasets -->

- **spec 기반 데이터셋** 23종 — `make verify` 4단계 기계 검증 통과 (22종은 실API 검증 날짜까지 기록)
- **catalogue 기반 데이터셋** 150종 (bok 4, datago 41, fds 1, kipris 1, korean 1, kosis 2, krx 3, law 3, localdata 59, lofin 6, neis 2, semas 17, seoul 7, sgis 3)

> 이 수치는 `scripts/gen_readme_datasets.py`로 생성했다 — 직접 편집 금지. 데이터셋별 상태는 [SUPPORTED_DATA.md](./SUPPORTED_DATA.md).
<!-- END: datasets -->

> **Verification level (#498)**: in [SUPPORTED_DATA.md](./SUPPORTED_DATA.md), "지원" (supported) is used only for a
> dataset with a recorded live-API response (`meta.json`). That column is computed from the fixtures by
> `scripts/sync_supported_data.py`; schema-only and awaiting-application datasets are listed there too.

## 무엇을 해결하나

- **Differences in auth, pagination and response shape** — they stay inside adapters
- **Evidence behind the word "supported"** — nothing is supported until fixture, unit
  and contract tests pass, and live-API verification records the date
- **Provider-specific features** — kept as they are rather than flattened into fake
  universal semantics, with `call_raw` as the escape hatch

## 무엇을 하지 않나

- Does not store or redistribute data — the key is yours and so is the call
- Does not invent capabilities a provider's API does not have
- Publishing and distribution belong to
  [kpubdata-builder](https://github.com/yeongseon/kpubdata-builder)

## 설치

```bash
pip install kpubdata
```

## 빠른 시작

```python
from kpubdata import Client

client = Client()  # reads KPUBDATA_DATAGO_API_KEY
batch = client.dataset("datago.apt_trade").list(LAWD_CD="11110", DEAL_YMD="202501")
print(batch.records[0])
```

Issuing an API key and setting the environment variables is covered in
[quickstart](docs/quickstart.md); per-provider procedure is under
[providers](docs/providers/). Those pages are in Korean, because the procedures are —
the screens, the 활용신청 application and the 공공누리 licence terms are Korean, and
translating their names loses what they refer to.

## 지원 범위

| | |
|---|---|
| Providers | `datago` `bok` `kosis` `krx` `law` `localdata` `lofin` `semas` `seoul` `sgis` `kipris` `korean` `neis` `fds` |
| Python | 3.10 and later |
| Per-dataset status and verification | [SUPPORTED_DATA.md](./SUPPORTED_DATA.md) |

## 문서

| | |
|---|---|
| [Quickstart](docs/quickstart.md) | Install to first query |
| [CLI](docs/cli.md) | The `kpubdata` command |
| [Providers](docs/providers/) | Key issuance and per-provider quirks |
| [Dataset examples](docs/dataset-examples.md) | Runnable examples |
| [Architecture](ARCHITECTURE.md) | Design and layers |
| [API specification](API_SPEC.md) | The public Python API |
| [Adapter contract](PROVIDER_ADAPTER_CONTRACT.md) | What a provider adapter must honour |
| [Contributing](CONTRIBUTING.md) | Development setup and verification |
| [Security](SECURITY.md) | Reporting, and the limits we know about |

The project runs on [POLICY.md](docs/governance/POLICY.md) and
[VERIFICATION.md](docs/governance/VERIFICATION.md).

## 제품군

| Repository | Role |
|---|---|
| **kpubdata** | Collection and normalisation — this repository |
| [kpubdata-builder](https://github.com/yeongseon/kpubdata-builder) | Pipeline and publishing |
| [kpubdata-studio](https://github.com/yeongseon/kpubdata-studio) | Screens and workflow |

## 라이선스

[MIT](./LICENSE) for the code. What you may do with the data you collect follows each
provider's 공공누리 licence type, which this licence does not cover.
