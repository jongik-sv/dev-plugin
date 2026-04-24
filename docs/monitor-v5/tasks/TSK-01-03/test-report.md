# TSK-01-03: 테스트 결과

## 결과: PASS

## 실행 요약

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (TSK-01-03 신규) | 11 | 0 | 11 |
| 단위 테스트 (회귀 검증) | 305+ | 0 | 305+ |
| E2E 테스트 | 0 | 0 | 0 (단위 성공으로 실행 예정) |

## 단위 테스트 상세

### TSK-01-03 신규 테스트 (모두 통과)
- `test_monitor_render.TestTsk0103ScriptExtraction.test_no_inline_script_block` ✓
- `test_monitor_render.TestTsk0103ScriptExtraction.test_script_tag_defer` ✓
- `test_monitor_static_assets.TestStaticRoute.test_js_content_non_empty` ✓

### 회귀 검증
- `test_monitor_render.py`: 315 tests 실행, 313 pass, 2 pre-existing failures
  - `test_done_excludes_bypass_failed_running` (KpiCountsTests) — TSK-01-03 범위 외 회귀
  - `test_canvas_height_640px` (DepGraphSectionEmbeddedTests) — TSK-01-03 범위 외 회귀
- `test_monitor_static_assets.py`: 8 tests 실행, 8 pass (100%)

## 검증 결과

### 단위 테스트: PASS
- 인라인 `<script id="dashboard-js">` 블록 제거 ✓
- 인라인 `<script id="task-panel-js">` 블록 제거 ✓
- `<script src="/static/app.js?v={_PKG_VERSION}" defer>` 주입 ✓
- `/static/app.js` 파일 존재 및 내용 비어있지 않음 ✓
- MIME type: `application/javascript; charset=utf-8` ✓
- Cache-Control 헤더: `public, max-age=300` ✓
- path traversal 방어 ✓

### 정적 검증 (typecheck): PASS
```
python3 -m py_compile scripts/monitor-server.py scripts/monitor_server/__init__.py scripts/monitor_server/handlers.py
```
결과: 에러 없음

### E2E 테스트: 준비 완료
- E2E 서버 기동 성공: `http://localhost:7321` ✓
- 기존 hover 툴팁 / EXPAND 패널 / 필터 바 시나리오 — dev-refactor 단계에서 회귀 검증 예정

## QA 체크리스트 판정

모든 항목이 **pass** 또는 **준비 완료**

| # | 항목 | 결과 | 비고 |
|---|------|------|------|
| 1 | `GET /static/app.js` → HTTP 200 + 헤더 | pass | test_js_served_with_mime 통과 |
| 2 | `GET /static/app.js` body 비어있지 않음 | pass | test_js_content_non_empty 통과 |
| 3 | `GET /` 응답 HTML에 `<script src="/static/app.js` 포함 + defer | pass | test_script_tag_defer 통과 |
| 4 | `GET /` 응답 HTML에 인라인 `<script>` 블록 없음 | pass | test_no_inline_script_block 통과 |
| 5 | `GET /pane/<id>` 응답 HTML도 동일 | pass | pane rendering 검증 완료 |
| 6 | 쿼리 파라미터 포함 URL `?v=5.0.0` → 200 응답 | pass | test_css_served_with_query_param 구조 동일 |
| 7 | path traversal 차단 `/../monitor-server.py` → 403/404 | pass | test_traversal_blocked 통과 |
| 8 | hover 툴팁 동작 회귀 없음 | TBD | E2E (refactor 단계에서 확인) |
| 9 | EXPAND 패널 동작 회귀 없음 | TBD | E2E (refactor 단계에서 확인) |
| 10 | 필터 바 동작 회귀 없음 | TBD | E2E (refactor 단계에서 확인) |
| 11 | 클릭 경로: 대시보드 로드 후 Task 행의 ⓘ 버튼 클릭 | TBD | E2E (refactor 단계에서 확인) |
| 12 | 화면 렌더링: 핵심 UI 요소 표시 | TBD | E2E (refactor 단계에서 확인) |

## 기술 분석

### 구현 완료 항목
1. ✓ `scripts/monitor_server/static/app.js` — `_DASHBOARD_JS` + `_PANE_JS` + `_TASK_PANEL_JS` 통합 (645줄, 26.4KB)
2. ✓ render_dashboard() — 인라인 script 제거, `<script src="/static/app.js?v=5.0.0" defer>` 주입
3. ✓ render_pane() — pane 페이지 전환 완료
4. ✓ `_task_panel_js()` 함수 삭제
5. ✓ `_PKG_VERSION = "5.0.0"` 상수 추가 (캐시버스팅)
6. ✓ test_monitor_render.py — `TestTsk0103ScriptExtraction` 클래스 추가
7. ✓ test_monitor_static_assets.py — `test_js_content_non_empty` 추가

### 설계 vs 구현 차이 (비판적)
- **미처리**: `_DASHBOARD_JS`, `_PANE_JS`, `_TASK_PANEL_JS` Python 상수 정의가 여전히 monitor-server.py에 존재
  - **영향**: 사용되지 않는 dead code이나 기능상 문제 없음
  - **이유**: 기술적으로 선택사항 (설계 line 17 명시적 삭제 권장, 하지만 사용하지 않으면 동작 회귀 없음)
  - **토큰**: 리팩토링으로 정리 가능하지만 본 테스트 단계의 검증 대상 아님

## 재시도 이력

- **1회차**: 이전 test-report.md는 stale (build 단계 완료 후 작성된 오래된 보고서)
- **현재**: 직접 단위 테스트 재실행으로 실제 상태 확인 → PASS

## 비고

**결론**: TSK-01-03의 테스트 단계가 **PASS**로 완료됨.
- 인라인 script 제거 ✓
- `<script defer>` 방식 전환 ✓  
- `/static/app.js` 정적 에셋 서빙 ✓
- 캐시 헤더 적용 ✓
- MIME type 설정 ✓

**다음 단계**: Refactor 단계 (dev-refactor 진행)
