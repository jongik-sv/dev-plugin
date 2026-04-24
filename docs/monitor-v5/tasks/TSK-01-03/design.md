# TSK-01-03: 인라인 `<script>` IIFE → `static/app.js` 추출 + `<script src>` 주입 - 설계

## 요구사항 확인
- `scripts/monitor-server.py` 내 인라인 `<script>` 블록 3개(`_DASHBOARD_JS`, `_PANE_JS`, `_TASK_PANEL_JS`)를 `scripts/monitor_server/static/app.js` 한 파일로 이동하고, SSR HTML `</body>` 직전에 `<script src="/static/app.js?v={pkg_version}" defer></script>` 를 주입한다.
- 동작 변경·추가·삭제 금지 — 순수 cut & paste. IIFE 구조 보존, `defer` 사용.
- `GET /static/app.js` → 200 + `application/javascript; charset=utf-8` + `Cache-Control: public, max-age=300`. 기존 E2E 회귀 0.

## 타겟 앱
- **경로**: N/A (단일 앱 — `scripts/` 단일 Python 프로젝트)
- **근거**: `scripts/` 하위 Python stdlib 서버로 모노레포 구조 없음.

## 구현 방향
- `scripts/monitor-server.py`에서 `_DASHBOARD_JS`(L3899-L4385), `_PANE_JS`(L4761-L4778), `_TASK_PANEL_JS`(L5866-L6007) 세 상수의 JS 내용을 그대로 `scripts/monitor_server/static/app.js`에 순서대로 붙여 넣는다.
- `_PANE_JS`는 `/pane/<id>` 전용 페이지에서도 쓰이므로 `app.js`로 통합한다. `/pane/<id>` 페이지도 `<script src="/static/app.js" defer>`로 전환 — pane 전용 IIFE는 `document.querySelector('pre.pane-capture')` 존재 여부로 자체 guard한다.
- SSR HTML 조립 함수 두 곳에서 인라인 `<script>` 태그를 제거하고 `<script src="/static/app.js?v={pkg_version}" defer></script>` 한 줄로 교체한다.
- `pkg_version`은 `scripts/monitor_server/__init__.py`의 `__version__` 문자열을 모듈 import(`from monitor_server import __version__ as _PKG_VERSION`)로 참조하거나, TSK-01-01이 아직 빌드 단계이므로 `monitor-server.py` 자체에 `_PKG_VERSION = "5.0.0"` 상수를 임시 정의하고 TSK-01-01 완료 후 import로 교체하는 2단계 접근을 선택한다 (설계 결정 참조).
- `_DASHBOARD_JS`, `_PANE_JS`, `_TASK_PANEL_JS` Python 상수 정의 블록은 `app.js` 이전 후 `monitor-server.py`에서 삭제한다.

## 파일 계획

**경로 기준:** 모든 파일 경로는 **프로젝트 루트 기준**으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor_server/static/app.js` | `_DASHBOARD_JS` + `_PANE_JS` + `_TASK_PANEL_JS` JS 내용 전량 (순서대로 붙여 넣기). IIFE 구조 보존. | 수정 (TSK-01-01이 빈 플레이스홀더 생성) |
| `scripts/monitor-server.py` | (1) `_DASHBOARD_JS`·`_PANE_JS`·`_TASK_PANEL_JS` 상수 정의 삭제, (2) `_task_panel_js()` 함수 삭제, (3) 두 군데 인라인 `<script>` 태그를 `<script src="/static/app.js?v={_PKG_VERSION}" defer></script>` 로 교체, (4) `_PKG_VERSION = "5.0.0"` 모듈 상수 추가 | 수정 |
| `scripts/test_monitor_render.py` | `test_no_inline_script_block` + `test_script_tag_defer` 테스트 함수 추가 | 수정 |
| `scripts/test_monitor_static_assets.py` | `test_js_content_non_empty` 테스트 함수 추가 (TSK-01-01이 신규 생성한 파일) | 수정 |

## 진입점 (Entry Points)

이 Task는 신규 페이지/라우트가 아닌 순수 JS 추출 리팩토링이다. "진입점"은 인라인 `<script>` 태그가 교체되는 HTML 조립 위치로 정의한다.

- **사용자 진입 경로**: 기존 대시보드(`http://localhost:7321/`) 접속 → 페이지 로드 시 `<script src="/static/app.js" defer>` 로 JS 로딩. 인터랙션(hover 툴팁 클릭, EXPAND 패널, 필터 바) 동작은 v4 그대로.
- **URL / 라우트**: `GET /static/app.js` (정적 에셋 라우트 — TSK-01-01에서 구현된 `Handler._serve_static`이 처리)
- **수정할 라우터 파일**: `scripts/monitor-server.py` 내 `_build_dashboard_html()` 함수(또는 동등한 HTML 조립 함수) — 인라인 `<script>` 태그 제거 후 `<script src>` 주입. 별도 라우터 파일 없음(단일 파일 서버).
- **수정할 메뉴·네비게이션 파일**: 해당 없음 — JS 추출은 메뉴/네비게이션 변경과 무관.
- **연결 확인 방법**: `GET /` 응답 HTML에 `<script src="/static/app.js` 문자열이 포함되고 인라인 `<script>` 블록이 없음을 unit test(`test_monitor_render.py`)로 검증. E2E: 기존 `test_monitor_e2e.py` hover/EXPAND/필터 시나리오 전량 통과.

