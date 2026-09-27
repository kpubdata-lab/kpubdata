# Provider 키가 전송될 수 있는 호스트

`kpubdata` 는 provider 키를 **그 provider 의 허용 호스트에만** 보낸다. spec 이
가리키는 호스트가 목록에 없으면 호출 자체를 하지 않는다.

## 왜 있는가

spec 은 두 가지를 함께 선언한다.

- `endpoint.base_url` — 호출할 곳
- `auth.provider_key` — 붙일 credential

이 둘이 서로 맞는지 확인하는 곳이 없었다(#519). 그래서 spec 이 아무 호스트를
가리켜도 키가 거기로 갔다. spec 은 YAML 파일이고 PR 로 바뀌므로, 호스트 한 줄을
고치는 것으로 키를 밖으로 내보낼 수 있었다.

## 기본 허용 호스트

| provider | 호스트 |
|---|---|
| `datago` · `localdata` · `semas` | `data.go.kr` 및 그 하위 도메인, `api.odcloud.kr`, `openapi.its.go.kr` |
| `bok` | `ecos.bok.or.kr` |
| `kosis` | `kosis.kr` 및 하위 도메인 |
| `krx` | `data.krx.co.kr` |
| `kipris` | `kipo-api.kipi.or.kr` |
| `law` | `law.go.kr`, `www.law.go.kr` |
| `lofin` | `lofin365.go.kr`, `www.lofin365.go.kr` |
| `neis` | `open.neis.go.kr` |
| `seoul` | `openapi.seoul.go.kr`, `swopenapi.seoul.go.kr` |
| `sgis` | `sgisapi.kostat.go.kr` |
| `fds` | `openapi.foodsafetykorea.go.kr` |
| `korean` | `stdict.korean.go.kr` |

정본은 `src/kpubdata/_hosts.py` 의 `PROVIDER_ALLOWED_HOSTS` 다.

## 목록에 없으면 어떻게 되는가

`InvalidRequestError` 가 발생하고 **요청은 나가지 않는다.**

```
datago.apt_trade: refusing to send the 'datago' credential to a host that is not
on its allowlist. Set KPUBDATA_DATAGO_EXTRA_HOSTS if this host is legitimate.
```

`auth.type: none` 인 spec 은 붙일 credential 이 없으므로 이 검사를 받지 않는다.

**목록에 없는 provider 는 통과하지 못한다.** "등재를 잊었다" 가 "아무 호스트나
괜찮다" 로 읽히면 안 되기 때문이다.

## 허용 호스트 추가

프록시나 스테이징 게이트웨이를 거쳐야 하는 배포는 환경변수로 넓힌다.

```bash
# 쉼표 또는 공백 구분. provider 이름은 대문자.
export KPUBDATA_DATAGO_EXTRA_HOSTS="gateway.internal,proxy.corp.example"
export KPUBDATA_SEOUL_EXTRA_HOSTS="seoul-proxy.internal"
```

이름 규칙은 `KPUBDATA_<PROVIDER>_EXTRA_HOSTS` 다. `KPUBDATA_DATAGO_EXTRA_HOSTS`
는 #261 부터 쓰던 이름 그대로다.

값은 **정확히 일치**로 비교한다. 하위 도메인까지 열려면 `.example.com` 처럼
점으로 시작하는 항목이 필요한데, 환경변수로는 정확한 호스트만 추가할 수 있다 —
와일드카드를 환경변수로 받으면 오타 하나로 목록이 무의미해진다.

## 업그레이드 시 확인할 것

이 검사가 없던 버전에서 올라온다면, 다음 중 하나라도 해당하면 위 환경변수가
필요하다.

- 사내 프록시를 통해 공공 API 를 호출한다
- 스테이징·목(mock) 게이트웨이로 spec 을 돌린다
- 표에 없는 호스트를 쓰는 자체 provider spec 이 있다

해당 사항이 없으면 설정할 것이 없다. 번들된 spec 23종은 전부 `apis.data.go.kr`
을 쓰므로 그대로 동작한다.
