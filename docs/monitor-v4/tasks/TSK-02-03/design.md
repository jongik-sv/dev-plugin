# TSK-02-03: Task hover 툴팁 (state.json 요약) - 설계

## 요구사항 확인
- 대시보드 Work Packages 섹션의 각 Task 행(`.trow`)에 300ms hover 시 `state.json` 요약(status / last_event + at / elapsed / 최근 3 phase)을 표시하는 플로팅 툴팁을 추가한다 (PRD §2 P1-5, §4 S2, AC-10/11, TRD §3.5).
- 서버는 `_render_task_row_v2`의 `.trow` 루트에 `data-state-summary='{JSON}'`을 실어 SSR 하고, 클라이언트는 body 직계에 단 1개 생성되는 `#trow-tooltip` DOM + document-level 이벤트 delegation으로 5초 auto-refresh(innerHTML 교체)에서도 회귀 없이 동작한다.
- 외부 툴팁 라이브러리 금지(vanilla), XSS 안전(`json.dumps(ensure_ascii=False)` → `html.escape(..., quote=True)`로 single-quote 속성에 삽입).

## 타겟 앱
- **경로**: N/A (단일 앱 — dev-plugin 루트 `scripts/monitor-server.py` 모놀리스)
- **근거**: dev-monitor 대시보드는 워크스페이스/패키지 분할 없는 단일 Python HTTP 서버이며, 모든 HTML/CSS/JS가 `scripts/monitor-server.py`에 인라인 모놀리스 형태로 존재한다 (Dev Config `frontend` 설명 + 실제 파일 구조 확인).

## 구현 방향
- **서버 사이드 (SSR)**: `_render_task_row_v2(item, ...)` 내부에서 `item`의 상태를 `_build_state_summary_json(item)` 헬퍼로 dict 로 만들고 `_encode_state_summary_attr(dict)`로 안전 인코딩 후, `.trow` 루트 `<div>`에 `data-state-summary='...'` 속성으로 부착. 기존 7개 child div 구조는 그대로 유지 — 루트 속성만 추가하므로 기존 CSS/테스트 회귀 없음.
- **클라이언트 사이드 (DOM + JS + CSS)**: body 직계 `_trow_tooltip_skeleton()`(신규 헬퍼)이 `<div id="trow-tooltip" role="tooltip" hidden></div>` 반환 → `render_dashboard`에서 `_drawer_skeleton()` 옆에 같이 주입. 인라인 JS IIFE `setupTaskTooltip()`을 `_DASHBOARD_JS` 문자열에 추가(TRD §3.5 코드 그대로). CSS 규칙은 `DASHBOARD_CSS` 내 `.trow` 블록 아래에 삽입.
- **phase_tail 계산**: `state.json.phase_history` 배열의 최근 3개(tail)를 slice. history가 3개 미만이면 있는 만큼만. history 자체가 없으면 빈 배열.
- **`item` 데이터 출처**: `_render_task_row_v2`는 이미 `item` 객체에 `status/bypassed/error/...`를 받고 있다. `state.json` 파싱 결과(last_event, last_event_at, elapsed, phase_history)는 현재 item 에 없으므로, **Task 스캔 단계(`_scan_tasks`/`_load_task_state`)에서 이미 읽고 있는 `state.json`의 필드를 item dataclass 에 추가 필드로 노출**해야 한다 (아래 "파일 계획" 참조).

## 파일 계획

**경로 기준:** 모든 파일 경로는 프로젝트 루트 기준으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `_render_task_row_v2`에 `data-state-summary` 속성 추가; `_build_state_summary_json` + `_encode_state_summary_attr` 헬퍼 신규; `_trow_tooltip_skeleton()` 헬퍼 신규 + `render_dashboard`에서 주입; `DASHBOARD_CSS`에 `#trow-tooltip` 규칙 추가; `_DASHBOARD_JS`에 `setupTaskTooltip` IIFE 추가; Task item dataclass 또는 스캔 헬퍼에 `last_event`/`last_event_at`/`elapsed_seconds`/`phase_tail` 필드 노출 | 수정 |
| `scripts/test_monitor_render.py` | `test_trow_has_data_state_summary_json` — `.trow`의 `data-state-summary` 속성 존재 + 유효 JSON 파싱 + 필수 키 존재 검증; `test_trow_tooltip_dom_in_body` — `render_dashboard` 결과 HTML에 `<div id="trow-tooltip"` 이 1회만 나타나고 body 직계인지 (data-section 바깥) 확인; `test_state_summary_phase_tail_is_last_three` — phase_history 4개면 tail 3개만; `test_state_summary_escapes_xss` — last_event에 `<script>` 포함 시 속성 문자열에 `&lt;script&gt;` 로 이스케이프됨 | 수정 |
| `scripts/test_monitor_e2e.py` | `test_task_tooltip_hover` — Playwright 또는 headless HTTP 레벨 검증. Playwright 미사용 환경이면 "HTML 스냅샷 + JS 파싱 검증"으로 대체(실제 DOM 이벤트 시뮬레이션은 JSDOM 미탑재이므로 skip 마커 + 수동 확인 노트). 5초 auto-refresh 후에도 `#trow-tooltip`이 body 직계에 존재하고 `data-state-summary` 가 유지되는지 서버 응답 2회로 검증 | 수정 |
| `docs/monitor-v4/tasks/TSK-02-03/design.md` | 본 설계 문서 | 신규 |

