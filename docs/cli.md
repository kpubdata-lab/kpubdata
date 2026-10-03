# CLI 가이드

KPubData를 설치하면 `kpubdata` 명령이 함께 등록됩니다. 노트북이나 짧은 탐색 세션에서 데이터셋을 찾고, 파라미터를 시험하고, 원본 응답을 빠르게 확인할 때 유용합니다.

## 설치 후 명령 확인

```bash
pip install kpubdata
kpubdata --help
```

개발 환경에서는 다음처럼 바로 실행할 수도 있습니다.

```bash
uv run kpubdata --help
```

## 전역 옵션

모든 서브커맨드 앞에서 다음 옵션을 사용할 수 있습니다.

| 옵션 | 설명 |
| :--- | :--- |
| `--cache` | 응답 캐시를 명시적으로 활성화합니다. 기본값은 비활성화입니다. |
| `--log-level {warning,info,debug}` | `kpubdata` 로거 레벨을 설정합니다. 기본값은 `warning`입니다. |
| `--provider-key PROVIDER=KEY` | 환경 변수 대신 특정 Provider 키를 직접 덮어씁니다. 여러 번 지정할 수 있습니다. |
| `--version` | 현재 설치된 KPubData 버전을 출력합니다. |

## datasets list

사용 가능한 데이터셋을 나열합니다.

```bash
kpubdata datasets list
```

Provider별로 좁히기:

```bash
kpubdata datasets list --provider bok
```

텍스트 검색과 JSON 출력:

```bash
kpubdata datasets list --search 금리 --format json
```

기본 출력은 `id`, `name`, `provider`, `operations` 열을 가진 간단한 표입니다.

## datasets show

특정 데이터셋의 메타데이터를 확인합니다.

```bash
kpubdata datasets show bok.base_rate
```

JSON으로 보면 자동화에 더 편리합니다.

```bash
kpubdata datasets show bok.base_rate --format json
```

출력에는 다음 정보가 포함됩니다.

- `id`
- `name`
- `provider`
- `operations`
- `capabilities`
- `raw_metadata_keys`

## fetch

정규화된 `dataset.list(...)`를 호출합니다.

```bash
kpubdata fetch bok.base_rate -p start_date=202401 -p end_date=202412
```

CSV 저장:

```bash
kpubdata fetch bok.base_rate \
  -p start_date=202401 \
  -p end_date=202403 \
  --format csv \
  --output base_rate.csv
```

JSON 출력:

```bash
kpubdata fetch datago.air_quality -p sidoName=서울 -p numOfRows=5 --format json
```

페이지 옵션:

```bash
kpubdata fetch localdata.general_restaurant --page 1 --page-size 20
```

모든 페이지 순회:

```bash
kpubdata fetch lofin.expenditure_budget -p fyr=2024 --all --format table
```

출력 형식은 다음을 지원합니다.

- `table`: 첫 행의 키를 기준으로 최대 20개 열을 정렬해 출력
- `json`: 사람이 읽기 쉬운 들여쓰기된 JSON 배열
- `csv`: 헤더 포함 CSV

## raw

원본 비상구인 `dataset.call_raw(...)`를 호출합니다.

```bash
kpubdata raw datago.air_quality getCtprvnRltmMesureDnsty -p sidoName=서울 -p numOfRows=5
```

파일로 저장:

```bash
kpubdata raw datago.air_quality getCtprvnRltmMesureDnsty \
  -p sidoName=서울 \
  -p numOfRows=5 \
  --output raw-air-quality.json
```

`raw`는 항상 사람이 읽기 쉬운 JSON으로 출력합니다.

## 캐시와 로그 예시

응답 캐시를 켜고 기준금리를 조회하기:

```bash
kpubdata --cache fetch bok.base_rate -p start_date=202401 -p end_date=202401
```

디버그 로그를 켜고 원인 추적하기:

```bash
kpubdata --log-level debug fetch bok.base_rate -p start_date=202401 -p end_date=202401
```

기본 동작은 캐시 비활성화 + `warning` 로그 레벨입니다.

## 환경 변수와의 관계

CLI도 `Client.from_env()`와 동일한 환경 변수 규칙을 따릅니다.

| 환경 변수 | 설명 |
| :--- | :--- |
| `KPUBDATA_<PROVIDER>_API_KEY` | Provider API 키를 읽습니다. |
| `<PROVIDER>_API_KEY` | Provider API 키의 fallback 이름입니다. |
| `KPUBDATA_CACHE=1` | CLI에서 `--cache`를 주지 않아도 캐시를 활성화합니다. |
| `KPUBDATA_CACHE_DIR` | 캐시 디렉터리를 지정합니다. |
| `KPUBDATA_CACHE_TTL` | 캐시 TTL(초)을 지정합니다. |

`--provider-key PROVIDER=KEY`는 같은 Provider에 대해 환경 변수보다 우선합니다. `kpubdata probe`도 이 옵션을 따릅니다 (`Client.probe`/`Client.probe_all` 위에서 동작, #694). `--cache`를 주면 캐시를 명시적으로 켠 것으로 간주합니다.

## 종료 코드

| 코드 | 의미 |
| :--- | :--- |
| `0` | 성공 |
| `1` | 일반 오류 |
| `2` | `InvalidRequestError`, `DatasetNotFoundError` |
| `3` | `AuthError` |
| `4` | `TransportError`, `ProviderResponseError` |

오류 메시지는 표준 에러로 `error: <type>: <message>` 형식으로 출력됩니다. `--log-level debug`가 아닐 때는 스택 트레이스를 보여주지 않습니다.

## 관련 문서

- [README.md](https://github.com/kpubdata-lab/kpubdata/blob/main/README.md) — 설치와 빠른 시작
- [docs/caching.md](./caching.md) — 캐시 세부 동작
- [docs/logging.md](./logging.md) — 로거 이름과 디버깅 방법
