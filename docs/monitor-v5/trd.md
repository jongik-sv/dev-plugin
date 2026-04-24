# TRD: dev-monitor v5

> version: 1.0
> description: dev-monitor v5 — UI 개선 6건(FR-01~FR-06) + monitor-server.py 6937줄 모놀리스 모듈 분할(FR-07) + 관련 프롬프트·문서 중복 제거(FR-08)
> depth: 3
> start-date: 2026-04-24
> target-date: 2026-05-01
> updated: 2026-04-24
> prd-ref: docs/monitor-v5/prd.md

---

## 1. 아키텍처 개요

### 현재(v4 기준)

```
scripts/monitor-server.py   ← 6937줄 단일 파일
  ├─ 임포트·상수 (L1–100)
  ├─ phase helpers, signal kinds, label maps (L85–1170)
  ├─ 인라인 CSS (`<style>` 블록, L1540–3000)  ← 메인 그리드·WP 카드·team·subagents·dep-graph·tooltip
  ├─ Python 섹션 렌더 함수 (_section_wp_cards, _section_team_agents, _section_dep_graph, …)
  ├─ _render_task_row_v2 (L3020–3083)
  ├─ _build_graph_payload (L5225–5320)
  ├─ 인라인 JS IIFE (setupTaskTooltip, openTaskPanel, patchSection, filter-bar 바인딩, …)
  └─ HTTP 라우팅 (BaseHTTPRequestHandler.do_GET, L6200+)
```

메모리 경고(`project_monitor_server_inline_assets.md`): 단일 파일 6937줄 + 시각 토큰 가드 부재 → 동시 머지 시 무성 회귀 위험 누적.

### 타깃(v5)

```
scripts/monitor-server.py                  ← 얇은 entry (서버 기동, 인자 파싱, handler 등록). 500줄 이내.
scripts/monitor_server/                    ← 파이썬 패키지 (언더스코어: 파이썬 import 규칙)
  ├─ __init__.py
  ├─ handlers.py                           ← HTTP 라우팅 (do_GET 분기) + MIME/캐시 헤더
  ├─ api.py                                ← /api/* 엔드포인트 구현 (task-detail, merge-status, graph, state)
  ├─ renderers/
  │   ├─ __init__.py                       ← render_dashboard() 엔트리
  │   ├─ wp.py                             ← _section_wp_cards + _render_task_row_v2
  │   ├─ team.py                           ← _section_team_agents + pane 카드
  │   ├─ subagents.py                      ← _section_subagents
  │   ├─ activity.py                       ← _section_live_activity
  │   ├─ depgraph.py                       ← _section_dep_graph SSR + _build_graph_payload
  │   ├─ taskrow.py                        ← 공용 _render_task_row, phase label/attr helper
  │   ├─ filterbar.py                      ← _section_filter_bar
  │   └─ panel.py                          ← task/merge 슬라이드 패널 DOM 스캐폴드
  └─ static/
      ├─ style.css                         ← 기존 인라인 CSS 전량 + v5 신규 규칙
      └─ app.js                            ← 기존 인라인 JS IIFE 전량 + v5 팝오버·포커스 핸들러
```

**핵심 원칙**:
- 파이썬 패키지 이름은 `monitor_server`(언더스코어) — entry 파일명 `monitor-server.py`(하이픈)는 사용자 접근성 유지(기존 `monitor-launcher.py`가 subprocess로 호출). 하이픈-언더스코어 매핑은 `monitor-server.py`가 `sys.path.insert(0, str(Path(__file__).parent))` 후 `from monitor_server import ...` 으로 해결.
- 모듈 분할 후 **단일 파일 최대 1500줄 미만** 목표(비기능 요구사항 NF-03).
- 정적 에셋은 `/static/<path>` 라우트로 서빙(화이트리스트). SSR HTML은 `<link rel="stylesheet">` + `<script src="/static/app.js">`로 변경.

## 2. 변경 파일

