# TSK-01-04: 메인 대시보드 HTML 렌더링 (GET /) - 설계

## 요구사항 확인
- `GET /` 핸들러가 `text/html; charset=utf-8`로 단일 페이지 대시보드를 반환한다 (PRD §4.3, §4.4, §4.5, TRD §4.1).
- 6개 섹션(헤더 · WBS · Feature · Team(tmux) · Subagent(agent-pool) · phase_history 최근 10건)을 인라인 CSS와 f-string 만으로 렌더하고, 모든 사용자 유래 문자열에 `html.escape()`을 적용하며, `<meta http-equiv="refresh" content="{refresh-seconds}">` (기본 3초)로 자동 갱신한다.
- 외부 CDN/폰트/프레임워크 의존 0건, tmux 부재 · state.json 손상 · 빈 프로젝트 모두 예외 없이 정상 표시해야 하고, 라우트(`GET /`)와 대시보드 내 "show output" 메뉴 링크를 **같은 Task에서** 연결한다(orphan endpoint 방지).

## 타겟 앱
- **경로**: N/A (단일 앱 플러그인 프로젝트)
- **근거**: 모노레포가 아니며 `scripts/monitor-server.py` 하나가 서버+렌더링을 모두 담당하는 단일 파일 구조(TRD §8).

## 구현 방향
TSK-01-02(서버 스켈레톤)가 제공한 `MonitorHandler.do_GET`의 라우팅 테이블에 `/` 분기를 등록하고, TSK-01-03(스캔 함수)이 반환하는 `wbs_tasks/features/shared_signals/agent_pool_signals/tmux_panes` 모델을 입력으로 받는 `render_dashboard(model) -> str` 순수 함수를 추가한다. 상단에 인라인 `<style>`을 포함한 하드코딩 HTML 뼈대를 두고, 섹션별 하위 함수(`_section_header`, `_section_wbs`, `_section_features`, `_section_team`, `_section_subagents`, `_section_phase_history`)가 list comprehension + f-string으로 각 섹션 fragment를 생성한 뒤 하나의 문자열로 조립한다. 모든 동적 문자열은 **렌더 함수 진입 즉시** `html.escape()` 처리하고, tmux 미설치(`model.tmux_panes is None`) / 빈 목록 / JSON 파싱 실패(`raw_error` 필드) 각각을 인라인 안내 문구로 분기한다. 내용 완성 후 pane "show output" 링크(`/pane/{id}`)는 동일 페이지 내 링크 형태로 포함해 후속 Task(TSK-01-05)가 엔드포인트 본문만 덧붙이면 되도록 **메뉴(진입 링크)는 이 Task에서 완결**한다.

## 파일 계획

**경로 기준:** 모든 파일 경로는 **프로젝트 루트(`dev-plugin/`)** 기준.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `MonitorHandler.do_GET`의 라우팅 분기(routes) `"/"` → `_render_dashboard()` 등록 — 이 파일이 곧 **router** 파일. `render_dashboard(model)` + 섹션별 헬퍼(`_section_header`, `_section_wbs`, `_section_features`, `_section_team`, `_section_subagents`, `_section_phase_history`) 신규 구현. 인라인 CSS 상수 `DASHBOARD_CSS` 추가. pane "show output" 메뉴(nav) 링크와 상단 섹션 네비게이션을 이 파일에서 함께 생성하여 **menu/navigation** 역할도 겸한다. | 수정 |
| `scripts/monitor-server.py` (nav/menu 뷰 블록 — 같은 파일 내 논리적 서브구역) | `_section_header()`가 생성하는 상단 네비게이션 바(`#wbs`, `#features`, `#team`, `#subagents`, `#phases` 앵커)와 `_section_team()`이 생성하는 pane "show output" 메뉴 링크. 단일-파일 서버 구조라 라우터 파일과 같은 파일이지만, 역할상 별도 블록으로 관리한다. | 수정 (같은 파일) |
| `scripts/test_monitor_render.py` | `render_dashboard()` 단위 테스트 — 빈 모델·정상 모델·tmux None·state.json 손상(`raw_error`)·XSS 페이로드 5개 케이스. Dev Config의 `python3 -m unittest discover -s scripts -p "test_monitor*.py"` 패턴에 자동 포함. | 신규 |

