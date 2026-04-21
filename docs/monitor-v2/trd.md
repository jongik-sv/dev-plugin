# TRD — dev-plugin 웹 모니터링 도구 v2 (Visual Redesign)

**문서 버전:** 0.1 (초안)
**작성일:** 2026-04-21
**대상 플러그인:** `dev` (dev-plugin)
**선행 문서:** `docs/monitor-v2/prd.md` (v2, 2026-04-21), `docs/monitor/trd.md` (v1)
**상태:** Draft

---

## 1. 범위

PRD v2 §2 목표에 따른 **렌더링 레이어 교체**에 한정. 범위 내/외 구분:

| 영역 | 범위 | 변경 |
|------|------|------|
| 스킬 커맨드 (`/dev-monitor`) | 범위 외 | v1 유지 |
| `monitor-launcher.py` (기동/정지/PID) | 범위 외 | v1 유지 |
| `monitor-server.py` HTTP 핸들러·라우팅 | 범위 외 | v1 유지 |
| `monitor-server.py` 데이터 수집 함수 | 범위 외 | v1 유지 (scan_tasks / scan_features / scan_signals / list_tmux_panes / capture_pane / _build_state_snapshot) |
| `monitor-server.py` 렌더링 함수 | **범위 내** | 재작성 (DASHBOARD_CSS + _section_* + 신규 _section_kpi, _section_live, _section_timeline + 드로어 HTML/JS 인라인) |
| 클라이언트 JS | **범위 내** | v1의 `_PANE_JS` 확장 + 신규 대시보드 JS (부분 fetch, 필터, 드로어) |
| 엔드포인트 | 범위 외 | `/`, `/api/state`, `/pane/{id}`, `/api/pane/{id}` — 경로·응답 스키마 동일, 신규 없음 |

## 2. 아키텍처 개요

```
┌────────────── Browser (single tab) ──────────────┐
│                                                  │
│  ┌─────── Main Dashboard (/) ─────────┐          │
│  │  <head>                            │          │
│  │   inline DASHBOARD_CSS             │          │
│  │   inline DASHBOARD_JS              │          │
│  │  <body>                            │          │
│  │   [KPI][WP cards][Features]        │          │
│  │   [Live Activity][Timeline]        │          │
│  │   [Team with inline preview]       │          │
│  │                                    │          │
│  │   setInterval(fetch /api/state,    │          │
│  │               5s);                 │          │
│  │   → diff-patch DOM                 │          │
│  └────────────────────────────────────┘          │
│                                                  │
│  ┌─────── Side Drawer (overlay) ──────┐          │
│  │   <pre> 500 lines                  │          │
│  │   setInterval(fetch                │          │
│  │     /api/pane/{id}, 2s);           │          │
│  │   → replace <pre>.textContent      │          │
│  └────────────────────────────────────┘          │
└──────────────────────────────────────────────────┘
                    ▲ fetch
                    │
┌──────────── Local Python HTTP Server ────────────┐
│   BaseHTTPRequestHandler                         │
│   ├─  GET /            → render_dashboard()      │
│   ├─  GET /api/state   → json.dumps(snapshot)    │
│   ├─  GET /pane/{id}   → render_pane_html()      │
│   └─  GET /api/pane/{id} → json pane lines        │
│                                                  │
│   _build_state_snapshot() — v1 그대로            │
│     ├─ scan_tasks(docs_dir)                      │
│     ├─ scan_features(docs_dir)                   │
│     ├─ scan_signals()                            │
│     ├─ list_tmux_panes()                         │
│     └─ phase_history_tail aggregation            │
└──────────────────────────────────────────────────┘
```

## 3. 파일 변경 목록

```
scripts/
└── monitor-server.py                # 수정 — 렌더 레이어 교체

docs/
└── monitor-v2/
    ├── prd.md                       # 이미 존재
    ├── trd.md                       # 본 문서
    ├── prototype.html               # 신규 (P1 산출물)
    └── wbs.md                       # 신규 (추후)
```

