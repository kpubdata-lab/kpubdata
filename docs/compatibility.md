# Cross-Repo 호환성 매트릭스 및 릴리스 정책

KPubData Product Family는 세 저장소가 독립적으로 릴리스되지만, 함께 사용될 때의 호환성을 보장하기 위해 다음 규칙을 따른다.

| 저장소 | 역할 | Python | 의존 관계 |
| :--- | :--- | :--- | :--- |
| [kpubdata](https://github.com/yeongseon/kpubdata) | 데이터 수집·정규화 코어 | 3.10+ | (없음) |
| [kpubdata-builder](https://github.com/yeongseon/kpubdata-builder) | 빌드 파이프라인 | 3.10+ | `kpubdata` |
| [kpubdata-studio](https://github.com/yeongseon/kpubdata-studio) | 웹 대시보드 | Node **22+** | `kpubdata-builder` (REST) |

전체 아키텍처 관계는 [Product Family 아키텍처](product-family-architecture.md) 문서를 참고한다.

## 1. 호환성 매트릭스

각 행은 builder/studio 릴리스가 명시적으로 검증된 의존 저장소 버전을 표시한다. **빈 셀은 검증되지 않았음을 의미**하며, 동작할 수도 있지만 보장되지는 않는다.

### kpubdata-builder × kpubdata

| kpubdata-builder | kpubdata | 비고 |
| :--- | :--- | :--- |
| 0.4.0.dev0 | 0.6.x | 현재 개발 라인. `pyproject.toml` 의 의존 핀은 `>=0.6.0,<0.7` 이다. |
| 0.1.x | 0.5.x | Medallion(Bronze→Silver→Gold) 파이프라인 + 서비스 façade 도입. |

> **선언과 태그가 어긋나 있다.** builder 의 `pyproject.toml` 은 `0.4.0.dev0` 이고
> 발행된 최신 태그는 `v0.1.0` 이다. studio 는 태그가 없다. 즉 위 표의 첫 행은
> **아직 릴리스되지 않은 상태**를 가리킨다 — 설치 가능한 artifact 로 검증된
> 조합이 아니다. 정리는
> [kpubdata-builder#690](https://github.com/yeongseon/kpubdata-builder/issues/690)
> 에서 한다. 그때까지 버전 번호 대신 커밋 SHA 로 조합을 특정하는 것이 정확하다.

### kpubdata-studio × kpubdata-builder

| kpubdata-studio | kpubdata-builder | 비고 |
| :--- | :--- | :--- |
| 0.4.0 (태그 없음) | 0.4.0.dev0 | studio 는 builder 의 HTTP façade(OpenAPI 3.1, `contract/builder-api.yaml` **v1.28.0**)를 통해 통신한다. |
| (TBD) | 0.1.x | |

> **표 갱신 규칙**: 새 minor 릴리스가 나면, 해당 릴리스가 호환되는 의존 저장소 버전 범위를 표에 새 행으로 추가한다. 이전 행은 보존(EOL 표시 가능)하여 사용자가 자신의 조합을 찾아볼 수 있게 한다.

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

## 6. EOL 및 보안 패치

- minor 라인은 다음 minor 릴리스가 나간 시점부터 **3개월** 동안 PATCH(보안·치명적 버그) 백포트 대상이다.
- pre-1.0 라인(0.x)은 EOL을 보장하지 않지만, 알려진 보안 이슈는 최신 라인에 즉시 반영한다.