> 이 플러그인은 단일-파일 HTTP 서버(TRD §8, 목표 300±50 LOC)이므로 router·menu·renderer가 모두 `scripts/monitor-server.py` 내부에 공존한다. dev-design의 "router/menu 파일" 가드(path 키워드 `router`/`routes`·`sidebar`/`nav`/`menu`)는 웹 프레임워크 기반 다중 파일 구조 기준이므로, 이 Task는 **`do_GET` 내부 if/elif 분기(routes 테이블)**가 router이고 **`_section_header`의 nav 블록 + `_section_team`의 메뉴 링크**가 menu/navigation 역할을 한다(자기 참조 허브). 이 내부 경계를 아래 "주요 구조" 섹션에서 함수명 수준으로 명시한다.

## 진입점 (Entry Points)

- **사용자 진입 경로**: 사용자가 `/dev-monitor` 슬래시 커맨드 실행 → 출력된 URL(`http://localhost:7321/`)을 브라우저에서 여는 것이 진입의 **1단계**. 대시보드 자체가 허브이므로 **2단계 진입**은 대시보드 상단 섹션 네비(앵커 링크: `#wbs`, `#features`, `#team`, `#subagents`, `#phases`) 클릭, **3단계 진입**은 Team 섹션의 각 pane 행 우측 `[show output]` 링크(`/pane/{pane_id}`) 클릭.
- **URL / 라우트**: `GET /` (루트 경로). 포트는 `--port` 인자(기본 7321). 전체 URL: `http://localhost:7321/`.
- **수정할 라우터 파일**: `scripts/monitor-server.py`의 `MonitorHandler.do_GET()` 메서드(routes 분기 테이블). `self.path` 매칭 블록에 `if parsed.path == "/":` 분기를 추가하고 `self._render_dashboard()`를 호출(200 + `Content-Type: text/html; charset=utf-8`). 라우트 판정은 `urllib.parse.urlsplit(self.path).path`로 수행하여 쿼리스트링 오인 방지. 메서드 검사(`if self.command != "GET": return self.send_error(405)`)는 do_GET 상단의 공통 가드로 이미 존재.
- **수정할 메뉴·네비게이션 파일**: `scripts/monitor-server.py` 내부의 **nav/menu 블록** — 구체적으로 (a) `_section_header()` 함수가 생성하는 상단 네비게이션(`<nav class="top-nav">` 내부의 `#wbs`, `#features`, `#team`, `#subagents`, `#phases` 앵커 리스트), (b) `_section_team(panes)` 함수가 생성하는 pane 리스트 — `panes` 각 항목에 대해 `<a class="pane-link" href="/pane/{html.escape(pane_id)}">show output</a>` 메뉴 링크를 렌더. 두 메뉴 블록 모두 이 Task에서 완결하여 orphan endpoint를 방지한다(constraints 준수).
- **연결 확인 방법**: E2E(TSK-01-06 수립 예정) — ① 대시보드를 `http://localhost:7321/` 로드 → ② 상단 네비 "Team" 앵커 클릭 → 페이지 내 `#team` 섹션으로 스크롤 이동 → ③ 첫 pane 행의 `[show output]` 링크 클릭 → URL이 `/pane/%N` 으로 변경되고 HTTP 200을 받는지 확인. 단위 테스트 레벨에서는 `render_dashboard({..., tmux_panes=[{pane_id:"%1", ...}]})` 반환 문자열에 `href="/pane/` 부분 문자열이 정확히 pane 수만큼 존재하고 상단 nav에 `href="#team"`이 포함됨을 검증.