| 파일 | 변경 |
|------|------|
| `scripts/monitor-server.py` | entry 전용으로 축소. `http.server` 기동 + `HTTPServer((host, port), handlers.Handler)`. 인자 파싱(`--port`, `--docs`)만 유지. 기존 내부 로직은 전량 `scripts/monitor_server/` 로 이전. |
| (신규) `scripts/monitor_server/__init__.py` | 빈 패키지 초기화 + 버전 문자열. |
| (신규) `scripts/monitor_server/handlers.py` | `BaseHTTPRequestHandler` 서브클래스. 라우팅: `/`(dashboard), `/api/<name>`(→`api.py`), `/static/<path>`(화이트리스트 + MIME + `Cache-Control: public, max-age=300`). |
| (신규) `scripts/monitor_server/api.py` | `/api/task-detail`, `/api/merge-status`, `/api/graph`, `/api/state` 구현. 기존 계약 **무변경**. |
| (신규) `scripts/monitor_server/renderers/__init__.py` | `render_dashboard(model, lang, sps, sp)` 엔트리. 하위 섹션 렌더러 조립 + `<link>`/`<script src>` 주입. |
| (신규) `scripts/monitor_server/renderers/wp.py` | `_section_wp_cards`, `_render_task_row_v2` 이전. FR-06 `.badge[data-phase]` + FR-01 `<button class="info-btn">` 삽입. |
| (신규) `scripts/monitor_server/renderers/team.py` | `_section_team_agents` 이전. FR-04 `.pane-head` 패딩 확대 + `.pane-preview` max-height 2배. |
| (신규) `scripts/monitor_server/renderers/subagents.py` | `_section_subagents` 이전. 내부 변경 없음. |
| (신규) `scripts/monitor_server/renderers/activity.py` | `_section_live_activity` 이전. 내부 변경 없음. |
| (신규) `scripts/monitor_server/renderers/depgraph.py` | `_section_dep_graph` + `_build_graph_payload` 이전. FR-05 `.dep-node.critical` 색상 분리 + FR-06 `data-phase` 전달. |
| (신규) `scripts/monitor_server/renderers/taskrow.py` | `_phase_label`, `_phase_data_attr`, `_trow_data_status` 공용 헬퍼 이전. |
| (신규) `scripts/monitor_server/renderers/filterbar.py` | `_section_filter_bar` 이전. |
| (신규) `scripts/monitor_server/renderers/panel.py` | task/merge 슬라이드 패널 body-직계 DOM 스캐폴드 이전. |
| (신규) `scripts/monitor_server/static/style.css` | 인라인 `<style>` 전량 추출. FR-03 `.grid{2fr/3fr}`, FR-04 `.pane-head`/`.pane-preview`, FR-05 `.dep-node.critical{border-color:#f59e0b}`, FR-06 `.badge[data-phase="dd|im|ts|xx|failed|bypass|pending"]` 배경·테두리 세트 + `.dep-node[data-phase]` 동일 적용, `.info-btn`/`.info-popover` 신규. |
| (신규) `scripts/monitor_server/static/app.js` | 인라인 JS IIFE 전량 추출. FR-01 클릭 팝오버 모듈(싱글톤), FR-02 `renderTaskProgressHeader(state)` 함수, FR-06 배지 스피너 내부화 바인딩. |
| `skills/dev-monitor/SKILL.md` | FR-08 중복 문구 정리(구체 범위는 §3.8에서 스코프 한정). |
| `scripts/test_monitor_render.py` | 기존 테스트가 내부 import 경로 변경에 영향받는지 확인 + 필요 시 경로 수정. 계약은 동일. |
| (신규) `scripts/test_monitor_static_assets.py` | `/static/style.css` / `/static/app.js` 응답 200 + `content-type`(text/css, application/javascript) + `Cache-Control` 헤더 검증. 알 수 없는 경로 404. |
| (신규) `scripts/test_monitor_info_popover.py` | FR-01 `.info-btn` 클릭 팝오버 DOM + 위치(`top = r.top - tipH - 8`) + ESC/외부 클릭 닫기(Playwright 또는 stdlib DOM 스냅샷). |
| (신규) `scripts/test_monitor_progress_header.py` | FR-02 EXPAND 패널 상단 진행 요약 헤더 SSR + JS 렌더 스냅샷. |
| (신규) `scripts/test_monitor_grid_ratio.py` | FR-03 `.grid` `grid-template-columns` 가 `2fr/3fr` 인지 CSS 파싱. |
| (신규) `scripts/test_monitor_pane_size.py` | FR-04 `.pane-preview` `max-height` 가 v4 대비 2배(≥ 9em) 인지 CSS 파싱. |
| (신규) `scripts/test_monitor_critical_color.py` | FR-05 `.dep-node.critical` 색상이 `#f59e0b`(앰버) + `.dep-node.status-failed` 는 `var(--fail)`(적색) 유지. |
| (신규) `scripts/test_monitor_phase_badge_colors.py` | FR-06 `.badge[data-phase="dd|im|ts|xx|failed|bypass|pending"]` 각각 고유 배경·테두리 규칙 존재 + `.dep-node[data-phase]` 동일 적용. |
| (신규) `scripts/test_monitor_module_split.py` | FR-07 `scripts/monitor_server/*` 패키지가 import 가능 + `scripts/monitor-server.py` 가 1500줄 미만(회귀 가드). |
| `~/.claude/plugins/marketplaces/dev-tools/` | 위 변경 미러링 (CLAUDE.md 규약). |

**변경하지 않을 파일**

- `scripts/dep-analysis.py` — 계약 그대로.
- `scripts/args-parse.py`, `scripts/wbs-parse.py`, `scripts/wbs-transition.py`, `scripts/wp-setup.py`, `scripts/merge-preview.py`, `scripts/merge-preview-scanner.py` — v5 는 UI/구조 개선만.
- `scripts/monitor-launcher.py` — entry 파일명(`monitor-server.py`) 불변이므로 launcher 수정 불필요.
- `skills/dev-monitor/vendor/graph-client.js` — v5 에서는 graph 내부 로직 변경 없음. 다만 `data-phase` 속성 전달만 추가 소비(기존 `statusKey()` 옆에 `nd.phase` 읽기 1줄).
- `references/state-machine.json`, `scripts/_platform.py`, signal helpers — 무관.

