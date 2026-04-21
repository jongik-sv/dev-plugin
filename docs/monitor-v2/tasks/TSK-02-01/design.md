# TSK-02-01: 부분 fetch + DOM 교체 엔진 - 설계

## 요구사항 확인
- 5초 주기로 `/`를 재요청해 응답 HTML의 `<section data-section="…">` 블록을 추출, 변경된 섹션만 `innerHTML`을 교체한다 (서버 SSR 결과를 단일 진실원으로 사용; TRD §13 첫 열린 질문 — 단순 교체 결정).
- 폴링은 `AbortController`로 중복 요청을 취소하고, 실패는 silent catch로 다음 틱에서 재시도하며, auto-refresh 토글 OFF 시 `clearInterval`로 중지한다.
- 부분 교체 후에도 `<details open>` 펼침 / 스크롤 위치 / 필터 칩 / 드로어 상태 등 사용자 인터랙션 상태를 잃지 않는다 (이벤트 위임 + DOM 외부 state object 사용).

## 타겟 앱
- **경로**: N/A (단일 앱 — `scripts/monitor-server.py` 단일 stdlib 모듈)
- **근거**: dev-plugin 저장소는 모노레포가 아니며 모니터 서버는 `scripts/monitor-server.py` 한 파일에 인라인 CSS/JS 문자열을 갖는 구조다 (dev-config `frontend.description` 참조).

## 구현 방향
- TSK-01-06이 도입한 `_DASHBOARD_JS` 슬롯에 IIFE 한 개를 추가한다. 모듈 로컬 state object와 `startMainPoll/stopMainPoll/fetchAndPatch/patchSection` 4개 함수만 노출한다.
- 폴링은 `setInterval(tick, 5000)` + 첫 틱은 즉시 실행. 각 틱은 ① 직전 `AbortController.abort()` → ② 새 `AbortController` 생성 → ③ `fetch('/', {cache:'no-store', signal})` → ④ `text/html` 응답을 `DOMParser`로 파싱 → ⑤ 신규 doc의 모든 `[data-section]`을 순회하며 현재 doc의 동일 키 섹션과 `innerHTML`을 비교, 다르면 통째 교체.
- auto-refresh 토글(`#auto-refresh-toggle`, TSK-01-06 sticky header 안에 위치)의 `change` 이벤트로 `state.autoRefresh`를 갱신하고, `false`면 `stopMainPoll()`, `true`면 `startMainPoll()`로 재기동한다 (`change`/`click` 위임 한 곳에서 처리).
- DOM 교체 후 클릭 핸들러 유실을 방지하기 위해 모든 click/`change` 리스너는 `document` 한 곳에 위임 등록한다 (특히 `data-pane-expand`).

## 파일 계획

