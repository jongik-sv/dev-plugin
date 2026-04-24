# TSK-01-02 Build Report

**Task**: 인라인 `<style>` → `static/style.css` 추출 + `<link>` 주입  
**Status**: `[im]` (build.ok)  
**Date**: 2026-04-24

---

## 구현 요약

### 1. CSS 추출 (`scripts/monitor_server/static/style.css`)

세 개의 인라인 CSS 소스를 단일 파일로 통합:
- **Section 1** – `DASHBOARD_CSS` (37804 chars): 대시보드 메인 스타일
- **Section 2** – `_task_panel_css()` (~3500 chars): 슬라이드 패널 스타일
- **Section 3** – `_PANE_CSS` (~1042 chars): pane 상세 페이지 스타일

총 파일 크기: **42706 bytes**

### 2. `<link>` 태그 주입 (`scripts/monitor-server.py`)

- `render_dashboard`: `<meta name="viewport">` 직후, `<title>` 이전에 `<link rel="stylesheet" href="/static/style.css?v={_css_version()}">` 삽입; 기존 `<style>` 블록 2개 제거
- `_render_pane_html`: `<meta charset="utf-8">` 직후에 동일 `<link>` 삽입; 기존 `<style>` 블록 제거

### 3. `_css_version()` 헬퍼 추가

캐시 버스팅을 위한 버전 문자열 생성:
1. `monitor_server.__version__` 우선 (패키지 설치 시)
2. `style.css` mtime hex 폴백
3. 최종 폴백: `"0"`

### 4. `_STATIC_WHITELIST` 확장

`style.css`, `app.js` 추가 (5 → 7 항목)  
`_PACKAGE_STATIC_FILES = frozenset({"style.css", "app.js"})` — 패키지 로컬 라우팅 분기용

### 5. 인라인 `<style>` 제거 확인

```
grep -n "<style" scripts/monitor-server.py → 0 matches
```

---

## 테스트 결과

### TSK-01-02 전용 테스트 (신규)

| 테스트 파일 | 클래스 | 테스트 수 | 결과 |
|---|---|---|---|
| `test_monitor_render.py` | `TestTsk0102CssExtraction` | 6 | ✅ ALL PASS |
| `test_monitor_static_assets.py` | `TestStaticRoute` (+2) | 8 | ✅ ALL PASS |
| `test_monitor_static.py` | (whitelist count 수정) | 62 total | ✅ ALL PASS |

### 회귀 분석

- **베이스라인 실패 수**: 53 (HEAD 기준)
- **현재 실패 수**: 45
- **신규 실패**: 0 (TSK-01-02가 도입한 실패 없음)
- **해소된 실패**: 8 (CSS-in-HTML assertion → style.css 파일 기반으로 마이그레이션)

해소된 테스트:
- `test_monitor_task_detail_api.py::TestSlidePanelDomInBody::test_slide_panel_css_included`
- `test_monitor_task_detail_api.py::TestSlidePanelDomInBody::test_slide_panel_transition_css`
- `test_monitor_task_detail_api.py::TestSlidePanelDomInBody::test_slide_panel_zindex_overlay`
- `test_monitor_task_detail_api.py::TestSlidePanelDomInBody::test_slide_panel_zindex_panel`
- `test_monitor_task_expand_ui.py::TestDashboardIncludesPanelAssets::test_task_panel_css_in_output`
- `test_monitor_static.py::TestIsStaticPath::test_whitelist_constant_has_five_entries`
- `test_monitor_static.py::TestNodeHtmlLabelStaticRoute::test_whitelist_has_five_entries`
- `test_monitor_render.py::V3Stage4PhaseHistoryDrawerTests::test_render_dashboard_has_script_tag`

---

## 스코프 준수

- **Zero CSS rule 추가**: 기존 CSS를 그대로 복사, 신규 규칙 없음
- **TSK-01-03 스코프 오염 없음**: `_PKG_VERSION` 상수 및 app.js `<script src>` 변경 제거 완료
- **JS 블록 유지**: `render_dashboard`의 `<script id="dashboard-js">`, `<script id="task-panel-js">` 인라인 유지 (TSK-01-03 범위)
- **pane JS 유지**: `_render_pane_html`의 `<script>{_PANE_JS}</script>` 인라인 유지 (TSK-01-03 범위)