## 3. 기술 스택

- **언어·런타임**: Python 3 stdlib only (`http.server`, `pathlib`, `mimetypes`, `json`, `re`). **pip 의존성 추가 금지**.
- **프론트엔드**: vanilla JS(IIFE), CSS Variables, `:root` 토큰. 외부 프레임워크 금지.
- **lint/format**: 기존 방식 유지 — `python3 -m py_compile scripts/monitor-server.py scripts/monitor_server/**/*.py`.
- **신규 의존성 없음** (FR-07 모듈 분할은 순수 파이썬 패키지 + 화이트리스트 static 라우트로 해결).

## 4. 모듈 설계 (FR-07 핵심)

### 4.1 패키지 레이아웃

§1 "타깃(v5)" 참조.

### 4.2 점진적 분할 순서 (증분 원칙)

**한 번에 한 덩어리만 분리, 각 분리 후 전체 테스트 통과 확인 후 다음 단계로 진행**. 각 단계는 독립 PR로 머지하여 동시 머지 회귀(§9 R-C)를 방지한다.

| 단계 | 범위 | 완료 조건 |
|------|------|-----------|
| S1 | `scripts/monitor_server/` 패키지 스캐폴드 생성 + `monitor-server.py` 에 `sys.path.insert` 추가, **로직 이전 없음** | `python3 -c "import monitor_server"` 성공, 기존 테스트 전량 통과. |
| S2 | CSS 추출 → `static/style.css`. `/static/` 라우트 + `<link rel="stylesheet">` 주입. 인라인 `<style>` 블록 제거. | 대시보드 시각 스냅샷(`test_monitor_render.py` SSR 검증) 회귀 0, 신규 `test_monitor_static_assets.py` 통과. |
| S3 | JS IIFE 추출 → `static/app.js`. `<script src="/static/app.js" defer>` 주입. | 기존 e2e(hover 툴팁, EXPAND 패널, 필터 바) 전량 회귀 0. |
| S4 | `renderers/` 패키지로 Python 섹션 함수 이전 — 1 파일 = 1 커밋 (wp → team → subagents → activity → depgraph → taskrow → filterbar → panel). | 각 커밋마다 전체 테스트 통과. |
| S5 | `api.py` 로 `/api/*` 이전. | `/api/task-detail`, `/api/merge-status`, `/api/graph`, `/api/state` 계약 테스트 전량 통과. |
| S6 | `handlers.py` 로 HTTP 라우팅 이전. `monitor-server.py` 는 `HTTPServer((host, port), handlers.Handler)` 한 줄로 축소. | `monitor-server.py` < 500 줄 확인. |
| S7 | FR-01 ~ FR-06 UI 변경 (§5 기술 결정 개별 단계로 세분). | 각 FR별 수락 기준 통과. |
| S8 | FR-08 문서·프롬프트 중복 제거. | `skills/dev-monitor/SKILL.md` 중복 문구 제거 diff 확인. |

**롤백 경로**: 각 S 단계는 독립 PR로 머지. 문제 발생 시 `git revert <merge-sha>` 로 직전 단계로 복귀 — 모놀리스 버전은 S1 시작 전 tag(`monitor-server-pre-v5`)로 보존.

## 5. API 설계

### 5.1 기존 계약 유지

| 엔드포인트 | 응답 | 비고 |
|-----------|------|------|
| `GET /?subproject=X&lang=ko` | HTML (dashboard) | `<link>`/`<script src>` 주입 외 본문 동일 |
| `GET /api/state` | JSON | v4 계약 무변경 |
| `GET /api/graph` | JSON | v4 계약 무변경 (단, 노드에 `phase` 필드 전달 — FR-06) |
| `GET /api/task-detail?task=X&subproject=Y` | JSON | v4 계약 무변경 |
| `GET /api/merge-status?subproject=X[&wp=Y]` | JSON | v4 계약 무변경 |

### 5.2 신규 — 정적 에셋 라우트

```
GET /static/<path>
```

**구현** (`handlers.py`):

```python
_STATIC_ROOT = Path(__file__).parent / "static"
_STATIC_WHITELIST = {"style.css", "app.js"}  # 명시 화이트리스트 — 경로 순회 공격 차단
_MIME = {"css": "text/css; charset=utf-8",
         "js":  "application/javascript; charset=utf-8"}

def _serve_static(self, path: str) -> None:
    name = path[len("/static/"):]
    if name not in _STATIC_WHITELIST:
        self.send_error(404); return
    asset = _STATIC_ROOT / name
    if not asset.is_file():
        self.send_error(404); return
    ext = name.rsplit(".", 1)[-1]
    body = asset.read_bytes()
    self.send_response(200)
    self.send_header("Content-Type", _MIME.get(ext, "application/octet-stream"))
    self.send_header("Content-Length", str(len(body)))
    self.send_header("Cache-Control", "public, max-age=300")
    self.end_headers()
    self.wfile.write(body)
```

