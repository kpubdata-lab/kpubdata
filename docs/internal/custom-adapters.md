# 커스텀 어댑터 유지 목록 (Phase 0.2)

> 생성일: 2026-09-07 · 이슈: [#377](https://github.com/kpubdata-lab/kpubdata/issues/377)
>
> 선언적 spec으로 설명하지 않기로 결정된 데이터셋(="사람 몫" 목록). Generic Executor와 공존하며
> 기존 `ProviderAdapter` 구현체로 유지한다. 사유가 해소되면 이 목록에서 제외하고 spec으로 이전한다.

## 확정: 영구 커스텀

| 데이터셋 | 사유 | 비고 |
|---|---|---|
| `krx.kospi_index` 외 3개 | **비HTTP** — pykrx 라이브러리 기반(DataFrame). REST 호출 자체가 없어 spec의 endpoint/params/response 축이 성립하지 않음. 접근 강화(로그인/키)로 pykrx 의존 지속 관리 필요 | `providers/krx/adapter.py`, 선택 의존성 `kpubdata[krx]` |
| `datago.road_traffic` | ITS 국가교통정보센터 **별도 apiKey 인증** + `its_flat` envelope + 정책상 `call_raw` 전용(list 미지원) | `envelope_style: its_flat`는 parser가 지원하지만 list 경로 미제공 |

## 확정: 지연 전환 (executor 기능 대기)

| 데이터셋 | 사유 | 전환 조건 |
|---|---|---|
| `sgis.sido_boundaries` 외 3개 | `oauth_exchange`(consumer_key/secret → accessToken 캐시·갱신) + GeoJSON `features` 정규화 | executor가 `auth.type: oauth_exchange`와 `format: geojson`을 지원하면 spec 이전. 스키마 enum에는 이미 포함 예정이라 우선순위만 뒤로 |

## 참고: raw 비상구 (데이터셋 아님, spec 대상 제외)

- `datago.generic` — 카탈로그 밖 임의 data.go.kr endpoint 호출용 `call_raw` 전용 게이트. SSRF 방지 호스트 allowlist(`*.data.go.kr` + `KPUBDATA_DATAGO_EXTRA_HOSTS`) 유지 필수.

## 유지 관리 규칙

1. 이 목록의 데이터셋은 Phase 1.4 `migrate-to-spec` 대상에서 **제외**한다.
2. 커스텀 어댑터에 행위 변경이 생기면 종전대로 fixture/unit/contract 테스트와 `SUPPORTED_DATA.md`를 같은 PR에서 갱신한다(AGENTS.md 어댑터 작업 규칙 그대로 적용).
3. 사유가 무효화된 경우(예: krx가 REST API로 전환) 이 문서에서 행을 옮기고 spec 전환 이슈(`migrate-to-spec`)를 등록한다.
