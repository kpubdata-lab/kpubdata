# 용어 사전 (Terminology)

이 표가 UI · 문서 · 이슈 리뷰의 기준이다. **공개 용어와 내부 용어를 구분한다** —
내부 이름을 바꾸지 않고도 사용자가 보는 말을 정리할 수 있고, 둘을 한 번에 바꾸면
diff 가 커져 기능 회귀 위험만 올라간다.

## 개념별 대응

| 개념 | 공개 용어 | 내부 용어 (유지) |
|---|---|---|
| 공공 API 원천 데이터셋 | **Source** | `DatasetRef`, catalogue entry |
| 분석 가능한 데이터 | **Table** | Gold/Silver artifact |
| 특정 시점의 불변 버전 | **Snapshot** | run artifact |
| 데이터를 다시 수집하는 일 | **Refresh** | build |
| 그 실행 | **Refresh Run** | `BuildRun` |
| 처음 만드는 일 | **Create Table** / **Materialize** | build |
| 데이터셋·테이블 생성 | **KPubData Builder** | `kpubdata-builder`, `BuilderService` |
| 공공데이터 접근 SDK | **KPubData** | `kpubdata` |
| 웹 작업공간 | **KPubData Studio** | `kpubdata-studio` |
| 공공데이터 신뢰성 관측 서비스 | **KPubData Watch** | `kpubdata-watch` |
| AI 도우미 | **Ask KPubData** | `features/kubi`, `features/assistant` |
| 질의 화면 | **SQL Workspace** | query service |
| 원천 탐색 | **Catalog** | discover, add-data |
| API 키 설정 | **Connections** | provider credential |

## Build 를 기계적으로 Refresh 로 바꾸지 않는다

세 경우가 서로 다르다.

| 상황 | 공개 용어 |
|---|---|
| 테이블을 **처음** 만든다 | Create Table · Materialize |
| 기존 테이블을 **다시** 수집한다 | Refresh |
| 내부 구현·spec·타입 | `Build`, `BuildSpec`, `BuildRun` 유지 |

"Refresh" 를 첫 생성에 쓰면 없던 것을 새로 고친다는 말이 된다.

## Dataset 단독 사용을 피한다

`Dataset` 이 세 가지를 가리킬 수 있다 — 공공 API 원천, 빌드 결과, warehouse
테이블. 단독으로 쓰지 않고 **qualifier 를 붙인다.**

```
Source Dataset   (원천)
Table            (분석 대상)
Table Snapshot   (특정 버전)
```

## 상태 어휘

서로 다른 축을 하나의 badge 로 합치지 않는다. 합치면 "왜 이 상태인지" 를 되물어야
한다.

| 축 | 값 |
|---|---|
| Table health | Healthy · Stale · Degraded · Unknown |
| Completeness | Complete · Partial · Unknown |
| Refresh | Queued · Running · Succeeded · Failed · Cancelled |
| Access | Available · Key required · Application required · Unavailable · Unknown · Retired |
| Maturity | Stable · Beta · Experimental |

Access 축의 어휘는 **KPubData Builder 가 소유한다**(`AccessStatus`, kpubdata-builder#831).
Builder 는 kpubdata 의 probe 분류를 명시적인 매핑으로 옮기고, 매핑에 없는 값은 `unknown`
으로 보낸다 — kpubdata 의 enum 이 그대로 wire 로 나가지 않는다. 지금은 값이 probe 분류와
같지만 그것은 매핑의 결과이지 계약이 아니다. Studio 는 Builder OpenAPI 의 값만 본다
([ADR 0007](../adrs/0007-independence-rules.md) Rule 8·9).

## 현재 규모 (실측 2026-09-27)

`kpubdata-studio` 의 i18n 문자열 기준이다. 이 숫자가 작업량이고, 추정이 아니다.

| 용어 | en.json | ko.json |
|---|---|---|
| Build | 236 | 166 (+ "빌드" 78) |
| Dataset | 136 | 81 (+ "데이터셋" 61) |
| Builder | 86 | 86 |
| Provider | 75 | 59 |
| Kubi | 55 | 55 |
| Artifact | 18 | 1 (+ "산출물" 3) |

`Kubi` 는 92개 파일에 걸쳐 있고, `features/kubi` 와 `features/assistant` 가 이미
병존한다 — 이전 이관이 중간에 멈춰 있다.