**Cache-Control 정책**:
- `/static/*` → `public, max-age=300` (5분, FR-07 페이지 로드 부하 완화)
- `/` (HTML) → 기존 `no-cache` 유지 (폴링 신선도 보장)
- `/api/*` → 기존 정책 유지

## 6. 데이터 모델

**변경 없음**. `state.json` 스키마, `graph_stats` 출력, signal 프로토콜 모두 v4 그대로 유지. v5 는 **표현 계층 전용** 변경.

## 7. 기능별 기술 결정 (FR-01 ~ FR-08)

### 7.1 FR-01 — hover 툴팁 제거 + ⓘ 아이콘 클릭 팝오버 (위쪽 위치)

**대상 제거** (기존 hover):
- `scripts/monitor_server/static/app.js` 의 `setupTaskTooltip` IIFE 전량 삭제
- CSS `#trow-tooltip` 규칙 삭제
- `.trow` 의 `data-state-summary` 속성은 팝오버 컨텐츠용으로 재활용(삭제 금지)

**신규 DOM** (`.trow` 내부, `.badge` 뒤):
```html
<button class="info-btn" aria-label="상세" aria-expanded="false" aria-controls="trow-info-popover">ⓘ</button>
```

**팝오버 DOM** (body 직계, 싱글톤 1개):
```html
<div id="trow-info-popover" role="dialog" hidden></div>
```

**위치 로직** (Task **위쪽** 우선):
```javascript
function positionPopover(btn, pop) {
  pop.hidden = false;                     // 치수 측정을 위해 먼저 노출
  var r = btn.getBoundingClientRect();
  var ph = pop.offsetHeight;
  var pw = pop.offsetWidth;
  var top = r.top + window.scrollY - ph - 8;   // 기본: 위쪽
  if (top < window.scrollY + 8) {
    top = r.bottom + window.scrollY + 8;       // 상단 공간 부족 시 아래쪽 폴백
  }
  var left = r.left + window.scrollX + r.width/2 - pw/2;
  left = Math.max(8, Math.min(left, window.innerWidth - pw - 8));
  pop.style.top = top + 'px';
  pop.style.left = left + 'px';
}
```

**싱글톤 상태 관리**:
```javascript
(function setupInfoPopover(){
  var pop = document.getElementById('trow-info-popover');
  var openBtn = null;
  function close() {
    if (!openBtn) return;
    openBtn.setAttribute('aria-expanded', 'false');
    pop.hidden = true;
    openBtn = null;
  }
  document.addEventListener('click', function(e){
    var btn = e.target.closest && e.target.closest('.info-btn');
    if (btn) {
      e.stopPropagation();
      if (openBtn === btn) { close(); return; }
      if (openBtn) close();
      var row = btn.closest('.trow[data-state-summary]');
      var data; try { data = JSON.parse(row.getAttribute('data-state-summary')); } catch(_) { return; }
      pop.innerHTML = renderInfoPopoverHtml(data);      // 기존 renderTooltipHtml 재활용
      openBtn = btn;
      btn.setAttribute('aria-expanded', 'true');
      positionPopover(btn, pop);
      return;
    }
    if (openBtn && !pop.contains(e.target)) close();     // 외부 클릭 닫기
  });
  document.addEventListener('keydown', function(e){
    if (e.key === 'Escape' && openBtn) { close(); openBtn.focus(); }
  });
  window.addEventListener('scroll', close, true);
  window.addEventListener('resize', close);
})();
```

**접근성**:
- `.info-btn` 은 `<button>` — 기본 키보드 포커스 가능 + `Enter`/`Space` 로 `click` 디스패치(브라우저 기본 동작).
- `aria-expanded="true|false"` 동적 갱신.
- 팝오버는 `role="dialog"` + focus trap 없이 ESC 닫힘(간단한 정보 표시용).

### 7.2 FR-02 — EXPAND 슬라이드 패널에 진행 요약 헤더 추가

**대상**: `openTaskPanel()` 내 `body.innerHTML` 조립에서 `renderWbsSection(...)` **이전**에 `renderTaskProgressHeader(state)` 호출 삽입.

