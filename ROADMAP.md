# Roadmap — KPubData

> **이 문서는 작업 진행상태의 정본이 아니다.** 방향(NOW / NEXT / LATER)만 적는다.
> **Epic, Project 보드, 필수 상태·유형 라벨을 사용하지 않습니다.**
> 독립 Issue(Open/Closed)와 연결된 PR이 작업 상태의 정본이며, 필요하면 근거 있는 `priority:*` 라벨만 사용합니다.
> 데이터셋 지원 상태는 여기에 손으로 적지 않는다 — spec 과 evidence 에서 생성되는 `SUPPORTED_DATA.md` · `docs/status.md` 가 기준이다(3절).

> kpubdata는 **한국 공공데이터 접근 코어 프레임워크**에 집중합니다.
> 장기 목표는 한국에서 많이 쓰이는 공공데이터를 production-grade로 접근하는 표준 레이어입니다.
> **50~100개 확보는 장기 확장 지표이며 별도 MCP v0.1의 선행조건이 아닙니다.**
> MCP, HTTP API 등 서비스 레이어는 SDK에 포함하지 않고 독립 저장소로 분리합니다.

## 현재 실행 순서 — NOW / NEXT / LATER (2026-11-19)

> 아래는 **우선순위와 의존성 방향**이며 완료 상태표가 아닙니다. 실제 미해결 범위와
> 진행·병합 여부는 각 Issue/PR 및 [안정화 동결 정책](docs/governance/POLICY.md#13-안정화-전용-개발-모드--2026-10-12)을 확인합니다.
> `priority:critical/high/medium/low` 이외 P0/P1/P2 라벨, Epic, 보드를 만들지 않습니다.

### NOW — SDK의 안전한 조회와 기존 계약 안정화

1. **전송 및 자격 증명 차단** — [#893](https://github.com/kpubdata-lab/kpubdata/issues/893)의
   번들 spec 22개 HTTPS 전환은 2026-11-19 완료 기록이 있습니다. 남은
   catalogue-only HTTP 경로는 인증정보가 포함된 요청을 전송 계층에서 거부하므로
   *평문 키 전송이 아니라 조회 불가/지원 범위* 문제입니다. 남은 99개 경로의 처리 원칙과
   검증 범위를 결정하되, 미검증 데이터셋을 작동한다고 홍보하지 않습니다.
2. **출처와 이용 조건** — [#933](https://github.com/kpubdata-lab/kpubdata/issues/933)의
   잘못된 terms 링크·라이선스를 근거로 정정하고, MCP 후보의 외부 AI host 전송·재이용
   조건을 개별 확인합니다. unknown을 허용으로 취급하지 않습니다.
3. **조회 정확성·검증 증거** — [#967](https://github.com/kpubdata-lab/kpubdata/issues/967)의
   SGIS 토큰 처리와 [#973](https://github.com/kpubdata-lab/kpubdata/issues/973)의
   페이지네이션은 실제 영향 경로를 먼저 재현하고 필요한 부분만 수정합니다.
   [#887](https://github.com/kpubdata-lab/kpubdata/issues/887)의 수동 국내 실API 검증과
   replay/계약 테스트를 구분합니다. 전체 catalogue가 아니라 **안전한 후보 3~5개**
   중심으로 초기 사용 경로를 검증합니다.

### NEXT — 독립 MCP의 Live v0.1 (SDK 코드에 포함하지 않음)

1. 독립 비공개 [kpubdata-mcp](https://github.com/kpubdata-lab/kpubdata-mcp)는 초기 구현 단계입니다.
   소스 체크아웃에서 `stdio`를 시작해 SDK 카탈로그의 탐색·설명·상태 확인을 실행할 수
   있습니다. 단일 페이지 조회 도구도 구현됐지만, 허용 목록이 비어 Live 조회는
   비활성화돼 있으며 패키지는 미출시 상태입니다. 구현 승인 범위는
   [#974](https://github.com/kpubdata-lab/kpubdata/issues/974)에 기록돼 있습니다.
2. Live v0.1은 데이터셋별 이용 조건·AI 호스트 전송 조건을 확인하고, 승인된 후보를
   대상으로 설치·MCP 클라이언트·실API 검증을 마친 뒤 릴리스 판단을 합니다.
   Live 조회는 SDK의 공개 API를 사용하며 Engine 없이 실행됩니다.
3. SDK의 구형 MCP optional extra 및 오래된 문서 표현은 **별도 호환성 검토 후**
   정리합니다. 새 MCP 기능을 넣기 위해 SDK 공개 계약을 편의적으로 확장하지 않습니다.

### PARALLEL / LATER — Engine 독립 MVP 및 Gold v0.2

- [Engine #20](https://github.com/kpubdata-lab/kpubdata-engine/issues/20)은
  SDK를 이용한 **독립 설치·빌드·검증·복구 MVP**를 진행합니다. 이것이 MCP Live 출시에
  선행하지 않습니다. 실제 OCI VM 검증은 소유자의 2026-11-17 **보류 결정**을 유지합니다.
- Engine이 승인된 불변 Gold artifact + manifest 외부 계약을 제공하고 MCP Live v0.1이
  검증된 **이후에만**, MCP v0.2에서 명시적 `source=gold` 읽기 경로를 추가합니다.
  Engine 사설 DB·작업 디렉터리나 서버 프로세스에 MCP를 결합하지 않습니다.
- 신규 provider/dataset 확장([#950](https://github.com/kpubdata-lab/kpubdata/issues/950)
  등), 광범위한 catalogue 통합([#898](https://github.com/kpubdata-lab/kpubdata/issues/898)),
  명명·편의 기능([#988](https://github.com/kpubdata-lab/kpubdata/issues/988))은
  안전성 및 실제 사용자 수요와 동결 해제 근거가 확보될 때까지 보류합니다.

---

## 개발 3축

| 축 | 설명 | 대표 이슈 |
| :--- | :--- | :--- |
| **Core** | 핵심 계약(contract), 스키마, 메타데이터, discovery 안정화 | #55, #57, #63 |
| **Plugin Ecosystem** | entry-point plugin discovery, provider scaffolding 도구 | #112, #61 |
| **Provider Adapters** | 기관별 어댑터 확장 (datago, localdata, semas, bok, ...) | #87-#94, #161-#168 |

---

> 아래 버전별 목록은 **과거 계획/이력**으로 보존합니다. 현재 실행 순서는 위 NOW/NEXT/LATER와 각 Issue가 기준입니다.

## v0.1 ✅

Foundation release.

- finalize core contracts
- implement transport skeleton
- implement 3 distinct adapters (datago, bok, kosis)
- support XML + JSON
- support discovery + list + raw
- ship docs and contract tests

## v0.2 ✅

Stabilization and ergonomics.

- dataset metadata enrichment
- schema improvements
- pandas adapter (`to_pandas()`)
- single-page pagination contract + `list_all()`
- more examples and documentation

## v0.3 ✅

Provider expansion.

- localdata provider: 195개 인허가 데이터셋
- sgis provider: 행정구역 경계 GeoJSON
- semas provider: 상가(상권)정보 17개 데이터셋
- seoul provider: 지하철 실시간, 따릉이
- lofin provider: 6개 재정 데이터셋
- datago provider: 부동산 실거래가, 관광, 지하철 어댑터 추가

## v0.4 — Core 안정화

- dataset metadata enrichment (#55)
- schema improvements (#57)
- more robust discovery (#63)
- documentation (#59, #172)
- integration tests (#80)

## v0.5 — Provider 확장

- datago: 실시간 도로교통정보 (#87), 농수축산물 가격정보 (#88)
- datago: 건축물대장 (#90), 사업자등록 상태조회 (#91)
- datago: 의약품 안전사용정보 (#92), 지하철역별 승하차 인원 (#93)
- datago: 기상청 중기예보 (#94)
- datago: 워크넷 채용정보 (#161), 긴급재난문자 (#162), 채권시세정보 (#163)
- datago: NEIS 급식식단정보 (#164), 식품이력추적 (#165), 전국체육시설 (#166)
- datago: 문화시설 (#167), 환경소음 측정망 (#168)

## v1.0 criteria

- public API feels stable
- **production-grade spec 데이터셋 50개 이상** (`make verify` 4단계 기계 검증 + 실API 검증 통과)
- adapter contract proven across multiple provider families (7+ providers)
- plugin discovery로 외부 provider 패키지 등록 가능
- docs/examples sufficient for external users
- breakage policy and versioning discipline established

---

## 본체에 포함하지 않는 것

아래 항목은 kpubdata 코어에 넣지 않습니다. 필요 시 product family 별도 레포로 분리합니다.

| 항목 | 분리 대상 레포 | 상태 |
| :--- | :--- | :--- |
| MCP adapter | `kpubdata-mcp` | 비공개 초기 구현, Live 조회 비활성화, 미출시 |
| HTTP/REST API 서비스 | `kpubdata-api` | 미생성 (필요 시 분리) |
| LLM tool schema / agent helper | `kpubdata-mcp` | 탐색·설명·상태 확인 사용 가능, Live 조회 비활성화 |

---

## 관련 문서

### 이 저장소 내 문서
| 문서 | 설명 |
| :--- | :--- |
| [PRD.md](./PRD.md) | 제품 요구사항 정의 |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 시스템 아키텍처 설계 |
| [API_SPEC.md](./API_SPEC.md) | 파이썬 API 명세 |

### KPubData Product Family
| 저장소 | 역할 | 문서 |
| :--- | :--- | :--- |
| [kpubdata](https://github.com/kpubdata-lab/kpubdata) | **KPubData** — 한국 공공데이터 접근을 위한 독립 Python SDK | 이 문서 |
| [kpubdata-engine](https://github.com/kpubdata-lab/kpubdata-engine) | **KPubData Engine** — SDK 기반 독립 데이터 빌드 및 검증된 스냅샷 생성(MVP) | [ROADMAP.md](https://github.com/kpubdata-lab/kpubdata-engine/blob/main/ROADMAP.md) |
| [kpubdata-mcp](https://github.com/kpubdata-lab/kpubdata-mcp) | **KPubData MCP Server** — 독립 AI 인터페이스(비공개 초기 구현) | [ROADMAP.md](https://github.com/kpubdata-lab/kpubdata-mcp/blob/main/ROADMAP.md) |
| [kpubdata-builder](https://github.com/kpubdata-lab/kpubdata-builder) | **KPubData Builder(레거시)** — 기존 릴리스·호환성 이력 | [ROADMAP.md](https://github.com/kpubdata-lab/kpubdata-builder/blob/main/ROADMAP.md) |
| [kpubdata-studio](https://github.com/kpubdata-lab/kpubdata-studio) | **KPubData Studio** — KPubData Builder 의 시각적 작업공간 (관련 프로젝트) | [ROADMAP.md](https://github.com/kpubdata-lab/kpubdata-studio/blob/main/ROADMAP.md) |