> 라우터/메뉴 파일 — **N/A**. 본 Task 는 기존 Work Packages 섹션 내부의 행에 부착되는 툴팁 UX 강화로, 신규 URL/라우트/사이드바 메뉴를 추가하지 않는다 (아래 "진입점" 참조).

## 진입점 (Entry Points)

**대상**: `domain=frontend` (비-페이지 UI, 기존 페이지 내부 컴포넌트 확장).

- **사용자 진입 경로**: 대시보드 접속 (`http://localhost:7321/?subproject=monitor-v4`) → 'Work Packages' 섹션(WP-02 카드)까지 스크롤 → WP-02 details 펼침(기본 open) → **Task 행(`.trow`, 예: `TSK-02-01 build done`)에 마우스를 올림(hover 300ms 유지)** → `#trow-tooltip`이 행 우측(또는 뷰포트 경계 시 조정)에 나타남
- **URL / 라우트**: `/` (기존 대시보드 라우트 — 신규 라우트 없음). 쿼리 `?subproject={name}&lang={ko|en}` 기존 유지.
- **수정할 라우터 파일**: **해당 없음 (신규 라우트 추가 없음)**. 단, `scripts/monitor-server.py`의 `render_dashboard` 함수(L4125~)가 최종 HTML 조립 지점이므로 `_trow_tooltip_skeleton()` 호출을 `_drawer_skeleton()` 다음 줄(L4240 부근)에 추가한다.
- **수정할 메뉴·네비게이션 파일**: **해당 없음 (메뉴 항목 추가 없음)**. 본 Task 는 기존 Work Packages 섹션의 행에 부착되는 hover 상호작용이라 사이드바/네비게이션에 변화가 없다. (비-페이지 UI 규정 적용)
- **비-페이지 UI 적용 상위 페이지**: `/` 대시보드의 `data-section="wp-cards"` 내부 `.trow` 전부 (WP별로 N개). E2E는 해당 섹션 렌더 HTML에 `.trow[data-state-summary]`가 다수 포함되고 body 직계에 `#trow-tooltip`이 1회 존재함을 검증한다.
- **연결 확인 방법**: 서버 기동 후 `GET /?subproject=monitor-v4` → 응답 HTML에서 (a) `<div class="trow"` 출현 + 각 행이 `data-state-summary='{"status":...}'` 속성 보유, (b) `<div id="trow-tooltip"` 이 body 직계(outer `<aside>`/`<section>`/`data-section` 래퍼 바깥)에 정확히 1회, (c) `<script id="dashboard-js">` 내에 `setupTaskTooltip` 식별자 포함. 수동: 브라우저에서 Task 행에 마우스 hover 300ms → 툴팁 가시화 → mouseleave/scroll → hidden.