**구현** (`app.js`):
```javascript
function renderTaskProgressHeader(state) {
  if (!state) return '';
  var statusCode  = state.status || '—';
  var lastEvent   = (state.last && state.last.event) || '—';
  var lastAt      = (state.last && state.last.at) || state.updated || '—';
  var phaseCount  = (state.phase_history || []).length;
  var elapsedSec  = state.elapsed_seconds;
  var elapsed     = (elapsedSec != null) ? (Math.round(elapsedSec) + 's') : '—';
  return '<header class="progress-header">'
    + '<div class="ph-badge" data-phase="' + escapeHtml(statusCode.replace(/[\[\]]/g, '')) + '">' + escapeHtml(statusCode) + '</div>'
    + '<dl class="ph-meta">'
    +   '<dt>last event</dt><dd>' + escapeHtml(lastEvent) + '</dd>'
    +   '<dt>at</dt><dd>' + escapeHtml(lastAt) + '</dd>'
    +   '<dt>elapsed</dt><dd>' + escapeHtml(elapsed) + '</dd>'
    +   '<dt>phase steps</dt><dd>' + phaseCount + '</dd>'
    + '</dl></header>';
}

// openTaskPanel 수정:
b.innerHTML = renderTaskProgressHeader(data.state)
            + renderWbsSection(data.wbs_section_md || '')
            + renderStateJson(data.state || {})
            + renderArtifacts(data.artifacts || [])
            + renderLogs(data.logs || []);
```

**데이터 소스**: 기존 `/api/task-detail` 응답 `state` 필드만 사용 — 서버 변경 0.

### 7.3 FR-03 — 메인 그리드 `3fr : 2fr` → `2fr : 3fr`

**CSS 변경** (`static/style.css`):
```css
.grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 3fr);  /* v4: 3fr 2fr */
  gap: 28px;
  padding-top: 8px;
}
.wp-stack {
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));  /* v4: 520px */
}
```

**보조 조정**: `.wp-stack` 의 `min-width` 값은 **520px → 380px** 로 축소해 좌측 열이 좁아져도 카드 2열 유지 가능.

### 7.4 FR-04 — 팀 에이전트 pane 카드 높이 2배

**CSS 변경** (`static/style.css`):
```css
.pane-head {
  padding: 20px 14px 16px;    /* v4: 10px 14px 8px — 상하 2배 */
}
.pane-preview {
  max-height: 9em;            /* v4: 4.5em — 2배 */
  line-height: 1.5;
}
.pane-preview::before {
  content: "\\25B8 last 6 lines";  /* v4: "last 3 lines" */
}
```

**Python 변경** (`renderers/team.py`): `pane-preview` 에 표시할 pane 스크롤백 라인 수 상수 `_PANE_PREVIEW_LINES = 6` 로 상향(v4: 3). 라벨 문구와 일치.

### 7.5 FR-05 — 크리티컬 패스 색상 분리 (앰버)

**현재 이슈** (L2096-2110): `.dep-node.status-failed` 와 `.dep-node.critical` 가 **같은 `var(--fail)` 적색**을 공유해 사용자가 "빨간 노드가 실패인지 크리티컬인지" 구분 불가.

**CSS 변경** (`static/style.css`):
```css
/* failed: 적색 유지 */
.dep-node.status-failed {
  border-left-color: var(--fail);
  --_tint: color-mix(in srgb, var(--fail) 10%, transparent);
}
.dep-node.status-failed .dep-node-id { color: var(--fail); }

/* critical: 앰버로 분리 */
.dep-node.critical {
  border-color: #f59e0b;                                            /* v4: var(--fail) */
  box-shadow: 0 0 0 2px color-mix(in srgb, #f59e0b 35%, transparent);
}
```

**범례 갱신** (`renderers/depgraph.py` `#dep-graph-legend` 인라인 스타일): critical 범례 swatch 색상 `#f59e0b` 로 변경 + 라벨 "Critical Path".

**CSS 변수 추가** (`:root`):
```css
:root {
  --critical: #f59e0b;
}
```

`.dep-node.critical` 에서 리터럴 대신 `var(--critical)` 사용으로 토큰화.

### 7.6 FR-06 — Phase 배지 색상 구분 + 스피너 + 그래프 노드 적용

**현재** (v4): `.badge` 는 배경·테두리가 phase 별 구분 없이 단일 스타일. `.trow[data-running="true"] .spinner { display: inline-block }` 로 row 수준 스피너만 존재.

