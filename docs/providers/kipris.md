# 특허정보검색 KIPRIS (kipris)

## 개요

KIPRIS(한국특허정보검색시스템)는 특허청에서 제공하는 특허·실용신안·상표·디자인 검색 API입니다. KPubData는 특허패밀리정보 검색을 지원합니다.

- KPubData Provider 이름: `kipris`
- API 기반 URL: https://kipris.or.kr/openapi/

## API 키 발급 방법

1. [KIPRIS 오픈 API 포털](https://kipris.or.kr/openapi/)에 접속합니다.
2. 회원가입 후 로그인합니다.
3. "API 신청" 메뉴에서 원하는 API를 신청합니다.
4. 발급된 API 키를 확인합니다.
5. 환경변수에 설정합니다.

```bash
export KPUBDATA_KIPRIS_API_KEY="your-key"
```

## 지원 데이터셋

### patent_family (특허패밀리정보 검색)

특허패밀리(동일 발명에 대한 각국 특허 출원 묶음) 정보를 검색합니다.

- 출원번호로 특허패밀리 조회
- 필수 파라미터: `applicationNumber`

```python
ds = client.dataset("kipris.patent_family")
result = ds.list(applicationNumber="1020210123456")
```