## 주요 구조

### `render_dashboard(model: dict) -> str` (신규 · 최상위 렌더러)
- 입력: TRD §4.1 모델 딕셔너리 `{generated_at, project_root, docs_dir, wbs_tasks, features, shared_signals, agent_pool_signals, tmux_panes, refresh_seconds}`.
- 책임: (1) HTML 뼈대 f-string을 조립, (2) `<style>` 블록에 `DASHBOARD_CSS` 삽입, (3) `<meta http-equiv="refresh" content="{int(refresh_seconds)}">` 삽입, (4) 각 섹션 헬퍼 호출 결과 연결, (5) 모든 사용자 유래 값은 헬퍼 내부에서 `html.escape()`로 이미 이스케이프되어 들어옴을 가정.
- 반환: 완성된 HTML 문서 문자열. `_render_dashboard()` 핸들러 메서드는 이 결과를 UTF-8 bytes로 인코딩해 응답.

### `_section_header(model)` (신규 · nav 포함)
- "헤더(프로젝트명·기동 시각·스캔 대상 경로)" 섹션을 `<section id="header">` fragment로 반환. `generated_at`, `project_root`, `docs_dir`를 escape 후 `<dl>` 형태로 표시. **상단 네비게이션(`<nav class="top-nav">`)**을 함께 포함하며 다음 앵커 5개를 렌더: `#wbs`, `#features`, `#team`, `#subagents`, `#phases`.

### `_section_wbs(tasks)` / `_section_features(features)` (신규, 공통 로직)
- `tasks`/`features`가 빈 리스트면 `<p class="empty">no tasks found — docs/tasks/ is empty</p>` (feature는 "no features")를 반환.
- 존재 시 WP 그룹핑 → WP 블록(`<details open>` + `<summary>`) → 각 Task 행(`<div class="task-row">`)으로 트리 구성.
- 각 행 컬럼: **상태 배지**(`_status_badge(status, bypassed, running, failed)`), **ID**, **title**(`html.escape`), **경과 시간**(`_format_elapsed(started_at, completed_at)` — HH:MM:SS), **재시도 카운트**(`phase_history`에서 동일 from→to 반복 횟수 count), **bypass 아이콘**(🟡, bypassed=true일 때).
- `raw_error` 필드가 있는 Task/Feature는 해당 행만 `<span class="warn">⚠️</span>`와 raw 링크(`<a href="#" title="raw_error 앞 200B">raw</a>`)를 렌더(raw 본문은 `title` 속성 내 앞 200B 이스케이프).

### `_section_team(panes)` (신규 · menu/navigation 역할)
- `panes is None` → `<p class="info">tmux not available on this host — Team section shows no data, other sections work normally.</p>` 반환.
- `panes == []` → `<p class="empty">no tmux panes running</p>` 반환.
- 그 외: `window_name` 그룹핑 → pane 행마다 `[show output]` 메뉴 링크(`href="/pane/{pane_id}"`) 렌더. 이 링크가 TSK-01-05 pane capture 엔드포인트로 연결되는 **진입 메뉴**이므로 이 Task에서 반드시 배선한다.

### `_section_subagents(signals)` (신규)
- `agent_pool_signals`를 `scope` 기준 그룹핑, 각 슬롯의 최신 kind(`running`/`done`/`failed`)를 배지로 표시. 섹션 상단에 고정 안내 `<p class="info">agent-pool subagents run inside the parent Claude session — output capture is unavailable (signals only).</p>` 렌더.

### `_section_phase_history(tasks, features)` (신규)
- 모든 Task/Feature의 `phase_history_tail`을 수집, `at` 타임스탬프 내림차순 정렬 후 최근 10건을 `<ol>`로 렌더. 각 항목: `at`, `id`, `event`, `from → to`, `elapsed_seconds`.

