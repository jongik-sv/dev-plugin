# TSK-01-02: 인라인 `<style>` → `static/style.css` 추출 + `<link>` 주입 - 설계

## 요구사항 확인
- `scripts/monitor-server.py` 내 세 곳의 인라인 `<style>` CSS(DASHBOARD_CSS, _task_panel_css(), _PANE_CSS)를 `scripts/monitor_server/static/style.css`로 cut & paste 이전한다. 규칙 변경·추가·삭제 금지 — 순수 이전만.
- SSR HTML 두 곳(`render_dashboard`, `_render_pane_html`)의 `<head>` 최상단(meta 다음 즉시)에 `<link rel="stylesheet" href="/static/style.css?v={version}">` 태그를 주입하고 인라인 `<style>` 블록을 완전히 제거한다.
- 시각 스냅샷 diff 0이 유일한 허용 기준 — `test_monitor_e2e.py`가 회귀 없이 통과해야 하고, `grep -n "<style" scripts/monitor-server.py` 결과가 0이어야 한다.

## 타겟 앱
- **경로**: N/A (단일 앱)
- **근거**: 이 프로젝트는 `scripts/monitor-server.py` 단일 파이썬 모듈 + `scripts/monitor_server/` 패키지로 구성된 단일 앱이다.

## 구현 방향
- `DASHBOARD_CSS` (현재 L1184~L2231, `_minify_css` 압축 후 `<head>` `<style>` 주입), `_task_panel_css()` 함수 반환 CSS (현재 `<body>` 하단 `<style>`), `_PANE_CSS` 상수 (pane 페이지 `<head>` `<style>`)를 **하나의** `scripts/monitor_server/static/style.css` 파일로 합산 이전한다.
- `monitor-server.py`에서 세 CSS 원천을 제거하고, 두 HTML 렌더러(`render_dashboard`, `_render_pane_html`)에 `<link rel="stylesheet" href="/static/style.css?v={version}">` 태그를 삽입한다.
- 버전 값은 TSK-01-01이 제공하는 `monitor_server.__version__` 문자열을 사용한다. 패키지 import가 불가한 fallback 경로에서는 `style.css` 파일의 mtime 기반 값을 사용한다.
- `_handle_static`은 TSK-01-01 화이트리스트(`{"style.css", "app.js"}`)에 `style.css`가 이미 포함되어 있으므로 `Cache-Control: public, max-age=300` + `text/css; charset=utf-8` 헤더로 자동 서빙된다.
- `test_monitor_render.py`의 기존 `DASHBOARD_CSS` 직접 참조 테스트들은 `monitor_server.DASHBOARD_CSS` 재-export 또는 `monitor_server/static/style.css` 파일 read로 마이그레이션이 필요하다 — dev-build 범위.

## 파일 계획

**경로 기준:** 모든 파일 경로는 **프로젝트 루트 기준**으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor_server/static/style.css` | 세 CSS 블록(DASHBOARD_CSS 원본, _task_panel_css() 원본, _PANE_CSS)을 section 주석으로 구분하여 합산 저장. UTF-8, LF 개행. | 신규 |
| `scripts/monitor-server.py` | DASHBOARD_CSS 변수(L1184~L2238), `_task_panel_css()` 함수 CSS 내용, `_PANE_CSS` 상수 제거. 두 렌더러에 `<link>` 태그 주입. `_css_version()` 헬퍼 추가. | 수정 |
| `scripts/test_monitor_render.py` | `DASHBOARD_CSS` 직접 참조 테스트들을 `style.css` 파일 read 또는 re-export 변수로 마이그레이션. `test_no_inline_style_block`, `test_link_tag_injected_in_head` 신규 추가. | 수정 |
| `scripts/test_monitor_static_assets.py` | `test_css_content_non_empty`(style.css 내용 비어있지 않음), `test_css_served_with_cache_control`(200 + text/css + max-age=300) 신규 추가. | 신규 |

> 이 Task는 순수 인프라 이전으로 라우터 파일이나 메뉴/네비게이션 파일 수정이 없다. 정적 파일 서빙은 TSK-01-01의 `_handle_static` 라우트가 담당한다.

## 진입점 (Entry Points)

- **사용자 진입 경로**: 브라우저에서 `http://localhost:7321/` 접속 → 대시보드 페이지 렌더링. 또는 `http://localhost:7321/pane/{id}` 접속 → pane 페이지 렌더링.
- **URL / 라우트**: `/` (대시보드), `/pane/{id}` (pane 페이지), `/static/style.css?v=...` (정적 에셋)
- **수정할 라우터 파일**: `scripts/monitor-server.py`의 `MonitorHandler.do_GET` 라우팅 — `/static/*` 처리는 기존 `_handle_static`이 담당하므로 추가 수정 없음. `_is_static_path` 화이트리스트는 TSK-01-01이 `style.css`를 포함시킴.
- **수정할 메뉴·네비게이션 파일**: 해당 없음 — 이 Task는 CSS 위치 이전이며 UI 네비게이션 구조 변경 없음.
- **연결 확인 방법**: `GET /static/style.css` → 200 응답 + `text/css; charset=utf-8` + `Cache-Control: public, max-age=300`. `GET /` HTML에 `<link rel="stylesheet" href="/static/style.css?v=...">` 포함 여부 확인.

