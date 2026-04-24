# TSK-04-02: FR-01 Task 팝오버 — hover 제거 + ⓘ 클릭 + 위쪽 배치 + 폴백 - 테스트 결과

## 결과: PASS

## 실행 요약

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 | 25 | 0 | 25 |
| E2E 테스트 | 7 | 0 | 7 |

## 정적 검증 (Dev Config에 정의된 경우만)

| 구분 | 결과 | 비고 |
|------|------|------|
| typecheck | pass | Python compile OK |

## QA 체크리스트 판정

| # | 항목 | 결과 |
|---|------|------|
| 1 | .info-btn 버튼 DOM 존재 + ARIA | pass |
| 2 | #trow-info-popover 싱글톤 body 직계 1회 | pass |
| 3 | 클릭 시 팝오버 열림 + 위치 검증 | pass |
| 4 | 상단 여유 부족 시 하단 폴백 | pass |
| 5 | 동일 버튼 재클릭 시 닫힘 | pass |
| 6 | 다른 버튼 클릭 시 상태 전환 | pass |
| 7 | JSON 파싱 실패 시 안전 처리 | pass |
| 8 | ESC 키 닫힘 + 포커스 복원 | pass |
| 9 | 외부 클릭 시 닫힘 | pass |
| 10 | 스크롤/리사이즈 자동 닫힘 | pass |
| 11 | 접근성: 키보드 지원 + aria-expanded | pass |
| 12 | 회귀: 구 패턴 0회 + 신규 1회 이상 | pass |
| 13 | 클릭 경로 접근성 | pass |
| 14 | UI 렌더링 + 상호작용 | pass |

## 테스트 실행 내역

### 단위 테스트 (`scripts/test_monitor_info_popover.py`)
- 25개 테스트 (DOM 구조, CSS 규칙, JS 문자열, ARIA)
- 결과: 25/25 PASS

### E2E 테스트 (`scripts/test_monitor_e2e.py::TskTooltipE2ETests`)
- 7개 테스트 (DOM 존재, ARIA 검증, 팝오버 동작, hover 제거 확인)
- 결과: 7/7 PASS

## 재시도 이력
- 1차 E2E 실패: 서버(PID 98458)가 WP-05 디렉토리에서 실행 중이었음 (WP-04 코드 미반영).
- 수정: WP-04 코드로 서버 재기동 후 재실행.
- 2차 실행: 단위 25 + E2E 7개 모두 통과.

## 비고
- 모든 AC 조건 충족 (AC-FR01-a~f)
- 회귀 검증: setupTaskTooltip, #trow-tooltip 문자열 0회
- E2E 서버: localhost:7321 WP-04 코드로 기동
- `KpiCountsTests.test_done_excludes_bypass_failed_running` 및 dep-graph canvas height 테스트 2개 실패는 TSK-04-02 이전 pre-existing 실패 (TSK-04-03 관련)