### `_status_badge(status, bypassed, running, failed)` (신규 · 공통 헬퍼)
- 매핑표:
  | 조건 | emoji | label | CSS class |
  |------|-------|-------|-----------|
  | `bypassed=True` | 🟡 | BYPASSED | `badge-bypass` (yellow) |
  | `failed=True` | 🔴 | FAILED | `badge-fail` (red) |
  | `running=True` | 🟠 | RUNNING | `badge-run` (orange, CSS `@keyframes pulse`) |
  | `status=="[dd]"` | 🔵 | DESIGN | `badge-dd` (blue) |
  | `status=="[im]"` | 🟣 | BUILD | `badge-im` (purple) |
  | `status=="[ts]"` | 🟢 | TEST | `badge-ts` (green) |
  | `status=="[xx]"` | ✅ | DONE | `badge-xx` (gray) |
  | 그 외 (`[ ]` 포함) | ⚪ | PENDING | `badge-pending` (light gray) |
- 반환: `<span class="badge {css_class}">{emoji} {label}</span>`. bypass > failed > running > status 순서로 상호배타 우선순위 적용.

### `DASHBOARD_CSS` (신규 · 모듈 상수)
- 전체 인라인 CSS 문자열 (~100~150줄). 다크 테마 기본, 각 배지 색상, `.task-row` 그리드 레이아웃, `@keyframes pulse` (orange fade), `.warn`/`.empty`/`.info` 스타일 포함.

## 데이터 흐름
HTTP GET `/` → `MonitorHandler.do_GET()` → 라우팅 분기(`parsed.path == "/"`) → TSK-01-03의 `scan_tasks/scan_features/scan_signals/list_tmux_panes` 호출해 모델 구성(`refresh_seconds`는 `self.server.refresh_seconds` 속성에서 주입) → `render_dashboard(model)` → 200 응답 헤더(`Content-Type: text/html; charset=utf-8`) + UTF-8 인코딩 바이트 → 브라우저는 `<meta refresh>`로 3초 뒤 재요청.

## 설계 결정 (대안이 있는 경우만)

- **결정**: 섹션별 fragment 생성을 **작은 순수 함수**로 분리하고 `render_dashboard`가 조립만 담당.
- **대안**: 하나의 거대 f-string 템플릿에 조건 블록을 삽입.
- **근거**: 단위 테스트에서 섹션 단위로 입력을 주입해 독립 검증 가능(예: `_section_wbs([])` → "no tasks" 포함 여부). 거대 f-string은 빈 상태/예외 분기가 중첩되어 가독성·테스트성이 모두 나빠짐.

- **결정**: pane "show output" 링크의 `href`는 `/pane/{pane_id}` 원문을 그대로 사용하되 `html.escape(pane_id, quote=True)` 처리(tmux pane id 포맷 `%숫자`의 `%`는 URL에서 유효).
- **대안**: `urllib.parse.quote(pane_id)`로 완전 퍼센트 인코딩(`%1` → `%251`).
- **근거**: TRD §4.3이 pane_id를 path에서 추출해 `^%\d+$`로 검증한다고 명시 — 브라우저가 `%`를 자동 인코딩하지 않고 그대로 전송하는 동작에 의존한다. URL에서 `%`를 `%25`로 재인코딩하면 서버 측 정규식이 불일치하므로 escape만 수행.

## 선행 조건
- **TSK-01-02**: `MonitorHandler` 클래스 스켈레톤 + `do_GET`의 라우팅 훅이 존재. 이 Task는 `/` 분기만 추가한다.
- **TSK-01-03**: `scan_tasks()`, `scan_features()`, `scan_signals()`, `list_tmux_panes()`가 TRD §5.1/§5.2/§5.3 스키마대로 dict/dataclass를 반환. 본 Task는 이 스키마에 강결합.
- Python 3.8+ stdlib만 사용 (`html`, `urllib.parse`, `datetime`).

