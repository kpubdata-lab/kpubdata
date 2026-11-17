# 응답 캐시 가이드

KPubData SDK의 디스크 기반 응답 캐시는 느리거나 호출 제한이 있는 공공데이터 API를 반복 조회할 때 유용합니다. 같은 GET 요청을 다시 보낼 때 네트워크 대신 로컬 파일을 사용하므로, 노트북 탐색·프로토타이핑·반복 디버깅이 훨씬 빨라집니다.

기본값은 **비활성화**입니다. 명시적으로 켠 경우에만 동작합니다.

## 무엇을 캐시하나요?

- `GET` 요청만 캐시합니다.
- HTTP `2xx` 성공 응답만 캐시합니다.
- `POST`와 오류 응답은 캐시하지 않습니다.
- 캐시 자체의 파일시스템 오류는 모두 `DEBUG` 로그만 남기고 무시합니다. 실제 요청을 깨뜨리지 않습니다.

## 빠르게 켜기

### 코드에서 켜기

```python
from kpubdata import Client

client = Client(cache=True)
```

TTL(초)을 직접 지정할 수도 있습니다.

```python
client = Client(cache=True, cache_ttl_seconds=3600)
```

### 직접 캐시 인스턴스 주입하기

```python
from kpubdata import Client
from kpubdata.transport.cache import ResponseCache

cache = ResponseCache(base_dir="/tmp/kpubdata-cache")
client = Client(cache=cache, cache_ttl_seconds=1800)
```

### 환경 변수로 켜기

```bash
export KPUBDATA_CACHE=1
export KPUBDATA_CACHE_TTL=3600
export KPUBDATA_CACHE_DIR="$HOME/.cache/kpubdata/responses"
```

```python
from kpubdata import Client

client = Client.from_env()
```

## 환경 변수

이름과 단위는 [공통 환경변수 안내](environment-variables.md)를 따릅니다. 기존 변수는 호환성을 위해 유지합니다.

| 변수 | 의미 | 기본값 |
| :--- | :--- | :--- |
| `KPUBDATA_CACHE` | `1`이면 캐시 활성화 | 비활성화 |
| `KPUBDATA_CACHE_DIR` | 캐시 디렉터리 경로 | 플랫폼 기본 경로 |
| `KPUBDATA_CACHE_TTL` | 캐시 TTL(초) | `86400` |

## 캐시 디렉터리

기본 경로는 다음 우선순위를 따릅니다.

1. `XDG_CACHE_HOME/kpubdata/responses`
2. `~/.cache/kpubdata/responses`

`KPUBDATA_CACHE_DIR`를 지정하면 `Client.from_env()`에서는 이 경로를 우선 사용합니다.

## TTL 동작

- 각 엔트리는 `created_at + ttl_seconds`가 지나면 만료됩니다.
- 만료된 엔트리는 읽는 시점에 자동으로 무시되고 삭제됩니다.
- 필요하면 `clear_expired()`로 만료된 파일만 정리할 수 있습니다.

## 캐시 비우기

전체 캐시를 비우려면 다음처럼 호출합니다.

```python
from kpubdata.transport.cache import ResponseCache

ResponseCache().clear()
```

특정 디렉터리를 쓴 경우에는 같은 경로로 인스턴스를 만들어 지우면 됩니다.

## 보안 메모

캐시 키는 HTTP 메서드, URL, 정렬된 파라미터, 일부 헤더를 기반으로 SHA-256 해시로 만듭니다. 이때 다음 민감 키의 값은 해시 전에 항상 `[REDACTED]`로 치환됩니다.

```text
servicekey, service_key, api_key, apikey, token, authorization, secret, password, key
```

즉, API 키가 교체되어도 같은 요청 의미라면 동일한 캐시 키를 계속 재사용할 수 있습니다.
