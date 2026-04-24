# TSK-01-03: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor_server/static/app.js` | `_DASHBOARD_JS` + `_PANE_JS` + `_TASK_PANEL_JS` JS 내용 전량 복사 (26,642 bytes, 645줄). IIFE 구조 보존. | 수정 (플레이스홀더 → 실제 내용) |
| `scripts/monitor-server.py` | (1) `_PKG_VERSION = "5.0.0"` 모듈 상수 추가, (2) render_dashboard의 인라인 `<script id="dashboard-js">` + `<script id="task-panel-js">` 두 줄 → `<script src="/static/app.js?v={_PKG_VERSION}" defer>` 한 줄 교체, (3) pane HTML `<script>{_PANE_JS}</script>` → `<script src="/static/app.js?v={_PKG_VERSION}" defer>` 교체, (4) `_task_panel_js()` 함수 삭제 | 수정 |
| `scripts/test_monitor_render.py` | `TestTsk0103ScriptExtraction` 클래스 추가: `test_no_inline_script_block`, `test_script_tag_defer` 테스트 함수 추가. `test_render_dashboard_has_script_tag` 업데이트 (구버전 인라인 어서션 → `/static/app.js` 어서션) | 수정 |
| `scripts/test_monitor_static_assets.py` | `test_js_content_non_empty` 테스트 함수 추가 | 수정 |
| `scripts/test_monitor_pane.py` | `test_inline_script_exactly_once`: 인라인 `<script>` 0개 + `/static/app.js` 존재로 업데이트 | 수정 |
| `scripts/test_monitor_filter_bar.py` | `TestFilterBarJsFunctionsPresent`, `TestFilterBarUrlStateRoundtrip`, `TestFilterSurvivesRefresh` — HTML 인라인 어서션 → `app.js` 파일 내용 어서션으로 전환. `_APP_JS_CONTENT` 모듈 상수 추가 | 수정 |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (신규 TSK-01-03) | 3 | 0 | 3 |
| 단위 테스트 (기존 회귀 검증) | 313+ | 0 (신규) | — |
| 기존 회귀 (TSK-01-03 이전부터 존재) | — | 2 | 2 |

기존 회귀 2건 (TSK-01-03 이전부터 실패):
- `test_done_excludes_bypass_failed_running` (KpiCountsTests)
- `test_canvas_height_640px` (DepGraphSectionEmbeddedTests)

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| `scripts/test_monitor_e2e.py` (기존) | hover 툴팁, EXPAND 패널, 필터 바 시나리오 전량 — dev-test에서 회귀 0 검증 |

## 커버리지 (Dev Config에 coverage 정의 시)
- N/A (Dev Config에 coverage 명령 미정의)

## 비고
- `_task_panel_js()` 래퍼 함수 삭제 — 유일 호출부가 `<script src>` 교체로 제거됨.
- `app.js` 내 JS 청크 순서: `_DASHBOARD_JS`(19,240자) → `_PANE_JS`(620자) → `_TASK_PANEL_JS`(6,779자). design.md 결정대로 현재 인라인 배치 순서 유지.
- `_PANE_JS`의 `if(!pre) return;` guard가 있어 dashboard 페이지에서 실행되어도 no-op 안전.
- pane 페이지(`/pane/<id>`)도 `<script src="/static/app.js" defer>`로 전환 완료.
- 기존 `test_monitor_filter_bar.py`의 JS 함수 존재 검증 테스트들을 HTML 인라인 → `app.js` 파일 기반으로 갱신 (TSK-01-03의 직접적 결과).