신규 파일 생성 없이 `monitor-server.py` in-place 수정 우선. 프로토타입 HTML은 설계 검증용 임시 산출물.

## 4. `monitor-server.py` 모듈 구조

### 4.1 현재(v1) 구조 요약

| 구역 | 라인 대략치 | 역할 |
|------|-------------|------|
| Signal scan | 74–196 | SignalEntry, scan_signals() |
| tmux pane | 198–315 | PaneInfo, list_tmux_panes, capture_pane |
| WorkItem + state.json | 317–645 | PhaseEntry, WorkItem, _read_state_json, scan_tasks, scan_features |
| CSS (dashboard) | 668–731 | DASHBOARD_CSS (~63줄) |
| render helpers | 734–830 | _esc, _refresh_seconds, _signal_set, _format_elapsed, _retry_count, _status_badge, _group_preserving_order, _section_wrap, _empty_section |
| section renderers | 841–1076 | _section_header, _section_wbs, _section_features, _section_team, _section_subagents, _section_phase_history |
| render_dashboard | 1079–1125 | 최종 조립 |
| pane page | 1132–1400+ | _PANE_CSS, _PANE_JS, _render_pane_html, _render_pane_json, _handle_pane_* |
| HTTP handler | ~1400–1852 | MonitorHandler, main() |

### 4.2 v2 변경 상세

#### 4.2.1 `DASHBOARD_CSS` (668~731 → ~400줄 상한)

현재 CSS를 **확장**. 추가 영역 요약:

```css
/* Layout grid */
.page       { display: grid; grid-template-columns: 3fr 2fr; gap: 1rem; max-width: 1600px; margin: 0 auto; }
@media (max-width: 1279px) { .page { grid-template-columns: 1fr; } }

/* Sticky header + KPI cards */
.sticky-hdr { position: sticky; top: 0; z-index: 10; background: var(--bg); backdrop-filter: blur(8px); }
.kpi-row    { display: grid; grid-template-columns: repeat(5, 1fr); gap: 0.75rem; }
.kpi-card   { background: var(--panel); border-left: 4px solid var(--muted); border-radius: 6px; padding: 0.75rem 1rem; }
.kpi-card.running { border-left-color: var(--orange); }
.kpi-card.failed  { border-left-color: var(--red); }
.kpi-card.bypass  { border-left-color: var(--yellow); }
.kpi-card.done    { border-left-color: var(--green); }
.kpi-num    { font-size: 1.8rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.kpi-sparkline { height: 24px; margin-top: 0.25rem; }

/* Filter chips */
.chip { padding: 0.25rem 0.75rem; border: 1px solid var(--border); border-radius: 999px;
        font-size: 0.85rem; cursor: pointer; user-select: none; }
.chip[aria-pressed="true"] { background: var(--accent); color: var(--bg); border-color: var(--accent); }

/* WP card with CSS donut */
.wp-donut { width: 80px; height: 80px; border-radius: 50%;
            background: conic-gradient(var(--green)       0deg var(--pct-done-end),
                                       var(--orange) var(--pct-done-end) var(--pct-run-end),
                                       var(--light-gray)  var(--pct-run-end) 360deg); }
.wp-progress { height: 6px; border-radius: 3px; background: var(--border); overflow: hidden; }

/* Task row with left colored bar */
.task-row::before { content: ""; position: absolute; left: 0; top: 4px; bottom: 4px; width: 4px; border-radius: 2px; }
.task-row.done::before    { background: var(--green); }
.task-row.running::before { background: var(--orange); }
.task-row.failed::before  { background: var(--red); }
.task-row.bypass::before  { background: var(--yellow); }
.task-row.pending::before { background: var(--light-gray); }
.task-row.running .run-line { height: 2px; background: var(--orange); animation: slide 1.2s linear infinite; }
@keyframes slide { 0% { transform: translateX(-100%); } 100% { transform: translateX(100%); } }

/* Live activity fade-in */
.activity-row { display: grid; grid-template-columns: 6rem 8rem 6rem 1fr auto; gap: 0.5rem;
                font-family: ui-monospace, Consolas, monospace; font-size: 0.85rem;
                animation: fade-in 0.3s; }
@keyframes fade-in { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: none; } }

/* Phase timeline SVG classes */
.timeline-svg .tl-dd { fill: var(--blue); }
.timeline-svg .tl-im { fill: var(--purple); }
.timeline-svg .tl-ts { fill: var(--green); }
.timeline-svg .tl-xx { fill: var(--gray); }
.timeline-svg .tl-fail { fill: url(#hatch); opacity: 0.6; }

/* Pane inline preview */
.pane-preview { margin-left: 1.5rem; padding: 0.5rem; background: var(--bg);
                border: 1px solid var(--border); border-radius: 4px;
                font-family: ui-monospace, Consolas, monospace; font-size: 0.8rem;
                white-space: pre-wrap; max-height: 4.5em; overflow: hidden; color: var(--muted); }

/* Side drawer */
.drawer-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 50; display: none; }
.drawer-backdrop.open { display: block; }
.drawer          { position: fixed; top: 0; right: 0; bottom: 0; width: 640px; background: var(--panel);
                   border-left: 1px solid var(--border); z-index: 60; display: none; flex-direction: column;
                   transform: translateX(100%); transition: transform 0.25s ease-out; }
.drawer.open     { display: flex; transform: translateX(0); }
.drawer-body pre { margin: 0; font-family: ui-monospace, Consolas, monospace; font-size: 0.85rem;
                   line-height: 1.4; white-space: pre-wrap; }
@media (max-width: 767px) { .drawer { width: 100vw; } }

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  .badge-run, .task-row.running .run-line, .activity-row { animation: none !important; }
  .drawer { transition: none; }
}
```