## 주요 구조

- **`_css_version() -> str`** (`scripts/monitor-server.py` 신규 헬퍼): `monitor_server.__version__` import 시도 → 실패 시 `style.css` mtime 기반 hex 문자열 반환. render 함수들이 이를 호출하여 `?v=` 쿼리 파라미터를 생성한다.
- **`DASHBOARD_CSS` 제거 + `_minify_css` 제거**: 변수와 함수 모두 삭제. 기존 `assertIn("...", monitor_server.DASHBOARD_CSS)` 테스트는 `style.css` 파일 read 기반으로 전환.
- **`_task_panel_css()` 반환값 제거**: 함수 자체를 삭제하거나 빈 문자열 반환으로 변경. `<style>{_task_panel_css()}</style>` → 제거.
- **`_PANE_CSS` 상수 제거**: 상수 삭제 후 `_render_pane_html`에서 `<style>{_PANE_CSS}</style>` → `<link>` 태그 교체.
- **`render_dashboard` 수정**: `<style>{DASHBOARD_CSS}</style>` 줄과 `<style>{_task_panel_css()}</style>` 줄을 `<link rel="stylesheet" href="/static/style.css?v={_css_version()}">` 한 줄로 교체. 위치는 `<meta name="viewport">` 다음, 기존 preconnect `<link>` 이전.
- **`_render_pane_html` 수정**: `<style>{_PANE_CSS}</style>` → `<link rel="stylesheet" href="/static/style.css?v={_css_version()}">`.
- **`style.css` 구성**: Section 주석으로 세 CSS 블록을 구분. 순서: (1) DASHBOARD_CSS 원본(압축 전 원문), (2) task-panel CSS, (3) pane CSS.

## 데이터 흐름

`monitor-server.py` 기동 → `_css_version()` 호출 시 `monitor_server.__version__` 조회(또는 mtime) → 버전 문자열 생성 → `render_dashboard`/`_render_pane_html`이 `<link href="/static/style.css?v={ver}">` 포함한 HTML 반환 → 브라우저가 `GET /static/style.css?v={ver}` 요청 → `_handle_static`이 `scripts/monitor_server/static/style.css` 파일 read → `text/css; charset=utf-8` + `Cache-Control: public, max-age=300` 응답.

## 설계 결정 (대안이 있는 경우만)

- **결정**: 세 CSS 블록(DASHBOARD_CSS, _task_panel_css, _PANE_CSS)을 하나의 `style.css`로 통합
- **대안**: `dashboard.css`, `task-panel.css`, `pane.css` 세 파일로 분리 서빙
- **근거**: TSK-01-01 화이트리스트가 `style.css` 단일 파일을 명시하고, fan-in Task(TSK-03-01 등)가 단일 진입점을 기대하므로 단일 파일이 명세 준수에 적합하다.

- **결정**: `_css_version()`에서 `monitor_server.__version__` import → mtime fallback 순서
- **대안**: 하드코딩된 버전 상수 또는 mtime 전용
- **근거**: TSK-01-01 완료 후 패키지가 존재하면 의미있는 버전 문자열을 사용하고, 개발 중(TSK-01-01 미완료 상태)에는 mtime으로 캐시 무효화를 보장한다.

- **결정**: `<link>` 태그를 `<meta charset>` / `<meta name="viewport">` 다음 즉시, preconnect `<link>` 이전에 배치
- **대안**: preconnect 이후 배치
- **근거**: TRD R-A(FOUC 방지)는 `<head>` 최상단 배치를 요구한다. preconnect 힌트보다 실제 스타일시트를 먼저 브라우저에 선언하면 파싱 초기부터 스타일이 준비된다.

## 선행 조건

- **TSK-01-01 완료 필수**: `scripts/monitor_server/` 패키지 디렉토리, `__init__.py`(버전 문자열 포함), `static/` 디렉토리, `/static/*` 라우트 + 화이트리스트(`style.css` 포함)가 모두 존재해야 한다.
- `_handle_static`이 `style.css`를 `text/css; charset=utf-8` + `Cache-Control: public, max-age=300`으로 서빙하는 기능이 TSK-01-01에서 구현되어야 한다.

## 리스크