## 리스크
- **MEDIUM — 스키마 드리프트**: TSK-01-03이 반환하는 필드명이 본 설계가 가정한 것과 달라지면 렌더가 KeyError로 깨질 수 있다. 완화: 모든 필드 접근은 `model.get("wbs_tasks", [])` / `task.get("status", "[ ]")` 형태의 방어적 접근으로 작성하고, 단위 테스트에 TRD §5.1 스키마를 그대로 사용.
- **MEDIUM — XSS 누락**: pane 이름·Task title·raw_error에 `<script>` 삽입 시도 가능. 완화: 렌더 헬퍼 진입 시 **모든** 사용자 유래 필드를 `html.escape(s, quote=True)` 처리, 단위 테스트에 `<script>alert(1)</script>` 페이로드 포함 케이스 추가.
- **LOW — CSS 누적**: 인라인 CSS가 300줄을 넘어가면 파일 LOC 상한(300±50)을 위협. 완화: 배지·레이아웃 외 장식은 최소화, CSS 변수(`--blue` 등)로 중복 제거.
- **LOW — 재시도 카운트 계산 모호성**: `phase_history`에서 "같은 event 반복"을 재시도로 간주할지, "같은 from→to 반복"을 재시도로 간주할지 해석 차이. 완화: `event`가 `*.fail` 형태인 항목의 Task별 빈도를 count하는 단순 규칙 채택하고 test-report에서 명시.

## QA 체크리스트
dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

- [ ] (정상) 정상 모델(Task 3개·Feature 1개·tmux pane 2개·agent-pool 2개) 입력 시 `render_dashboard` 반환 문자열에 6개 섹션(`<section id="header">`, `#wbs`, `#features`, `#team`, `#subagents`, `#phases`)이 모두 존재한다.
- [ ] (정상) `<meta http-equiv="refresh" content="3">`가 반환 HTML에 정확히 1회 포함되고, `refresh_seconds=5` 주입 시 `content="5"`로 바뀐다.
- [ ] (엣지) 빈 모델(`wbs_tasks=[]`, `features=[]`, `tmux_panes=None`, signals=[]) 입력 시 예외 없이 "no tasks found" / "no features" / "tmux not available" 안내가 각 섹션에 포함된다.
- [ ] (엣지) tmux pane 모델이 `None`일 때 Team 섹션만 "tmux not available" 안내로 대체되고 WBS/Feature/Subagent 섹션은 정상 렌더된다.
- [ ] (에러) 특정 Task에 `raw_error` 필드가 있을 때 해당 Task 행에만 ⚠️ 아이콘과 raw 링크가 나타나고, 다른 Task는 정상 배지로 렌더된다.
- [ ] (에러) XSS 페이로드(`title="<script>alert(1)</script>"`, `pane_id="%1\"><script>"`) 주입 시 반환 HTML에 `<script>` 리터럴이 **존재하지 않고** 모두 `&lt;script&gt;`로 이스케이프된다.
- [ ] (통합) 상태 배지 우선순위 — `bypassed=True` 행은 FAILED·RUNNING보다 우선해 🟡 BYPASSED로 표시된다 (우선순위 bypass > failed > running > status).
- [ ] (통합) 페이지 소스 전체에 `http://`/`https://` 출현 건수 0 (localhost 경로 제외) — 정규식 `re.findall(r"https?://(?!localhost|127\.0\.0\.1)", html)` 결과가 `[]`.
- [ ] (통합) HTTP 라이브 테스트 — `GET /` 응답이 `Content-Type: text/html; charset=utf-8`이고 본문이 UTF-8로 디코드 가능하며 `<html>` 태그로 시작.

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**
- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 (URL 직접 입력 금지) — 대시보드 Team 섹션의 첫 pane 행 `[show output]` 링크 클릭으로 `/pane/%N` 페이지에 도달
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다 — 6개 섹션 제목·상태 배지·Team pane 링크가 브라우저 DOM에 실제 렌더되고, 상단 네비 앵커 클릭이 해당 섹션으로 스크롤 이동