**상한 체크**: v1 CSS 63줄 + 위 추가 ~280줄 ≈ 343줄. 400줄 상한 이내.

#### 4.2.2 신규 / 확장 렌더 함수

| 함수 | 종류 | 역할 |
|------|------|------|
| `_section_sticky_header(model)` | **신규** | 로고 dot · 제목 · 프로젝트 경로 · refresh 라벨 · auto 토글 버튼 |
| `_section_kpi(model)` | **신규** | 5장 KPI 카드 + 스파크라인 SVG + 필터 칩 |
| `_section_wp_cards(tasks, ...)` | **신규** | WP 카드 리스트 (도넛 + progress + 카운트) |
| `_section_wbs(tasks, ...)` | **수정** | 카드 하단 펼침 영역의 task-row 렌더 (좌측 컬러 바 클래스 추가) |
| `_section_features(features, ...)` | 거의 유지 | task-row 클래스 확장 |
| `_section_live_activity(model)` | **신규** | 최근 20건 phase_history 이벤트 (우측 상단) |
| `_section_phase_timeline(tasks, features)` | **신규** | SVG 가로 스트립 (우측 중단) |
| `_section_team(panes)` | **수정** | pane row에 inline preview 영역 + expand 버튼 추가 |
| `_section_subagents(signals)` | 유지 | v1 그대로 |
| `_kpi_spark_svg(buckets, color)` | **신규** | SVG `<polyline>` 스파크라인 유틸 |
| `_timeline_svg(rows, span_minutes)` | **신규** | SVG rect + tick 축 렌더 유틸 |
| `_drawer_skeleton()` | **신규** | 페이지 로드 시 함께 주입되는 드로어 골격 (비어있는 `<pre>`) |
| `render_dashboard(model)` | **수정** | sections 조립을 `.page` 2단 grid + sticky header 기준으로 재배치 |

#### 4.2.3 `/api/state` 응답 스키마 (v1 계승, 변경 없음)