- **HIGH: 기존 테스트의 `DASHBOARD_CSS` 직접 참조 회귀** — `test_monitor_render.py`에 `monitor_server.DASHBOARD_CSS`를 직접 assert하는 테스트가 약 10개 이상 존재한다. CSS를 파일로 이전하면 이 변수가 사라져 테스트가 깨진다. dev-build 단계에서 `monitor_server` 모듈 레벨에서 `DASHBOARD_CSS = Path(...).read_text()` 형태로 re-export하거나, 각 테스트를 파일 read 기반으로 전환해야 한다.
- **HIGH: `_minify_css` 의존 제거** — 현재 `render_dashboard`의 HTML 비교 테스트들이 압축된(공백 제거) CSS 형식을 기대할 수 있다. 파일로 이전 후 minify 여부를 결정해야 하며, 결정에 따라 기존 CSS 내용 비교 테스트가 영향받을 수 있다.
- **MEDIUM: pane 페이지의 `_PANE_CSS`는 별도 `:root` 변수 정의 포함** — `DASHBOARD_CSS`와 `:root` 변수 이름 충돌 여부 확인 필요. 두 블록이 같은 파일에 합산될 때 `:root` 블록이 중복될 수 있다. 실제로 `--bg`, `--accent` 변수명이 두 블록 모두에 다른 값으로 정의되어 있어 나중 선언이 이전 선언을 덮어쓸 수 있다.
- **MEDIUM: `style.css` 파일 경로 해석** — `_handle_static`이 `plugin_root/skills/dev-monitor/vendor/` 경로를 사용하는 현재 구현을 TSK-01-01이 `Path(__file__).parent / "static"` 기반으로 변경해야 한다. 이 변경이 TSK-01-01 범위인지 TSK-01-02 범위인지 명확히 경계를 그어야 한다.
- **LOW: 버전 쿼리 파라미터 무시 처리** — `/static/style.css?v=...`에서 `?v=` 부분을 URL parse 시 path 분리가 필요하다. 현재 `_is_static_path`는 raw path를 비교하므로 쿼리 스트링 포함 시 whitelist 매칭 실패할 수 있다. dev-build에서 `urlsplit(path).path` 추출 후 whitelist 비교로 수정 필요.

## QA 체크리스트

- [ ] `grep -n "<style" scripts/monitor-server.py` 결과가 0이다 (인라인 style 블록 완전 제거)
- [ ] `GET /static/style.css` → HTTP 200 + `Content-Type: text/css; charset=utf-8` + `Cache-Control: public, max-age=300`
- [ ] `scripts/monitor_server/static/style.css` 파일이 존재하고 내용이 비어있지 않다 (`test_monitor_static_assets.py::test_css_content_non_empty`)
- [ ] `render_dashboard(model)` 반환 HTML의 `<head>` 내에 `<link rel="stylesheet" href="/static/style.css?v=...">` 태그가 존재한다 (`test_monitor_render.py::test_link_tag_injected_in_head`)
- [ ] `render_dashboard(model)` 반환 HTML에 `<style>` 태그가 존재하지 않는다 (`test_monitor_render.py::test_no_inline_style_block`)
- [ ] `<link rel="stylesheet" href="/static/style.css?v=...">` 태그가 `<meta charset="utf-8">` 바로 다음 또는 `<meta name="viewport">` 다음 즉시 위치한다 (TRD R-A: FOUC 방지)
- [ ] `_render_pane_html(...)` 반환 HTML의 `<head>`에도 `<link>` 태그가 존재하고 `<style>` 태그가 없다
- [ ] `style.css` 내 CSS 규칙이 이전 전후 동일하다 (추가·삭제·변경 없음, 공백만 허용)
- [ ] 기존 `test_monitor_render.py` 전체 회귀 0 (`pytest -q scripts/test_monitor_render.py` 통과)
- [ ] 기존 `test_monitor_e2e.py` 시각 스냅샷 diff 0 (브라우저 렌더링 픽셀 회귀 없음)
- [ ] `style.css`에 `DASHBOARD_CSS`, task-panel CSS, pane CSS 세 블록이 모두 존재한다
- [ ] `_css_version()` 함수가 빈 문자열 또는 None이 아닌 유효한 문자열을 반환한다
- [ ] `GET /static/style.css?v=someversion` (쿼리 파라미터 포함) → 200 정상 서빙 (쿼리 스트링 무시)
- [ ] path traversal 시도 `GET /static/../monitor-server.py` → 404
- [ ] (클릭 경로) 브라우저에서 `http://localhost:7321/` 접속 → 스타일이 적용된 대시보드가 렌더링된다 (FOUC 없음)
- [ ] (화면 렌더링) 대시보드의 핵심 UI 요소(WP 카드, KPI 섹션, Phase 표)가 올바른 색상·레이아웃으로 표시된다 — 시각 스냅샷 기준으로 이전 버전과 동일해야 한다
