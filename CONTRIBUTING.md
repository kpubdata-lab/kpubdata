# KPubData 기여 가이드 (CONTRIBUTING.md)

> **프로젝트 관리·리뷰 정책의 정본은 [POLICY.md](./docs/governance/POLICY.md) 하나다.**
> Epic · Issue · Priority · Review Level · Verification · Release 규칙은 그 문서를 따른다.
> 이 문서에는 이 저장소 고유의 절차(빌드 명령, 디렉터리 규칙)만 남긴다.
> 충돌하면 POLICY.md 가 우선한다.

KPubData 프로젝트에 관심을 가져주셔서 감사합니다! 이 프로젝트는 대학생을 포함한 모든 초보 개발자의 첫 기여를 환영합니다. 오픈소스 기여가 처음이라도 괜찮습니다. 이 가이드를 따라 차근차근 시작해 보세요.

## 1. 환영 인사 및 프로젝트 소개

KPubData는 공공데이터를 더 쉽고 표준화된 방식으로 다루기 위한 프로젝트 패밀리입니다.
- **kpubdata**: 핵심 라이브러리 (공공데이터 어댑터 엔진)
- **kpubdata-builder**: 데이터를 가공하고 내보내는 도구
- **kpubdata-studio**: 데이터를 시각화하고 관리하는 웹 대시보드

이 레포지토리(`kpubdata`)는 다양한 공공데이터 API를 하나의 표준 인터페이스로 연결하는 역할을 합니다.

## 2. 개발 환경 설정 (처음부터 끝까지)

Python 코드를 수정하고 테스트하기 위한 환경을 만들어 봅시다.

