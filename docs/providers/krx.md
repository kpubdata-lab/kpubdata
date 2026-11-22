# 한국거래소 KRX (krx)

## 개요

한국거래소(KRX)의 주가 지수, 투자자 동향, 밸류에이션 데이터를 조회합니다. KPubData는 KRX 정보데이터시스템의 일별 시세 데이터를 표준화된 인터페이스로 제공합니다.

- KPubData Provider 이름: `krx`
- 데이터 출처: [KRX 정보데이터시스템](http://data.krx.co.kr/)
- 인증: **불필요** (공개 데이터 크롤링 방식)

## API 키 발급 방법

KRX는 공개 데이터이므로 API 키가 필요하지 않습니다.

```bash
# 키 설정 불필요
```

## 지원 데이터셋

### kospi_index (코스피 지수 일별 시세)

코스피 지수의 일별 시가·고가·저가·종가·거래량을 조회합니다.

- 날짜 범위로 조회 (`start_date`, `end_date`, YYYYMMDD)
- 거래소에 따라 코스닥(`kosdaq_index`)도 조회 가능

### investor_flow (투자자별 순매수 추이)

개인·외국인·기관 등 투자자별 순매수 금액을 일별로 조회합니다.

!!! note "`RecordBatch.raw` 예외"
    이 데이터셋의 `RecordBatch.raw` 는 pykrx가 돌려준 프레임이 아니다. 어댑터가 매수·매도 프레임을
    투자자 유형별 행으로 합친 뒤 레코드로 바꾼 값(투자자 유형, 매수·매도·순매수 금액)이며,
    합치는 과정에서 생긴 `index` 키가 함께 들어 있다. 원본 프레임이 필요하면 pykrx를 직접 호출한다.
    어댑터 계약(raw를 손실 없이 보존한다)의 알려진 예외이다.

### market_valuation (시장 밸류에이션 지표)

코스피 시장의 PER, PBR, 배당수익률 등 밸류에이션 지표를 일별로 조회합니다.

```python
ds = client.dataset("krx.kospi_index")
result = ds.list(start_date="20240101", end_date="20240131")
```
