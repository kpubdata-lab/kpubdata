# 로깅 가이드

KPubData는 파이썬 표준 [`logging`](https://docs.python.org/3/library/logging.html) 모듈을 사용합니다. 별도의 의존성 없이 여러분이 사용 중인 로깅 설정에 자연스럽게 통합됩니다.

라이브러리 관례에 따라 모든 내부 로그는 **`DEBUG` 레벨**로 기록됩니다. 기본값으로는 출력되지 않으며, 사용자가 명시적으로 활성화해야 합니다.

## 로거 이름 규칙

| 로거 이름 | 출처 | 무엇을 기록하나? |
| :--- | :--- | :--- |
| `kpubdata.client` | `client.py` | 클라이언트 초기화/종료, 데이터셋 바인딩, 외부 어댑터 등록 |
| `kpubdata.registry` | `registry.py` | 어댑터 등록(즉시/지연), 조회 성공·실패, 지연 어댑터 인스턴스화 |
| `kpubdata.catalog` | `catalog.py` | 데이터셋 목록·검색·해석(resolve) 호출과 결과 건수 |
| `kpubdata.dataset` | `core/dataset.py` | `list()`, `list_all()`, `call_raw()`, `schema()` 호출 흐름 |
| `kpubdata.config` | `config.py` | Provider API 키 조회 실패 등 설정 검증 |
| `kpubdata.transport` | `transport/http.py`, `transport/retry.py` | HTTP 요청/응답, 재시도, 상태 코드, `Retry-After` 처리 |
| `kpubdata.transport.decode` | `transport/decode.py` | JSON/XML 디코딩 실패 컨텍스트, 미인식 content-type |
| `kpubdata.provider.datago` | `providers/datago/adapter.py` | datago 요청 진입, `resultCode` 검증 |
| `kpubdata.provider.bok` | `providers/bok/adapter.py` | BOK ECOS 요청 진입, 응답 검증 |
| `kpubdata.provider.kosis` | `providers/kosis/adapter.py` | KOSIS 요청 진입, 에러 페이로드 감지 |
| `kpubdata.provider.lofin` | `providers/lofin/adapter.py` | LOFIN 요청 진입, 응답 검증 |

모든 로거는 `kpubdata`를 부모로 가지므로, 이 이름 하나로 KPubData 전체 로그를 한꺼번에 제어할 수 있습니다.

## 활성화 방법

### 모든 KPubData 로그를 표준 출력에 보기

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logging.getLogger("kpubdata").setLevel(logging.DEBUG)
```

### 특정 영역만 디버깅하기

예: HTTP 요청만 자세히 보고 싶을 때.

```python
import logging

logging.basicConfig(level=logging.WARNING)
logging.getLogger("kpubdata.transport").setLevel(logging.DEBUG)
```

### 어댑터 한 개만 디버깅하기

예: data.go.kr 어댑터의 응답 처리만 추적하고 싶을 때.

```python
import logging

logging.basicConfig(level=logging.WARNING)
logging.getLogger("kpubdata.provider.datago").setLevel(logging.DEBUG)
```

## 구조화된 컨텍스트(`extra`)

대부분의 로그 레코드는 사람이 읽기 쉬운 메시지와 함께, 머신이 처리하기 쉬운 키-값 컨텍스트를 `record.extra`에 첨부합니다.

| 로거 | 대표 키 |
| :--- | :--- |
| `kpubdata.client` | `providers`, `timeout`, `max_retries`, `dataset_id`, `provider`, `operations` |
| `kpubdata.registry` | `provider`, `adapter_type` |
| `kpubdata.catalog` | `provider`, `provider_filter`, `text`, `dataset_id`, `count` |
| `kpubdata.dataset` | `dataset_id`, `provider`, `page`, `page_size`, `cursor`, `filter_keys`, `item_count`, `total_count`, `next_page`, `next_cursor`, `iteration`, `iterations`, `operation`, `param_keys` |
| `kpubdata.config` | `provider` |
| `kpubdata.transport` | `method`, `url`, `attempt`, `max_retries`, `status_code`, `params`, `content_type`, `content_length`, `preview`, `delay_seconds`, `exception_type`, `dataset_id`, `provider`, `cache_key` |
| `kpubdata.transport.decode` | `byte_length`, `char_length`, `preview`, `line`, `column`, `root_type`, `content_type`, `exception_type` |
| `kpubdata.provider.*` | `dataset_id`, `provider`, `page`, `page_size`, `total_count`, `result_code`, `result_msg`, `code`, `message`, `operation` |

JSON 포맷터와 결합하면 곧바로 관측(observability) 파이프라인에 연결할 수 있습니다.

## 실패 경로 디버깅

라이브 API 재현 시 원인 파악을 쉽게 하기 위해, 주요 실패 경로는 이제 예외를 던지기 **직전**에 DEBUG 로그를 남깁니다.

- `DatasetNotFoundError`, `InvalidRequestError`, `ParseError`
- Provider별 envelope/API 오류 (`result_code`/`result_msg`, `code`/`message`)
- 정상 envelope 이지만 `items=[]` 인 빈 결과 응답

이 로그들은 `dataset_id`를 공통으로 포함하며, 가능한 경우 `provider`, `page`, `page_size`, `total_count` 같은 상관관계 키를 함께 기록합니다. `kpubdata.transport`도 선택적으로 `dataset_id`/`provider`를 받아 HTTP 요청 시작·성공·재시도·오류 로그에 같은 컨텍스트를 첨부하므로, 어댑터 실패와 실제 HTTP 호출을 한 흐름으로 추적할 수 있습니다.

```python
import json
import logging


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"message": record.getMessage(), "logger": record.name}
        for key, value in record.__dict__.items():
            if key in {
                "args",
                "msg",
                "name",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "taskName",
                "message",
            }:
                continue
            try:
                json.dumps(value)
                payload[key] = value
            except TypeError:
                payload[key] = repr(value)
        return json.dumps(payload, ensure_ascii=False)


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())

