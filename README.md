# KPubData Core

**한국 공공데이터를, 바로 분석할 수 있는 테이블로.**

[English](./README.en.md)

> KPubData 제품군: [Core](https://github.com/yeongseon/kpubdata) (접근 계층) → [Engine](https://github.com/yeongseon/kpubdata-builder) (실행·웨어하우스) → [Studio](https://github.com/yeongseon/kpubdata-studio) (시각적 작업공간)

공공데이터 API 는 기관마다 인증 방식·응답 형식·페이지 처리가 제각각입니다.
KPubData 는 그 차이를 어댑터가 흡수해, 하나의 Python 인터페이스로 탐색하고 수집하게
합니다. **사용자의 공식 API 키를 그대로 쓰는 SDK 구조**이므로 데이터를 소유하거나
재배포하지 않습니다.

<!-- BEGIN: datasets -->

- **spec 기반 데이터셋** 23종 — `make verify` 4단계 기계 검증 통과 (22종은 실API 검증 날짜까지 기록)
- **catalogue 기반 데이터셋** 150종 (bok 4, datago 41, fds 1, kipris 1, korean 1, kosis 2, krx 3, law 3, localdata 59, lofin 6, neis 2, semas 17, seoul 7, sgis 3)

> 이 수치는 `scripts/gen_readme_datasets.py`로 생성했다 — 직접 편집 금지. 데이터셋별 상태는 [SUPPORTED_DATA.md](./SUPPORTED_DATA.md).
<!-- END: datasets -->

## 무엇을 해결하나

- **인증·페이지네이션·응답 형식의 차이** — 어댑터 안에 머무릅니다
- **"지원한다"는 말의 근거** — fixture·unit·contract 테스트가 통과해야 지원이라고
  적고, 실API 검증은 날짜까지 기록합니다
- **기관 고유 기능** — 가짜 범용 의미론으로 바꾸지 않고, `call_raw` 비상구를 남깁니다

## 무엇을 하지 않나

- 데이터를 보관하거나 재배포하지 않습니다 — 키는 사용자 것이고 호출도 사용자 것입니다
- 기관 API 에 없는 기능을 만들어내지 않습니다
- 게시·배포는 [kpubdata-builder](https://github.com/yeongseon/kpubdata-builder) 가 합니다

## 설치

```bash
pip install kpubdata
```

## 빠른 시작

```python
from kpubdata import Client

client = Client()                              # KPUBDATA_DATAGO_API_KEY 를 읽는다
batch = client.dataset("datago.apt_trade").list(
    LAWD_CD="11110", DEAL_YMD="202501"
)
print(batch.records[0])
```

API 키 발급과 환경 변수 설정은 [빠른 시작](docs/quickstart.md), 기관별 절차는
[제공기관 문서](docs/providers/)에 있습니다.

## 지원 범위

| | |
|---|---|
| 제공기관 | `datago` `bok` `kosis` `krx` `law` `localdata` `lofin` `semas` `seoul` `sgis` `kipris` `korean` `neis` `fds` |
| Python | 3.10 이상 |
| 데이터셋별 상태·검증 수준 | [SUPPORTED_DATA.md](./SUPPORTED_DATA.md) |

## 문서

| | |
|---|---|
| [빠른 시작](docs/quickstart.md) | 설치부터 첫 조회까지 |
| [CLI](docs/cli.md) | `kpubdata` 명령 |
| [제공기관](docs/providers/) | 기관별 키 발급과 특이사항 |
| [데이터셋 예제](docs/dataset-examples.md) | 실행 가능한 예제 |
| [아키텍처](ARCHITECTURE.md) | 설계와 계층 |
| [API 명세](API_SPEC.md) | 공개 Python API |
| [어댑터 계약](PROVIDER_ADAPTER_CONTRACT.md) | 제공기관 어댑터 구현 규약 |
| [기여 가이드](CONTRIBUTING.md) | 개발 환경과 검증 |
| [보안 정책](SECURITY.md) | 취약점 보고와 알려진 한계 |

프로젝트 운영은 [POLICY.md](docs/governance/POLICY.md) 와
[VERIFICATION.md](docs/governance/VERIFICATION.md) 를 따릅니다.

## 제품군

| 저장소 | 역할 |
|---|---|
| **kpubdata** | 수집과 정규화 — 이 저장소 |
| [kpubdata-builder](https://github.com/yeongseon/kpubdata-builder) | 파이프라인과 게시 |
| [kpubdata-studio](https://github.com/yeongseon/kpubdata-studio) | 화면과 워크플로 |

## 라이선스

[MIT](./LICENSE). 수집한 데이터의 이용 조건은 각 기관의 공공누리 유형을 따릅니다 —
이 라이선스는 코드에만 적용됩니다.