```json
{
  "generated_at": "2026-04-21T11:09:22+09:00",
  "project_root": "/path/to/repo",
  "docs_dir": "docs",
  "refresh_seconds": 5,
  "wbs_tasks": [
    {
      "id": "TSK-01-07",
      "wp_id": "WP-01",
      "title": "build-dash",
      "status": "[xx]",
      "bypassed": false,
      "elapsed_seconds": 210,
      "phase_history_tail": [
        {"event": "dd.ok", "from_status": "", "to_status": "[dd]",
         "at": "2026-04-21T11:02:04+09:00", "elapsed_seconds": 22}
      ],
      "error": null
    }
  ],
  "features": [ /* 동일 구조, wp_id 없음 */ ],
  "tmux_panes": [
    { "pane_id": "%2", "window_name": "dev-WP-01",
      "pane_index": "2", "pane_current_command": "claude", "pane_pid": "48121" }
  ],
  "shared_signals": [
    { "kind": "running", "task_id": "TSK-01-09",
      "scope": "project", "mtime": "2026-04-21T11:08:00+09:00" }
  ],
  "agent_pool_signals": [ /* 동일 구조 */ ]
}
```

**누락 여부 점검**: v2 KPI/타임라인 계산에 필요한 필드는 전부 v1이 이미 제공. 추가 데이터 요구 없음.

**검증 작업**: `/api/state` 응답이 위 스키마와 1:1 일치하는지 unit test 1건 추가 (회귀 방지).

#### 4.2.4 클라이언트 JS (신규 인라인, ≤200줄 목표)

`monitor-server.py` 상단에 `_DASHBOARD_JS` 문자열로 추가. `render_dashboard()`에서 `<script>` 태그에 삽입.

```javascript
(function(){
  "use strict";

  var state = {
    autoRefresh: true,
    pollMs: 5000,
    activeFilter: 'all',   // 'all' | 'running' | 'failed' | 'bypass'
    drawerPaneId: null,
    drawerPollId: null,
  };

  // --- Main polling ---
  var mainPollId = null, mainAbort = null;
  function startMainPoll(){
    stopMainPoll();
    mainPollId = setInterval(function(){
      if (!state.autoRefresh) return;
      if (mainAbort) mainAbort.abort();
      mainAbort = new AbortController();
      fetch('/api/state', {cache:'no-store', signal: mainAbort.signal})
        .then(function(r){ return r.ok ? r.json() : null; })
        .then(function(j){ if (j) patchDashboard(j); })
        .catch(function(){});
    }, state.pollMs);
  }
  function stopMainPoll(){ if (mainPollId) { clearInterval(mainPollId); mainPollId = null; } }

  // --- DOM patching (simple section-level innerHTML replacement) ---
  // For v1 parity we re-request /api/state and have the server render only the
  // data payload; sections are regenerated client-side from cached templates.
  // Alternatively (simpler): request `/` HTML and extract <section> blocks.
  // v2 pragmatic choice: re-fetch `/` HTML, diff by [data-section] attribute,
  // and replace sections whose innerHTML changed.
  function patchDashboard(model){
    // implemented in full in P3: see §5 for data computation helpers
  }

  // --- Filter chips ---
  document.querySelectorAll('.chip').forEach(function(el){
    el.addEventListener('click', function(){
      state.activeFilter = el.dataset.filter;
      document.querySelectorAll('.chip').forEach(function(c){
        c.setAttribute('aria-pressed', c === el ? 'true' : 'false');
      });
      applyFilter();
    });
  });
  function applyFilter(){
    document.querySelectorAll('.task-row').forEach(function(row){
      var hide = state.activeFilter !== 'all' && !row.classList.contains(state.activeFilter);
      row.style.display = hide ? 'none' : '';
    });
  }

  // --- Drawer ---
  function openDrawer(paneId){
    state.drawerPaneId = paneId;
    document.querySelector('.drawer-title').textContent = 'PANE: ' + paneId;
    document.querySelector('.drawer').classList.add('open');
    document.querySelector('.drawer-backdrop').classList.add('open');
    startDrawerPoll();
  }
  function closeDrawer(){
    state.drawerPaneId = null;
    stopDrawerPoll();
    document.querySelector('.drawer').classList.remove('open');
    document.querySelector('.drawer-backdrop').classList.remove('open');
  }
  function startDrawerPoll(){
    stopDrawerPoll();
    tickDrawer();
    state.drawerPollId = setInterval(tickDrawer, 2000);
  }
  function stopDrawerPoll(){ if (state.drawerPollId) { clearInterval(state.drawerPollId); state.drawerPollId = null; } }
  function tickDrawer(){
    if (!state.drawerPaneId) return;
    fetch('/api/pane/' + encodeURIComponent(state.drawerPaneId), {cache:'no-store'})
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(function(j){ if (j) updateDrawerBody(j); })
      .catch(function(){});
  }
  function updateDrawerBody(j){
    document.querySelector('.drawer-body pre').textContent = (j.lines || []).join('\n');
    document.querySelector('.drawer-footer .ts').textContent = 'captured at ' + j.captured_at;
  }

  // --- Event wire-up (delegation — survives DOM replacement) ---
  document.addEventListener('click', function(e){
    var exp = e.target.closest('[data-pane-expand]');
    if (exp) { openDrawer(exp.dataset.paneExpand); return; }
    if (e.target.matches('.drawer-close, .drawer-backdrop')) closeDrawer();
  });
  document.addEventListener('keydown', function(e){
    if (e.key === 'Escape' && state.drawerPaneId) closeDrawer();
  });
  var tog = document.querySelector('.refresh-toggle');
  if (tog) tog.addEventListener('click', function(){
    state.autoRefresh = !state.autoRefresh;
    this.setAttribute('aria-pressed', state.autoRefresh);
    this.textContent = state.autoRefresh ? '◐ auto' : '○ paused';
  });

  startMainPoll();
})();
```

