# TSK-02-04: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | `/api/task-detail` 라우트 + `_WBS_SECTION_RE` / `_TSK_ID_VALID_RE` / `_is_api_task_detail_path` / `_extract_wbs_section` / `_collect_artifacts` / `_build_task_detail_payload` / `_handle_api_task_detail` / `_task_panel_css` / `_task_panel_js` / `_task_panel_dom` 추가, `do_GET` 디스패치에 분기 삽입, `_render_task_row_v2`에 `.expand-btn` 추가, `render_dashboard`에 `#task-panel` DOM + CSS + JS 삽입 | 수정 |
| `scripts/test_monitor_task_detail_api.py` | 백엔드 단위 테스트 — 스키마 / 섹션 경계(h3↔h3, h3↔h2) / 아티팩트 탐지 / 400/404 / XSS 안전 / HTTP 핸들러 통합 | 신규 |
| `scripts/test_monitor_task_expand_ui.py` | 프론트엔드 단위 테스트 — `.expand-btn` 렌더 / `#task-panel` DOM / CSS/JS 헬퍼 / body 직계 배치 | 신규 |
| `scripts/test_monitor_e2e.py` | `TaskExpandPanelE2ETests` 클래스 append — `test_task_expand_panel_dom_in_dashboard`, `test_expand_btn_in_task_rows`, `test_task_detail_api_schema`, `test_task_detail_api_404_for_unknown_id`, `test_task_panel_survives_refresh`, `test_slide_panel_css_in_dashboard`, `test_task_panel_js_functions_in_dashboard` | 수정 (build 작성, 실행은 dev-test) |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (신규 — test_monitor_task_detail_api.py) | 28 | 0 | 28 |
| 단위 테스트 (신규 — test_monitor_task_expand_ui.py) | 56 | 0 | 56 |
| 단위 테스트 (기존 전체 — 회귀 없음) | 1279 | 0 | 1279 |

> E2E 테스트 12건 실패는 live 서버(localhost:7321)가 현재 이전 코드로 실행 중이기 때문 — 우리 변경 이전부터 존재하는 상태. 단위 테스트 범주에 해당하지 않음.

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| `scripts/test_monitor_e2e.py::TaskExpandPanelE2ETests` | `test_task_expand_panel_dom_in_dashboard` (AC-12), `test_expand_btn_in_task_rows` (AC-12), `test_task_detail_api_schema` (AC-13), `test_task_detail_api_404_for_unknown_id` (AC-13), `test_task_panel_survives_refresh` (AC-14), `test_slide_panel_css_in_dashboard`, `test_task_panel_js_functions_in_dashboard` |

## 커버리지

- N/A (Dev Config에 `quality_commands.coverage` 미정의)

## 비고

- `_render_task_row_v2`에 `↗` expand-btn 추가 시 기존 `data-phase` / `data-running` 속성을 유지하여 TSK-02-01/02 테스트 회귀 없음 확인.
- E2E 테스트 12건 실패는 TSK-02-03 이후부터 live 서버가 구버전으로 실행 중인 pre-existing 상태 — 본 TSK 변경 전에도 동일하게 실패.
- `_WBS_SECTION_RE`는 모듈 상수로 추가 (`data-model` 스펙 일치).
- design.md §1 결정에 따라 `/api/file` 엔드포인트는 추가하지 않음 — 아티팩트는 경로+크기 메타만 표시.