## 주요 구조
- **`_build_state_summary_json(item) -> dict`**: item에서 `status`(raw 코드, 예: `[im]`), `last_event` (str|None), `last_event_at` (ISO str|None), `elapsed` (int초, default 0), `phase_tail` (list[dict], 최대 3개 — 각 dict 는 `{event, from, to, at, elapsed_seconds}`)을 뽑아 **정렬된 dict** 로 반환. item 에 필드가 없으면 graceful default (빈 문자열/None/0/[]).
- **`_encode_state_summary_attr(summary: dict) -> str`**: `json.dumps(summary, ensure_ascii=False, separators=(',', ':'))` → `html.escape(result, quote=True)` → single-quote 감싸기용으로 리턴. 호출부는 `data-state-summary='{encoded}'` 형태로 소비.
- **`_render_task_row_v2` 패치**: 기존 루트 `<div class="trow" data-status="{data_status}">` 줄을 `<div class="trow" data-status="{data_status}" data-state-summary='{encoded}'>` 로 교체. 속성 추가 외에 기존 7개 child 구조/클래스/텍스트는 완전 동일 유지 (시각 토큰/기존 테스트 회귀 방지).
- **`_trow_tooltip_skeleton() -> str`**: `'<div id="trow-tooltip" role="tooltip" hidden></div>'` 반환. `render_dashboard`에서 `_drawer_skeleton()` 다음에 이어 주입.
- **`setupTaskTooltip` IIFE (inline JS, `_DASHBOARD_JS` 내)**: document-level `mouseenter`/`mouseleave`(useCapture=true) delegation — `closest('.trow[data-state-summary]')`; 300ms `setTimeout` debounce; `getBoundingClientRect()` + `window.scrollY`로 좌표 계산, `tip.style.top`/`left` 설정 후 `tip.hidden=false`; `window.scroll` 캡처 시 `tip.hidden=true`; 내부 `renderTooltipHtml(data)` 함수가 `<dl>` 로 status / last_event + at / elapsed / phase_tail 렌더 (모든 값은 `textContent`/`document.createTextNode` 경유 — `innerHTML` 은 구조 컨테이너에만 사용, 사용자 데이터는 text 노드로).
- **CSS `#trow-tooltip`**: position:fixed; z-index:100; max-width:420px; background:var(--bg-2); border:1px solid var(--border); border-radius:6px; padding:10px 12px; font:12px/1.4 var(--font-mono); pointer-events:none; box-shadow:0 4px 12px rgba(0,0,0,.3); `[hidden]{display:none}` (TRD §3.5 그대로).

## 데이터 흐름
`docs/tasks/{TSK-ID}/state.json` → (스캔) `item.last_event`/`last_event_at`/`elapsed_seconds`/`phase_tail` 필드 → `_build_state_summary_json(item)` → `_encode_state_summary_attr()` → SSR `<div class="trow" data-state-summary='{JSON}'>` → (브라우저) hover 300ms → `setupTaskTooltip`이 `JSON.parse(attr)` → `renderTooltipHtml()` → `#trow-tooltip.innerHTML` + 좌표 배치 → mouseleave/scroll → hidden.

## 설계 결정 (대안이 있는 경우만)
- **결정**: `.trow` 루트에 `data-state-summary='{JSON}'` **속성 직렬화** 방식 (TRD §3.5 지정).
- **대안**: `.trow`에 `data-task-id` 만 부착하고 툴팁 표시 시 `fetch('/api/task-detail?task=...')` 로 비동기 조회.
- **근거**: (a) TRD 가 속성 직렬화 방식을 명시. (b) 툴팁은 전체 Task 목록 렌더 시 이미 확보한 state.json 요약의 **재활용**이라 네트워크 RT 불필요. (c) /api/task-detail 은 TSK-02-04 EXPAND 패널에서 재사용하므로 역할 분리 깔끔.
- **결정 (JS 배치)**: 툴팁 DOM 을 `data-section` 바깥 body 직계에 두고 document-level event delegation 사용.
- **대안**: `.trow` 각 행에 `onmouseenter` 인라인 핸들러 부착.
- **근거**: 5초 auto-refresh 가 `data-section` 내부 innerHTML 을 통째로 교체하므로 (a) 섹션 바깥 DOM 은 교체 대상이 아니고 (b) document-level delegation 은 `.trow` 가 재생성돼도 closest() 매칭이 자동 유지됨. Dev Config `frontend` design_guidance 가 정확히 이 패턴을 지시.

## 선행 조건
- **TSK-02-01** (Task DDTR 단계 배지): 설계 진행은 독립 가능하나 **파일 병합 지점은 동일한 `_render_task_row_v2` 함수**. 실제 구현 시 TSK-02-01 머지 후 동일 함수의 루트 `<div>` 속성만 추가하는 방식이라 conflict 최소화. 만약 TSK-02-01 이 아직 머지 전이면 빌드 순서를 조정하거나 rebase 로 해결 (note 필드에 명시됨).
- **기존 Task 스캔 인프라**: `_scan_tasks`/`_load_task_state` 또는 동급 함수가 이미 `state.json`을 파싱한다면 필드 노출만으로 충분. 파싱 자체가 누락돼 있으면 본 Task 에서 **최소한의 필드만** 추가 파싱 (비즈니스 로직 변경 없음).
- Python 3 stdlib 만 사용 (`json`, `html`). 외부 라이브러리 추가 금지.

