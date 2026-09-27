# Roadmap — KPubData

> **이 문서는 작업 진행상태의 정본이 아니다.** 방향(NOW / NEXT / LATER)만 적는다.
> Issue 의 Status · Priority · Epic · Target Release 는 GitHub Project 에서 관리한다 — [POLICY.md](./docs/governance/POLICY.md) 2.1절.
> 데이터셋 지원 상태는 여기에 손으로 적지 않는다 — spec 과 evidence 에서 생성되는 `SUPPORTED_DATA.md` · `docs/status.md` 가 기준이다(3절).

> kpubdata는 **한국 공공데이터 접근 코어 프레임워크**에 집중합니다.
> 목표는 대한민국에서 가장 많이 쓰이는 공공데이터 **50~100개를 production-grade로 접근할 수 있는 표준 레이어**를 제공하는 것입니다.
> MCP, HTTP API 등 서비스 레이어는 본체에 포함하지 않으며, 필요 시 별도 레포(`kpubdata-mcp` 등)로 분리합니다.

## 개발 3축

| 축 | 설명 | 대표 이슈 |
| :--- | :--- | :--- |
| **Core** | 핵심 계약(contract), 스키마, 메타데이터, discovery 안정화 | #55, #57, #63 |
| **Plugin Ecosystem** | entry-point plugin discovery, provider scaffolding 도구 | #112, #61 |
| **Provider Adapters** | 기관별 어댑터 확장 (datago, localdata, semas, bok, ...) | #87-#94, #161-#168 |

---

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
| MCP adapter | `kpubdata-mcp` | 미생성 (필요 시 분리) |
| HTTP/REST API 서비스 | `kpubdata-api` | 미생성 (필요 시 분리) |
| LLM tool schema / agent helper | `kpubdata-mcp` | 미생성 (필요 시 분리) |

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
| [kpubdata](https://github.com/yeongseon/kpubdata) | **Access** — 데이터 접근 프레임워크 | 이 문서 |
| [kpubdata-builder](https://github.com/yeongseon/kpubdata-builder) | **Generation** — 데이터셋 생성/검증/퍼블리싱 | [ROADMAP.md](https://github.com/yeongseon/kpubdata-builder/blob/main/ROADMAP.md) |
| [kpubdata-studio](https://github.com/yeongseon/kpubdata-studio) | **Experience** — 빌드 작성/실행 시각적 인터페이스 | [ROADMAP.md](https://github.com/yeongseon/kpubdata-studio/blob/main/ROADMAP.md) |
