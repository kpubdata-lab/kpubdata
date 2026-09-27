# ADR 0005: 기본은 관대하게, 불일치는 반드시 드러낸다

## 상태

채택됨(Accepted) — 2026-09-28

## 요약 (English summary)

> Column casting stays lenient and all-or-nothing, but a mismatch stops being
> invisible: every query carries a `ValidationReport` naming the fields that
> disagreed, how many values failed and what they looked like. Strict mode is opt-in
> and fails only on `uncastable`. An **absent** report means "not examined" and must
> never be read as "no problems".

## 문제

spec 의 `fields[].type` 과 실제 데이터가 다르면 컬럼이 캐스팅되지 않는다. 그것은
의도된 정책이다. 문제는 **그 사실이 남지 않는다**는 것이었다.

```python
if not castable:
    logger.debug("leaving column uncast: ...")
    continue
```

`logger.debug` 한 줄이 유일한 흔적이고, 기본 로거 레벨이 WARNING 이면 그것조차 사라진다.
그리고 **첫 실패에서 `break`** 하므로 몇 건이 틀렸는지도 모른다.

이 프로젝트는 "지원한다" 는 말의 근거를 fixture·contract 테스트로 둔다. spec 과 현실의
불일치는 **그 근거 밖에서 조용히 쌓였다.**

## 결정

### 1. 캐스팅 정책은 바꾸지 않는다

컬럼 단위, 전부 성공할 때만 캐스팅한다. 행 단위로 하면 한 컬럼에 int 와 str 이 섞인다 —
아파트 실거래가의 `aptDong` 은 대부분 `"105"` 인데 일부 행이 동 이름이다. 표로 다루는
소비자에게 그 컬럼은 타입이 없는 컬럼이 된다.

**이 결정은 옳고 유지한다.** 바꾸는 것은 은닉이다.

### 2. 리포트는 선택이 아니다

모든 질의가 `ValidationReport` 를 싣는다. 이슈가 없어도 싣는다.

```
uncastable   선언된 타입으로 캐스팅 실패
missing      응답에 그 필드가 없다
undeclared   spec 에 없는 키가 응답에 있다 — 제공기관이 뭔가 추가했다
```

세 번째가 **drift 탐지**다. 지금까지 아무것도 감지하지 못하던 방향이다.

`failed_count` 와 `sample_values`(최대 3개)를 담기 위해 **첫 실패에서 멈추지 않고 끝까지
순회한다.** `"3 of 500"` 과 `"300 of 500"` 은 다른 문제이고, 읽는 사람이 다르게 판단한다.

### 3. 빈 리포트와 부재 리포트는 다르다

```
validation = ValidationReport(ok=True)   검사했고 깨끗하다
validation = None                        검사하지 않았다
```

손으로 짠 어댑터 14개는 spec executor 를 거치지 않으므로 `None` 이다. 그것을 "문제 없음"
으로 읽으면 **검사한 적 없는 데이터셋을 검증됐다고 보고**하게 된다.

같은 구별을 `kpubdata-builder#700` 이 drift baseline 에서 했다 — `not_evaluated` 는
`healthy` 가 아니다. 제품군 전체가 같은 규칙을 쓴다.

### 4. `strict` 는 opt-in 이고 `uncastable` 에서만 실패한다

`missing` 과 `undeclared` 는 strict 에서도 경고다.

- `missing` 은 **공공데이터에서 정상**이다. 선택 필드가 비는 응답이 흔하고, 그것으로
  실패시키면 strict 를 켤 수 있는 데이터셋이 거의 없다.
- `undeclared` 는 **제공기관이 추가한 것**이다. 우리 spec 이 뒤처진 신호이지 데이터가
  잘못된 것이 아니다. 여기서 실패하면 제공기관이 필드를 추가할 때마다 사용자의 코드가
  멈춘다.

`uncastable` 만 다르다. 선언한 타입으로 못 쓴다는 뜻이고, 타입을 신뢰해 코드를 쓴
사람에게는 실패가 맞는 답이다.

### 5. 로그는 질의당 한 줄로 승격한다

`logger.debug` → `logger.info`, 단 **이슈가 있을 때만, 그리고 필드당이 아니라 질의당
한 줄.** 필드가 30개인 spec 에서 제공기관이 바뀌면 필드당 로그는 로그를 묻는다.

리포트가 정본이고 로그는 그것을 놓치지 않게 하는 장치다.

## 필드 이름을 `validation` 으로 한 이유

`quality` 를 쓰지 않았다. `kpubdata-builder` 가 이미 `QualityCheckResult` 로 **다른 것**을
가리킨다 — PASS/WARN/FAIL 게이트다. 제품군 안에서 같은 단어가 두 가지를 뜻하면 Studio 의
품질 화면에서 어느 쪽인지 알 수 없다.

`validation` 은 "선언과 실제가 맞는가" 이고 `quality` 는 "데이터가 쓸 만한가" 다.

## 기각한 대안

**기본을 엄격하게.** 타입 선언이 즉시 의미를 갖는다. 기존 사용자의 코드가 제공기관의
데이터 하나 때문에 멈추므로 기각했다 — 이 라이브러리는 그 데이터를 통제하지 않는다.

**`meta` dict 에 넣기.** 필드를 추가하지 않아도 된다. 타입이 없어서 소비자가 키 이름을
외워야 하고, 있는지 없는지도 확인해야 한다. `RecordBatch` 는 공개 API 이므로 타입 있는
필드가 맞다.

**행 단위 캐스팅으로 바꾸기.** 불일치가 사라진다. 컬럼 타입이 사라지므로 기각했다 —
위 1번.

## 관련

- [ADR 0001 Dialect 아키텍처](0001-dialect-inspired-architecture.md)
- `CANONICAL_MODEL.md` — `ValidationReport` · `FieldIssue`
- `#461` `#481` — 캐스팅 정책 결정. 이 리포트가 그 결정의 입력이다
- `kpubdata-builder#700` — `not_evaluated` 는 `healthy` 가 아니다 (같은 규칙)
