# 브랜드 (Brand)

## 제품 브랜드

```
KPubData
```

한 개다. 하위 구성요소는 별도 브랜드가 아니라 **접미사**다.

```
KPubData
├── KPubData          독립 Python SDK · 한국 공공데이터 접근
├── KPubData Builder  수집 · 변환 · Snapshot · 질의 (KPubData 사용)
├── KPubData Studio   Catalog · Tables · SQL · Lineage · Quality (Builder 사용)
└── KPubData Watch    공공데이터 신뢰도 관측 · Public Status (KPubData 사용)
```

AI 기능은 **독립 브랜드를 만들지 않는다.**

```
Ask KPubData
```

`Kubi`, `Kubi AI`, `Kubi Assistant` 는 사용자에게 보이는 곳에서 쓰지 않는다.

## 한 줄 정의

```
KPubData — Korean public data, ready to query.
```

```
한국 공공데이터를, 바로 분석할 수 있는 테이블로.
```

설명:

> 제각각인 한국 공공 API 를 수집하고 버전 관리해 SQL 로 분석하면서도, 원천·출처·
> 수집 범위·이용 조건을 그대로 추적합니다.

> Turn fragmented Korean public APIs into versioned, queryable tables without
> losing source context, provenance, or usage conditions.

## 구성요소별 한 문장

| | |
|---|---|
| **KPubData** | 한국 공공 API 의 차이를 흡수하는 독립 Python SDK |
| **Builder** | KPubData를 활용해 재현 가능한 데이터셋·테이블을 생성하고 관리 |
| **Studio** | 한국 공공데이터를 수집하고, 출처와 이용 조건을 유지한 스냅샷으로 관리하며, 표와 SQL 로 분석하는 작업공간 |
| **Watch** | 한국 공공데이터 API를 지속 관측해 "지금 믿고 쓸 수 있는가"를 근거와 함께 공개 |

## 저장소 이름과 제품 이름은 다르다

저장소는 **바꾸지 않는다.**

```
kpubdata          → 제품명 KPubData
kpubdata-builder  → 제품명 KPubData Builder
kpubdata-studio   → 제품명 KPubData Studio
kpubdata-watch    → 제품명 KPubData Watch
```

패키지 이름(`kpubdata`, `kpubdata-builder`)도 그대로다. rename 은 설치된 사용자와
의존 관계를 깨뜨리는 일이고, 제품명 정리와는 별개 결정이다. **향후 rename 여부는
결정하지 않은 상태로 남긴다.**

## 목소리 (Voice)

```
정확 · 간결 · 차분 · 증거 기반
```

쓰지 않는 표현:

```
Magic · Smart · Powerful · Revolutionary · AI-powered everything
```

쓰는 표현:

```
Last refreshed 2 hours ago
Live access not verified
Policy review required
3 rows could not be mapped
```

**"프레임워크가 거짓말하지 않는다" 를 UI 문구에도 적용한다.** 확인하지 않은 것을
확인한 것처럼 쓰지 않고, 모르는 것은 모른다고 쓴다 — `Unknown` 은 실패가 아니라
정직한 상태다.

## 제품명을 반복하지 않는다

App Shell 에서 sidebar 로고 · topbar 제품명 · tagline 을 동시에 보여주지 않는다.

```
Sidebar   로고만
Topbar    현재 위치 — Tables / Housing / apartment_trade_monthly
```

사용자는 자기가 어느 제품을 쓰는지 이미 안다. 화면이 반복해서 알려줄 필요가 없고,
그 자리는 현재 보고 있는 대상에 쓰는 게 낫다.

## 정보 밀도가 marketing heading 보다 앞선다

DW 화면이다. 큰 제목으로 여백을 채우지 않고, 한 화면에서 판단할 수 있는 정보를
보여준다. SQL 과 식별자에는 monospace 를 일관되게 쓴다.

```
housing.apartment_trade_monthly
region_id
snap_019
```

## 색

브랜드 색과 상태 색을 섞지 않는다.

- 모든 성공을 브랜드색으로 칠하지 않는다 — 그러면 브랜드색이 "성공" 을 뜻하게 된다
- `warning` · `partial` · `stale` 이 같은 amber 여도 **label 로 구분한다**
- dark mode 에서 같은 의미 체계를 유지한다

## Ask KPubData 의 경계

context-aware 도우미이고 **실행 권한이 아니다.**

금지:

- 독립 AI 제품 페이지 중심 UX
- 별도 마스코트 브랜드
- SQL 자동 실행
- 정책 자동 판정
- 근거 없는 source 자동 선택

진입점은 topbar 버튼과 맥락별 동작이다 — `Ask about this table`,
`Explain this query`, `Explain this issue`.

## 관련 문서

- [용어 사전](TERMINOLOGY.md) — 공개 용어 ↔ 내부 용어 대응, 실측 규모
- [ADR 0003 언어 정책](../adrs/0003-language-policy.md)
