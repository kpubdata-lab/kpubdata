# 지원 공공데이터 현황

이 문서는 KPubData가 지원하는 공공데이터 목록과 진행 현황을 관리하는 기준 문서입니다.

> **상태 정의** (#498)
>
> - 지원: 실API 검증 완료 — \`meta.json\`이 있는 record 완료본. 호출 가능.
> - 스키마만: 구현·테스트는 통과했으나 실API 검증 미완 (fixture에 meta 없음). 호출은 가능하나 데이터 품질 미확인.
> - 활용신청 대기: 활용신청이 승인되지 않아 호출 시 403. 지원으로 표시하지 않는다.
> - 진행 중: 구현 중이지만 아직 테스트가 완료되지 않음
> - 예정: 후보 단계 (이슈 등록 또는 아이디어)
>
> 상태·검증·검증일 열은 `scripts/sync_supported_data.py` 가 `tests/fixtures` 의 `meta.json` 에서 계산한다 —
> 손으로 "지원" 을 쓰지 않는다. 검증일은 그 데이터셋 meta 의 가장 최근 `recorded_at` 이다.
> 활용신청 대기·폐기·진행 중 같은 판단은 사람이 쓰고 스크립트가 보존한다.
>
> **검증 정의**
>
> - 테스트 검증: fixture 기반 unit 테스트 + contract 테스트 통과
> - 실API 검증: 위 조건 + 실 API integration 테스트 통과 ([#80](https://github.com/kpubdata-lab/kpubdata/issues/80))
>
> **실API 최종 검증일**
>
> - 실API 검증을 마지막으로 성공한 날짜 (`YYYY-MM-DD`). 테스트 검증만 완료된 데이터셋은 `-`로 표기합니다.
> - 검증일이 90일을 초과한 데이터셋은 재검증을 권장합니다.

## 현재 지원

| 상태 | 검증 | 실API 최종 검증일 | Provider | Dataset ID | 데이터셋명 | 인증 | 공식 문서 | 비고 |
|---|---|---|---|---|---|---|---|---|
| 지원 | 실API 검증 | 2026-09-09 | 공공데이터포털 (`datago`) | `apt_trade` | 아파트매매 실거래가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) — **spec 단일원천 전환 완료**(catalogue 제거, #378 청소) | 국토교통부 제공 |
| 지원 | 실API 검증 | 2026-09-09 | 공공데이터포털 (`datago`) | `apt_rent` | 아파트 전월세 실거래가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 국토교통부 제공 |
| 지원 | 실API 검증 | 2026-09-09 | 공공데이터포털 (`datago`) | `offi_trade` | 오피스텔 매매 실거래가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 국토교통부 제공 |
| 지원 | 실API 검증 | 2026-09-09 | 공공데이터포털 (`datago`) | `offi_rent` | 오피스텔 전월세 실거래가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 국토교통부 제공 |
| 활용신청 대기 | 테스트 검증 | - | 공공데이터포털 (`datago`) | `rh_trade` | 연립다세대 매매 실거래가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 국토교통부 제공, 활용신청 승인 반영 대기 (2026-04-21 시점 403) — 활용신청 필요(2026-09-09 프로브 #409) |
| 지원 | 실API 검증 | 2026-09-09 | 공공데이터포털 (`datago`) | `rh_rent` | 연립다세대 전월세 실거래가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 국토교통부 제공 |
| 지원 | 실API 검증 | 2026-09-09 | 공공데이터포털 (`datago`) | `sh_trade` | 단독/다가구 매매 실거래가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 국토교통부 제공 |
| 지원 | 실API 검증 | 2026-09-09 | 공공데이터포털 (`datago`) | `sh_rent` | 단독/다가구 전월세 실거래가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 국토교통부 제공 |
| 지원 | 실API 검증 | 2026-09-09 | 공공데이터포털 (`datago`) | `village_fcst` | 단기예보 조회서비스 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) — **spec 단일원천 전환 완료**(catalogue 제거, #378 청소) | 기상청 제공 |
| 지원 | 실API 검증 | 2026-10-01 | 공공데이터포털 (`datago`) | `ultra_srt_ncst` | 초단기실황 조회서비스 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 기상청 제공 |
| 지원 | 실API 검증 | 2026-10-01 | 공공데이터포털 (`datago`) | `ultra_srt_fcst` | 초단기예보 조회 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15084292](https://www.data.go.kr/data/15084292/openapi.do) | VilageFcstInfoService_2.0 / `getUltraSrtFcst` — spec 절차 (E2E #398), 초단기 카테고리 T1H/RN1 |
| 지원 | 실API 검증 | 2026-09-09 | 공공데이터포털 (`datago`) | `air_quality` | 대기오염정보 조회서비스 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) |  |
| 지원 | 실API 검증 | 2026-10-01 | 공공데이터포털 (`datago`) | `bus_arrival` | 경기도 버스도착정보 조회서비스 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 경기도 v2 endpoint (`getBusArrivalListv2`) + 자체 envelope (`msgHeader`/`msgBody`) — spec 단일원천 전환 완료(catalogue 제거, #409) |
| 지원 | 실API 검증 | 2026-09-09 | 공공데이터포털 (`datago`) | `hospital_info` | 병원정보서비스 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) — **spec 단일원천 전환 완료**(catalogue 제거, #378 청소) |  |
| 지원 | 실API 검증 | 2026-09-09 | 공공데이터포털 (`datago`) | `air_station` | 측정소별 실시간 대기측정정보 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15000581](https://www.data.go.kr/data/15000581/openapi.do) | ArpltnInforInqireSvc / `getMsrstnAcctoRltmMesureDnsty` — **spec 기반 최초 데이터셋** (E2E #396), items 네이스트 배열 |
| 활용신청 대기 | 테스트 검증 | - | 공공데이터포털 (`datago`) | `dur_usjnt_taboo` | 의약품 안전사용서비스 DUR 병용금기 품목정보 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15059486](https://www.data.go.kr/data/15059486/openapi.do) | 식품의약품안전처 제공, 이용허락범위 제한 없음, DURPrdlstInfoService03 / `getUsjntTabooInfoList03`, [#92](https://github.com/kpubdata-lab/kpubdata/issues/92) — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 공공데이터포털 (`datago`) | `dur_older_adult_caution` | 의약품 안전사용서비스 DUR 노인주의 정보조회 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15059486](https://www.data.go.kr/data/15059486/openapi.do) | 식품의약품안전처 제공, 이용허락범위 제한 없음, DURPrdlstInfoService03 / `getOdsnAtentInfoList03`, [#92](https://github.com/kpubdata-lab/kpubdata/issues/92) — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 공공데이터포털 (`datago`) | `dur_product_info` | 의약품 안전사용서비스 DUR품목정보 조회 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15059486](https://www.data.go.kr/data/15059486/openapi.do) | 식품의약품안전처 제공, 이용허락범위 제한 없음, DURPrdlstInfoService03 / `getDurPrdlstInfoList03`, [#92](https://github.com/kpubdata-lab/kpubdata/issues/92) — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 공공데이터포털 (`datago`) | `dur_age_taboo` | 의약품 안전사용서비스 DUR 특정연령대금기 정보조회 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15059486](https://www.data.go.kr/data/15059486/openapi.do) | 식품의약품안전처 제공, 이용허락범위 제한 없음, DURPrdlstInfoService03 / `getSpcifyAgrdeTabooInfoList03`, [#92](https://github.com/kpubdata-lab/kpubdata/issues/92) — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 공공데이터포털 (`datago`) | `dur_dosage_caution` | 의약품 안전사용서비스 DUR 용량주의 정보조회 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15059486](https://www.data.go.kr/data/15059486/openapi.do) | 식품의약품안전처 제공, 이용허락범위 제한 없음, DURPrdlstInfoService03 / `getCpctyAtentInfoList03`, [#92](https://github.com/kpubdata-lab/kpubdata/issues/92) — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 공공데이터포털 (`datago`) | `dur_medication_period_caution` | 의약품 안전사용서비스 DUR 투여기간주의 정보조회 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15059486](https://www.data.go.kr/data/15059486/openapi.do) | 식품의약품안전처 제공, 이용허락범위 제한 없음, DURPrdlstInfoService03 / `getMdctnPdAtentInfoList03`, [#92](https://github.com/kpubdata-lab/kpubdata/issues/92) — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 공공데이터포털 (`datago`) | `dur_efficacy_duplication` | 의약품 안전사용서비스 DUR 효능군중복 정보조회 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15059486](https://www.data.go.kr/data/15059486/openapi.do) | 식품의약품안전처 제공, 이용허락범위 제한 없음, DURPrdlstInfoService03 / `getEfcyDplctInfoList03`, [#92](https://github.com/kpubdata-lab/kpubdata/issues/92) — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 공공데이터포털 (`datago`) | `dur_er_tablet_split_caution` | 의약품 안전사용서비스 DUR 서방정분할주의 정보조회 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15059486](https://www.data.go.kr/data/15059486/openapi.do) | 식품의약품안전처 제공, 이용허락범위 제한 없음, DURPrdlstInfoService03 / `getSeobangjeongPartitnAtentInfoList03`, [#92](https://github.com/kpubdata-lab/kpubdata/issues/92) — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 공공데이터포털 (`datago`) | `dur_pregnancy_taboo` | 의약품 안전사용서비스 DUR 임부금기 정보조회 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15059486](https://www.data.go.kr/data/15059486/openapi.do) | 식품의약품안전처 제공, 이용허락범위 제한 없음, DURPrdlstInfoService03 / `getPwnmTabooInfoList03`, [#92](https://github.com/kpubdata-lab/kpubdata/issues/92) — 활용신청 필요(2026-09-09 프로브 #409) |
| 지원 | 실API 검증 | 2026-09-09 | 공공데이터포털 (`datago`) | `tour_kor_area` | 한국관광공사 지역기반 관광정보 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15101578](https://www.data.go.kr/data/15101578/openapi.do) | TourAPI KorService2 / `areaBasedList2` — 2026-09-07 실API 스모크 실패(전송 오류), 재검증 대기 [#382](https://github.com/kpubdata-lab/kpubdata/issues/382) |
| 지원 | 실API 검증 | 2026-09-09 | 공공데이터포털 (`datago`) | `tour_kor_location` | 한국관광공사 위치기반 관광정보 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15101578](https://www.data.go.kr/data/15101578/openapi.do) | TourAPI KorService2 / `locationBasedList2` — 2026-09-07 실API 스모크 실패(전송 오류), 재검증 대기 [#382](https://github.com/kpubdata-lab/kpubdata/issues/382) |
| 지원 | 실API 검증 | 2026-09-09 | 공공데이터포털 (`datago`) | `tour_kor_keyword` | 한국관광공사 키워드 검색 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15101578](https://www.data.go.kr/data/15101578/openapi.do) | TourAPI KorService2 / `searchKeyword2` — 2026-09-07 실API 스모크 실패(전송 오류), 재검증 대기 [#382](https://github.com/kpubdata-lab/kpubdata/issues/382) |
| 지원 | 실API 검증 | 2026-09-09 | 공공데이터포털 (`datago`) | `tour_kor_festival` | 한국관광공사 행사정보 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15101578](https://www.data.go.kr/data/15101578/openapi.do) | TourAPI KorService2 / `searchFestival2` — 2026-09-07 실API 스모크 실패(전송 오류), 재검증 대기 [#382](https://github.com/kpubdata-lab/kpubdata/issues/382) |
| 지원 | 실API 검증 | 2026-09-09 | 공공데이터포털 (`datago`) | `metro_fare` | 서울교통공사 실시간 운임정보 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15143846](https://www.data.go.kr/data/15143846/openapi.do) | 서울교통공사 / `getRltmFare2` (실API 502: 게이트웨이→백엔드 SSL 검증 실패, 포털 측 인프라 이슈, [#139](https://github.com/kpubdata-lab/kpubdata/issues/139)) |
| 스키마만 | 테스트 검증 | - | 공공데이터포털 (`datago`) | `road_traffic` | 국토교통부 실시간 도로교통정보 | ITS 국가교통정보센터 `apiKey` (별도 발급) | [data.go.kr/15040463](https://www.data.go.kr/data/15040463/openapi.do) | ITS Open API (`openapi.its.go.kr:9443/trafficInfo`), flat envelope (`its_flat`), `call_raw` 전용, [#87](https://github.com/kpubdata-lab/kpubdata/issues/87) |
| 스키마만 | 테스트 검증 | - | 법제처 (`law`) | `law_search` | 법령 검색 | 법제처 `OC` 인증키 | [law.go.kr](https://www.law.go.kr/LSW/openApi/guideResult.do?htmlName=lsSearchGuide) | 국가법령정보 공동활용 / `lawSearch.do?target=law&type=JSON` |
| 스키마만 | 테스트 검증 | - | 법제처 (`law`) | `law_detail` | 법령 본문 조회 | 법제처 `OC` 인증키 | [law.go.kr](https://www.law.go.kr/LSW/openApi/guideResult.do?htmlName=lsEfYdInfoGuide) | 국가법령정보 공동활용 / raw 중심 `lawService.do?target=law&type=JSON&MST=...` |
| 스키마만 | 테스트 검증 | - | 법제처 (`law`) | `ordin_search` | 자치법규 검색 | 법제처 `OC` 인증키 | [law.go.kr](https://www.law.go.kr/LSW/openApi/guideResult.do?htmlName=ordinSearchGuide) | 국가법령정보 공동활용 / `lawSearch.do?target=ordin&type=JSON` |
| 지원 | 실API 검증 | 2026-09-09 | 지방행정인허가 (`localdata`) | `general_restaurant` | 일반음식점 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, service_name 실API 검증 완료 (data.go.kr 이관) |
| 지원 | 실API 검증 | 2026-09-09 | 지방행정인허가 (`localdata`) | `rest_cafe` | 휴게음식점 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, service_name 실API 검증 완료 |
| 지원 | 실API 검증 | 2026-09-09 | 지방행정인허가 (`localdata`) | `bakery` | 제과점 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, KSIC I56 |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `hospital` | 병원 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, KSIC Q86 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `clinic` | 의원 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, KSIC Q86 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `pharmacy` | 약국 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, KSIC Q86 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `animal_hospital` | 동물병원 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 동물병원 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `optical_shop` | 안경업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, KSIC S96 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `public_bath` | 목욕장업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, KSIC S96 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `laundry` | 세탁업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, KSIC S96 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `barber_shop` | 이용업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, KSIC S96 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `beauty_salon` | 미용업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, KSIC S96 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `pet_grooming` | 동물미용업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, KSIC S96 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `dance_academy` | 무도학원업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, KSIC P85 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `karaoke` | 노래연습장업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, KSIC R90 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `singing_bar` | 단란주점 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, KSIC R90 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `billiard_hall` | 당구장업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, KSIC R90 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `performance_hall` | 공연장업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, KSIC R90 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `movie_theater` | 영화상영관 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, KSIC R91 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `swimming_pool` | 수영장업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, KSIC R93 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `fitness_center` | 체력단련장업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, KSIC R93 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `ice_rink` | 빙상장업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, KSIC R93 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `golf_course` | 골프장업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, KSIC R93 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `golf_practice_range` | 골프연습장업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, KSIC R93 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `horse_riding` | 승마장업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, KSIC R93 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `ski_resort` | 스키장업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, KSIC R93 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `affiliated_medical_institution` | 부속의료기관 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 건강/의료기관 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `postpartum_care` | 산후조리업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 건강/의료기관 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `dental_lab` | 치과기공소 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 건강/의료기기 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `animal_import` | 동물수입업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 동물/동물 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `slaughterhouse` | 도축업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 동물/축산 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `hatchery` | 부화업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 동물/축산 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `youth_game_provider` | 청소년게임제공업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 문화/게임 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `tourist_performance_hall` | 관광공연장업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 문화/공연 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `tourism_business` | 관광사업자 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 문화/관광 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `general_amusement_facility` | 일반유원시설업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 문화/관광 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `comprehensive_amusement_facility` | 종합유원시설업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 문화/관광 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `video_viewing_room` | 비디오물감상실업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 문화/비디오 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `tourist_accommodation` | 관광숙박업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 문화/숙박 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `tourist_pension` | 관광펜션업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 문화/숙박 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `online_music_service` | 온라인음악서비스제공업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 문화/음악 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `door_to_door_sales` | 방문판매업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 생활/유통 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `dance_hall` | 무도장업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 생활/체육 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `yacht_marina` | 요트장업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 생활/체육 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `comprehensive_sports_facility` | 종합체육시설업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 생활/체육 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `food_vending_machine` | 식품자동판매기영업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 식품/제조·가공·판매 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `milk_collection` | 집유업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 식품/제조·가공·판매 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `livestock_processing` | 축산물가공업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 식품/제조·가공·판매 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `livestock_storage` | 축산물보관업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 식품/제조·가공·판매 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `entertainment_bar` | 유흥주점영업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 식품/유흥주점 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `tourist_restaurant` | 관광식당 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 식품/음식점 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `tourist_entertainment_restaurant` | 관광유흥음식점업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 식품/음식점 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `log_production` | 원목생산업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 자원환경/목재 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `sawmill` | 제재업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 자원환경/목재 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `high_pressure_gas` | 고압가스업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 자원환경/에너지 — 활용신청 필요(2026-09-09 프로브 #409) |

| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `groundwater_construction` | 지하수시공업체 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 자원환경/지하수 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `water_tank_cleaning` | 저수조청소업 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 자원환경/환경관리 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `publisher` | 출판사 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 기타/미디어 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 지방행정인허가 (`localdata`) | `logistics_warehouse` | 물류창고업체 인허가 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 행정안전부 제공, 기타/물류 — 활용신청 필요(2026-09-09 프로브 #409) |
| 폐기 | 폐기 확인 | 2026-09-10  공공데이터포털 (`datago`) | `g2b_contract` | 나라장터 조달계약정보 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 조달청 제공 (CntrctInfoService / `getCntrctInfoListThng`), [#188](https://github.com/kpubdata-lab/kpubdata/issues/188) | — 2026-09-10 본문 프로브: NO_OPENAPI_SERVICE (drift #414/#415에서 확정) |
| 지원 | 실API 검증 | 2026-10-01 | 공공데이터포털 (`datago`) | `social_enterprise` | 사회적기업 인증현황 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 고용노동부 제공 (ODcloud `socialEnterpriseList/v1`) — spec 단일원천 전환 완료(catalogue 제거, #409), PII 컬럼 3종 선언(대표자명·전화·팩스) |
| 스키마만 | 테스트 검증 | - | 공공데이터포털 (`datago`) | `g2b_catalog` | 나라장터 종합쇼핑몰 품목정보 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 조달청 제공 (ShoppingMallPrdctInfoService / `getShoppingMallPrdctInfoList`), 필수 파라미터 `inqryDiv` 자동 전송 (`default_filters`), [#191](https://github.com/kpubdata-lab/kpubdata/issues/191), [#414](https://github.com/kpubdata-lab/kpubdata/issues/414) — 실API 검증 2026-09-09 로 표기됐으나 record(`meta.json`)가 없다 → `make record` 로 재기록하면 지원 (#621) |
| 스키마만 | 테스트 검증 | - | 통계청 통계지리정보서비스 (`sgis`) | `boundary.sido` | 시도 행정구역 경계 | SGIS `consumer_key` + `consumer_secret` | [sgis.kostat.go.kr](https://sgis.kostat.go.kr/developer/html/main.html) | GeoJSON FeatureCollection 응답을 레코드 단위(`items`)로 정규화 |
| 스키마만 | 테스트 검증 | - | 통계청 통계지리정보서비스 (`sgis`) | `boundary.sigungu` | 시군구 행정구역 경계 | SGIS `consumer_key` + `consumer_secret` | [sgis.kostat.go.kr](https://sgis.kostat.go.kr/developer/html/main.html) | `boundary/hadmarea.geojson` + `low_search` 기반 조회 |
| 스키마만 | 테스트 검증 | - | 통계청 통계지리정보서비스 (`sgis`) | `boundary.emd` | 읍면동 행정구역 경계 | SGIS `consumer_key` + `consumer_secret` | [sgis.kostat.go.kr](https://sgis.kostat.go.kr/developer/html/main.html) | fixture/contract 검증 완료, 실API 검증은 후속 |
| 활용신청 대기 | 테스트 검증 | - | 소상공인시장진흥공단 (`semas`) | `zone_one` | 지정상권 조회 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 상가(상권)정보 API / `storeZoneOne` — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 소상공인시장진흥공단 (`semas`) | `zone_radius` | 반경상권 조회 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 상가(상권)정보 API / `storeZoneInRadius` — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 소상공인시장진흥공단 (`semas`) | `zone_rect` | 사각형상권 조회 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 상가(상권)정보 API / `storeZoneInRectangle` — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 소상공인시장진흥공단 (`semas`) | `zone_admi` | 행정구역상권 조회 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 상가(상권)정보 API / `storeZoneInAdmi` — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 소상공인시장진흥공단 (`semas`) | `store_one` | 단일상가 조회 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 상가(상권)정보 API / `storeOne` — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 소상공인시장진흥공단 (`semas`) | `store_building` | 건물상가 조회 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 상가(상권)정보 API / `storeListInBuilding` — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 소상공인시장진흥공단 (`semas`) | `store_pnu` | 지번상가 조회 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 상가(상권)정보 API / `storeListInPnu` — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 소상공인시장진흥공단 (`semas`) | `store_dong` | 행정동상가 조회 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 상가(상권)정보 API / `storeListInDong` — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 소상공인시장진흥공단 (`semas`) | `store_area` | 상권상가 조회 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 상가(상권)정보 API / `storeListInArea` — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 소상공인시장진흥공단 (`semas`) | `store_radius` | 반경상가 조회 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 상가(상권)정보 API / `storeListInRadius` — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 소상공인시장진흥공단 (`semas`) | `store_rect` | 사각형상가 조회 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 상가(상권)정보 API / `storeListInRectangle` — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 소상공인시장진흥공단 (`semas`) | `store_polygon` | 다각형상가 조회 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 상가(상권)정보 API / `storeListInPolygon` — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 소상공인시장진흥공단 (`semas`) | `store_upjong` | 업종별상가 조회 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 상가(상권)정보 API / `storeListInUpjong` — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 소상공인시장진흥공단 (`semas`) | `store_date` | 수정일자상가 조회 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 상가(상권)정보 API / `storeListByDate` — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 소상공인시장진흥공단 (`semas`) | `upjong_large` | 업종대분류 조회 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 상가(상권)정보 API / `largeUpjongList` — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 소상공인시장진흥공단 (`semas`) | `upjong_middle` | 업종중분류 조회 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 상가(상권)정보 API / `middleUpjongList` — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 소상공인시장진흥공단 (`semas`) | `upjong_small` | 업종소분류 조회 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr](https://www.data.go.kr) | 상가(상권)정보 API / `smallUpjongList` — 활용신청 필요(2026-09-09 프로브 #409) |
| 스키마만 | 테스트 검증 | - | 서울 열린데이터광장 (`seoul`) | `subway_realtime_arrival` | 서울시 지하철 실시간 도착정보 | [서울 열린데이터광장](https://data.seoul.go.kr/) 인증키 | [data.seoul.go.kr](https://data.seoul.go.kr/) | 경로 기반 인증키 + 서비스별 top-level envelope |
| 스키마만 | 테스트 검증 | - | 서울 열린데이터광장 (`seoul`) | `bike_rent_month` | 서울시 공공자전거 이용정보(월별) | [서울 열린데이터광장](https://data.seoul.go.kr/) 인증키 | [data.seoul.go.kr](https://data.seoul.go.kr/) | 경로 기반 인증키 + 인덱스 페이지네이션 — 실API 검증 2026-05-05 로 표기됐으나 record(`meta.json`)가 없다 → `make record` 로 재기록하면 지원 (#621) |
| 스키마만 | 테스트 검증 | - | 서울 열린데이터광장 (`seoul`) | `bike_realtime` | 서울시 공공자전거 따릉이 실시간 대여정보 | [서울 열린데이터광장](https://data.seoul.go.kr/) 인증키 | [data.seoul.go.kr](https://data.seoul.go.kr/) | envelope_key `rentBikeStatus` ≠ service_name `bikeList`, path params 없음 — 실API 검증 2026-05-05 로 표기됐으나 record(`meta.json`)가 없다 → `make record` 로 재기록하면 지원 (#621) |
| 스키마만 | 테스트 검증 | - | 서울 열린데이터광장 (`seoul`) | `bike_station_master` | 서울시 공공자전거 따릉이 대여소 마스터 정보 | [서울 열린데이터광장](https://data.seoul.go.kr/) 인증키 | [data.seoul.go.kr](https://data.seoul.go.kr/) | envelope_key `stationInfo` ≠ service_name `tbCycleStationInfo`, path params 없음 — 실API 검증 2026-05-05 로 표기됐으나 record(`meta.json`)가 없다 → `make record` 로 재기록하면 지원 (#621) |
| 스키마만 | 테스트 검증 | - | 서울 열린데이터광장 (`seoul`) | `park_info` | 서울시 공영주차장 안내 정보 | [서울 열린데이터광장](https://data.seoul.go.kr/) 인증키 | [data.seoul.go.kr](https://data.seoul.go.kr/) | path params 없음 |
| 스키마만 | 테스트 검증 | - | 서울 열린데이터광장 (`seoul`) | `park_usage` | 서울시 공원 정보 | [서울 열린데이터광장](https://data.seoul.go.kr/) 인증키 | [data.seoul.go.kr](https://data.seoul.go.kr/) | path params 없음, [#227](https://github.com/kpubdata-lab/kpubdata/issues/227) |
| 스키마만 | 테스트 검증 | - | 서울 열린데이터광장 (`seoul`) | `citydata` | 서울시 실시간 도시데이터 인구현황 | [서울 열린데이터광장](https://data.seoul.go.kr/) 인증키 | [data.seoul.go.kr/dataList/OA-21285](https://data.seoul.go.kr/dataList/OA-21285/A/1/datasetView.do) | `citydata_ppltn`, top-level `RESULT`, 필수 path param `area`, [#225](https://github.com/kpubdata-lab/kpubdata/issues/225) |
| 스키마만 | 테스트 검증 | - | 한국은행 ECOS (`bok`) | `base_rate` | 한국은행 기준금리 | [ECOS](https://ecos.bok.or.kr/api/) 인증키 | [ecos.bok.or.kr](https://ecos.bok.or.kr/api/) | 실API 검증 2025-04-15 로 표기됐으나 record(`meta.json`)가 없다 → `make record` 로 재기록하면 지원 (#621) |
| 스키마만 | 테스트 검증 | - | 한국은행 ECOS (`bok`) | `money_supply` | 통화량(M2) 구 통계 (198601~200409) | [ECOS](https://ecos.bok.or.kr/api/) 인증키 | [ecos.bok.or.kr](https://ecos.bok.or.kr/api/) | ECOS 통계표 `101Y003`, 항목코드 `BBHS00`, 월별, 2006 통화지표 개편 이전 구 시계열, [#229](https://github.com/kpubdata-lab/kpubdata/issues/229) |
| 스키마만 | 테스트 검증 | - | 한국은행 ECOS (`bok`) | `bond_yield_3y` | 국고채 3년물 수익률 | [ECOS](https://ecos.bok.or.kr/api/) 인증키 | [ecos.bok.or.kr](https://ecos.bok.or.kr/api/) | ECOS 통계표 `817Y002`, 항목코드 `010200000`, 일별 데이터 |
| 스키마만 | 테스트 검증 | - | 한국은행 ECOS (`bok`) | `usd_krw` | 원/달러 환율 매매기준율 | [ECOS](https://ecos.bok.or.kr/api/) 인증키 | [ecos.bok.or.kr](https://ecos.bok.or.kr/api/) | ECOS 통계표 `731Y003`, 항목코드 `0000003`, 일별 데이터 |
| 스키마만 | 테스트 검증 | - | 통계청 KOSIS (`kosis`) | `population_migration` | 시도별 이동자수 | [KOSIS](https://kosis.kr/openapi/index/index.jsp) 인증키 | [kosis.kr](https://kosis.kr/openapi/index/index.jsp) | 실API 검증 2025-04-15 로 표기됐으나 record(`meta.json`)가 없다 → `make record` 로 재기록하면 지원 (#621) |
| 스키마만 | 테스트 검증 | - | 통계청 KOSIS (`kosis`) | `industrial_production` | 광공업생산지수 | [KOSIS](https://kosis.kr/openapi/index/index.jsp) 인증키 | [kosis.kr](https://kosis.kr/openapi/index/index.jsp) | KOSIS 통계표 `DT_1J22003`, 기본 파라미터 `objL1=T10`, `itmId=T`, `prdSe=M` — 실API 검증 2026-04-27 로 표기됐으나 record(`meta.json`)가 없다 → `make record` 로 재기록하면 지원 (#621) |
| 스키마만 | 테스트 검증 | - | 지방재정365 (`lofin`) | `expenditure_budget` | 세출결산총괄 | [지방재정365](https://www.lofin365.go.kr) 인증키 | [lofin365.go.kr](https://www.lofin365.go.kr) | API 코드: AJGCF — 실API 검증 2025-04-16 로 표기됐으나 record(`meta.json`)가 없다 → `make record` 로 재기록하면 지원 (#621) |
| 스키마만 | 테스트 검증 | - | 지방재정365 (`lofin`) | `revenue_budget` | 세입결산총괄 | [지방재정365](https://www.lofin365.go.kr) 인증키 | [lofin365.go.kr](https://www.lofin365.go.kr) | API 코드: IIBBH — 실API 검증 2025-04-16 로 표기됐으나 record(`meta.json`)가 없다 → `make record` 로 재기록하면 지원 (#621) |
| 스키마만 | 테스트 검증 | - | 지방재정365 (`lofin`) | `expenditure_function` | 기능별세출 | [지방재정365](https://www.lofin365.go.kr) 인증키 | [lofin365.go.kr](https://www.lofin365.go.kr) | API 코드: GGNSE — 실API 검증 2025-04-16 로 표기됐으나 record(`meta.json`)가 없다 → `make record` 로 재기록하면 지원 (#621) |
| 스키마만 | 테스트 검증 | - | 지방재정365 (`lofin`) | `debt_ratio` | 채무비율현황 | [지방재정365](https://www.lofin365.go.kr) 인증키 | [lofin365.go.kr](https://www.lofin365.go.kr) | API 코드: HEDFC — 실API 검증 2025-04-16 로 표기됐으나 record(`meta.json`)가 없다 → `make record` 로 재기록하면 지원 (#621) |
| 스키마만 | 테스트 검증 | - | 지방재정365 (`lofin`) | `fiscal_independence` | 재정자립도현황 | [지방재정365](https://www.lofin365.go.kr) 인증키 | [lofin365.go.kr](https://www.lofin365.go.kr) | API 코드: JFIED — 실API 검증 2025-04-16 로 표기됐으나 record(`meta.json`)가 없다 → `make record` 로 재기록하면 지원 (#621) |
| 스키마만 | 테스트 검증 | - | 지방재정365 (`lofin`) | `revenue_by_source` | 재원별 회계별 세입결산 | [지방재정365](https://www.lofin365.go.kr) 인증키 | [lofin365.go.kr](https://www.lofin365.go.kr) | API 코드: FIACRV — 실API 검증 2025-04-17 로 표기됐으나 record(`meta.json`)가 없다 → `make record` 로 재기록하면 지원 (#621) |
| 스키마만 | 테스트 검증 | - | 한국거래소 (`krx`) | `kospi_index` | 코스피 지수 일별 시세 | 인증 불필요 (`pykrx`) | [data.krx.co.kr](https://data.krx.co.kr/) | KRX 지수 OHLCV, 기본 ticker `1001` (KOSPI) |
| 스키마만 | 테스트 검증 | - | 한국거래소 (`krx`) | `investor_flow` | 투자자별 순매수 추이 | 인증 불필요 (`pykrx`) | [data.krx.co.kr](https://data.krx.co.kr/) | KRX 시장별 투자자 매수/매도/순매수, 기본 market `KOSPI` |
| 스키마만 | 테스트 검증 | - | 한국거래소 (`krx`) | `market_valuation` | 시장 밸류에이션 지표 | 인증 불필요 (`pykrx`) | [data.krx.co.kr](https://data.krx.co.kr/) | KRX 시장 PER/PBR/배당수익률/EPS/BPS 일별 집계, 기본 market `KOSPI` |
| 활용신청 대기 | 테스트 검증 | - | 공공데이터포털 (`datago`) | `agri_price` | 친환경농산물 가격정보 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15156073](https://www.data.go.kr/data/15156073/openapi.do) | 한국농수산식품유통공사(aT) 제공 (ecoFriendly / `price`), [#88](https://github.com/kpubdata-lab/kpubdata/issues/88) — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 공공데이터포털 (`datago`) | `subway_passengers` | 지하철역별 승하차 인원 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15143845](https://www.data.go.kr/data/15143845/openapi.do) | 서울교통공사 제공 (psgr / `getStnPsgr`), pasngYmd 필수·최근 1주, [#93](https://github.com/kpubdata-lab/kpubdata/issues/93) — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 공공데이터포털 (`datago`) | `mid_fcst` | 중기전망 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15059468](https://www.data.go.kr/data/15059468/openapi.do) | 기상청 제공 (MidFcstInfoService / `getMidFcst`), stnId+tmFc, live integration 시나리오 추가(`tests/integration/test_datago_live.py`), [#94](https://github.com/kpubdata-lab/kpubdata/issues/94) — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 공공데이터포털 (`datago`) | `mid_land_fcst` | 중기육상예보 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15059468](https://www.data.go.kr/data/15059468/openapi.do) | 기상청 제공 (MidFcstInfoService / `getMidLandFcst`), regId+tmFc, [#94](https://github.com/kpubdata-lab/kpubdata/issues/94) — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 공공데이터포털 (`datago`) | `asos_daily` | 기상청 종관기상관측 일자료 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15059093](https://www.data.go.kr/data/15059093/openapi.do) | AsosDalyInfoService / `getWthrDataList`, 필수 filter `stnIds`+`startDt`+`endDt`, 기존 serviceKey 재사용(기상자료개방포털 별도 키 불필요), [#217](https://github.com/kpubdata-lab/kpubdata/issues/217) — 엔드포인트 실측 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 공공데이터포털 (`datago`) | `asos_hourly` | 기상청 종관기상관측 시간자료 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15057210](https://www.data.go.kr/tcs/dss/selectApiDataDetailView.do?publicDataPk=15057210) | AsosHourlyInfoService / `getWthrDataList`, 필수 filter `stnIds`+`startDt`+`endDt`(1년 상한), [#217](https://github.com/kpubdata-lab/kpubdata/issues/217) — 엔드포인트 실측 — 활용신청 필요(2026-09-09 프로브 #409) |
| 스키마만 | 테스트 검증 | - | 공공데이터포털 (`datago`) | `airkorea_station_realtime` | 에어코리아 측정소별 실시간 측정정보 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15073861](https://www.data.go.kr/data/15073861/openapi.do) | ArpltnInforInqireSvc / `getMsrstnAcctoRltmMesureDnsty`, 필수 filter \`stationName\`, PM10/PM2.5/O3/CAI, [#224](https://github.com/kpubdata-lab/kpubdata/issues/224) — 엔드포인트 실측 |
| 지원 | 실API 검증 | 2026-09-09 | 공공데이터포털 (`datago`) | `airkorea_forecast` | 에어코리아 대기질 예보통보 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15073861](https://www.data.go.kr/data/15073861/openapi.do) | ArpltnInforInqireSvc / `getMinuDustFrcstDspth`, 지역별 예보등급, [#224](https://github.com/kpubdata-lab/kpubdata/issues/224) — 엔드포인트 실측 |
| 진행 중 | - | - | 공공데이터포털 (`datago`) | `ocean_buoy` | 해양관측부이 최신 관측데이터 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15155516](https://www.data.go.kr/data/15155516/openapi.do) | 국립해양조사원 twRecent / `GetTWRecentApiService` — spec `status: unstable`, fixture 없음 (#627) |
| 활용신청 대기 | 테스트 검증 | - | 공공데이터포털 (`datago`) | `culture_facility` | 한국문화정보원 문화시설조회 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15138930](https://www.data.go.kr/data/15138930/openapi.do) | 문화포털 nopenapi (cultureartspaces/performingplace), [#167](https://github.com/kpubdata-lab/kpubdata/issues/167) — 엔드포인트 실측 — 활용신청 필요(2026-09-09 프로브 #409) |
| 스키마만 | 테스트 검증 | - | 특허청 KIPRIS (`kipris`) | `patent_family` | 특허패밀리정보 검색 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15002126](https://www.data.go.kr/data/15002126/openapi.do) | kipo-api.kipi.or.kr / `getAppNoPatFamInfoSearch`, 필수 filter `applicationNumber`, DOCDB 패밀리 멤버, [#223](https://github.com/kpubdata-lab/kpubdata/issues/223) |
| 스키마만 | 테스트 검증 | - | 국립국어원 (`korean`) | `dict_search` | 표준국어대사전 검색 | [stdict open API](https://stdict.korean.go.kr/openapi/openApiInfo.do) 인증키 | [stdict.korean.go.kr](https://stdict.korean.go.kr/openapi/openApiInfo.do) | `search.do`, 필수 filter `q`, channel/item/sense 엔벨로프 — 다의어 sense별 레코드 정규화, statusCode 019→AuthError, [#222](https://github.com/kpubdata-lab/kpubdata/issues/222) |
| 스키마만 | 테스트 검증 | - | 식품의약품안전처 (`fds`) | `traceability_item` | 식품이력추적 관리품목 등록정보 | [식약처 open API](http://openapi.foodsafetykorea.go.kr/api) 인증키 | [data.go.kr/15111975](https://www.data.go.kr/data/15111975/openapi.do) | URL 경로 인증키(`/api/{KEY}/{service}/json/{start}/{end}`), `I1200`, `code=000` 정상 / `INFO-100` AuthError, [#165](https://github.com/kpubdata-lab/kpubdata/issues/165) |
| 스키마만 | 테스트 검증 | - | 교육부 나이스 (`neis`) | `school_info` | 학교알리미 학교기본정보 | [NEIS open API](https://open.neis.go.kr/) KEY | [open.neis.go.kr](https://open.neis.go.kr/portal/data/servicePage.do) | `schoolInfo`, 필수 filter 없음(교육청 코드 권장), 학교 마스터 데이터, [#218](https://github.com/kpubdata-lab/kpubdata/issues/218) |
| 스키마만 | 테스트 검증 | - | 교육부 나이스 (`neis`) | `meal_diet` | 학교 급식식단정보 | [NEIS open API](https://open.neis.go.kr/) KEY | [data.go.kr/15139198](https://www.data.go.kr/data/15139198/openapi.do) | `mealServiceDietInfo`, 필수 filter `ATPT_OFCDC_SC_CODE`+`SD_SCHUL_CODE`, NEIS 고유 이중-list 엔벨로프, [#164](https://github.com/kpubdata-lab/kpubdata/issues/164) |
| 활용신청 대기 | 테스트 검증 | - | 공공데이터포털 (`datago`) | `bond_price` | 금융위원회 채권시세정보 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15094784](https://www.data.go.kr/data/15094784/openapi.do) | GetBondSecuritiesInfoService / `getBondPriceInfo`, [#163](https://github.com/kpubdata-lab/kpubdata/issues/163) — 엔드포인트 실측 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 공공데이터포털 (`datago`) | `sports_facility` | 전국체육시설 정보 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15113986](https://www.data.go.kr/data/15113986/openapi.do) | KSPO 제공 (SRVC_API_SFMS_FACI / `TODZ_API_SFMS_FACI`), [#166](https://github.com/kpubdata-lab/kpubdata/issues/166) — 엔드포인트 실측 — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 공공데이터포털 (`datago`) | `mid_ta` | 중기기온 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15059468](https://www.data.go.kr/data/15059468/openapi.do) | 기상청 제공 (MidFcstInfoService / `getMidTa`), regId+tmFc, [#94](https://github.com/kpubdata-lab/kpubdata/issues/94) — 활용신청 필요(2026-09-09 프로브 #409) |
| 활용신청 대기 | 테스트 검증 | - | 공공데이터포털 (`datago`) | `mid_sea_fcst` | 중기해상예보 | [공공데이터포털](https://www.data.go.kr) 서비스키 | [data.go.kr/15059468](https://www.data.go.kr/data/15059468/openapi.do) | 기상청 제공 (MidFcstInfoService / `getMidSeaFcst`), regId+tmFc, [#94](https://github.com/kpubdata-lab/kpubdata/issues/94) — 활용신청 필요(2026-09-09 프로브 #409) |

## 한국거래소 (`krx`)

- 상태: 스키마만 — 실API 기록(`meta.json`)이 없다. 위 표의 행이 기준이다 (#621)
- 인증: 없음 (`requires_api_key = False`)
- 백엔드: optional `pykrx` extra (`pip install kpubdata[krx]`)
- 데이터셋:
  - `krx.kospi_index`: 코스피 지수 일별 시세
  - `krx.investor_flow`: 투자자별 순매수 추이
  - `krx.market_valuation`: 시장 밸류에이션 지표

## 진행 예정 / 진행 중

| 상태 | Provider | Dataset ID | 데이터셋명 | 메모 |
|---|---|---|---|---|
| 예정 | 기상청 | `weather_forecast` | 동네예보 | provider/adapter 구조 확정 후 착수 |

## 갱신 규칙

새로운 adapter를 추가할 때는 아래 절차에 따라 이 문서를 함께 업데이트합니다.

1. **기획 단계**: `진행 예정 / 진행 중` 표에 `예정`으로 추가
2. **구현 시작**: fixture 수집 또는 adapter skeleton이 생기면 `진행 중`으로 변경
3. **지원 전환**: fixture + unit test + contract test + 문서가 모두 포함된 PR이 merge되면 `현재 지원` 표로 이동하고 `지원`으로 표시
4. **README 동기화**: `지원` 항목만 [README.md](./README.md)의 요약 표에 추가
5. **명칭 규칙**: provider slug와 dataset id는 코드의 실제 이름과 정확히 일치시킬 것
6. **PR 포함**: adapter 추가/상태 변경 PR에는 이 문서의 업데이트를 반드시 포함

## 비상구 / 고급 기능 (Escape Hatches)

정규화된 데이터셋은 아니지만, 미등록 endpoint를 즉시 호출할 수 있게 해주는 raw 비상구입니다. 정규화·페이지네이션·스키마·엔드포인트별 호환은 보장되지 않으며, 호출자가 원본 응답을 직접 처리해야 합니다.

| Provider | 비상구 키 | 용도 | 제약 |
|---|---|---|---|
| 공공데이터포털 (`datago`) | `datago.generic` | 카탈로그에 없는 임의의 data.go.kr endpoint를 `call_raw(operation, _base_url=..., **params)`로 호출 | `list()` 미지원 · 표준 envelope 검증은 옵션 (`_envelope=False`) · 응답 정규화 없음 · `*.data.go.kr` 외 호스트는 경고 로그 |

특정 endpoint가 반복 사용된다면 비상구를 확장하지 말고 정식 dataset으로 등록(`기여자를 위한 새 데이터셋 추가 가이드` 참고)하는 것을 권장합니다.
