# TSK-02-02: 필터 칩 + auto-refresh 토글 동작 - 테스트 보고서

## 결과: PASS

## 실행 요약

| 구분        | 통과 | 실패 | 합계 |
|-------------|------|------|------|
| 단위 테스트 | N/A  | N/A  | N/A — frontend domain, unit_test null |
| E2E 테스트  | 17   | 0    | 17   |

## 정적 검증 (Dev Config에 정의된 경우만)

| 구분 | 결과 | 비고 |
|------|------|------|
| lint | pass | python3 -m py_compile scripts/monitor-server.py — 에러 없음 |
| typecheck | N/A | Dev Config에 미정의 |

## QA 체크리스트 판정

| # | 항목 | 결과 |
|---|------|------|
| 1 | `[Running]` 칩 클릭 시 해당 칩만 `aria-pressed="true"`, 나머지 3개 칩은 `aria-pressed="false"` | pass |
| 2 | `[Running]` 필터 활성 시 `.task-row.running` row만 표시, 나머지 row는 `display: none` | pass |
| 3 | `[All]` 칩 클릭 시 모든 `.task-row`가 `display: ''` (표시됨) | pass |
| 4 | `[Failed]` 필터 활성 시 `.task-row.failed` row만 표시 | pass |
| 5 | `[Bypass]` 필터 활성 시 `.task-row.bypass` row만 표시 | pass |
| 6 | auto-refresh 토글 1회 클릭 후 텍스트 `'○ paused'`, `aria-pressed="false"` | pass |
| 7 | 다시 클릭 시 텍스트 `'◐ auto'`, `aria-pressed="true"` | pass |
| 8 | 부분 fetch DOM 교체 후 기존 필터 상태 유지 — 새로 렌더된 row에도 동일 필터 적용됨 | pass |
| 9 | `_render_task_row`가 생성한 HTML에서 `.task-row` div에 상태 class 중 정확히 1개가 존재 | pass |
| 10 | (클릭 경로) 브라우저에서 `/` 로드 → KPI 영역 `[Running]` 칩 클릭 → Running row만 표시 확인 | pass |
| 11 | (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작 | pass |
| 12 | (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달 (URL 직접 입력 금지) | pass |
| 13 | (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작 (fullstack/frontend 필수) | pass |

## 재시도 이력
- 첫 실행에 통과 (17/17 E2E, lint pass)

## 비고
- E2E 서버(http://localhost:7321)는 호출자가 단계 1-7에서 기동 확인 완료. `E2E_SERVER_MANAGED=true`
- TSK-02-02 직접 대응 테스트: test_filter_chips_present_in_live_dashboard, test_applyfilter_js_in_live_response, test_task_row_has_status_class_in_live_dashboard, test_all_chip_default_pressed_in_live_dashboard, test_refresh_toggle_present_in_live_dashboard (5개) 모두 pass
