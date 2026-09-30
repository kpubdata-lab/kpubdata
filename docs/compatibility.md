# Cross-Repo 호환성 매트릭스 및 릴리스 정책

KPubData Product Family는 세 저장소가 독립적으로 릴리스되지만, 함께 사용될 때의 호환성을 보장하기 위해 다음 규칙을 따른다.
의존은 **Studio → Builder → KPubData** 한 방향으로만 흐른다([ADR 0007](adrs/0007-independence-rules.md)).

| 저장소 (제품명) | 역할 | Python | 의존 관계 |
| :--- | :--- | :--- | :--- |
| [kpubdata](https://github.com/yeongseon/kpubdata) (KPubData) | 한국 공공데이터 접근을 위한 독립 Python SDK | 3.10+ | (없음) |
| [kpubdata-builder](https://github.com/yeongseon/kpubdata-builder) (KPubData Builder) | KPubData 로 재현 가능한 데이터셋·테이블을 만들고 관리 | 3.10+ | `kpubdata` 공개 API, **릴리스된 버전만** |
| [kpubdata-studio](https://github.com/yeongseon/kpubdata-studio) (KPubData Studio) | KPubData Builder 의 시각적 작업공간 | Node **22+** | Builder HTTP/OpenAPI 계약만 (kpubdata 를 직접 쓰지 않는다) |

전체 아키텍처 관계는 [Product Family 아키텍처](product-family-architecture.md) 문서를 참고한다.

## 1. 호환성 매트릭스

builder 와 studio 는 **한 애플리케이션, 한 버전**이다(ADR 0004 1절). 그래서 표는 두 열이다 —
애플리케이션 버전 × kpubdata 버전.

**kpubdata 열은 범위가 아니라 사실이다.** `pyproject.toml` 의 `kpubdata>=0.8.0,<0.9` 는
의도이고, 릴리스 게이트는 `uv.lock` 이 고정한 **한 버전**으로 돌았다. 그 버전을 적는다.
**빈 셀은 검증되지 않았음을 뜻한다** — 동작할 수도 있지만 보장하지 않는다.

| 애플리케이션 (builder = studio) | kpubdata (릴리스 게이트가 검증한 버전) | 비고 |
| :--- | :--- | :--- |
| main (다음 릴리스) | 0.8.0 | 릴리스가 아니다 — 행은 릴리스 때 확정된다. 의존 핀 `>=0.8.0,<0.9` (builder#882, 2026-09-30). 0.8.0 은 코드 열의 앞자리 0 을 보존해 `str` 로 돌려준다(BREAKING, #613). |
| 0.4.0 | 0.6.0 | 2026-09-28, builder·studio 모두 태그·GitHub Release. Builder API 계약 v1.29.0. 의존 핀 `>=0.6.0,<0.7`. |
| 0.1.x (builder 만) | 0.5.x | studio 가 같은 버전을 쓰기 전. Medallion(Bronze→Silver→Gold) 파이프라인 + 서비스 façade 도입. |

선언과 태그는 맞춰져 있다(builder#690). builder 의 `release.yml`·`docker.yml` 이
`scripts/check_version_consistency.py` 로 `pyproject.toml`·CHANGELOG·태그가 어긋나면 태그와
이미지 발행을 거부하고, studio 의 `release.yml` 은 버전을 고르지 않고 builder 의 최신 릴리스
태그를 그대로 쓴다.

### 표 갱신 절차 (builder#718)

1. builder 릴리스가 끝나면 그 **GitHub Release 노트 마지막 줄**을 본다. `release.yml` 이
   게이트를 통과한 직후 `scripts/release_facts.py` 로 적어 둔 것이다:

   ```
   Tested with kpubdata **0.7.0** (pinned in `uv.lock` while the release gates ran) · Builder API contract **1.32.0**.
   ```

2. 위 표 맨 위(`main` 행 아래)에 새 행을 추가한다 — 애플리케이션 버전, 그 줄의 kpubdata 버전,
   비고에 날짜와 계약 버전.
3. 이전 행은 지우지 않는다(EOL 표시는 가능). 사용자가 자기 조합을 찾아볼 수 있어야 한다.
4. studio 는 builder 의 태그를 따라가므로 행을 따로 만들지 않는다.

## 2. 버전 규약 — Semantic Versioning

세 저장소 모두 [Semantic Versioning 2.0](https://semver.org/lang/ko/)을 따른다.

- **MAJOR**: 공개 API(`API_SPEC.md`/`builder-api.yaml`/`kpubdata-studio` 공개 라우트)에 호환성을 깨는 변경.
- **MINOR**: 후방 호환되는 기능 추가. 예) 새 Provider, 새 Exporter, 새 엔드포인트.
- **PATCH**: 후방 호환되는 버그 수정·문서·내부 리팩토링.

`0.x` 라인은 **pre-1.0 규약**을 따른다. 즉 minor bump가 호환성을 깰 수 있으나, 그럴 때마다 `CHANGELOG.md`에 `BREAKING CHANGE` 마커와 마이그레이션 노트를 동봉한다.

## 3. 공개 API의 정의

각 저장소가 호환성 약속을 거는 "공개 API"의 범위는 다음과 같다.

### kpubdata

- `kpubdata` 최상위에서 import 가능한 심볼(`Client`, `DatasetRef`, `Operation`, `PaginationMode`, `Query`, `RecordBatch`, `QuerySupport`, 정규 예외 등) — [`API_SPEC.md`](https://github.com/yeongseon/kpubdata/blob/main/API_SPEC.md)에 명시된 것.
- Provider adapter가 외부에 노출하는 dataset id 표면(`datago.apt_trade` 등) — `SUPPORTED_DATA.md` 에 표시된 상태 중 호환성 약속 대상이 무엇인지는 상태 모델 재설계(#498)에서 정한다. **"지원" 이라는 손으로 쓴 표기는 근거가 무엇인지 말해주지 않아서 약속의 기준이 될 수 없다** — POLICY 3절이 생성 파일만 기준으로 쓰라고 하는 이유다.
- 정규(canonical) 데이터 모델 — [`CANONICAL_MODEL.md`](https://github.com/yeongseon/kpubdata/blob/main/CANONICAL_MODEL.md).

내부 구현 디테일(transport 헬퍼, provider 내부 모듈 등)은 호환성 약속 대상이 아니다.

### kpubdata-builder

- CLI 표면 — `kpubdata-builder validate`/`preview`/`build` 의 서브커맨드·인자·종료 코드.
- HTTP façade — `contract/builder-api.yaml`(OpenAPI 3.1)에 정의된 엔드포인트·요청/응답 스키마.
- 공개 모델 — `BuildSpec`(YAML 스키마 포함), `BuildResult`, `ServiceResponse`, exporter/publisher 계약 클래스.

### kpubdata-studio

- 사용자 가시 URL 경로와 외부 통합점(builder 호출 contract 준수).

## 4. Breaking change 시 절차

다음 중 하나라도 변경되면 BREAKING이며, 동일 PR에서 의존 저장소에 영향 범위를 명시하고 cross-repo PR을 동반한다.

- 공개 심볼 제거·이름 변경·시그니처 변경.
- 정규 데이터 모델의 필드 제거·필수성(required) 변경.
- HTTP 엔드포인트 제거, 경로/메서드 변경, 응답 스키마의 필드 제거.
- 의존 저장소가 의존하는 동작 정책(예: build 실패 시 응답 코드)의 변경.

PR 본문에 다음을 포함한다:

1. **무엇이 깨졌는가** — 변경 전/후 표.
2. **다른 저장소 영향** — builder/studio가 어느 부분에서 깨지는지, 동반 PR 링크.
3. **마이그레이션 노트** — 사용자/다운스트림 저장소가 따라야 할 단계.

릴리스에 동봉되는 `CHANGELOG.md` 항목에도 동일 정보를 요약해 `BREAKING CHANGE` 헤더로 표시한다.

## 5. 릴리스 조율

- 각 저장소는 독립적으로 릴리스할 수 있지만, **MAJOR 또는 BREAKING MINOR 릴리스는 dependent 저장소와 같은 주(week) 내에 호환 릴리스를 동반**한다.
- 호환 릴리스가 준비되지 않은 상태로 main에 BREAKING을 머지하지 않는다. 필요하다면 long-lived 브랜치를 유지하거나, 변경을 feature flag 뒤에 둔다.
- 릴리스 직후 본 문서의 호환성 매트릭스 표를 갱신한다.

<a id="release-cadence"></a>

### 5.1 릴리스 규칙 — kpubdata 는 수시, 애플리케이션은 월 1회

두 종류의 저장소에 두 가지 규칙을 둔다(#685, 소유자 결정 2026-09-30).

| 저장소 | 규칙 | 게이트 |
|---|---|---|
| **kpubdata** | **수시.** 이유가 있을 때 낸다 — 하위 저장소가 막힘, 보안 수정, 쌓인 변경. **직전 정식 릴리스로부터 7일에 한 번까지** | `release-window` `policy: on-demand` |
| **kpubdata-builder + kpubdata-studio** | **월 1회.** 그 달의 마지막 목요일이 속한 주(월–일)에만. builder 는 수요일까지, studio 는 목요일까지 | `release-window` `policy: monthly` |

**왜 둘로 나누는가.** kpubdata 는 독립 SDK 다([ADR 0007](adrs/0007-independence-rules.md)).
Builder 는 **릴리스된** kpubdata 만 쓴다(Rule 12). 세 저장소를 한 달짜리 기차에 묶으면
kpubdata 의 새 기능을 Builder 가 쓰기까지 최대 한 달이 걸리고, 그 기다림이 규칙 밖의
릴리스를 만든다 — 2026-09 에 kpubdata 가 9/9·9/28·9/30 세 번 나갔고, 0.7.0 과 0.8.0
은 이틀 간격이었다. 반면 builder·studio 는 한 애플리케이션이라 사용자가 받는 것은
한 달에 한 번이어야 "이번 달 릴리스" 가 무언가를 가리킨다.

**날짜는 KST(UTC+9) 로 센다.** 러너의 UTC 달력이 아니라 서울의 달력이 "마지막 주" 를
정한다. 마지막 주의 일요일은 다음 달로 넘어갈 수 있다 — `2026-10` 의 창은 10/26(월)
~ 11/01(일) 이다.

#### kpubdata — 수시

- **7일 간격**은 직전 **정식**(pre-release 가 아닌) GitHub Release 의 게시일부터 센다.
  9/30 에 냈다면 다음은 10/7 부터다.
- 월간 기차에서 빠졌지만 **순서는 그대로다.** builder 가 그 달 창에서 새 kpubdata 를
  받아야 하면 kpubdata 가 먼저 나간다 — 5절의 "같은 주 안에 호환 릴리스" 조건은 그
  순서로 지켜진다.
- **변경이 없으면 내지 않는다.** 이유 없는 릴리스는 없다.
- **kpubdata `main` 은 동결하지 않는다.**

#### kpubdata-builder + kpubdata-studio — 월 1회

| 요일 | 늦어도 이때까지 |
|---|---|
| 월 | 동결 시작 — 이후 builder·studio `main` 에는 릴리스 PR 만 병합한다 |
| 수 | kpubdata-builder |
| 목 | kpubdata-studio, 이어서 1절 매트릭스와 `compatibility.json` 갱신 |

**당기는 것은 이 주 안에서만이다.** 준비가 빨리 됐다고 셋째 주에 내지 않는다.
그 안에서 **요일은 상한이지 약속이 아니다.** 지켜야 하는 것은 **순서**다 — studio 가
builder 의 릴리스를 받는다. builder 가 끝났고 studio 가 준비됐으면 **월요일에 둘 다 내도
된다.** 미루는 쪽만 이유가 필요하다. 공휴일이 끼면 하루씩 민다. 순서는 바꾸지 않는다.

- **릴리스 PR** 은 버전·CHANGELOG·의존 핀·호환성 문서를 바꾸는 PR, 그리고 릴리스
  게이트를 막는 결함의 수정이다. 동결 기간의 다른 PR 은 브랜치에서 기다린다.
  **동결은 studio 가 나가면 끝난다** — 목요일이 아니라.
- **Builder 의 kpubdata 핀 상향 PR 은 언제든 병합한다.** 핀은 릴리스가 아니다 — 그
  변경이 사용자에게 가는 것은 다음 월간 릴리스다.
- **builder 와 studio 는 같은 버전이다**(ADR 0004). 한쪽만 바뀐 릴리스에서도 둘 다
  오르고, 따로 건너뛸 수 없다. 둘 다 변경이 없으면 그 달은 릴리스하지 않는다.

#### 공통

- **Critical patch** — 보안 수정, 또는 릴리스를 막는 결함 — 는 두 규칙 모두를 넘는다.
  **이슈 번호가 있어야 한다.** 워크플로에서는 `critical_patch: true` 와
  `critical_issue: #N` 을 주고, PR 병합 경로에서는 release PR 본문에
  `Critical-Patch: #N` 줄을 둔다(prepare 가 쓴다). 이슈 없는 critical patch 는 거부된다.
- **버전은 날짜가 아니라 내용으로 정한다**(2절). 0.x 에서는 BREAKING 이나 새 기능이
  있으면 minor, 수정만 있으면 patch 다. 버전 번호에 날짜를 넣지 않는다(CalVer 아님).
- **Target Release 는 버전이 아니라 달이다** — `2026-10`. builder·studio 이슈는 그 달의
  창에, kpubdata 이슈는 그 달 안의 어느 릴리스에 실린다는 뜻이다. 끝나지 못한 이슈는
  다음 달로 옮긴다.
- **누가 하는가**: 에이전트는 준비까지 한다 — CHANGELOG 정리, Release 워크플로
  `dry_run`, 버전·핀 PR 초안. 태그 push, GitHub Release 생성, PyPI 환경 승인, 릴리스
  범위 변경은 사람이 한다(POLICY 14절). 규칙 밖의 릴리스를 권하지 않는다 — 막힌 작업은
  kpubdata `main` 을 도는 CI 잡(`kpubdata main ↔ Builder`)으로 진행하고, 핀은 다음
  릴리스에서 올린다.

#### 게이트

`scripts/release_window.py` 가 규칙의 유일한 구현이고, `.github/actions/release-window`
가 그것을 감싸 세 저장소의 `release.yml` 이 **prepare 와 release 두 경로의 첫 단계**로
부른다. 창 밖이면 버전을 계산하거나 브랜치를 만들기 전에 멈춘다. `dry_run` 은 판단을
경고로만 보여주고 계속한다. 거부는 prepare 에서 먼저 일어나므로, PR 병합 경로에서
거부되는 것은 규칙 밖에서 병합된 release PR 뿐이다. 그때도 태그·릴리스 전에 멈추므로
되돌릴 것은 없다 — 올린 버전이 태그 없이 `main` 에 남고, 창 안에서 또는 지금
`critical_patch`·`critical_issue` 와 함께 `mode=release` 로 내면 된다. 실패한 job 을
다시 돌리는 것은 소용없다 — 같은 이벤트를 다시 읽으므로 병합 뒤 본문에 추가한
`Critical-Patch` 줄은 보이지 않는다.

**동결을 막는 게이트는 아직 없다.** 릴리스 자체는 막지만, 동결 기간에 릴리스가 아닌
PR 이 builder·studio `main` 에 들어오는 것은 기계가 막지 않는다.

**첫 회차(2026-09)는 9/28(월) ~ 10/01(목) 에 했다** — 규칙대로면 9/21 ~ 9/27 이었지만
규칙을 쓴 시점에 이미 지났다. 한 번뿐인 예외였고, `2026-10` 부터는 게이트가 규칙
그대로 본다.


## 6. EOL 및 보안 패치

- minor 라인은 다음 minor 릴리스가 나간 시점부터 **3개월** 동안 PATCH(보안·치명적 버그) 백포트 대상이다.
- pre-1.0 라인(0.x)은 EOL을 보장하지 않지만, 알려진 보안 이슈는 최신 라인에 즉시 반영한다.
