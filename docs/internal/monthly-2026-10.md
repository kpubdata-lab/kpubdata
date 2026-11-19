# 월간 집계 — 2026-10

> 생성: 2026-11-19 13:21 UTC — `scripts/monthly_report.py` (직접 편집 금지)

## 증거 범위
- 월별 집계는 생성일로 조회한 드리프트 이슈에만 적용합니다. 이슈 상태는 조회 시점의 값입니다.
- 파일럿 로그는 날짜 없는 누적 기록으로, 해당 월의 실행 실적이 아닙니다.
- 데이터셋 상태 스냅샷 생성 시각: 2026-11-19T10:38:33+00:00. 월말 상태나 현재 API 가용성을 입증하지 않습니다.
- 월별 fixture/probe/live API 실행과 키·runner 부재를 구분할 실행 증거가 없어 월간 실행 통과율은 계산하지 않습니다.

## 파일럿 누적 통계
- 기록 7건 · 통과 3 · 보류 4 · 실패 0
- 누적 기록 중 통과 비율 (보류 포함): 43%

## 드리프트 이슈
- #959 [종료] [drift] datago.village_fcst: live_verified → unstable (UNKNO
- #958 [종료] [drift] datago.ultra_srt_ncst: live_verified → unstable (UNK
- #957 [종료] [drift] datago.ultra_srt_fcst: live_verified → unstable (UNK
- #943 [종료] [drift] datago.hospital_info: live_verified → unstable (UNKN
- #951 [종료] [drift] datago.bus_arrival: live_verified → broken (SCHEMA_C

## 데이터셋 상태
- spec: 25종
- catalogue: 131종

## 계열별 통과율
- 원천: `docs/status/latest.json` 의 `family_pass_rate` (`scripts/gen_status_page.py` 가 `dataset_metadata.json` 에서 계산)
- 분모는 스냅샷에 등록된 계열별 데이터셋 수입니다. 실행 횟수 기준의 월간 통과율이 아닙니다.

| 계열 | 전체 | 실API 검증 기록 | 기록 비율 | 테스트 검증 기록 | 기록 비율 |
|---|---|---|---|---|---|
| bok | 4 | 0 | 0.0% | 4 | 100.0% |
| datago | 47 | 21 | 44.7% | 45 | 95.7% |
| fds | 1 | 0 | 0.0% | 1 | 100.0% |
| kipris | 1 | 0 | 0.0% | 1 | 100.0% |
| korean | 1 | 0 | 0.0% | 1 | 100.0% |
| kosis | 2 | 0 | 0.0% | 2 | 100.0% |
| krx | 3 | 0 | 0.0% | 3 | 100.0% |
| law | 3 | 0 | 0.0% | 3 | 100.0% |
| localdata | 59 | 3 | 5.1% | 59 | 100.0% |
| lofin | 6 | 0 | 0.0% | 6 | 100.0% |
| neis | 2 | 0 | 0.0% | 2 | 100.0% |
| semas | 17 | 0 | 0.0% | 17 | 100.0% |
| seoul | 7 | 0 | 0.0% | 7 | 100.0% |
| sgis | 3 | 0 | 0.0% | 3 | 100.0% |

## 개선 권고 (자동 생성)
- 자동 집계만으로 검증 게이트를 바꾸지 않고 필요한 실행 증거를 먼저 확인합니다.
- doc-wrong 다수: 활용가이드 캐시 보강
- auth-blocked 다수: 활용신청 목록 갱신