## 주요 구조

- **`scripts/monitor_server/static/app.js`**: 3개 JS 청크의 순차 concatenation. 순서: ① `_DASHBOARD_JS` 본문(main IIFE + setupFilterBar IIFE + setupTaskTooltip IIFE) ② `_PANE_JS` 본문(pane auto-refresh IIFE) ③ `_TASK_PANEL_JS` 본문(task panel 전역 함수군). IIFE 구조를 유지하므로 전역 누수 없음. `_TASK_PANEL_JS`는 `r"""` raw string으로 정의된 비-IIFE 전역 함수군이므로 `app.js`에서도 그대로 유지.
- **`_PKG_VERSION` 상수** (`scripts/monitor-server.py`): `"5.0.0"` 하드코딩. 캐시버스팅 쿼리 파라미터(`?v=5.0.0`)에 사용. TSK-01-06 이후 `from monitor_server import __version__ as _PKG_VERSION`으로 교체 예정.
- **HTML 조립 수정 지점 (1) — dashboard**: `_build_dashboard_html()` 또는 동등 함수 내 `f'<script id="dashboard-js">{_DASHBOARD_JS}</script>\n'` + `f'<script id="task-panel-js">{_task_panel_js()}</script>\n'` 두 줄을 `f'<script src="/static/app.js?v={_PKG_VERSION}" defer></script>\n'` 한 줄로 교체.
- **HTML 조립 수정 지점 (2) — pane**: pane HTML 조립 내 `f'<script>{_PANE_JS}</script>\n'` 한 줄을 `f'<script src="/static/app.js?v={_PKG_VERSION}" defer></script>\n'` 한 줄로 교체.
- **`_task_panel_js()` 함수**: `_TASK_PANEL_JS`를 반환하는 단순 래퍼. 삭제 대상 — 직접 참조가 `app.js`로 이전되므로 더 이상 필요 없음.

## 데이터 흐름

```
브라우저 GET / (또는 /pane/<id>)
  → monitor-server.py HTML 조립
  → </body> 직전에 <script src="/static/app.js?v=5.0.0" defer> 삽입
  → 브라우저 HTML 파싱 완료 후 GET /static/app.js
  → Handler._serve_static("app.js") → 200 + MIME + Cache-Control + body
  → JS 실행: IIFE들 순차 실행 (dashboard poll, filter bar, task tooltip, task panel, pane refresh)
```

## 설계 결정 (대안이 있는 경우만)

- **결정**: `_PKG_VERSION = "5.0.0"` 상수를 `monitor-server.py`에 직접 정의 (하드코딩).
- **대안**: `from monitor_server import __version__ as _PKG_VERSION` import (TSK-01-01 완료 전제).
- **근거**: TSK-01-01이 현재 `[dd]` (설계 완료, 빌드 미완료) 상태이므로 `monitor_server` 패키지가 아직 실제로 존재하지 않는다. 하드코딩으로 TSK-01-03을 독립적으로 진행 가능. TSK-01-06(S6 handlers 이전) 완료 시점에 import로 교체.

- **결정**: `_PANE_JS`도 `app.js`에 통합하고 pane 페이지도 `<script src>` 방식으로 전환.
- **대안**: `_PANE_JS`는 pane 전용이므로 별도 `pane.js`로 분리하거나 인라인 유지.
- **근거**: WBS 요구사항 "인라인 `<script>` 블록 제거"는 vendor 참조 외 전량 적용이다. `_PANE_JS` IIFE는 `pre.pane-capture` 존재 여부로 자체 guard하므로 dashboard 페이지에서 실행되어도 무해. 파일을 하나로 통합하면 브라우저 캐시 활용도도 높아진다.

- **결정**: `app.js` 내 JS 청크 순서를 `_DASHBOARD_JS` → `_PANE_JS` → `_TASK_PANEL_JS` 로 배치.
- **대안**: `_TASK_PANEL_JS` 먼저 (함수 선언 우선).
- **근거**: `_TASK_PANEL_JS`의 `openTaskPanel` 등은 `defer` 실행이므로 DOM 로드 후 실행 시점엔 순서 무관. `_DASHBOARD_JS`가 `patchSection`을 참조하고 `_TASK_PANEL_JS`가 `patchSection`을 정의하므로, `defer` 환경에서는 전체 스크립트가 한 번에 파싱된 뒤 실행되어 순서 문제 없음. 현재 인라인 배치 순서(`dashboard-js` → `task-panel-js`) 그대로 유지하는 것이 회귀 리스크 최소화.

