# TSK-05-01: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | `_task_panel_css()`에 `.progress-header` sticky + `.ph-badge` + `.ph-meta` + `.ph-history` CSS 추가; `_TASK_PANEL_JS`에 `renderTaskProgressHeader(state)` 함수 신설 + `openTaskPanel()` innerHTML 조립 순서 변경(헤더 맨 앞 삽입) | 수정 |
| `scripts/test_monitor_progress_header.py` | FR-02 헤더 DOM 존재·배지 data-phase·phase_history 3건·sticky position·스피너·null guard 등 30개 단위 테스트 | 신규 |
| `scripts/test_monitor_task_detail_api.py` | `TestApiTaskDetailSchemaUnchanged` 클래스 추가 — v4 응답 필드 집합 회귀 테스트 3개 (`test_api_task_detail_schema_unchanged`, `test_api_task_detail_no_extra_fields`, `test_api_task_detail_no_missing_fields`) | 수정 |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (progress_header) | 30 | 0 | 30 |
| 단위 테스트 (task_detail_api, 전체) | 66 | 0 | 66 |

## E2E 테스트 (작성만 — 실행은 dev-test)

design.md의 QA 체크리스트 중 통합/E2E 케이스는 `scripts/test_monitor_e2e.py` 에 추가 예정 (dev-test 단계에서 실행).
현재 단위 테스트 범위: JS/CSS 문자열 분석 기반 구조 검증.

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| `scripts/test_monitor_e2e.py` (dev-test에서 작성/실행) | `#task-panel-body > .progress-header` DOM 존재, `position:sticky` computed style, `.expand-btn` 클릭 → 헤더 표시 end-to-end |

## 커버리지 (Dev Config에 coverage 정의 시)

N/A — Dev Config에 `quality_commands.coverage` 미정의

## 비고

- `renderTaskProgressHeader(state)` 신설: `state.phase_history.slice(-3).reverse()`로 최근 3건 역순 렌더. `state.last.event` 가 `/_start|_running$` 패턴이면 `.ph-badge` 안에 `.spinner` 삽입 (`data-running="true"` attribute + CSS).
- `openTaskPanel()` 내 `b.innerHTML=` 조립 순서: `renderTaskProgressHeader(data.state)` → `renderWbsSection(...)` → `renderStateJson(...)` → `renderArtifacts(...)` → `renderLogs(...)`
- 기존 실패 테스트 3개 (`test_monitor_dep_graph_html.py::TestDepGraphCanvasHeight640`, `test_monitor_render.py::KpiCountsTests::test_done_excludes_bypass_failed_running`, `test_monitor_render.py::DepGraphSectionEmbeddedTests::test_canvas_height_640px`)는 본 Task 변경 이전부터 존재하는 선행 실패이며 회귀가 아님 (git stash 전/후 동일 실패 확인).
- `/api/task-detail` 응답 스키마 무변경 확인: 기존 8개 키 집합 `{task_id, title, wp_id, source, wbs_section_md, state, artifacts, logs}` 정확히 일치.