**CSS 변경** (`static/style.css` 신규 섹션):
```css
/* Phase 배지 색상 토큰 (:root에 추가) */
:root {
  --phase-dd:      #6366f1;  /* indigo — Design */
  --phase-im:      #0ea5e9;  /* sky    — Build  */
  --phase-ts:      #a855f7;  /* violet — Test   */
  --phase-xx:      #10b981;  /* emerald — Done  */
  --phase-failed:  #ef4444;  /* red    — Failed */
  --phase-bypass:  #f59e0b;  /* amber  — Bypass */
  --phase-pending: #6b7280;  /* gray   — Pending */
}

/* badge 에 data-phase 적용 */
.badge { position: relative; padding: 2px 8px; border-radius: 3px;
         border: 1px solid transparent; background: var(--bg-2); }
.badge[data-phase="dd"]      { background: color-mix(in srgb, var(--phase-dd)      15%, transparent); border-color: var(--phase-dd); color: var(--phase-dd); }
.badge[data-phase="im"]      { background: color-mix(in srgb, var(--phase-im)      15%, transparent); border-color: var(--phase-im); color: var(--phase-im); }
.badge[data-phase="ts"]      { background: color-mix(in srgb, var(--phase-ts)      15%, transparent); border-color: var(--phase-ts); color: var(--phase-ts); }
.badge[data-phase="xx"]      { background: color-mix(in srgb, var(--phase-xx)      15%, transparent); border-color: var(--phase-xx); color: var(--phase-xx); }
.badge[data-phase="failed"]  { background: color-mix(in srgb, var(--phase-failed)  15%, transparent); border-color: var(--phase-failed); color: var(--phase-failed); }
.badge[data-phase="bypass"]  { background: color-mix(in srgb, var(--phase-bypass)  15%, transparent); border-color: var(--phase-bypass); color: var(--phase-bypass); }
.badge[data-phase="pending"] { background: color-mix(in srgb, var(--phase-pending) 15%, transparent); border-color: var(--phase-pending); color: var(--phase-pending); }

/* 스피너를 badge 내부로 이동 (v4: row 오른쪽에 별도 .spinner) */
.badge .spinner-inline {
  display: none;
  width: 8px; height: 8px;
  border: 2px solid currentColor; border-top-color: transparent;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-left: 6px; vertical-align: middle;
}
.trow[data-running="true"] .badge .spinner-inline { display: inline-block; }

/* 그래프 노드에도 phase 토큰 적용 (status 클래스와 병행) */
.dep-node[data-phase="dd"]     .dep-node-id { color: var(--phase-dd); }
.dep-node[data-phase="im"]     .dep-node-id { color: var(--phase-im); }
.dep-node[data-phase="ts"]     .dep-node-id { color: var(--phase-ts); }
.dep-node[data-phase="xx"]     .dep-node-id { color: var(--phase-xx); }
.dep-node[data-phase="failed"] .dep-node-id { color: var(--phase-failed); }
.dep-node[data-phase="bypass"] .dep-node-id { color: var(--phase-bypass); }
```

**Python 변경**:
- `renderers/wp.py _render_task_row_v2`: `<div class="badge" data-phase="...">{txt}<span class="spinner-inline"></span></div>` — 기존 row-level `.spinner` 제거.
- `renderers/depgraph.py _build_graph_payload`: 노드 dict 에 `phase` 필드 추가(`_phase_data_attr(...)` 재사용).
- `skills/dev-monitor/vendor/graph-client.js`: 노드 HTML 템플릿에 `data-phase="${nd.phase}"` 1줄 추가(기존 `status-${statusKey(nd)}` 와 공존).

**공용 keyframe**: 기존 `@keyframes spin` (v4 TSK-00-01 이전) 재사용 — 추가 선언 금지.

### 7.7 FR-07 — monitor-server.py 분할

§4 참조. 구현 단계는 §4.2 S1–S6.

**각 단계별 e2e 회귀 테스트**:
- S2 (CSS 추출) 직후: `test_monitor_static_assets.py` + `test_monitor_grid_ratio.py` + 기존 e2e 전량.
- S3 (JS 추출) 직후: 위 + `test_monitor_info_popover.py`(있다면 사전 도입) + 기존 하버/EXPAND 테스트.
- S4 (렌더 함수) 직후: `test_monitor_module_split.py` + `test_monitor_render.py` 스냅샷 동일.
- S5 (API) / S6 (handlers): `test_monitor_task_detail_api.py`, `test_monitor_graph_api.py`, `test_monitor_merge_badge.py` 전량.

### 7.8 FR-08 — 관련 프롬프트·문서 중복 제거

**스코프 한정** (조사 결과 기반):
1. `skills/dev-monitor/SKILL.md` — 중복 설명 블록(설치·기동·정지 절차가 README 와 중복) 점검 후 한 위치로 통합.
2. `skills/dev-monitor/references/*.md`(존재 시) — SKILL.md 와 중복되는 트러블슈팅 문구 제거.
3. 범위 **밖**: `scripts/monitor-server.py` 내부 docstring(코드 엔트리), PRD/TRD(본 문서), 타 스킬 문서.

**실행 절차**:
1. `grep -rn "monitor-launcher\|monitor-server\|dev-monitor" skills/dev-monitor/` 로 중복 후보 열거.
2. 각 후보를 단일 표준 위치(SKILL.md)로 통합 + 타 파일은 해당 섹션 링크 참조.
3. diff 로 순수 삭제/링크화만 발생했는지 검증(논리 변경 없음).

## 8. 테스트 전략

### 8.1 기존 자산 스캔

- `docs/e2e-skill-issues-2026-04-12.md` 참조하여 모니터 관련 이슈 목록 확인 (tooltip, EXPAND, graph hover).
- `scripts/test_monitor_*.py` 전량 실행 기준점 설정(S1 직전 green 확인).

### 8.2 신규 테스트 (FR-01 ~ FR-07)