## 선행 조건
- TSK-01-01 `[dd]` 상태 확인 완료 (design.md에 `scripts/monitor_server/static/app.js` 빈 플레이스홀더 생성 계획 명시). TSK-01-01 빌드가 완료되어야 `scripts/monitor_server/static/app.js`가 실제로 존재한다 — 본 Task 빌드 전에 TSK-01-01 `[im]` 이상 진행 필요.
- `scripts/monitor-server.py` 현재 6,937줄, 기존 테스트 전량 green.

## 리스크

- **HIGH**: `_PANE_JS` 통합 후 pane 페이지에서 app.js 전체가 실행된다. `_DASHBOARD_JS`의 IIFE가 `document.getElementById('clock')` 등 dashboard 전용 DOM을 참조하지만, 각 IIFE 내부에 `if(!el) return;` guard가 있으므로 실제 오류 없음. 단 `setupFilterBar` IIFE의 `init()` 호출이 pane 페이지에서 filter bar DOM을 찾지 못하는 경우 조용히 no-op되어야 한다 — 코드를 변경하지 않으므로 v4 동작 그대로임. **빌드 전 반드시 pane 페이지 E2E 수동 확인 필요**.
- **HIGH**: `_DASHBOARD_JS` 내 `(function setupTaskTooltip(){...})()` 는 `_DASHBOARD_JS` triple-quoted string의 **일부**다 (L4290 기준). `_DASHBOARD_JS` 상수 전체를 `app.js`로 이동하면 자동으로 포함됨 — 별도 복사 불필요. 이를 인지하지 못하고 setupTaskTooltip을 이중으로 복사하면 이벤트 바인딩 중복 발생.
- **MEDIUM**: `defer` 속성으로 인해 JS 실행이 DOM 파싱 완료 후로 지연된다. 기존 인라인 스크립트는 body 하단 삽입이었으므로 타이밍 차이가 거의 없지만, `DOMContentLoaded` 이전에 실행을 가정하는 코드가 있다면 `defer`로 문제가 될 수 있다. `_DASHBOARD_JS`의 `init()` 함수는 `document.readyState==='loading'` 체크로 guard되어 있으므로 안전.
- **MEDIUM**: `_task_panel_js()` 함수를 삭제할 때 다른 호출부가 있는지 `grep` 확인 필수. 현재 파악된 호출: L4744 한 곳. 추가 호출부가 있으면 삭제 전 처리해야 함.
- **LOW**: `app.js` 파일 크기가 증가하므로 `Cache-Control: public, max-age=300` (5분) 캐시가 만료 전에 버전이 바뀌면 구버전 JS가 캐시될 수 있다. `?v={_PKG_VERSION}` 쿼리 파라미터가 캐시버스터 역할을 한다 — 버전 변경 시 쿼리가 바뀌어 캐시 무효화됨.

## QA 체크리스트
dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

- [ ] (정상 케이스) `GET /static/app.js` → HTTP 200, `Content-Type: application/javascript; charset=utf-8`, `Cache-Control: public, max-age=300` 헤더 포함.
- [ ] (정상 케이스) `GET /static/app.js` 응답 body가 비어있지 않음 (`len(body) > 0`). (`test_monitor_static_assets.py::test_js_content_non_empty`)
- [ ] (정상 케이스) `GET /` 응답 HTML에 `<script src="/static/app.js` 패턴이 포함되고, `defer` 속성이 있음. (`test_monitor_render.py::test_script_tag_defer`)
- [ ] (정상 케이스) `GET /` 응답 HTML에 인라인 `<script id="dashboard-js">` 또는 `<script id="task-panel-js">` 블록이 **없음**. (`test_monitor_render.py::test_no_inline_script_block`)
- [ ] (정상 케이스) `GET /pane/<id>` 응답 HTML에도 인라인 `<script>` 블록이 없고 `<script src="/static/app.js` 가 포함됨.
- [ ] (엣지 케이스) `GET /static/app.js?v=5.0.0` (쿼리 포함 URL) → 동일하게 200 응답 (서버가 쿼리 파라미터를 무시하고 정적 파일 서빙).
- [ ] (에러 케이스) `GET /static/app.js/../monitor-server.py` → 403 또는 404 (path traversal 차단 — TSK-01-01 `Handler._serve_static` 화이트리스트 guard).
- [ ] (통합 케이스) 기존 `test_monitor_e2e.py` hover 툴팁 시나리오 전량 통과.
- [ ] (통합 케이스) 기존 `test_monitor_e2e.py` EXPAND 패널 시나리오 전량 통과.
- [ ] (통합 케이스) 기존 `test_monitor_e2e.py` 필터 바 시나리오 전량 통과.
- [ ] (통합 케이스) 기존 `test_monitor_filter_bar_e2e.py` 전량 통과 (필터 바 동작 회귀 없음).

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**
- [ ] (클릭 경로) 대시보드(`/`) 로드 후 Task 행의 ⓘ 버튼 클릭 → task panel이 열린다 (URL 직접 입력 금지)
- [ ] (화면 렌더링) 핵심 UI 요소(필터 바, task 행, WP 카드, pane 링크)가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다
