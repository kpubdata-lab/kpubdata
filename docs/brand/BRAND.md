# 브랜드 (Brand)

## 브랜드와 SDK 표시명

전체 브랜드는 **KPubData**, 이 저장소의 Python 라이브러리 표시명은
**KPubData SDK**입니다. SDK를 소개하는 제목과 문서 홈에는 표시명을 사용합니다.
SDK 사용 안내는 독립 설치·탐색·수집·정규화와 원본 응답 접근을 설명합니다.
다른 제품의 소개나 설치를 SDK 시작 경로에 끼워 넣지 않습니다.

## 한 줄 정의

```text
KPubData SDK — Python SDK for Korean Public Data
```

> 한국 공공 API의 인증·응답·페이지 처리 차이를 흡수하는 독립 Python SDK.
> 사용자의 공식 API 키로 데이터를 탐색하고 수집하며 원본 응답 접근을 유지합니다.

> A standalone Python SDK for discovering and querying Korean public-data APIs
> with your own official API key and access to provider-native responses.

데이터 게시·배포, SQL 작업공간과 파이프라인 운영은 SDK 기능으로 소개하지 않습니다.

## 저장소·패키지·import·CLI 이름

표시명 변경으로 설치 식별자를 바꾸지 않습니다.

| 구분 | 이름 |
|---|---|
| 사용자 표시명 | KPubData SDK |
| 저장소·PyPI 패키지 | `kpubdata` |
| Python import | `from kpubdata import Client` |
| CLI | `kpubdata` |

설치는 `pip install kpubdata` 그대로입니다. 공개 API와 의존성, URL 및 실행
동작은 표시명과 별개인 기존 계약을 따릅니다.

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