| FR | 테스트 파일 | 검증 항목 |
|----|------------|-----------|
| FR-01 | `test_monitor_info_popover.py` | `.info-btn` 클릭 → `#trow-info-popover[hidden=false]`, 위치 `top = r.top - tipH - 8`(또는 폴백 `r.bottom + 8`), ESC 닫기, 외부 클릭 닫기, 재클릭 토글, `aria-expanded` 동기화 |
| FR-02 | `test_monitor_progress_header.py` | `openTaskPanel(TSK-*)` 후 `#task-panel-body > .progress-header` DOM 존재, status/last event/elapsed/phase steps 4행 렌더 |
| FR-03 | `test_monitor_grid_ratio.py` | `static/style.css` 에서 `.grid { grid-template-columns: ... 2fr ... 3fr ... }` 정규식 매치 |
| FR-04 | `test_monitor_pane_size.py` | `.pane-preview { max-height: 9em }` + `::before content: "... last 6 lines"` |
| FR-05 | `test_monitor_critical_color.py` | `.dep-node.critical { border-color: #f59e0b ... }` + `.dep-node.status-failed` 는 `var(--fail)` 유지 |
| FR-06 | `test_monitor_phase_badge_colors.py` | `.badge[data-phase="dd|im|ts|xx|failed|bypass|pending"]` 7종 각각 배경·테두리 규칙 존재, `.badge .spinner-inline` 규칙, `.dep-node[data-phase="*"]` 규칙 |
| FR-07 | `test_monitor_static_assets.py` | `GET /static/style.css` → 200 + `text/css` + `Cache-Control: public, max-age=300`; `GET /static/app.js` → 200 + `application/javascript`; `GET /static/evil.sh` → 404 |
| FR-07 | `test_monitor_module_split.py` | `import monitor_server.renderers.wp` 등 import 가능 + `Path('scripts/monitor-server.py').read_text().count('\\n') < 500` |

### 8.3 회귀 방지

- **시각 회귀**: Playwright 스크린샷 비교(`scripts/test_monitor_e2e_v4.py` 연장). S2/S3/S7 각 직후 실행.
- **벤치마크**: `scripts/benchmark-monitor.py`(존재 시) 각 S 단계 전/후 실행. 없으면 신규로 간단 도입(`time curl http://localhost:7321/`).
- **플러그인 캐시 동기화**: CLAUDE.md 규약에 따라 각 단계 머지 후 `~/.claude/plugins/marketplaces/dev-tools/` 에 미러링 — 메모리 `feedback_always_sync_cache.md` 준수.

## 9. 리스크 및 완화

| # | 리스크 | 완화 |
|---|-------|------|
| R-A | FR-07 S2(CSS 추출) 중 `<link rel="stylesheet">` 로드 타이밍 변경으로 FOUC(flash of unstyled content) 발생 | `<link>` 를 `<head>` 내 **최상단** 배치(meta 다음 바로). `<script src="app.js" defer>` 는 `</body>` 직전. HTTP/1.1 keep-alive 로 CSS/HTML 한 번의 연결에서 순차 로드 — 로컬 대시보드라 RTT < 1ms. 스냅샷 테스트로 FOUC 재현 시 인라인 CSS 임시 폴백(fallback 옵션). |
| R-B | FR-01 hover → click 전환으로 마우스 전용 사용자(트랙패드 제외) 접근성 저하 — "빨리 정보 보기" 경험 상실 | `.info-btn` 을 `<button>` 로 구현해 기본 키보드 포커스 + `Enter`/`Space` 열기 지원(`aria-expanded` 동기화). 마우스 사용자는 ⓘ 클릭 1회가 hover 300ms 대기와 동일 비용. 팝오버에 "ESC 로 닫기" 힌트 표기. |
| R-C | FR-07 단계별 동시 머지 시 `static/style.css` 와 `renderers/*.py` 가 서로 다른 PR 에서 변경되어 무성 회귀(메모리 `project_monitor_server_inline_assets.md` 경고) | 증분 분할(§4.2) + 각 FR 독립 PR + 시각 회귀 테스트(`test_monitor_e2e_v4.py` + Playwright 스냅샷)로 가드. S2/S3/S7 전후 스냅샷 diff 가 0 아닐 때 블로킹. |
| R-D | `/static/` 라우팅 추가로 기존 단일 HTML 응답의 폴링 캐시 모델이 변화 — 브라우저가 오래된 CSS 를 캐시해 신규 UI 가 반영 안 됨 | 정적 에셋에 `Cache-Control: public, max-age=300` (5분 상한). HTML 은 기존 `no-cache` 유지. `<link>` URL 에 버전 쿼리(`/static/style.css?v=<pkg_version>`) 첨부하여 배포 시 강제 재로드. 개발 중에는 `?v=<mtime>` 로 즉시 무효화. |
| R-E | 화이트리스트 우회 경로 순회 공격(`/static/../../etc/passwd`) | `_STATIC_WHITELIST = {"style.css", "app.js"}` 로 **이름 정확 매치만 허용**. `Path` 산술 후 `is_file()` 이차 검증. `..` 포함 경로는 set 멤버십 검사에서 탈락. |
| R-F | FR-06 `data-phase` 토큰이 graph-client.js 의 `statusKey()` 와 충돌하여 이중 스타일 덧씌움 | `.dep-node.status-*` 는 **border-left-color** 만 담당, `.dep-node[data-phase="*"]` 는 **.dep-node-id 글자색**만 담당 — CSS property scope 분리. 테스트(`test_monitor_phase_badge_colors.py`)에서 둘 다 공존 검증. |
| R-G | FR-04 pane-preview 높이 2배로 동시 실행 중인 팀 에이전트가 많을 때 스크롤 길이 증가 → 우측 열 전체 길이 부담 | FR-03 `2fr:3fr` 로 우측 열 폭이 커져 상쇄됨. 그래도 부담이면 `.pane-preview { overflow-y: auto; max-height: 9em }` 유지(개별 스크롤), 전체 열 스크롤 대신 각 pane 내부 스크롤. |
| R-H | FR-07 Python 패키지 이름(`monitor_server`, 언더스코어) ↔ entry 파일(`monitor-server.py`, 하이픈) 혼동 | `monitor-server.py` 상단 주석에 명시 + `sys.path.insert(0, str(Path(__file__).parent))` 1줄 + `from monitor_server.handlers import Handler` — import 경로는 **언더스코어만**. `monitor-launcher.py` 는 entry 파일 경로만 참조하므로 영향 없음. |
| R-I | FR-08 문서 중복 제거 중 과도 삭제로 SKILL.md 의 `description` 프런트매터 키워드가 빠져 NL 트리거 깨짐 | 삭제 전 `description` 필드 변경 금지 룰 명시. 삭제 대상은 **본문 섹션 중복**만. diff 검토 시 frontmatter hunk 는 리뷰어가 명시 거부. |
| R-J | 정적 에셋 응답 실패 시(디스크 누락) 대시보드가 완전히 깨짐 | `handlers.py` 에서 static 파일 `read_bytes()` 실패 시 500 대신 **인라인 fallback** 1주기 — `/static/*` 라우트 이전의 인라인 `<style>`/`<script>` 버전을 `renderers/__init__.py` 에 `_INLINE_FALLBACK=False` 플래그로 보존. 프로덕션에서 기본 `False`, 디버그 시 `True` 로 전환 가능. NF-02 "graceful degradation" 요건 충족. |

