# 외부 전송 데이터 흐름표

이 문서는 kpubdata 제품군(SDK · Builder · Studio)이 **코드상** 어떤 외부 호스트와 통신하는지,
무엇을 보내는지를 적은 사실 기록이다(이슈 #846 의 데이터 흐름 추적 부분).

- 이 문서는 사실만 적는다. **법적 근거, 동의 문구, 위탁·제3자 제공·국외 이전 분류, 결론은 쓰지 않는다.**
  해당 칸은 `결정 필요` 로 두며, 운영 주체를 정하는 메인테이너와 법률 검토의 몫이다
  (베타 약관·개인정보 생애 주기를 정하는 #836 에 의존한다).
- 코드에서 확인하지 못한 것은 `확인 못 함` 으로, 코드에 없는 것은 `없음(코드 기준)` 으로 적는다.
- 호스트의 소재국은 코드나 저장소 문서에 적혀 있는 것만 옮긴다. 적혀 있지 않으면 `문서에 없음` 이다.
- 조사 기준: kpubdata `main`, kpubdata-builder `origin/main`, kpubdata-studio `origin/main`
  (2026-10-11 읽음). Builder · Studio 는 다른 저장소이므로 그쪽 코드가 바뀌면 이 표는 낡는다.

## 1. kpubdata SDK (이 저장소)

SDK 는 라이브러리이며 **자체 서버가 없다.** 텔레메트리 · 오류 추적 · 업데이트 확인 · 메일 · AI 호출은
`없음(코드 기준)` 이다. 네트워크 호출은 `src/kpubdata/transport/http.py` 의 `httpx` 클라이언트 하나를
거쳐 아래 공공데이터 호스트로만 나간다. 호스트는 `src/kpubdata/_hosts.py` 의 `PROVIDER_ALLOWED_HOSTS` 가
정본이며, provider 키는 이 목록에 있는 호스트에만 붙는다([허용 목록](../host-allowlist.md)).

| 수신 호스트 | provider | 소재·운영 | 보내는 것 | 개인정보·키 포함 가능성 |
|---|---|---|---|---|
| `data.go.kr` 및 하위(`apis.data.go.kr`) | datago, localdata, semas | 문서에 없음 | 사용자가 준 Query 필터·페이지 값, provider 키 | 키: 쿼리 파라미터로 포함. 필터 값은 사용자가 넣는 대로 전송(개인정보를 넣으면 그대로 나간다) |
| `api.odcloud.kr` | datago | 문서에 없음 | 위와 같음 | 위와 같음 |
| `openapi.its.go.kr` | datago | 문서에 없음 | 위와 같음 | 위와 같음 |
| `ecos.bok.or.kr` | bok | 문서에 없음 | 위와 같음 | 위와 같음 |
| `kosis.kr` 및 하위 | kosis | 문서에 없음 | 위와 같음 | 위와 같음 |
| `data.krx.co.kr` | krx | 문서에 없음 | 위와 같음 | 위와 같음 |
| `kipo-api.kipi.or.kr` | kipris | 문서에 없음 | 위와 같음 | 위와 같음 |
| `law.go.kr` · `www.law.go.kr` | law | 문서에 없음 | 위와 같음 | 위와 같음 |
| `lofin365.go.kr` · `www.lofin365.go.kr` | lofin | 문서에 없음 | 위와 같음 | 위와 같음 |
| `open.neis.go.kr` | neis | 문서에 없음 | 위와 같음 | 위와 같음 |
| `openapi.seoul.go.kr` · `swopenapi.seoul.go.kr` | seoul | 문서에 없음 | 위와 같음 | 위와 같음 |
| `sgisapi.kostat.go.kr` | sgis | 문서에 없음 | 위와 같음 | 위와 같음 |
| `openapi.foodsafetykorea.go.kr` | fds | 문서에 없음 | 위와 같음 | 위와 같음 |
| `stdict.korean.go.kr` | korean | 문서에 없음 | 위와 같음 | 위와 같음 |

SDK 쪽 사실:

- 로그에 남는 URL 과 파라미터의 키는 마스킹된다(`transport/http.py`, `transport/_sensitive.py`).
  키가 붙은 요청은 응답 캐시에 넣지 않는다.
- 응답 캐시는 로컬 파일이며 기본 꺼짐이다(`KPUBDATA_CACHE`, `KPUBDATA_CACHE_DIR`). 밖으로 나가지 않는다.
- `httpx` 기본값대로 `HTTP_PROXY` 등 환경 변수의 프록시를 따른다. 프록시 운영자는 요청 전체를 볼 수 있다.
- 배포 환경이 `KPUBDATA_<PROVIDER>_EXTRA_HOSTS` 로 허용 호스트를 넓힐 수 있다. 그 호스트는 이 표에 없다.
- 위 호스트에서 한국 공공기관이 응답한다는 것은 도메인에서 짐작할 뿐 코드나 문서로 확인한 것이 아니다.

## 2. kpubdata-builder (데이터셋을 만드는 서버 · CLI)

| 경로 | 켜지는 조건 | 수신처 | 보내는 것 | 개인정보·키 포함 가능성 |
|---|---|---|---|---|
| Hugging Face 게시 (`publishers/huggingface.py`, `service/publish_api.py`) | publish 실행 시. 토큰이 있어야 함 | `huggingface.co` | 토큰, 저장소 생성, 게시 산출물 파일(데이터셋 본문) | 토큰: 요청 헤더 또는 서버 `HF_TOKEN`(다중 사용자 모드에서는 요청 토큰만). 데이터셋 본문에 개인정보가 있으면 그대로 공개·비공개 저장소로 간다 |
| Kaggle 게시 (`publishers/kaggle.py`) | publish 실행 시 | `kaggle.com` (SDK) | Kaggle 사용자명·키, 산출물 파일 | 위와 같음. SDK 는 빈 임시 디렉터리에서 실행해 서버 홈의 `kaggle.json` 을 읽지 않는다 |
| 공공데이터 수집 (kpubdata SDK 경유: `service/provider_probe.py`, 빌드, `verify`) | 빌드·프로브·검증 시 | 1절의 호스트 | provider 키, 데이터셋 파라미터 | 1절과 같음. 키는 로그에서 마스킹 |
| 명세 `kind: url` 소스 수집 (`ingestion/url_fetch.py`) | 해당 소스가 든 명세를 빌드할 때 | **명세가 정한 URL(고정 목록 없음)** | 인증 없는 GET | 보내는 개인정보 없음. https 만, 비공개 IP 거부, 리다이렉트마다 재검증. **호스트 허용 목록은 없음** |
| `agent discover <url>` (`agent/discover.py`) | 수동 CLI | **사용자가 준 URL** | 고정 User-Agent 의 GET | 없음. 호스트 허용 목록 없음 |
| `agent pipeline` (`agent/pipeline.py`) | 수동 CLI | GitHub (`git push`, `gh pr create`) | 브랜치, PR 제목, 데이터셋 이름이 든 고정 본문 | 없음 |
| `verify` (`verify/runner.py`) | 수동 CLI | 명세의 `endpoint.base_url` | 인증 없는 HEAD | 없음 |
| OIDC 로그인 검증 (`service/auth.py`) | `OIDC_ISSUER` 설정 시. 기본 꺼짐 | 환경 변수의 발급자 호스트와 그가 알려 준 `jwks_uri` | GET 만. 사용자 데이터 없음 | 없음(토큰 검증은 내려받은 키로 로컬에서 수행) |
| 운영 점검 `scripts/check_cloudflare_ranges.py` | CI·운영 점검 | `cloudflare.com` | User-Agent 만 | 없음 |

Builder 가 받는 쪽(수신 경로, 외부 호스트로 나가는 것은 아님):

- 공개 진입점은 Cloudflare 프록시 DNS → Caddy → Builder 이며, Cloudflare 는 TLS 를 종단하므로 요청을
  읽을 수 있다고 Builder 문서(`docs/REQUEST_CREDENTIALS.md`)에 적혀 있다.
- 서버는 OCI Compute VM 의 Docker 로 운영한다고 ADR 에 적혀 있으나 **리전·소재국은 어디에도 적혀 있지 않다.**
  이미지는 GHCR 에서 받는다. Studio 정적 파일은 Cloudflare Pages 가 기준 배포로 적혀 있다.

보관(저장소 안에 남는 개인 관련 필드):

| 대상 | 내용 | 비고 |
|---|---|---|
| 사용자 원장 (`service/user_ledger.py`) | 행 키는 `owner_id` 의 단방향 해시, 표시 이름은 **검증된 이메일** | 보유기간 `결정 필요` |
| 실행 제출 (`events/store.py`) | `owner_id` 평문 | 보유기간 `결정 필요` |
| 프로바이더 테스트 (`service/provider_tests.py`) | `owner_id`, SQLite 파일 | 보유기간 `결정 필요` |
| 관리자 감사 로그 (`service/admin_audit.py`) | `owner_id` 평문을 로거로 출력 → 컨테이너 stdout | 컨테이너 로그는 `json-file` 로컬. 외부 전송 코드는 없음 |
| 요청·빌드 로그 | 소유자는 프로세스별 키의 HMAC(불투명) | |
| 자격 증명 | 암호화 저장소. 게시 토큰은 요청 범위로 저장하지 않음 | |
| 업로드·산출물 | 로컬 `/data` 볼륨 | 게시할 때만 HF · Kaggle 로 나감 |
| 백업 | **절차 없음.** 방식은 ADR 에 미정으로 적힘 | `결정 필요` |

Builder 에서 `없음(코드 기준)`: SMTP·메일 발송, Sentry 등 오류 추적, 텔레메트리, 웹훅, 로그 전송, 백업 작업,
객체 저장소, LLM·AI 호출(`stages/silver/pii_advisor.py` 등은 프롬프트 문자열만 만든다).
오류 로그에서 키가 모두 마스킹되는지(HF·Kaggle 예외 문구 포함)는 `확인 못 함` 이다.

## 3. kpubdata-studio (웹 UI)

| 경로 | 켜지는 조건 | 수신처 | 보내는 것 | 개인정보·키 포함 가능성 |
|---|---|---|---|---|
| Ask 어시스턴트 (`features/assistant/provider.ts`) | 사용자가 Ask 창에서 질문을 보낼 때만(사용자 키 지참, BYOK) | **사용자가 정한 base URL** 의 `/chat/completions`. 기본값 `https://api.openai.com/v1`. https 만 허용 | 시스템 프롬프트, 사용자 질문, Builder 에서 모은 근거 JSON(카탈로그·데이터셋 이름과 제목, 출처, 최근 실행 id·상태, 행 수, 컬럼 이름과 dtype). **샘플 행은 읽지 않음** | 사용자 API 키가 `Authorization` 으로 간다. 근거 JSON 은 키 이름(`*key`, `*token`, `*secret`) 과 24자 이상 고엔트로피 문자열을 휴리스틱으로 가린다. **사용자가 질문에 직접 쓴 내용은 가려지지 않는다.** 이메일·subject 가 근거에 들어가는지는 `확인 못 함` |
| Builder API (`shared/lib/builderApi.ts`) | 항상(운영자가 `BUILDER_API_URL` 지정, 미설정 시 `http://localhost:8000`) | Builder | 요청 본문, `Authorization: Bearer`, `X-Provider-Key` | 토큰·provider 키는 메모리에만 두고 URL 에 넣지 않는다 |
| Keycloak / OIDC 로그인 (`features/auth/keycloak.ts`) | `OIDC_ISSUER` 설정 시. 미설정이면 꺼짐 | 환경 변수의 발급자 origin | Authorization Code + PKCE 표준 흐름, 자동 갱신용 iframe | 비밀번호는 Studio 가 보지 못함. 토큰은 메모리에만 |

Studio 사실:

- 사용자 LLM 키는 기본으로 메모리에만 둔다. 사용자가 켜면 `localStorage`(`kpubdata-assist-key`) 에 평문 저장하고 경고를 보인다.
- 설정 화면에 "대화 내용이 사용자가 설정한 외부 LLM 제공자에게 전송된다"는 고지가 있다.
  base URL 이 기본값이 아니면 추가 경고가 뜬다. 전송 직전의 확인 대화상자는 `없음(코드 기준)`.
- 브라우저 CSP 의 `connect-src` 는 `'self' https:` 라서 **어떤 https 호스트로의 연결도 막지 않는다.**
  따라서 LLM 호스트를 CSP 로 제한하고 있지는 않다.
- 앱 런타임에서 `없음(코드 기준)`: 분석·Sentry 등 오류 추적, 글꼴·CDN·외부 이미지·외부 스크립트, 메일 발송.
  (문서 사이트 `mkdocs` 는 `unpkg.com` 의 mermaid 를 불러오며 앱과 별개다.)
- 지원 연락처는 운영자가 정하는 `mailto:`/`https:` 링크일 뿐 전송 코드가 아니다.
- 빌드 시점에만 npm 레지스트리와 Alpine 저장소를 쓴다. 실행 중인 컨테이너는 밖으로 나가지 않는다.

## 4. 분류 · 근거 · 보유 · 재위탁 (결정 필요)

이슈 #846 의 표 열 가운데 코드로 채울 수 없는 칸이다. 어느 것도 이 문서가 정하지 않는다.

| 항목 | 상태 |
|---|---|
| 각 흐름이 운영자 자신의 처리 · 수탁 처리 · 제3자 제공 중 무엇인가 | 결정 필요 |
| 위탁이라면 계약 · 공개 · 감독 확인 | 결정 필요 |
| 국외 이전에 해당하는 흐름과 그 근거 · 고지 · 별도 동의 · 보호조치 | 결정 필요 (수신처 소재국 확인 포함) |
| 선택 기능(AI)과 공개 게시에 "계약 이행에 필요" 예외를 적용할지 | 결정 필요 |
| 보유기간, 재위탁 · 재이전 | 결정 필요 |
| 외부 업체와의 실제 계약, 운영 주체, 서버 소재국 | 결정 필요 |

## 5. 후속 작업 (이 저장소 밖)

- 호스팅 베타에서 외부 전송이 확정되지 않은 경로(Studio 의 Ask, Builder 의 HF · Kaggle 게시)를
  기본 비활성화하는 기능 차단 장치와, 끈 상태에서 네트워크 호출이 0건임을 canary 값으로 확인하는 통합 테스트.
- Builder: 관리자 감사 로그 · 실행 제출의 `owner_id` 평문, `url_fetch` · `discover` 의 호스트 허용 목록 유무 검토.
- Builder: 백업과 보유기간 절차, 서버 리전 문서화.
- Studio: `connect-src` 범위, 전송 직전 확인 UI 검토.

## 6. 이 표를 최신으로 유지하는 방법

`tests/unit/core/test_data_flows_doc.py` 가 `PROVIDER_ALLOWED_HOSTS` 의 모든 호스트와 `src/kpubdata/specs`
의 모든 `endpoint.base_url` 호스트가 1절에 있는지 확인한다. 호스트를 추가하면 이 문서를 같은 PR 에서 고친다.
Builder · Studio 쪽 변경은 이 검사가 잡지 못한다.