**경로 기준:** 모든 파일 경로는 프로젝트 루트 기준이다. 단일 앱이므로 접두어는 없다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` (router — `MonitorHandler.do_GET` + `_route_*` 메서드 라우터 테이블) | 라우팅 자체는 변경하지 않으나, 기존 `/` 라우트가 반환하는 `render_dashboard()` 결과 HTML에 `<script>{_DASHBOARD_JS}</script>`가 `</body>` 직전 주입되도록 수정한다. 즉 본 라우터 파일의 `render_dashboard`/`_DASHBOARD_JS` 정의 영역만 수정한다. | 수정 |
| `scripts/monitor-server.py` (nav/menu — sticky header 안의 `<input id="auto-refresh-toggle">`) | 본 프로젝트는 단일 페이지 SPA로 별도 sidebar/nav 파일이 없다. 메뉴 진입점 역할은 `_section_sticky_header`(TSK-01-06)가 헤더에 그린 auto-refresh 토글이 담당한다. 본 Task는 이 토글의 `change` 이벤트를 `document.addEventListener('change', …)` 위임으로 구독·해제하여 폴링을 켜고 끈다. | 수정 |
| `scripts/test_monitor_dashboard_polling.py` | `_DASHBOARD_JS` 문자열에 대한 단위 테스트 (라인 수 ≤ 200, 필수 식별자 `startMainPoll`/`stopMainPoll`/`fetchAndPatch`/`patchSection`/`AbortController`/`'/'` fetch · `data-section` 셀렉터 포함, `<script>` 태그 1회 주입 검증). | 신규 |

> 라우터 추가/변경은 없다. TSK-01-06이 이미 `/`를 `render_dashboard`에 매핑했고, 본 Task는 **그 응답에 포함될 인라인 JS 문자열만** 채워 넣는다. 메뉴/네비게이션도 별도 파일이 없는 단일 페이지 SSR 대시보드이므로 sticky header 내 auto-refresh 토글 (`<input id="auto-refresh-toggle">`, TSK-01-06이 헤더에 내장)이 메뉴 진입점 역할을 한다.

## 진입점 (Entry Points)

**대상**: domain=frontend → 진입점 명시 필수. dev-plugin 모니터 대시보드는 단일 페이지 SPA이므로 "메뉴 진입"은 sticky header에 내장된 auto-refresh 토글로 갈음한다.

- **사용자 진입 경로**: 브라우저로 `http://localhost:7321/` 접속 → sticky header(`<header data-section="hdr">`) 안의 "Auto-refresh" 토글(`<input id="auto-refresh-toggle" type="checkbox">`)을 클릭하여 폴링을 켜고 끈다. 토글이 ON인 동안 5초마다 본문 섹션이 자동 업데이트된다.
- **URL / 라우트**: `/` (GET; HTML 대시보드 — `MonitorHandler.do_GET`이 `_handle_dashboard`로 분기하여 `render_dashboard(model)` 결과를 반환).
- **수정할 라우터 파일**: `scripts/monitor-server.py` — `render_dashboard()` 함수가 `</body>` 직전에 `<script>{_DASHBOARD_JS}</script>` 한 줄을 추가한다. `do_GET`의 라우팅 테이블(`_route_*` 메서드들)은 변경하지 않는다 (TSK-01-06이 기존 `/` 라우팅 그대로 사용).
- **수정할 메뉴·네비게이션 파일**: `scripts/monitor-server.py` — sticky header 안의 auto-refresh 토글(`<input id="auto-refresh-toggle">`, TSK-01-06이 `_section_sticky_header` 또는 `render_dashboard`에서 생성)을 본 Task의 JS가 `document.addEventListener('change', …)` 위임으로 구독한다. 별도 사이드바/네비 컴포넌트 파일은 존재하지 않는다.
- **연결 확인 방법**: 브라우저 QA에서 `http://localhost:7321/`에 접속 → DevTools Network 탭에서 5초 간격으로 `GET /`가 200으로 반복되는지 확인 → sticky header의 Auto-refresh 토글을 OFF → 다음 5초 동안 신규 `GET /`가 발생하지 않음 → 다시 ON → 폴링 재개. URL을 직접 입력해 진입한 뒤 토글 인터랙션만으로 검증한다 (`page.goto('/api/state')` 등 직접 호출 금지).

> 비-페이지 UI는 아니지만, JS는 모든 섹션(`data-section="hdr|kpi|wp-cards|wbs|features|activity|timeline|team|subagents"`)에 적용된다. 적용 대상 상위 페이지는 `/` 한 개다.

## 주요 구조

`_DASHBOARD_JS` 안의 IIFE는 다음 식별자를 노출한다 (모듈 외부에는 무엇도 노출하지 않음):

