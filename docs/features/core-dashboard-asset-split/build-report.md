# core-dashboard-asset-split: Build Report

## 결과: PASS

## 커밋 요약

| 커밋 | 내용 | core.py LOC 변화 |
|------|------|------------------|
| C0-1 (build-00) | baseline 기록 + bundle md5 pinning | — |
| C1-1 (build-01) | DASHBOARD_CSS → static/dashboard.css | −1,210 |
| C1-2 (build-02) | _DASHBOARD_JS → static/dashboard.js | −545 |
| C1-3 (build-03) | _PANE_CSS + _PANE_JS → static/pane.{css,js} | −42 |
| C1-4 (build-04) | _task_panel_css → static/task_panel.css | −103 |
| C1-5 (build-05) | _TASK_PANEL_JS → static/task_panel.js | −277 |
| C2-1 (build-06) | handlers.py 주석 업데이트 | 0 |
| C3-1 (build-07) | loader 섹션 주석 + __init__.py 업데이트 | 0 |

**Net LOC 변화**: 5,418 → 3,284 (−2,134 LOC)

## Bundle MD5 검증

| 번들 | baseline md5 | 최종 md5 | 일치 |
|------|-------------|---------|------|
| style.css | dcab587d6fd4fc32f46117fbdce06e44 | dcab587d6fd4fc32f46117fbdce06e44 | ✅ |
| app.js | 479d0ac147cd74f4664c00acd0d38c78 | 479d0ac147cd74f4664c00acd0d38c78 | ✅ |

## Pytest 결과

```
3 failed, 1996 passed, 176 skipped (baseline 유지)
pre-existing 실패 (변동 없음):
  - test_monitor_server_bootstrap.py::TestServerBinding::test_root_returns_200_or_501
  - test_monitor_task_expand_ui.py::TestTaskPanelCss::test_initial_right_negative
  - test_platform_smoke.py::SmokeTestBase::test_pane_polling_interval
```

## 생성/수정된 파일

### 신규 파일 (static/)
- `scripts/monitor_server/static/dashboard.css` (42334 bytes, md5=f61ba0d1bcbbe881050b43c89fa15ae2)
- `scripts/monitor_server/static/dashboard.js` (21587 bytes, md5=c8d737b021535d4e5d6df67722e97aea)
- `scripts/monitor_server/static/pane.css` (1042 bytes, md5=a305f191159b7e22f32eaae606b1e796)
- `scripts/monitor_server/static/pane.js` (619 bytes, md5=36b56d102aad652c3302584915cd14b6)
- `scripts/monitor_server/static/task_panel.css` (6577 bytes, md5=244b96ed7451aa9126a902ae1ac2031b)
- `scripts/monitor_server/static/task_panel.js` (12316 bytes, md5=816c2d3c53a5dae8f818480aa419c43d)

### 수정 파일
- `scripts/monitor_server/core.py` — 6개 인라인 블록 제거 + _load_static_text loader 추가
- `scripts/monitor_server/handlers.py` — _serve_local_static 주석 업데이트
- `scripts/monitor_server/__init__.py` — Phase 2-c 이관 내역 + static/ 모듈 설명 추가

### 테스트 Shim 적용
- `scripts/test_font_css_variables.py` — dashboard.css file-first fallback
- `scripts/test_monitor_dep_graph_html.py` — dashboard.css file-first fallback
- `scripts/test_monitor_shared_css.py` — dashboard.css file-first fallback
- `scripts/test_monitor_pane_size.py` — dashboard.css file-first fallback
- `scripts/test_monitor_task_spinner.py` — dashboard.css file-first fallback
- `scripts/test_monitor_grid_ratio.py` — dashboard.css file-first fallback
- `scripts/test_monitor_fold.py` — dashboard.js file-first fallback
- `scripts/test_monitor_fold_helper_generic.py` — dashboard.js file-first fallback

## 주요 결정 사항

### dashboard.css 저장 형식
design.md는 "pre-minify 원본" 저장을 명시했으나, Python `"""` 문자열의 이스케이프 해석
문제로 인해 **minified 런타임 값** 저장을 채택.
`_minify_css`는 이미 minified 문자열에 대해 idempotent하므로 round-trip 동작 보존 성립.

### C2-1 stale 파일 삭제 보류
design.md에서 `static/style.css`와 `static/app.js` 삭제를 계획했으나,
17개 이상 테스트 파일이 직접 디스크 파일 읽기를 수행하여 삭제 시 31개 이상 신규 실패 발생.
번들이 SSOT이므로 기능 영향은 없으며, stale 파일은 유지.

### facade 계약 유지
- `core.DASHBOARD_CSS` — hasattr True, minified string
- `core._DASHBOARD_JS` — hasattr True
- `core._PANE_CSS` — hasattr True
- `core._PANE_JS` — hasattr True
- `core._task_panel_css()` — callable, returns string
- `core._task_panel_js()` — callable, returns string
- `core._TASK_PANEL_JS` — hasattr True
