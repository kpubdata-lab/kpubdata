# Cross-Repo 호환성 매트릭스 및 릴리스 정책

KPubData Product Family는 세 저장소가 독립적으로 릴리스되지만, 함께 사용될 때의 호환성을 보장하기 위해 다음 규칙을 따른다.

| 저장소 | 역할 | Python | 의존 관계 |
| :--- | :--- | :--- | :--- |
| [kpubdata](https://github.com/yeongseon/kpubdata) | 데이터 수집·정규화 코어 | 3.10+ | (없음) |
| [kpubdata-builder](https://github.com/yeongseon/kpubdata-builder) | 빌드 파이프라인 | 3.10+ | `kpubdata` |
| [kpubdata-studio](https://github.com/yeongseon/kpubdata-studio) | 웹 대시보드 | Node **22+** | `kpubdata-builder` (REST) |

전체 아키텍처 관계는 [Product Family 아키텍처](product-family-architecture.md) 문서를 참고한다.

## 1. 호환성 매트릭스

builder 와 studio 는 **한 애플리케이션, 한 버전**이다(ADR 0004 1절). 그래서 표는 두 열이다 —
애플리케이션 버전 × kpubdata 버전.

**kpubdata 열은 범위가 아니라 사실이다.** `pyproject.toml` 의 `kpubdata>=0.7.0,<0.8` 는
의도이고, 릴리스 게이트는 `uv.lock` 이 고정한 **한 버전**으로 돌았다. 그 버전을 적는다.
**빈 셀은 검증되지 않았음을 뜻한다** — 동작할 수도 있지만 보장하지 않는다.

| 애플리케이션 (builder = studio) | kpubdata (릴리스 게이트가 검증한 버전) | 비고 |
| :--- | :--- | :--- |
| main (다음 릴리스) | 0.7.0 | 릴리스가 아니다 — 행은 릴리스 때 확정된다. 의존 핀 `>=0.7.0,<0.8` (builder#746). kpubdata 0.6.x 는 provider 키가 로그·traceback 에 남을 수 있어 올렸다. |
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

### 5.1 정기 릴리스 — 매월 마지막 주

세 저장소는 **매월 마지막 주**에 정기 릴리스를 한다. 마지막 주는 그 달의 마지막
목요일이 속한 주다.

| 요일 | 늦어도 이때까지 |
|---|---|
| 월 | 동결 시작 — 이후 main 에는 릴리스 PR 만 병합한다 |
| 화 | kpubdata |
| 수 | kpubdata-builder |
| 목 | kpubdata-studio, 이어서 1절 매트릭스와 `compatibility.json` 갱신 |

**당기는 것은 이 주 안에서만이다.** 릴리스는 마지막 주에 한다 — 준비가 빨리 됐다고
셋째 주에 내지 않는다. 한 달에 한 번이라는 것이 이 절의 전부이고, 그게 흔들리면
"이번 달 릴리스" 라는 말이 가리키는 것이 없어진다.

그 안에서 **요일은 상한이지 약속이 아니다.** 지켜야 하는 것은 **순서**다 — 아래
저장소가 위 저장소의 릴리스를 받아야 하고, 5절의 "같은 주 안에 호환 릴리스" 조건이
그 순서로 저절로 지켜진다. 위가 끝났고 아래가 준비됐으면 **월요일에 셋 다 내도 된다.**
하루를 비워두는 것 자체에는 아무 값이 없다.

미루는 쪽만 이유가 필요하다. 공휴일이 끼거나 위 저장소가 늦으면 그 뒤를 하루씩 민다.
순서는 어느 쪽으로도 바꾸지 않는다.

**정기 일정 밖에서 내야 하는 것**은 당기는 것이 아니라 아래의 Critical patch 다. 그
둘을 섞지 않는다 — 하나는 달력이고 하나는 사고다.

- **릴리스 PR** 은 버전·CHANGELOG·의존 핀·호환성 문서를 바꾸는 PR, 그리고 릴리스
  게이트를 막는 결함의 수정이다. 동결 기간의 다른 PR 은 브랜치에서 기다린다.
  **동결은 studio 가 나가면 끝난다** — 목요일이 아니라. 당겨서 끝내면 동결도 같이
  짧아지고, 그게 당길 이유다.
- **버전은 날짜가 아니라 내용으로 정한다**(2절). 0.x 에서는 BREAKING 이나 새 기능이
  있으면 minor, 수정만 있으면 patch 다. 버전 번호에 날짜를 넣지 않는다(CalVer 아님).
- **builder 와 studio 는 같은 버전이다**(ADR 0004). 둘은 함께 배포되는 한
  애플리케이션이고, 한쪽만 바뀐 릴리스에서도 둘 다 오른다. 그 대가로 "이
  애플리케이션은 0.4.0 이다" 를 한 문장으로 말할 수 있고, 1절 매트릭스는
  **2열**(애플리케이션 버전 × kpubdata 버전)로 줄어든다.
- **변경이 없으면 건너뛴다 — kpubdata 에만 해당한다.** builder·studio 는 버전이
  묶여 있어 따로 건너뛸 수 없다. 셋 다 변경이 없으면 그 달은 릴리스하지 않는다.
- **Target Release 는 버전이 아니라 달이다** — `2026-10`. 이슈를 만들 때는 minor 일지
  patch 일지 알 수 없다. 그 달에 끝나지 못한 이슈는 다음 달로 옮긴다.
- **정기 일정 밖의 릴리스**: Critical(POLICY 8절)은 기다리지 않고 patch 로 낸다.
  다른 저장소나 외부 제출이 특정 수정을 기다릴 때도 patch 를 먼저 낸다.
- **누가 하는가**: 에이전트는 준비까지 한다 — CHANGELOG 정리, Release 워크플로
  `dry_run`, 버전·핀 PR 초안. 태그 push, GitHub Release 생성, PyPI 환경 승인, 릴리스
  범위 변경은 사람이 한다(POLICY 14절).

**첫 회차는 2026-09 이고, 2026-09-28(월) ~ 10-01(목) 에 한다.** 규칙대로면 9월 창은
9/21~9/24 인데 이 문서를 쓴 시점에 이미 지났다. 목요일이 10월로 넘어가지만 이 회차가
닫는 것은 9월 작업이므로 `2026-09` 로 센다 — 한 번뿐인 예외다. 다음 회차부터는 규칙
그대로이고, `2026-10` 은 10/26 ~ 10/29 다.

> **동결을 막는 게이트는 아직 없다.** 지금은 규칙만 있고, 동결 기간에 릴리스가 아닌
> PR 이 들어오는 것을 기계가 막지 않는다. [VERIFICATION 3절](governance/VERIFICATION.md)
> 이 "게이트 없는 규칙은 희망이다" 라고 말하는 그 상태다. **2026-09 회차를 한 번
> 돌려본 뒤** 실제로 어긴 적이 있는지 보고 CI 체크를 붙일지 정한다. 그때 판단하기로
> 한 것이지, 잊은 것이 아니다.


## 6. EOL 및 보안 패치

- minor 라인은 다음 minor 릴리스가 나간 시점부터 **3개월** 동안 PATCH(보안·치명적 버그) 백포트 대상이다.
- pre-1.0 라인(0.x)은 EOL을 보장하지 않지만, 알려진 보안 이슈는 최신 라인에 즉시 반영한다.