root = logging.getLogger("kpubdata")
root.addHandler(handler)
root.setLevel(logging.DEBUG)
```

## 자격 증명 보호

`kpubdata.transport`는 요청 파라미터를 기록할 때 다음 키들을 자동으로 `[REDACTED]`로 마스킹합니다.

```
servicekey, service_key, api_key, apikey, token, authorization, secret, password, key
```

이 외에 어댑터/사용자 정의 자격 증명이 다른 키로 전달된다면, 직접 마스킹하거나 해당 로거의 레벨을 낮추세요.

## 운영 권장 사항

- **운영 환경**: 기본값(WARNING 이상)을 유지하세요. KPubData는 정상 흐름에서 INFO/WARNING 로그를 거의 발생시키지 않습니다.
- **이슈 재현**: `kpubdata`(루트) 로거를 DEBUG로 일시 활성화한 후, 로그 안의 `dataset_id`/`url`/`status_code`/`attempt` 등을 단서로 추적하세요.
- **민감 데이터**: 응답 본문 미리보기(`preview`)는 최대 500자만 기록되지만, 부분적으로 식별정보가 포함될 수 있습니다. 필요 시 `kpubdata.transport` 핸들러에 별도 필터를 적용하세요.

## 관련 문서

- [ARCHITECTURE.md](https://github.com/yeongseon/kpubdata/blob/main/ARCHITECTURE.md) — 전체 아키텍처와 계층 구분
- [PROVIDER_ADAPTER_CONTRACT.md](https://github.com/yeongseon/kpubdata/blob/main/PROVIDER_ADAPTER_CONTRACT.md) — 어댑터 구현 시 로거 사용 규약
- [API_SPEC.md](https://github.com/yeongseon/kpubdata/blob/main/API_SPEC.md) — 공개 API 명세