**Step 1: 필수 도구 설치**
*   **Git 설치**: [git-scm.com](https://git-scm.com)에서 설치하세요. — 설치 확인: `git --version`
*   **Python 3.10+ 설치**: [Python 공식 홈페이지](https://www.python.org/downloads/)에서 설치하세요. — 설치 확인: `python --version`
*   **uv 설치**: `uv`는 Python 패키지를 아주 빠르게 관리해 주는 도구입니다. — 설치 확인: `uv --version`
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```
*   **GitHub 계정 및 SSH 설정**: GitHub 계정이 필요합니다. [GitHub SSH 설정 가이드](https://docs.github.com/en/authentication/connecting-to-github-with-ssh)를 참고해 내 컴퓨터와 연결하세요.

**Step 2: 프로젝트 Fork & Clone**
```bash
# 1. GitHub 웹에서 오른쪽 상단의 'Fork' 버튼을 클릭해 내 계정으로 복사합니다.

# 2. 내 컴퓨터로 가져오기 (YOUR_USERNAME 부분을 본인 아이디로 바꾸세요)
git clone https://github.com/YOUR_USERNAME/kpubdata.git
cd kpubdata

# 3. 원본 저장소를 upstream으로 등록 (나중에 최신 코드를 받기 위해)
git remote add upstream https://github.com/yeongseon/kpubdata.git
```

**Step 3: 개발 환경 구축**
터미널에서 아래 명령어를 순서대로 입력하세요.
```bash
uv sync --extra dev    # 필요한 패키지 모두 설치
uv run pytest          # 모든 테스트 통과 확인
uv run ruff check .    # 코드 스타일 확인
uv run mypy src        # 타입 체크
```
> 이 4개 명령어가 모두 성공하면 개발 준비 끝!

## 3. 브랜치 전략과 협업 규칙

규칙은 적지만, 반드시 지킵니다. 모르는 것이 있다면 언제든 물어보세요.

### 3-1. 브랜치(Branch)란?
브랜치는 원본 코드의 안전한 복사본에서 작업하는 것입니다. 내가 마음껏 코드를 수정해도 다른 사람의 작업이나 원본 코드에는 아무런 영향을 주지 않습니다. 작업이 완료되면 '합쳐달라'고 요청(Pull Request)하면 됩니다.

### 3-2. 브랜치 전략 (Git Graph)

```mermaid
gitgraph
    commit id: "initial"
    branch feat/issue-1-add-adapter
    checkout feat/issue-1-add-adapter
    commit id: "feat: add skeleton"
    commit id: "feat: implement parser"
    checkout main
    merge feat/issue-1-add-adapter id: "PR #1 merged"
    branch fix/issue-2-typo
    checkout fix/issue-2-typo
    commit id: "fix: typo in docs"
    checkout main
    merge fix/issue-2-typo id: "PR #2 merged"
```

### 3-3. 브랜치 이름 규칙
항상 목적에 맞는 접두사를 사용하세요.

| 접두사 | 용도 | 예시 |
| :--- | :--- | :--- |
| `feat/issue-<번호>-<설명>` | 새로운 기능 추가 | `feat/issue-12-add-bus-adapter` |
| `fix/issue-<번호>-<설명>` | 버그 수정 | `fix/issue-5-fix-xml-parse` |
| `docs/<설명>` | 문서 수정 (이슈 번호 생략 가능) | `docs/update-readme` |

### 3-4. 전체 작업 흐름 (Workflow)

```mermaid
flowchart TD
    A[1. GitHub에서 Fork] --> B[2. git clone]
    B --> C[3. git checkout -b feat/issue-번호-설명]
    C --> D[4. 코드 수정]
    D --> E[5. git add + git commit]
    E --> F{더 수정할 것?}
    F -->|Yes| D
    F -->|No| G[6. git push origin 브랜치이름]
    G --> H[7. GitHub에서 PR 생성]
    H --> I[8. 리뷰 & 머지]
```

**실제 터미널 명령어 순서:**

```bash
# 1. 원본 저장소에서 최신 코드를 받아옵니다
git checkout main
git pull upstream main

# 2. 새로운 작업 브랜치를 만듭니다
git checkout -b feat/issue-12-add-bus-adapter

# 3. 코드를 수정하고 변경 사항을 기록(커밋)합니다
git add .
git commit -m "feat: add bus arrival adapter skeleton"

# 4. 내 GitHub 저장소로 올립니다
git push origin feat/issue-12-add-bus-adapter

# 5. GitHub 웹사이트에서 'Compare & pull request' 버튼을 눌러 PR을 생성합니다.
```

### 3-5. 커밋 메시지 규칙
커밋 메시지는 '무엇을 왜 바꿨는지' 설명합니다.

| 접두사 | 의미 | 예시 |
| :--- | :--- | :--- |
| `feat:` | 새 기능 추가 | `feat: add air quality adapter` |
| `fix:` | 버그 수정 | `fix: handle empty XML response` |
| `docs:` | 문서 수정 | `docs: update API spec` |
| `test:` | 테스트 추가/수정 | `test: add parser unit tests` |
| `refactor:` | 리팩토링 (코드 구조 개선) | `refactor: simplify transport layer` |

### 3-6. 절대 금지 사항
- **`main` 브랜치에 직접 push 금지**: 모든 작업은 브랜치에서 진행하세요.
- **`git push --force` 금지**: 특히 `main` 브랜치나 공유 브랜치에는 절대 사용하지 마세요.
- **타인의 브랜치 건드리지 않기**: 내가 만들지 않은 브랜치를 삭제하거나 이름을 바꾸지 마세요.
- **모르면 물어보기**: 추측해서 실행하지 말고, 이슈나 채팅방에 질문하세요.

### 3-7. PR 올리기 전 최종 체크리스트
이 4가지 명령어가 모두 성공해야 PR이 승인될 수 있습니다.

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```


## 4. 코딩 규칙 (Coding Convention)

우리는 깨끗한 코드를 유지하기 위해 몇 가지 규칙을 지킵니다.

- **타입 힌트**: 모든 함수에는 타입을 명시해야 합니다. `Any` 타입은 사용하지 않습니다.
- **문서화 (Docstring)**: 함수나 클래스가 무엇을 하는지 간단한 설명을 적어주세요.
- **포맷팅**: `uv run ruff format .` 명령어로 코드 스타일을 자동으로 맞출 수 있습니다.
- **Import**: 파일 맨 위에 `from __future__ import annotations`를 추가해 주세요.

## 5. 내가 할 일에 따라 수정할 파일 찾기

### 프로젝트 파일 구조 한눈에 보기

```text
kpubdata/
├── src/kpubdata/
│   ├── providers/          ← ⭐ 어댑터 코드 (가장 자주 수정)
│   │   ├── seoul/           ← 서울 열린데이터광장 어댑터
│   │   │   ├── __init__.py
│   │   │   ├── adapter.py   ← 핵심 로직 (API 호출, 파싱)
│   │   │   └── catalogue.json ← 데이터셋 목록 정의
│   │   ├── datago/          ← 공공데이터포털 어댑터
│   │   ├── bok/             ← 한국은행 어댑터
│   │   └── ...              ← 기관별 폴더
│   ├── core/               ← 핵심 추상 클래스 (수정 드묾)
│   ├── transport/           ← HTTP 통신 (수정 드묾)
│   ├── client.py            ← 사용자 진입점
│   └── exceptions.py        ← 공통 에러
├── tests/
│   ├── fixtures/            ← ⭐ API 응답 샘플 (JSON 파일)
│   │   └── seoul/           ← 기관별 폴더
│   ├── unit/providers/      ← ⭐ 유닛 테스트
│   │   └── seoul/
│   │       └── test_adapter.py
│   └── contract/            ← ⭐ 계약 테스트 (표준 인터페이스 검증)
│       └── test_seoul.py
├── docs/providers/          ← ⭐ 기관별 사용 문서
│   └── seoul.md
├── SUPPORTED_DATA.md        ← ⭐ 지원 현황 (PR마다 업데이트)
├── CONTRIBUTING.md          ← 이 파일!
└── README.md
```

### 시나리오별 "어디를 수정해야 하나요?"

#### 📝 시나리오 A: 문서만 수정하고 싶어요 (가장 쉬움)

| 하고 싶은 일 | 수정할 파일 |
|---|---|
| README 오타 수정 | `README.md` |
| 사용 예제 추가 | `docs/providers/<기관>.md` |
| 지원 현황 업데이트 | `SUPPORTED_DATA.md` |

#### 🔧 시나리오 B: 기존 어댑터에 새 데이터셋 추가

예: 서울 어댑터에 새로운 API 추가

| 순서 | 수정할 파일 | 설명 |
|:---:|---|---|
| 1 | `tests/fixtures/seoul/<새이름>_success.json` | 실제 API 응답을 저장 |
| 2 | `src/kpubdata/providers/seoul/catalogue.json` | 데이터셋 정보 등록 |
| 3 | `tests/unit/providers/seoul/test_adapter.py` | 유닛 테스트 추가 |
| 4 | `tests/contract/test_seoul.py` | 계약 테스트 추가 |
| 5 | `docs/providers/seoul.md` | 사용법 문서화 |
| 6 | `SUPPORTED_DATA.md` | 지원 현황 업데이트 |

> 💡 **팁**: `adapter.py`를 수정할 필요가 없는 경우도 많습니다! catalogue.json에 데이터셋을 등록하면 기존 어댑터 로직이 자동으로 처리해주는 구조입니다.

#### 🚀 시나리오 C: 완전히 새로운 기관 어댑터 추가

예: 기상청 API를 새로 연동

| 순서 | 수정/생성할 파일 | 설명 |
|:---:|---|---|
| 1 | `src/kpubdata/providers/kma/__init__.py` | 패키지 초기화 |
| 2 | `src/kpubdata/providers/kma/adapter.py` | 어댑터 구현 |
| 3 | `src/kpubdata/providers/kma/catalogue.json` | 데이터셋 목록 |
| 4 | `src/kpubdata/providers/manifest.py` | provider 등록 추가 |
| 5 | `tests/fixtures/kma/<dataset>_success.json` | 응답 샘플 |
| 6 | `tests/unit/providers/kma/test_adapter.py` | 유닛 테스트 |
| 7 | `tests/contract/test_kma.py` | 계약 테스트 |
| 8 | `docs/providers/kma.md` | 사용법 문서 |
| 9 | `SUPPORTED_DATA.md` | 지원 현황 등록 |

> ⚠️ 처음 기여라면 시나리오 A 또는 B부터 시작하는 것을 추천합니다!

### 실제 예시: seoul 어댑터 구조 뜯어보기

이해를 돕기 위해 실제 서울 어댑터의 파일을 살펴봅시다.

**`src/kpubdata/providers/seoul/catalogue.json`** (데이터셋 정의)
```json
[
  {
    "dataset_key": "bike_realtime",
    "name": "서울시 공공자전거 따릉이 실시간 대여정보",
    "base_url": "http://openapi.seoul.go.kr:8088",
    "default_operation": "bikeList",
    "envelope_key": "rentBikeStatus",
    "required_path_params": []
  }
]
```

**`tests/fixtures/seoul/bike_realtime_success.json`** (API 응답 샘플)
```json
{
  "rentBikeStatus": {
    "list_total_count": 5,
    "RESULT": { "CODE": "INFO-000", "MESSAGE": "정상" },
    "row": [ { "stationName": "102. 망원역 1번출구", ... } ]
  }
}
```

> 이 두 파일만 추가하면 기존 adapter.py 로직이 새 데이터셋을 자동으로 처리합니다!

---

## 6. 첫 번째 어댑터(Adapter) 추가하기 — 상세 가이드

### Step 1: API 응답을 파일로 저장 (Fixture 만들기)

먼저 연동할 API를 브라우저나 curl로 호출해서 응답을 복사합니다.

```bash
# 예: 서울시 따릉이 실시간 대여정보
curl "http://openapi.seoul.go.kr:8088/YOUR_KEY/json/bikeList/1/5" > response.json
```

이 응답을 `tests/fixtures/<기관명>/<데이터셋명>_success.json`에 저장합니다.

### Step 2: catalogue.json에 데이터셋 등록

`src/kpubdata/providers/<기관명>/catalogue.json`을 열어 배열에 새 항목을 추가합니다.
각 필드의 의미:

| 필드 | 설명 | 예시 |
|---|---|---|
| `dataset_key` | 데이터셋 고유 ID | `"bike_realtime"` |
| `name` | 한국어 이름 | `"서울시 공공자전거 실시간 대여정보"` |
| `base_url` | API 기본 URL | `"http://openapi.seoul.go.kr:8088"` |
| `default_operation` | 기본 서비스명 | `"bikeList"` |
| `envelope_key` | 응답 감싸는 키 (서비스명과 다를 때만) | `"rentBikeStatus"` |
| `required_path_params` | URL 경로에 필요한 파라미터 | `["stationName"]` 또는 `[]` |

### Step 3: 테스트 작성

```python
# tests/unit/providers/seoul/test_adapter.py 에 추가
def test_bike_realtime_parsing(seoul_adapter, mock_transport):
    """bike_realtime fixture가 올바르게 파싱되는지 확인"""
    mock_transport.set_response("fixtures/seoul/bike_realtime_success.json")
    result = seoul_adapter.query_records(dataset_ref, query)
    assert len(result.items) > 0
    assert result.total_count is not None
```

### Step 4: 확인하고 PR 올리기

```bash
uv run pytest tests/unit/providers/seoul/ -v  # 내 테스트만 먼저 확인
uv run pytest                                  # 전체 테스트 통과 확인
uv run ruff check .                            # 스타일 확인
uv run mypy src                                # 타입 확인
```

모두 통과하면 커밋하고 PR을 올리세요!

---

## 7. PR 가이드 및 체크리스트

PR을 보낼 때 제목은 `[#이슈번호] 간단한 설명` 형식을 지켜주세요.

**보내기 전 체크리스트:**
- [ ] `uv run pytest` 결과가 모두 통과(Pass)인가요?
- [ ] `uv run ruff check .`에서 경고가 없나요?
- [ ] `uv run mypy src`에서 타입 오류가 없나요?
- [ ] 새 데이터셋 추가 시 `SUPPORTED_DATA.md`를 업데이트했나요?

## 8. 자주 하는 실수와 해결법

| 실수 | 원인 | 해결 |
|---|---|---|
| `ModuleNotFoundError` | 환경 설정 안 됨 | `uv sync --extra dev` 다시 실행 |
| `ruff` 오류 | 코드 스타일 불일치 | `uv run ruff format .`으로 자동 수정 |
| `mypy` 타입 오류 | 타입 힌트 누락 | 함수 인자/반환값에 타입 추가 |
| 테스트 실패 | fixture 파일 경로 오류 | `tests/fixtures/<기관>/` 경로 확인 |
| `git push` 거부 | main에 직접 push 시도 | 브랜치 만들어서 push |

## 9. AI 에이전트를 활용한 기여 워크플로우

최근 개발 환경에서는 **AI 코딩 에이전트**(GitHub Copilot, Cursor, Windsurf, OpenCode 등)를 활용하여 이슈 분석부터 코드 작성, 리뷰, PR까지 전 과정을 진행할 수 있습니다. "사람이 방향을 잡고, 에이전트가 실행하고, 사람이 검증한다"는 흐름입니다.

### 전체 흐름 한눈에 보기

```mermaid
flowchart TD
    A[1. Issue 선택] --> B[2. 에이전트에게 설계 요청]
    B --> C[3. 에이전트가 코드 작성]
    C --> D[4. 에이전트에게 자체 리뷰 요청]
    D --> E[5. 품질 검사 통과 확인]
    E --> F{통과?}
    F -->|No| C
    F -->|Yes| G[6. PR 생성]
    G --> H[7. 다른 에이전트/사람이 리뷰]
    H --> I{승인?}
    I -->|No| J[8. 리뷰 피드백 반영]
    J --> E
    I -->|Yes| K[9. 머지]
```

### Step 1: Issue 가져오기

GitHub Issues에서 작업할 이슈를 고릅니다. 에이전트에게 이슈를 분석시키는 것도 좋은 시작입니다.

```text
# 에이전트에게 이렇게 요청하세요:
"GitHub issue #42를 읽고, 어떤 파일을 수정해야 하는지 분석해줘."
```

> 💡 **팁**: 에이전트가 이슈를 읽고 관련 코드를 탐색하면, 수정 범위를 파악하는 시간이 크게 줄어듭니다.

### Step 2: 설계 요청

바로 코드를 쓰라고 하지 마세요. 먼저 **설계(계획)**를 요청합니다. 에이전트가 잘못된 방향으로 코드를 쓰면 되돌리기 어렵습니다.

```text
"이 이슈를 해결하기 위한 설계 계획을 세워줘.
 - 어떤 파일을 수정할 건지
 - 어떤 함수를 추가/변경할 건지
 - 테스트는 어떻게 작성할 건지
 코드 작성은 아직 하지 마."
```

설계 결과를 읽고 **내가 이해할 수 있는지** 확인하세요. 이해가 안 되면 질문하세요. 내가 이해 못 하는 코드는 리뷰도 못 합니다.

### Step 3: 코드 작성

설계가 괜찮으면 구현을 시작시킵니다.

```text
"설계대로 구현해줘. AGENTS.md와 PROVIDER_ADAPTER_CONTRACT.md 규칙을 따라서."
```

에이전트가 코드를 작성하는 동안 지켜볼 것:
- 기존 코드 패턴을 따르고 있는가?
- `as any`, `type: ignore` 같은 꼼수를 쓰지 않는가?
- 테스트도 함께 작성하고 있는가?

### Step 4: 자체 리뷰 요청

코드 작성이 끝나면 에이전트에게 **스스로 리뷰**하게 합니다. 사람 리뷰어가 지적할 것을 미리 잡을 수 있습니다.

```text
"방금 작성한 코드를 리뷰해줘.
 - 누락된 edge case가 있는지
 - 기존 코드 스타일과 다른 부분이 있는지
 - 테스트가 충분한지
 문제를 발견하면 수정해."
```

### Step 5: 품질 검사 (Quality Gate)

PR을 올리기 전에 반드시 통과해야 하는 명령어들입니다:

```bash
uv run ruff check .          # 코드 스타일
uv run ruff format --check . # 포맷팅
uv run mypy src              # 타입 검사
uv run pytest                # 테스트
mkdocs build --strict        # 문서 빌드 (docs 수정 시)
```

하나라도 실패하면 에이전트에게 수정을 요청하세요:

```text
"pytest에서 test_parse_xml이 실패해. 에러 메시지 보고 수정해줘."
```

### Step 6: PR 생성

모든 검사가 통과하면 커밋하고 PR을 생성합니다. 에이전트에게 PR 생성까지 시킬 수 있습니다.

```text
"변경사항을 커밋하고 PR을 만들어줘. 이슈 #42를 해결하는 내용이야."
```

### Step 7: 상호 리뷰 (Cross-Review)

PR이 올라가면 **다른 에이전트 또는 다른 사람**이 리뷰합니다. 이것이 에이전트 코딩의 핵심입니다:

| 리뷰 방법 | 설명 | 언제 사용 |
|---|---|---|
| 🤖 에이전트 → 에이전트 | 다른 에이전트(Oracle 등)에게 PR diff를 리뷰 요청 | 빠른 피드백이 필요할 때 |
| 👤 사람 → 에이전트 코드 | 사람이 에이전트가 작성한 코드를 검토 | 최종 승인 전 |
| 🤖 에이전트 → 사람 코드 | 에이전트에게 다른 사람의 PR을 리뷰하게 요청 | 리뷰 학습용 |

```text
# 다른 에이전트에게 리뷰 요청:
"PR #42의 변경사항을 리뷰해줘. 코드 품질, 테스트 충분성, 보안 이슈를 확인해."
```

### Step 8: 피드백 반영 & 머지

리뷰에서 수정 요청이 오면:

```text
"PR #42에 리뷰 코멘트가 달렸어. 읽고 수정 사항을 반영해줘."
```

수정 후 다시 Quality Gate를 통과시키고, 승인을 받으면 머지합니다.

### 실전 예시: 전체 대화 흐름

```text
나: "Issue #42를 분석하고 설계 계획을 세워줘."
🤖: "분석 결과: src/kpubdata/transport/decode.py에서 ValueError를 ParseError로 변경..."

나: "좋아, 구현해줘."
🤖: (코드 작성 + 테스트 작성)

나: "자체 리뷰하고 문제 있으면 수정해."
🤖: "edge case 하나 발견해서 수정했습니다."

나: "pytest 돌려줘."
🤖: "✅ 전부 통과"

나: "커밋하고 PR 만들어줘."
🤖: "PR #43 생성 완료: https://github.com/.../pull/43"

나: "(다른 에이전트에게) PR #43 리뷰해줘."
🤖₂: "전체적으로 좋습니다. 한 가지 제안: ..."

나: "(원래 에이전트에게) 리뷰 반영해줘."
🤖: "수정 완료, force push 하지 않고 새 커밋으로 추가했습니다."

나: "머지해."
🤖: "✅ PR #43 머지 완료"
```

### 주의사항

| ❌ 하지 마세요 | ✅ 이렇게 하세요 |
|---|---|
| 에이전트 결과를 검증 없이 PR 올리기 | 항상 Quality Gate 통과 확인 후 PR |
| 이해 못 하는 코드 그대로 커밋 | 에이전트에게 설명을 요청하고 이해한 후 진행 |
| 하나의 에이전트만으로 리뷰 없이 머지 | 반드시 다른 시각(다른 에이전트/사람)의 리뷰 거치기 |
| 에러나면 무작정 "고쳐줘" 반복 | 에러 메시지를 읽고, 구체적으로 무엇이 문제인지 전달 |

> 📖 더 자세한 단계별 실습은 [AI 에이전트 워크플로우 튜토리얼](./docs/tutorial-ai-agent-workflow.md)을 참고하세요.

---

## 10. 도움 요청하기

모르는 것이 있다면 언제든 GitHub Issues에 질문을 남기세요. "이게 뭐죠?", "설치가 안 돼요" 같은 질문도 환영합니다. 누구나 처음은 어렵습니다. 함께 해결해 나가요!

---

## 관련 문서

### 이 저장소 내 문서
| 문서 | 설명 |
| :--- | :--- |
| [AGENTS.md](./AGENTS.md) | 에이전트 및 개발 규칙 가이드 |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 시스템 아키텍처 설계 |
| [PROVIDER_ADAPTER_CONTRACT.md](./PROVIDER_ADAPTER_CONTRACT.md) | 어댑터 구현 규약 (필독!) |
| [ROADMAP.md](./ROADMAP.md) | 프로젝트 로드맵 및 단계별 계획 |
| [API_SPEC.md](./API_SPEC.md) | 파이썬 API 명세 |

### KPubData Product Family
| 저장소 | 문서 | 설명 |
| :--- | :--- | :--- |
| [kpubdata-builder](https://github.com/yeongseon/kpubdata-builder) | [CONTRIBUTING.md](https://github.com/yeongseon/kpubdata-builder/blob/main/CONTRIBUTING.md) | Builder 기여 가이드 |
| [kpubdata-studio](https://github.com/yeongseon/kpubdata-studio) | [CONTRIBUTING.md](https://github.com/yeongseon/kpubdata-studio/blob/main/CONTRIBUTING.md) | Studio 기여 가이드 |
