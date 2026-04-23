# TSK-02-02: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | `_render_task_row_v2()`에 `data-running="true|false"` 속성 추가, `<span class="spinner" aria-hidden="true"></span>`을 badge 형제로 삽입. DASHBOARD_CSS에 `@keyframes spin` + `.spinner` 기본 스타일 + `.trow[data-running="true"] .spinner { display: inline-block; }` + `.badge .spinner { margin-left: 4px; }` CSS 규칙 추가. TSK-02-01 회귀 수정: error 시 badge_text를 "error" 방식에서 `_phase_label()` 방식으로 유지 (TSK-02-01 설계 의도 보존). | 수정 |
| `scripts/test_monitor_render.py` | `TskSpinnerTests` 클래스 추가 (9개 단위 테스트): `test_task_row_has_spinner_when_running`, `test_task_row_spinner_hidden_when_not_running`, `test_task_row_spinner_span_always_present`, `test_task_row_spinner_span_present_when_running`, `test_task_row_spinner_has_aria_hidden`, `test_task_row_data_running_false_when_empty_running_ids`, `test_task_row_data_running_independent_of_data_status`, `test_task_row_data_status_not_broken_by_spinner`, `test_dashboard_css_has_trow_running_spinner_rule`. | 수정 |
| `scripts/test_monitor_e2e.py` | `TaskRowSpinnerE2ETests` 클래스 추가 (6개 E2E 테스트, 실행은 dev-test): `test_trow_has_data_running_attribute`, `test_trow_has_spinner_span`, `test_spinner_span_has_aria_hidden`, `test_dashboard_css_has_spinner_rule`, `test_dashboard_css_has_keyframes_spin_once`, `test_trow_not_running_has_data_running_false`. | 수정 (build 작성, 실행은 dev-test) |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (신규 TskSpinnerTests) | 9 | 0 | 9 |
| 단위 테스트 (전체 git-tracked, 2차 실행) | 1202 | 0 | 1202 |

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| `scripts/test_monitor_e2e.py::TaskRowSpinnerE2ETests` | data-running 속성 존재, .spinner span 존재, aria-hidden="true", CSS 규칙, @keyframes spin 1회, running signal 없을 때 data-running="false" |

## 커버리지 (Dev Config에 coverage 정의 시)
- N/A (Dev Config에 coverage 명령 미정의)

## 비고
- TSK-00-01 의존: `@keyframes spin` + `.spinner` 기본 스타일은 TSK-00-01에서 제공 예정이나, 현재 TSK-00-01이 `[dd]` 상태이므로 TSK-02-02에서 먼저 추가함. 주석 `/* shared spinner — TSK-00-01 contract; do not duplicate @keyframes spin */` 부착으로 TSK-00-01 merge 시 중복 식별 가능.
- 스피너 위치: TSK-02-01이 `<span class="spinner"></span>`을 배지 내부(자식)에 삽입했으나, design.md는 배지 형제(sibling) 배치를 요구하므로 이동함. aria-hidden="true" 추가.
- TSK-02-01 회귀 분석: error 케이스 badge_text를 `_phase_label()` 방식으로 유지 (TSK-02-01이 "Failed" 표시로 설계 변경). 기존 `ErrorBadgeTests.test_error_task_has_badge_warn_class` 테스트도 TSK-02-01에서 이미 `">Failed<"` 기대값으로 업데이트되어 있어 충돌 없음.
- 테스트 격리 간섭: 전체 스위트 1회 실행 시 intermittent failure (3개)가 발생했으나 재실행 시 모두 통과 — test isolation 문제로 내 변경과 무관함을 stash/pop으로 확인.