**라인 체크**: 위 스켈레톤 약 120줄. diff 구현 + 예외 처리 포함 예상 ~180줄. 200줄 상한 이내.

#### 4.2.5 HTML 구조 변화

```html
<body>
  <header class="sticky-hdr" data-section="hdr">
    <!-- _section_sticky_header -->
  </header>

  <main>
    <section class="kpi-section" data-section="kpi">
      <!-- _section_kpi: 5 cards + filter chips -->
    </section>

    <div class="page">
      <div class="col-left">
        <section data-section="wp-cards"><!-- _section_wp_cards --></section>
        <section data-section="wbs"><!-- _section_wbs --></section>
        <section data-section="features"><!-- _section_features --></section>
      </div>
      <div class="col-right">
        <section data-section="activity"><!-- _section_live_activity --></section>
        <section data-section="timeline"><!-- _section_phase_timeline --></section>
        <section data-section="team"><!-- _section_team (inline preview) --></section>
        <section data-section="subagents"><!-- _section_subagents --></section>
      </div>
    </div>
  </main>

  <div class="drawer-backdrop" aria-hidden="true"></div>
  <aside class="drawer" role="dialog" aria-modal="true" aria-hidden="true">
    <div class="drawer-header">
      <span class="drawer-title">PANE</span>
      <button class="drawer-close" aria-label="close">✕</button>
    </div>
    <div class="drawer-body"><pre></pre></div>
    <div class="drawer-footer"><span class="ts">—</span></div>
  </aside>

  <script>/* inline _DASHBOARD_JS */</script>
</body>
```

v1의 `<meta http-equiv="refresh">`는 **제거**. 대신 `<script>`가 5초 polling.

## 5. 데이터 계산 로직

### 5.1 KPI 카운트