## 리스크
- **MEDIUM — item dataclass 확장 범위**: `item`에 `last_event` 등 필드가 없을 가능성 높음. 스캔 코드 수정은 본 Task 범위를 Work Packages 섹션 외(features/phase-history 렌더 등)로 번지게 할 수 있으므로, **필드 추가는 item 에만 한정**하고 소비자는 `getattr(item, ..., default)` 로 방어. 타 섹션에는 영향 없음을 테스트(`test_monitor_render_tsk04.py` 등)로 확인.
- **MEDIUM — auto-refresh 생존성 단위 테스트 어려움**: 5초 auto-refresh 시뮬레이션은 JS 런타임이 필요해 pytest 만으로는 완전 재현 불가. 설계 단계에서 "document-level delegation + body 직계 DOM"이 회귀하지 않도록 HTML 구조 단언 테스트(`test_trow_tooltip_dom_in_body`)로 방어하고, 실제 런타임 회귀는 E2E(Playwright) 또는 수동 QA로 커버.
- **LOW — XSS**: `html.escape(..., quote=True)` 로 `<`, `>`, `&`, `"`, `'` 모두 이스케이프되므로 single-quote 감싸기 안전. 클라이언트 `renderTooltipHtml` 은 사용자 데이터를 `textContent` 로만 주입 → 이중 안전.
- **LOW — 좌표 경계**: 뷰포트 우측 경계에 닿으면 툴팁 넘침 가능. 구현에서 `r.right + 8 + 420 > window.innerWidth` 체크 후 좌측 배치로 fallback 하는 1줄 추가 권장 (TRD 미명시지만 UX 관점 권장).

## QA 체크리스트
dev-test 단계에서 검증할 항목. 각 항목은 pass/fail 로 판정 가능해야 한다.

- [ ] (정상) `GET /?subproject=monitor-v4` 응답 HTML 내 `.trow` 각 행에 `data-state-summary='{...}'` 속성이 존재하고 `json.loads` 로 파싱되며 필수 키(`status`, `last_event`, `last_event_at`, `elapsed`, `phase_tail`) 를 모두 포함한다.
- [ ] (정상) 응답 HTML 에 `<div id="trow-tooltip" role="tooltip" hidden>` 이 **정확히 1회** 등장하고, 어떤 `data-section="..."` 래퍼의 **바깥(body 직계)** 에 위치한다.
- [ ] (정상) `<script id="dashboard-js">` 블록 본문에 `setupTaskTooltip` IIFE 가 포함되며, document-level `mouseenter`/`mouseleave` 리스너와 300ms debounce `setTimeout` 패턴이 존재한다.
- [ ] (엣지) `state.json.phase_history` 가 4개 이상이면 `phase_tail` 에 정확히 마지막 3개만 직렬화된다. history 가 없거나 비어 있으면 `phase_tail: []` 로 직렬화되며 JSON 파싱 에러가 없다.
- [ ] (엣지) `last_event`/`last_event_at` 이 `None` 인 Task (아직 실행 안 된 `[ ]` 상태) 에서 속성 JSON 의 해당 값이 `null` 로 직렬화되고, 기존 렌더 구조(7개 child div)는 변경되지 않는다 (TSK-02-01 회귀 0).
- [ ] (에러/보안) `state.json.last_event` 값에 `<script>alert(1)</script>` 가 들어 있어도 응답 HTML 에서 `&lt;script&gt;` 로 이스케이프되며, `data-state-summary` 속성 경계가 깨지지 않는다(single-quote `'` 포함 페이로드도 `&#x27;` 로 이스케이프).
- [ ] (통합) Work Packages 섹션이 5초 auto-refresh 로 innerHTML 교체되어도 `#trow-tooltip` DOM 은 여전히 body 직계에 1회 존재한다 (두 번의 `render_dashboard` 호출 결과 스냅샷 비교).
- [ ] (통합) `domain=fullstack` 인 기존 Task(배지/스피너)의 `.trow` 구조가 회귀 없이 동일하게 렌더된다 (기존 `test_monitor_render.py` 전부 pass).
- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 (URL 직접 입력 금지) — 본 Task 는 기존 대시보드 `/` 진입 후 Work Packages 섹션에서 Task 행에 hover 하는 상호작용으로 커버한다.
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다 — Task 행 hover 300ms 후 `#trow-tooltip` 가시화, mouseleave/scroll 시 hidden, 5초 auto-refresh 후에도 동일 동작.
