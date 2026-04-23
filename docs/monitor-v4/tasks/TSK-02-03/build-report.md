# TSK-02-03: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | `_build_state_summary_json()` + `_encode_state_summary_attr()` + `_trow_tooltip_skeleton()` 헬퍼 신규; `_render_task_row_v2`에 `data-state-summary` 속성 추가; `render_dashboard`에 `_trow_tooltip_skeleton()` 주입; `DASHBOARD_CSS`에 `#trow-tooltip` CSS 규칙 추가; `_DASHBOARD_JS`에 `setupTaskTooltip` IIFE 추가 | 수정 |
| `scripts/test_monitor_render.py` | `TskTooltipStateSummaryTests` 클래스 신규 (25개 단위 테스트) | 수정 |
| `scripts/test_monitor_e2e.py` | `TskTooltipE2ETests` 클래스 신규 (5개 E2E 테스트 — 실행은 dev-test) | 수정 (build 작성, 실행은 dev-test) |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (TskTooltipStateSummaryTests) | 25 | 0 | 25 |
| 전체 스위트 (scripts/) | 1373 | 0 | 1373 |

> E2E 기존 실패 15건 (test_monitor_e2e.py)은 서버 미기동 상태에서 skipTest 없이 실패하는 기존 테스트로, TSK-02-03 이전에도 동일하게 실패했음 (stash로 검증). 회귀 없음.

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| `scripts/test_monitor_e2e.py` | `test_task_tooltip_trow_has_data_state_summary` — GET / HTML 에 data-state-summary 속성 존재 |
| `scripts/test_monitor_e2e.py` | `test_task_tooltip_dom_body_direct` — #trow-tooltip 이 body 직계에 1회 존재 |
| `scripts/test_monitor_e2e.py` | `test_task_tooltip_state_summary_is_valid_json` — data-state-summary JSON 파싱 + 필수 키 |
| `scripts/test_monitor_e2e.py` | `test_task_tooltip_second_render_keeps_dom` — 두 번의 GET / 응답에서 #trow-tooltip 각 1회 존재 (auto-refresh 격리 검증) |
| `scripts/test_monitor_e2e.py` | `test_task_tooltip_setupTaskTooltip_in_script` — script 블록에 setupTaskTooltip 포함 |

수동 QA 확인 사항 (Playwright 미탑재):
- Task 행 mouseenter 300ms → #trow-tooltip 가시화
- mouseleave / scroll → hidden 전환
- 5초 auto-refresh 후에도 동일 동작 (document-level delegation 보장)

## 커버리지

N/A — Dev Config에 coverage 명령 미정의

## 비고

- `html.escape(..., quote=True)` 적용으로 XSS 안전: `<script>` → `&lt;script&gt;`, single-quote → `&#x27;`
- `phase_history_tail[-3:]` 슬라이스로 최근 3개만 직렬화 (4개 이상 테스트 통과)
- 기존 `_render_task_row_v2` 7개 child 구조 완전 유지 (회귀 테스트 통과)
- `_trow_tooltip_skeleton()` 은 `render_dashboard` 에서 `_drawer_skeleton()` 바로 다음에 주입 → body 직계 + data-section 바깥 격리
- `setupTaskTooltip` IIFE: document-level delegation (useCapture=true) + 300ms debounce + scroll 숨김 + getBoundingClientRect 기반 좌표 계산 + 뷰포트 우측 경계 fallback