```python
def _kpi_counts(tasks, features, signals):
    all_items = list(tasks) + list(features)
    running_ids = _signal_set(signals, "running")
    failed_ids  = _signal_set(signals, "failed")
    bypass_ids  = {it.id for it in all_items if getattr(it, "bypassed", False)}
    done_ids    = {it.id for it in all_items if getattr(it, "status", None) == "[xx]"}

    # Priority: bypass > failed > running > done > pending (per _status_badge).
    running = running_ids - bypass_ids - failed_ids
    failed  = failed_ids  - bypass_ids
    done    = done_ids    - bypass_ids - failed_ids - running_ids
    pending = len(all_items) - (len(bypass_ids) + len(failed) + len(running) + len(done))

    return {"running": len(running), "failed": len(failed),
            "bypass": len(bypass_ids), "done": len(done),
            "pending": pending}
```

### 5.2 스파크라인 버킷 (최근 N분, 1분 간격)

```python
def _spark_buckets(items, kind: str, now: datetime, span_min: int = 10):
    """kind in {'running','failed','bypass','done','pending'}. Returns list[int] length span_min."""
    buckets = [0] * span_min
    start = now - timedelta(minutes=span_min)
    for it in items:
        for ev in getattr(it, "phase_history_tail", None) or []:
            at = _parse_iso(getattr(ev, "at", None))
            if not at or at < start or at > now:
                continue
            if not _event_matches_kind(ev, kind):
                continue
            idx = int((at - start).total_seconds() // 60)
            if 0 <= idx < span_min:
                buckets[idx] += 1
    return buckets
```

SVG 렌더: `<polyline points="0,24 1,20 2,15 ..." stroke="..." fill="none" />`, viewBox `0 0 {span-1} 24`.

### 5.3 WP 도넛 각도 계산

```python
def _wp_donut_style(wp_counts) -> str:
    total = max(wp_counts["total"], 1)
    done_deg = int(360 * wp_counts["done"]    / total)
    run_deg  = int(360 * wp_counts["running"] / total)
    # CSS custom properties consumed by .wp-donut conic-gradient
    return (f'--pct-done-end: {done_deg}deg; '
            f'--pct-run-end: {done_deg + run_deg}deg;')
```

### 5.4 타임라인 SVG

각 row: `<g transform="translate(0,{y})">` 안에 phase 구간마다 `<rect x={start_x} width={width} height=16 class="tl-{dd|im|ts|xx}" />`.

- X 축 매핑: 현재 시각 - 60분 = x=0, 현재 = x=W (viewBox width 600)
- 실패 구간: 해칭 패턴 `<pattern id="hatch">` 정의 후 `fill="url(#hatch)"`
- bypass 마커: row 끝에 `<text>🟡</text>`
- `phase_history`에는 phase 전환만 기록되고 "시작 시각"은 있지만 "종료 시각"은 다음 이벤트의 `at`으로 추론. 최종 미완료 phase는 `generated_at`까지 연장

### 5.5 Team pane inline preview

- `capture_pane(pane_id)` 호출 결과 중 마지막 3줄만 추출
- preview는 초기 SSR 시점에 렌더 → 부분 fetch 시 drawer 폴링이 우선이면 생략
- pane 수가 많을 때 비용: 30 panes × `tmux capture-pane` 호출 ≈ 개당 < 50ms → 1.5s 이내. 문제 시 preview를 on-demand로 전환 (hover 시 load).

## 6. 엔드포인트 계약 (변경 없음 재확인)

| 메서드 | 경로 | 요청 | 응답 타입 | 응답 예 |
|--------|------|------|-----------|---------|
| GET | `/` | — | text/html | 전체 대시보드 HTML (SSR) |
| GET | `/api/state` | — | application/json | §4.2.3 스키마 |
| GET | `/pane/{pane_id}` | `pane_id` URL-encoded | text/html | v1의 `_render_pane_html` 결과 |
| GET | `/api/pane/{pane_id}` | 동일 | application/json | `{"pane_id":"%2","lines":[...],"captured_at":"..."}` |

드로어는 `/api/pane/{id}` 재사용. 신규 엔드포인트 **추가하지 않음**.

## 7. 테스트 전략