- `state` (object) — `{ autoRefresh: bool, mainPollId: int|null, mainAbort: AbortController|null }`. DOM 외부에서 사용자 인터랙션·폴링 상태를 보관 (DOM 교체에 영향받지 않음).
- `startMainPoll()` / `stopMainPoll()` — `setInterval`/`clearInterval`로 5초 폴링을 켜고 끈다. start는 즉시 1회 `tick()` 후 인터벌 등록, stop은 `mainAbort?.abort()`까지 호출.
- `tick()` — 한 사이클: `state.autoRefresh`가 false면 즉시 return, 그 외에는 `mainAbort = new AbortController()` → `fetchAndPatch(mainAbort.signal)`. 첫 줄에서 직전 abort 호출.
- `fetchAndPatch(signal)` — `fetch('/', {cache:'no-store', signal})` → `r.ok ? r.text() : null` → `DOMParser.parseFromString(text, 'text/html')` → 결과 doc의 모든 `[data-section]` 노드를 순회하며 `patchSection(name, newHtml)` 호출. 네트워크/파싱/abort 예외는 한 곳에서 silent catch.
- `patchSection(name, newHtml)` — `document.querySelector('[data-section="' + name + '"]')`로 현재 노드를 찾고, `current.innerHTML !== newHtml`일 때만 `current.innerHTML = newHtml`을 수행한다. 동일하면 무변경(스크롤·`<details open>` 보존). 헤더(`hdr`)는 토글 상태 유실 방지를 위해 교체 전 `<input id="auto-refresh-toggle">`의 `checked` 값을 보존한 뒤 교체 후 복원한다.
- `init()` — DOMContentLoaded 또는 즉시 실행: `document.addEventListener('change', …)`로 토글을 구독, `state.autoRefresh = document.getElementById('auto-refresh-toggle')?.checked ?? true`로 초기화, `startMainPoll()` 호출.

## 데이터 흐름
- 입력: 5초 타이머 틱 + auto-refresh 토글 변경 이벤트.
- 처리: `tick()` → 직전 요청 abort → `fetch('/')` → `DOMParser`로 응답 파싱 → 신규 doc의 `[data-section]` 노드들과 현재 doc의 동일 키 노드를 비교, `innerHTML` 차이가 있을 때만 교체.
- 출력: 변경된 섹션의 DOM이 갱신된다. 변경 없는 섹션의 스크롤·`<details open>`·필터 칩 상태는 보존되고, 토글·드로어 인터랙션 핸들러는 이벤트 위임으로 영향을 받지 않는다.

## 설계 결정 (대안이 있는 경우만)

- **결정**: `fetch('/')`로 SSR HTML을 다시 받아 `DOMParser`로 `[data-section]` 단위 비교·교체 (단순 innerHTML 치환).
- **대안 1**: `fetch('/api/state')`로 JSON만 받고 클라이언트가 템플릿으로 재렌더 (WBS requirements 첫 줄에 언급).
- **대안 2**: 수동 DOM diff (텍스트 노드 단위 비교 후 최소 패치 적용).
- **근거**: WBS tech-spec과 TRD §13 첫 열린 질문 결정에 따라 단순 교체 채택. `/api/state` JSON 경로는 클라이언트 템플릿 코드가 필요해 200줄 제한을 깨고, 서버 렌더와 클라이언트 렌더를 동시에 유지해야 하므로 거부. 수동 diff는 복잡도 대비 이득이 작다 (각 섹션이 ≤ 수십 KB이며 5초 주기로 충분히 가볍다). `/api/state`는 외부 통합용으로 유지하되 본 폴링 엔진은 사용하지 않는다.

- **결정**: `<input id="auto-refresh-toggle">`의 `checked` 상태를 헤더 섹션 교체 전후로 별도 보존·복원.
- **대안**: `data-section="hdr"`을 폴링 교체 대상에서 제외.
- **근거**: 헤더는 KPI/타임스탬프 등 갱신이 필요한 정보를 포함할 가능성이 있어(차후 Task) 일괄 제외는 부작용이 크다. 토글 1개의 checked 상태만 따로 복원하면 양쪽 요구를 모두 만족한다.

## 선행 조건
- **TSK-01-06 (`render_dashboard` 재조립 + sticky header + 드로어 골격)** — 본 Task의 JS는 `<section data-section="…">` 마커, `</body>` 직전 `<script>` 슬롯, `<input id="auto-refresh-toggle">`이 모두 존재한다는 전제로 동작한다. 본 Task의 dev-build는 TSK-01-06이 추가한 `_DASHBOARD_JS = ""` 빈 슬롯(또는 동등 placeholder)을 실제 IIFE로 채운다.
- 외부 라이브러리: 없음 (브라우저 내장 `fetch`, `AbortController`, `DOMParser`, `setInterval`만 사용).