## 10. 비기능 요구사항 매핑

| NF | 요구 | 구현 |
|----|------|------|
| NF-01 성능 | 폴링 주기 10초 유지, 정적 에셋은 브라우저 캐시로 2회차+ 로드 비용 0 | `Cache-Control: public, max-age=300` + HTTP keep-alive |
| NF-02 가용성 | static 에셋 로드 실패 시 graceful degradation — 1 주기 내 인라인 fallback 복원 옵션 | R-J 의 `_INLINE_FALLBACK` 플래그 + 인라인 버전 보존 |
| NF-03 유지보수성 | 분할 후 단일 파일 최대 **1500줄 미만** | `test_monitor_module_split.py` 가드 + §4.2 S6 종료 시 `monitor-server.py < 500줄` |
| NF-04 접근성 | 키보드만으로 팝오버 열기/닫기 가능 | FR-01 `<button>` + `aria-expanded` + ESC/Enter |
| NF-05 호환성 | 기존 `/api/*` 계약 무변경 | §5.1 테이블 + §8.2 API 테스트 통과 |
| NF-06 토큰 예산 | 워커 증가 0(서버·SSR 전용 변경) | `/api/*` 응답 크기 +< 100B (phase 필드 추가분) |

## 11. 스케줄·의존성

- **블로커**: 없음 — 독립 서브프로젝트. v4 머지 이후 시작.
- **전제조건**:
  - v4 관련 e2e 테스트(`test_monitor_e2e_v4.py`) 전량 green.
  - `docs/monitor-v4/wbs.md` 의 WP 전체 `[xx]` 상태.
- **사용 중 시스템 영향**: dev-monitor 사용자는 v5 적용 후 **1회 재기동 필요**(`python3 scripts/monitor-launcher.py --stop && --start`) — CSS/JS 캐시 초기화 목적. 릴리스 노트에 명시.
- **세부 일정**: WBS 생성 시 채움(본 TRD 에서는 전제·블로커만 명시).

## 12. 참고

- PRD: `docs/monitor-v5/prd.md`
- v4 TRD 포맷 벤치마크: `docs/monitor-v4/trd.md`
- 코드 엔트리: `scripts/monitor-server.py` (v5 이후 `scripts/monitor_server/` 패키지)
- 메모리: `project_monitor_server_inline_assets.md` (동시 머지 무성 회귀 경고 — R-C 근거)
- 프로젝트 컨벤션: `CLAUDE.md` "CLI 작성 원칙 — 모든 새 CLI 기능은 Python으로"