### 7.1 단위 테스트 (pytest, Python stdlib만)

| 대상 | 테스트 케이스 |
|------|---------------|
| `_kpi_counts` | 5개 카테고리 합 == 전체, 우선순위(bypass > failed > running > done > pending) 충돌 해소 |
| `_spark_buckets` | 10분 범위 외 이벤트 제외, kind 매칭 |
| `_wp_donut_style` | 분모 0 방어, 각도 합 ≤ 360 |
| `_section_kpi` | 렌더 결과에 5개 `.kpi-card` 포함, `data-kpi="running|failed|..."` 속성 |
| `_section_wp_cards` | WP ID 순서 보존, 도넛 CSS 변수 포함 |
| `_timeline_svg` | 태스크 0건일 때 empty state, phase fail 구간 `class="tl-fail"` |
| `_section_team` (수정) | 각 pane row에 `[data-pane-expand]` 버튼 + preview `<pre>` 존재 |
| HTML 전체 | v1 응답 스키마와 `/api/state` 필드 1:1 일치 (회귀 방지) |

### 7.2 통합 테스트

- 로컬 `monitor-server.py` 기동 후 `urllib.request`로 `/`, `/api/state`, `/api/pane/%2` 요청
- 응답 Content-Type 확인
- HTML에 드로어 골격 (`<aside class="drawer">`) 포함 확인

### 7.3 브라우저 수동 QA

- Chrome / Safari / Firefox 각 1회 — 레이아웃 깨짐, 애니메이션 동작, 드로어 ESC 닫힘
- `prefers-reduced-motion` 활성화 상태에서 애니메이션 정지 확인
- 반응형: 1440px / 1024px / 390px 3개 viewport
- 장시간 모니터링 시 메모리 누수 없음 (`performance.memory` 주시, 5분+)

### 7.4 플랫폼 회귀

- macOS / Linux / WSL2 / Windows(psmux): 기동 → 대시보드 로드 → 드로어 열기 → pane 출력 2초 폴링 확인
- tmux 미설치 시: Team 섹션 "tmux not available" 안내, 나머지 섹션 정상

## 8. 접근성 구현 포인트

| 항목 | 구현 |
|------|------|
| 색 대비 | 기본 팔레트 이미 WCAG AA 만족. border-left 4px로 색상 외 시각적 식별 보강 |
| 키보드 | `.chip`·`.refresh-toggle`·`[data-pane-expand]` 모두 `<button>`으로 렌더링 → 기본 focusable |
| 드로어 | `role="dialog"` `aria-modal="true"` · 열릴 때 focus를 `.drawer-close`로 이동 · 닫힐 때 트리거 요소로 복귀 |
| 스크린리더 | KPI 카드 숫자에 `aria-label="Running: 3"` · SVG에 `<title>`/`<desc>` |
| 모션 | `@media (prefers-reduced-motion: reduce)`로 pulse·fade·transition 비활성 |

## 9. 보안 고려사항

- localhost 전용 바인딩 (v1 유지) — 외부 노출 없음
- 모든 사용자 유래 문자열은 `_esc`로 HTML escape (v1 유지)
- 드로어가 표시하는 pane 출력은 클라이언트 JS가 `textContent`로만 삽입 → XSS 무해
- JSON 응답(`/api/*`)은 `json.dumps` 결과를 그대로 전송 (Content-Type application/json)
- `innerHTML` 주입은 서버 렌더 단편(이미 escape된 상태)에만 적용

## 10. 성능 / 사이즈 예산

| 항목 | 목표 | v1 | v2 예상 |
|------|------|----|---------|
| 초기 HTML 크기 (태스크 30건) | ≤ 200KB | ~50KB | ~120KB |
| `/api/state` 응답 (태스크 100건) | ≤ 100KB | ~60KB | ~60KB (변경 없음) |
| CSS 라인 | ≤ 400 | 63 | ~343 |
| 클라이언트 JS 라인 | ≤ 200 | 16 (pane only) | ~180 |
| 부분 fetch 주기 | 기본 5s / 최소 2s | — | 5s |
| 브라우저 메모리 (5분 운영) | ≤ 50MB | — | 측정 예정 |