## 리스크
- **MEDIUM**: 브라우저 백그라운드 탭에서 `setInterval`이 1초 미만으로 throttle 되어 5초보다 길게 발화할 수 있다. MVP 범위에서는 허용 (WBS acceptance: `visibilitychange` 미구현 명시).
- **MEDIUM**: `/`를 5초마다 fetch하는 부담이 서버에 추가된다. 단일 사용자 + 로컬 stdlib 서버이므로 측정 결과 부하가 크면 후속 Task에서 ETag/Last-Modified 도입 (현 Task 범위 외).
- **LOW**: `DOMParser`로 파싱한 외부 doc의 노드를 `innerHTML`로 직접 주입하므로 XSS 표면이 있다. 그러나 같은 출처(`/`)에서 받은 신뢰 가능한 SSR HTML이며 서버는 모든 사용자 데이터를 `_esc`/`html.escape`로 이스케이프하므로 위험은 SSR 자체와 동일하다.
- **LOW**: 직전 `AbortController.abort()` 호출이 신규 컨트롤러 생성 직전에 동기 예외를 던질 가능성 (구형 브라우저). `try/catch`로 감싸 silent.
- **LOW**: 헤더 교체 시 토글 `checked` 보존 로직은 `<input id="auto-refresh-toggle">`이 항상 헤더 섹션 안에 있음을 가정한다. TSK-01-06 산출물에서 위치가 바뀌면 dev-build 시점에 셀렉터를 조정해야 한다.

## QA 체크리스트
dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

- [ ] (정상) `render_dashboard(valid_model)` 결과 HTML에 `<script>` 태그가 정확히 1회 등장하고 그 안에 `startMainPoll`, `fetchAndPatch`, `patchSection`, `AbortController`, `data-section` 식별자가 모두 포함된다.
- [ ] (정상) `_DASHBOARD_JS` 문자열의 줄 수가 200줄 이하다 (WBS constraint).
- [ ] (정상) 단위 테스트로 `_DASHBOARD_JS`가 `setInterval(`와 `5000`을 포함한다 (5초 주기 검증).
- [ ] (엣지) `_DASHBOARD_JS`가 `'/'` 또는 `"/"`를 fetch URL로 사용한다 (tech-spec: 서버가 `/`를 재렌더 후 클라이언트 비교·교체 — `/api/state`가 아님).
- [ ] (엣지) `_DASHBOARD_JS`에 `cache:'no-store'` 또는 `cache:"no-store"`가 포함된다 (브라우저 캐시 우회).
- [ ] (에러) 폴링 catch 블록이 존재하여 fetch/parse 예외가 외부로 누출되지 않는다 (소스에 `.catch(` 또는 `try` 블록이 1개 이상).
- [ ] (통합) 단위 테스트로 `<script>{_DASHBOARD_JS}</script>` 주입 위치가 `</body>` 직전이며 `<head>`에는 `<meta http-equiv="refresh">`가 더 이상 존재하지 않는다 (TSK-01-06 결과와 정합).
- [ ] (통합) `_DASHBOARD_JS`가 `auto-refresh-toggle` 식별자를 참조한다 (헤더 토글과의 배선 검증).
- [ ] (통합) `_DASHBOARD_JS`가 `document.addEventListener` 또는 등가 위임 패턴을 사용한다 (이벤트 위임 — `data-pane-expand` 클릭 리스너가 DOM 재생성 후에도 동작해야 한다는 WBS test-criteria).

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**
- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 (URL 직접 입력 금지) — 본 Task는 `/`에 접속한 뒤 sticky header의 `#auto-refresh-toggle` 체크박스를 클릭하여 폴링을 ON/OFF 한다.
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다 — 5초 후 본문 `[data-section="wbs"]`(또는 다른 변경 섹션)이 새 SSR 결과로 갱신되며, 토글 OFF 시 그 다음 5초 동안 Network 탭에 신규 `GET /`가 기록되지 않는다.