## 11. 구현 순서 (PRD §8과 매칭)

1. **P1 — `docs/monitor-v2/prototype.html`** (정적 프로토타입, 목업 데이터 하드코딩)
2. **P2-a — `DASHBOARD_CSS` 교체** (기존 63줄 → 확장 ~343줄)
3. **P2-b — `_section_kpi`, `_section_wp_cards`, `_section_live_activity`, `_section_phase_timeline` 신규 + `_section_team` 수정** (inline preview + expand 버튼)
4. **P2-c — `render_dashboard` 조립 순서 변경 + sticky header + 드로어 골격 주입**
5. **P3 — `_DASHBOARD_JS` 추가** (부분 fetch + 필터 + 드로어 제어)
6. **P4 — 미디어 쿼리 + 접근성 속성 + `prefers-reduced-motion`**
7. **P5 — pytest 테스트 추가 + 브라우저 QA + 4개 플랫폼 Smoke**

각 단계 산출물에 대한 커밋/PR 단위는 WBS에서 세분화.

## 12. 리스크 & 대응

| 리스크 | 영향 | 대응 |
|--------|------|------|
| CSS `conic-gradient` 구형 Safari 미지원 | 도넛 차트 깨짐 | `@supports not (background: conic-gradient(red, blue))` 시 가로 막대로 대체 |
| SVG 해칭 패턴이 Firefox에서 어긋남 | 실패 구간 시각 혼란 | 단색 반투명(`rgba(248,81,73,0.3)`) 1차 fallback |
| JS 부분 fetch 충돌 (동일 탭 다중 폴링) | 중복 요청 | `AbortController`로 이전 요청 취소 |
| 드로어 열린 상태에서 대시보드 `innerHTML` 교체가 pane row를 재생성 → `data-pane-expand` 유실 | 드로어 닫힘 | drawer state는 DOM 참조 없이 state object의 `drawerPaneId`만 보유, 폴링은 독립 |
| 장시간 polling으로 누적 이벤트 리스너 | 메모리 누수 | 이벤트 위임(`document.addEventListener`)으로 row 재생성에 영향 없음 |
| 태스크 수 1000건 이상에서 timeline SVG 과다 | 렌더 지연 | 상위 50건만 렌더, "+N more" 링크 |
| Team inline preview용 `capture_pane` 호출 비용 | 초기 SSR 지연 | pane 수 ≥ 20일 때 preview 생략, 드로어 열어야 전체 캡처 |

## 13. 열린 기술 질문

- [ ] DOM diff를 수동 구현 vs 섹션 전체 innerHTML 교체로 단순화? (단순 교체는 스크롤 위치만 보존되면 충분)
- [ ] 타임라인 시간축 범위: 서버 모델에 `timeline_window_minutes` 필드 추가 vs 클라이언트 상수?
- [ ] KPI 필터 상태를 URL 해시(`#filter=failed`)에 반영할지 — 공유 가능 URL vs 단순함 트레이드오프
- [ ] 드로어 다중 탭 동시 오픈 지원 여부 (현재 단일 드로어 전제)
- [ ] Team inline preview를 초기 SSR에 포함 vs hover/expand 시 lazy load?
- [ ] 프로토타입 HTML은 svg 아이콘까지 포함할지, 또는 와이어프레임 수준(블록+색만)인지

## 14. 참고

- PRD: `docs/monitor-v2/prd.md`
- v1 TRD: `docs/monitor/trd.md`
- v1 구현: `scripts/monitor-server.py` (1852줄)
- v1 스킬: `skills/dev-monitor/SKILL.md`
- 상태 머신: `references/state-machine.json`
- 시그널 프로토콜: `references/signal-protocol.md`
- 플랫폼 유틸: `scripts/_platform.py`
