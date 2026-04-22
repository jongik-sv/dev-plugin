# monitor-redesign-v3: 설계

## 요구사항 확인

- `dev-plugin Monitor.html` (2099줄, 완성된 디자인 레퍼런스)의 CSS 토큰·레이아웃·마크업을 `scripts/monitor-server.py`의 `DASHBOARD_CSS` 및 `_section_*` 렌더러에 4단계 점진적으로 이식한다.
- 각 단계 완료 후 서버가 정상 기동 가능해야 하며, 기존 dataclass/헬퍼(`SignalEntry`, `PaneInfo`, `_signal_set`, `_format_elapsed` 등)와 스캔 함수는 전혀 변경하지 않는다.
- `scripts/test_monitor_render.py`의 스냅샷·구조 어서션을 단계별로 새 마크업에 맞춰 갱신한다.

## 타겟 앱

- **경로**: N/A (단일 앱 — `scripts/monitor-server.py` 단일 파일 프로젝트)
- **근거**: 별도 프레임워크 앱 경계 없이 Python stdlib HTTP 서버 + 인라인 HTML 생성 구조

---

## CSS 핵심 토큰 (전 단계 공통 기준)

새 `DASHBOARD_CSS`가 제공하는 디자인 시스템 변수:

| 토큰 | 값 | 의미 |
|------|----|------|
| `--bg` | `#0b0d10` | 최하단 배경 |
| `--bg-1` | `#0f1216` | 카드/패널 배경 |
| `--bg-2` | `#141820` | 서브 배경 |
| `--bg-3` | `#1a1f28` | 트랙/입력 배경 |
| `--line` | `#1f2530` | 기본 구분선 |
| `--line-2` | `#2a3140` | 보조 구분선 |
| `--line-hi` | `#3a4456` | 강조 구분선 |
| `--ink` | `#e8ecf1` | 기본 텍스트 |
| `--ink-2` | `#aeb5c1` | 보조 텍스트 |
| `--ink-3` | `#6b7480` | 3차 텍스트 |
| `--ink-4` | `#464e5a` | 최저 명도 텍스트 |
| `--accent` | `#c89b6a` | 브랜드 amber |
| `--accent-hi` | `#e6b884` | 강조 amber |
| `--accent-dim` | `#7a5e3f` | 다운 amber |
| `--run` | `#4aa3ff` | running — 파란색 |
| `--run-glow` | `rgba(74,163,255,.18)` | running glow |
| `--done` | `#4ed08a` | done — phosphor 녹색 |
| `--done-glow` | `rgba(78,208,138,.16)` | done glow |
| `--fail` | `#ff5d5d` | failed — 빨간색 |
| `--fail-glow` | `rgba(255,93,93,.16)` | fail glow |
| `--bypass` | `#d16be0` | bypass — magenta |
| `--bypass-glow` | `rgba(209,107,224,.16)` | bypass glow |
| `--pending` | `#f0c24a` | pending — 노란색 |
| `--pending-glow` | `rgba(240,194,74,.16)` | pending glow |
| `--mono` | `"JetBrains Mono", ...` | 코드/ID 폰트 |
| `--sans` | `"Space Grotesk", ...` | UI 폰트 |
| `--display` | `"Space Grotesk", ...` | 제목 폰트 |
| `--radius` | `4px` | 기본 반경 |
| `--radius-lg` | `6px` | 카드/섹션 반경 |

### 브레이크포인트

| 값 | 효과 |
|----|------|
| `max-width: 1280px` | `.grid` 2열 → 1열 전환 |
| `max-width: 768px` | `.cmdbar` 간소화, KPI 가로 스크롤, `.wp-meta` 숨김, `.trow` 컬럼 축소, `.drawer` 전폭 |

### 주요 애니메이션

| 이름 | 대상 | 설명 |
|------|------|------|
| `pulse` | `.pulse .dot` | 0→10px glow 펄스 1.6s |
| `breathe` | `.trow[data-status="running"] .badge::before`, `.sub[data-state="running"] .sw` | scale 1↔0.85 + opacity 1↔0.55, 1.4s |
| `led-blink` | `.btn[aria-pressed="true"] .led` | opacity 1↔0.55, 2s |
| `slide` | (단계 4에서 제거 또는 유지 선택) | 기존 `.run-line` 슬라이드 |

---

## 단계별 설계

---

## 단계 1: CSS 전면 교체 + shell/cmdbar/grid/section-head 골격

### 변경 대상 함수

| 함수/상수 | 현재 시그니처 | 변경 내용 |
|-----------|-------------|---------|
| `DASHBOARD_CSS` (모듈 상수) | 구 GitHub-dark 스타일 (`:root { --bg: #0d1117; ... }`) | 레퍼런스 HTML `<style>` 블록 전체로 교체. 구글 폰트 `@import` 포함. |
| `_section_header(model)` | `model: dict → str` | 구 `<section id="header">` nav 블록 → 새 `<header class="cmdbar">` `.brand`+`.meta`+`.actions` 구조로 교체. |
| `_section_sticky_header(model)` | `model: dict → str` | 구 `.sticky-hdr` 블록 → 제거 or `_section_header`로 통합 (cmdbar가 sticky이므로 별도 sticky 헤더 불필요). |
| `_build_dashboard_body(s)` | `s: dict → str` | 구 `.page` 래퍼 → 새 `.shell > .grid` 구조. `s["sticky-header"]`를 제거하고 `s["header"]`(cmdbar)를 맨 위에. |
| `render_dashboard(model)` | `model: dict → str` | `<body>` 직하에 `<div class="shell">` wrapper 추가. `.page` 클래스 → `.grid`. 구글 폰트 `<link>` preconnect 태그 `<head>`에 추가. |

### 마크업 스펙

**`_section_header` 출력 (단계 1 이후):**
```html
<header class="cmdbar" data-section="hdr" role="banner" aria-label="Command bar">
  <div class="brand">
    <span class="logo" aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
           stroke-linecap="round" stroke-linejoin="round">
        <path d="M4 7 L10 12 L4 17"/>
        <path d="M13 17 L20 17"/>
      </svg>
    </span>
    <span class="title">dev-plugin</span>
    <span class="slash">/</span>
    <span class="sub">monitor</span>
  </div>
  <div class="meta" role="group" aria-label="Session info">
    <span><span class="k">project</span><span class="v path">{project_root}</span></span>
    <span class="dot">·</span>
    <span><span class="k">docs</span><span class="v">{docs_dir}</span></span>
    <span class="dot">·</span>
    <span><span class="k">now</span><span class="v" id="clock">{generated_at}</span></span>
    <span class="dot">·</span>
    <span><span class="k">interval</span><span class="v">{refresh_s}s</span></span>
  </div>
  <div class="actions">
    <span class="pulse" aria-live="polite"><span class="dot" aria-hidden="true"></span> live</span>
    <button class="btn refresh-toggle" type="button" aria-pressed="true" aria-label="Auto-refresh">
      <span class="led" aria-hidden="true"></span>
      <span>auto</span>
      <span class="kbd" aria-hidden="true">R</span>
    </button>
  </div>
</header>
```

**`_build_dashboard_body` 구조 변경:**
- `s["header"]` → cmdbar (sticky)
- `<div class="shell">` wrapper (최대너비 1440px, 0 auto margin)
- KPI 섹션 (단계 1에서는 기존 로직 유지, CSS만 신규 토큰 반영)
- `<div class="grid">` (3fr/2fr, gap 28px, @media 1280px 이하 1fr)
  - `<div class="col">` (left): wp-cards + features
  - `<div class="col">` (right): live-activity + phase-timeline + team + subagents
- phase-history (전폭 하단)

**`render_dashboard` `<head>` 추가:**
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
```

### 단계 1 roll-forward 검증

**눈으로 확인:**
- 배경이 `#0b0d10` (거의 검정)으로 바뀌고 JetBrains Mono 폰트가 적용됨
- cmdbar: amber accent 밑줄, brand 로고 SVG, clock span, pulse dot 애니메이션
- 2열 그리드 레이아웃 (1280px 이하에서 1열 전환)
- 각 섹션 헤드에 `.section-head .eyebrow` + `.h2::before "▍"` 액센트 표시

**영향받는 테스트:**
- `test_section_sticky_header_*` → `_section_sticky_header` 제거/통합 후 어서션 갱신 또는 `_section_header` 케이스로 통합
- `test_render_dashboard_*` → `data-section="hdr"` 속성, `.cmdbar` 클래스 확인
- HTML `<head>` 구조 어서션 → 폰트 `<link>` 태그 포함 여부

---

## 단계 2: WP Cards — donut SVG + .trow 그리드

### 변경 대상 함수

| 함수 | 현재 시그니처 | 변경 내용 |
|------|-------------|---------|
| `_section_wp_cards(tasks, running_ids, failed_ids)` | `tasks: list, running_ids: set, failed_ids: set → str` | conic-gradient `.wp-donut` → SVG stroke-dasharray 4색 중첩 구조로 교체. `<details class="wp">` → `<details class="wp">` (구조 유지하되 내부 마크업 신규 클래스 반영). |
| `_render_task_row_v2(item, running_ids, failed_ids)` | `item: WorkItem, running_ids: set, failed_ids: set → str` | `<div class="task-row {state}">` 6열 그리드 → `<div class="trow" data-status="{state}">` 7열 그리드로 교체. |
| `_render_task_row(item, running_ids, failed_ids)` | 동일 | v2와 동일하게 갱신 (하위 호환 유지, 동일 출력). |
| `_section_features(features, running_ids, failed_ids)` | `features: list, ... → str` | `.features-wrap` 래퍼 + `.trow` 행 구조 사용. |
| `_wp_donut_style(counts)` | `counts: dict → str` | **삭제** — CSS `conic-gradient` 방식 제거. SVG 렌더 헬퍼로 대체. |
| `_wp_card_counts(items, running_ids, failed_ids)` | `items: list, ... → dict` | 시그니처 유지, 내부 로직 변화 없음. |

### 신규 헬퍼

**`_wp_donut_svg(counts: dict) -> str`**
- 입력: `{"done": n, "running": n, "failed": n, "bypass": n, "pending": n}`
- 출력: SVG 4개 circle stroke-dasharray 중첩 (pathLength="100" 기준, `rotate(-90deg)`)
- 각 circle: `stroke-dasharray="{slice} 100"`, `stroke-dashoffset="-{cumulative_offset}"`
- 순서: done → running → failed → bypass (pending은 track circle)
- 총합 0이면 track circle만 반환

**`_trow_data_status(item, running_ids, failed_ids) -> str`**
- 반환: `"done"` | `"running"` | `"failed"` | `"bypass"` | `"pending"`
- 기존 `_row_state_class` 로직과 동일 (래퍼)

### 마크업 스펙

**WP card 구조 (단계 2 이후):**
```html
<details class="wp" open>
  <summary style="list-style:none; display:block;">
    <div class="wp-head">
      <div class="wp-donut" aria-label="{pct}% complete">
        <svg viewBox="0 0 36 36">
          <!-- track -->
          <circle cx="18" cy="18" r="15.9" fill="none" stroke="var(--bg-3)" stroke-width="3"/>
          <!-- done slice -->
          <circle cx="18" cy="18" r="15.9" fill="none" stroke="var(--done)" stroke-width="3"
                  stroke-dasharray="{done_pct} 100" stroke-linecap="butt" pathLength="100"/>
          <!-- running slice -->
          <circle cx="18" cy="18" r="15.9" fill="none" stroke="var(--run)" stroke-width="3"
                  stroke-dasharray="{run_pct} 100" stroke-dashoffset="-{done_pct}" pathLength="100"/>
          <!-- failed slice -->
          <circle cx="18" cy="18" r="15.9" fill="none" stroke="var(--fail)" stroke-width="3"
                  stroke-dasharray="{fail_pct} 100" stroke-dashoffset="-{done_pct+run_pct}" pathLength="100"/>
          <!-- bypass slice -->
          <circle cx="18" cy="18" r="15.9" fill="none" stroke="var(--bypass)" stroke-width="3"
                  stroke-dasharray="{byp_pct} 100" stroke-dashoffset="-{done_pct+run_pct+fail_pct}" pathLength="100"/>
        </svg>
        <div class="pct">{pct}<small>PCT</small></div>
      </div>
      <div class="wp-title">
        <div class="row1">
          <span class="id">{wp_id}</span>
          <h3>{wp_title_or_id}</h3>
        </div>
        <div class="bar" aria-hidden="true">
          <div class="b-done" style="flex:{done}"></div>
          <div class="b-run"  style="flex:{run}"></div>
          <div class="b-fail" style="flex:{fail}"></div>
          <div class="b-byp"  style="flex:{byp}"></div>
          <div class="b-pnd"  style="flex:{pnd}"></div>
        </div>
        <div class="wp-counts">
          <span class="c" data-k="done"><span class="sw"></span><b>{n}</b> done</span>
          <span class="c" data-k="run"><span class="sw"></span><b>{n}</b> running</span>
          <span class="c" data-k="pnd"><span class="sw"></span><b>{n}</b> pending</span>
          <span class="c" data-k="fail"><span class="sw"></span><b>{n}</b> failed</span>
          <span class="c" data-k="byp"><span class="sw"></span><b>{n}</b> bypass</span>
        </div>
      </div>
      <div class="wp-meta">
        <span class="big">{total} tasks</span>
      </div>
    </div>
  </summary>
  <details class="wp-tasks">
    <summary><span>Tasks</span> <span class="ct">({n})</span></summary>
    <div class="task-list">
      <!-- .trow rows -->
    </div>
  </details>
</details>
```

**`.trow` 구조 (단계 2 이후):**
```html
<div class="trow" data-status="{done|running|failed|bypass|pending}">
  <div class="statusbar"></div>
  <div class="tid">{item_id}</div>
  <div class="badge">{status_label}</div>
  <div class="ttitle"><span class="path">{domain_prefix}/</span>{title}</div>
  <div class="elapsed">{elapsed}</div>
  <div class="retry">×{retry_count}</div>
  <div class="flags">{flag_html}</div>
</div>
```

- `data-status`: `_trow_data_status()` 반환값
- `.statusbar`: CSS로 컬러 처리 (`data-status` 어트리뷰트 선택자)
- `.badge`: 텍스트 라벨만 (`data-status` + CSS `::before` dot으로 표현)
- `.ttitle .path`: `item.path`에서 마지막 디렉토리명 추출 (없으면 생략)
- `.retry.hot` 클래스: retry_count >= 3일 때 추가
- `.flag.f-crit`: failed + retry >= 3 조합, `.flag.f-new`: 신규 (구현 판단)

### 단계 2 roll-forward 검증

**눈으로 확인:**
- WP 카드 헤더: SVG donut (4색 중첩 arc), `.wp-title` 바 그라디언트, `.wp-counts` 도트
- task row: 4px statusbar + badge dot + `.ttitle .path` muted prefix
- `running` 행: badge `::before` breathe 애니메이션

**영향받는 테스트:**
- `test_render_task_row_*` → `class="trow"` + `data-status=` 속성 어서션
- `test_section_wp_cards_*` → `.wp-donut svg` 존재, `.wp-title .bar` 존재, `.wp-counts` 존재
- `test_section_features_*` → `.trow` 구조 어서션
- `test_wp_donut_style` → `_wp_donut_svg` 헬퍼 테스트로 교체 (SVG 원소 개수/stroke-dasharray 검증)

---

## 단계 3: 우측 컬럼 — live-activity / phase-timeline / team / subagents

### 변경 대상 함수

| 함수 | 현재 시그니처 | 변경 내용 |
|------|-------------|---------|
| `_section_live_activity(model)` | `model: dict → str` | `.activity-row` → `.arow` grid 4열. `data-to` 어트리뷰트 추가. evt `from→to` 인라인 마크업. |
| `_section_phase_timeline(tasks, features)` | `tasks, features → str` | SVG 타임라인 → CSS positional `.tl-track .seg` 구조로 교체. X축 tick div 렌더. |
| `_timeline_svg(rows, ...)` | `... → str` | SVG 방식 유지 옵션 vs CSS 방식 전환. **CSS positional 방식 채택** (레퍼런스 HTML 기준). |
| `_section_team(panes)` | `panes → str` | `<details>` grouped 구조 → `.panel .team` 내 `.pane` card 구조. `.pane-head` 4열 grid. `pane-preview` `<pre>`. |
| `_render_pane_row(pane, preview_lines)` | `pane, preview_lines → str` | `.pane-row` → `.pane` + `.pane-head` + `.pane-preview` 구조로 완전 교체. |
| `_section_subagents(signals)` | `signals → str` | `<details>` grouped → `.panel .subs` chip 배열. `.sub` pill 마크업. |
| `_render_subagent_row(sig)` | `sig → str` | `.pane-row` → `.sub` pill 구조. `data-state` 어트리뷰트. |

### 마크업 스펙

**`.arow` 구조 (live-activity, 단계 3 이후):**
```html
<div class="arow" data-to="{to_state}">
  <span class="t">{HH:MM:SS}</span>
  <span class="tid">{item_id}</span>
  <span class="evt">
    {domain}
    <span class="arrow">→</span>
    <span class="from">{from_status}</span>
    <span class="arrow">→</span>
    <span class="to">{to_status}</span>
  </span>
  <span class="el">{elapsed}</span>
</div>
```
- `data-to`: `to_status` 값에서 raw 상태 추출 (예: `[xx]` → `"done"`, `.fail` 이벤트 → `"failed"`, etc.)
- `domain`: `item_id`에서 추출 (예: `TSK-01-06` → `"wbs"`) 또는 `phase_history` `event`에서

**phase-timeline CSS positional 구조:**
```html
<div class="panel timeline">
  <div class="timeline-head">
    <span>−{span_min}m</span>
    <span>now</span>
  </div>
  <div class="tl-row">
    <span class="lbl">{item_id}</span>
    <div class="tl-track">
      <div class="seg seg-{phase}" style="left:{left}%; width:{width}%"></div>
      ...
    </div>
  </div>
  ...
  <!-- axis row -->
  <div class="tl-row" style="margin-top: 8px;">
    <span class="lbl"></span>
    <div class="tl-axis" aria-hidden="true">
      <div class="tick major" style="left:0%"></div>
      ...
      <div class="tlabel" style="left:0%">−60m</div>
      ...
      <div class="tl-now" style="left:100%"></div>
    </div>
  </div>
</div>
```
- `seg-done`, `seg-running`, `seg-failed`, `seg-bypass`, `seg-pending`, `seg-idle`
- `left`/`width` %: 기존 `_x_of()` 로직을 % 기반으로 변환 (`x / W * 100`)

**`.pane` 구조 (team, 단계 3 이후):**
```html
<div class="pane" data-state="{live|idle}">
  <div class="pane-head">
    <div class="name">{window_name}</div>
    <div class="meta">{pane_id} · <span class="cmd">{command}</span> · pid {pid}</div>
    <button class="mini-btn" type="button">show output</button>
    <button class="mini-btn primary" type="button"
            data-pane-expand="{pane_id}" aria-label="Expand pane {pane_id}">
      expand <span class="kbd">↵</span>
    </button>
  </div>
  <pre class="pane-preview">{last_3_lines}</pre>
</div>
```
- `data-state="live"`: `pane_current_command != "zsh"` 또는 `is_active=True`로 판단
- 창이 20개 이상이면 `pane-preview` 생략 (기존 `_TOO_MANY_PANES_THRESHOLD` 유지)

**`.sub` 구조 (subagents, 단계 3 이후):**
```html
<span class="sub" data-state="{running|done|failed}">
  <span class="sw"></span>
  {task_id}
  <span class="n">×{count}</span>
</span>
```
- scope별 그룹화 제거 → 단순 flat chip 나열 (scope는 title에 표시)
- `data-state`: signal `kind` 매핑: `running`→`running`, `done`→`done`, `failed`→`failed`, `bypassed`→`done`

### 단계 3 roll-forward 검증

**눈으로 확인:**
- Live Activity: 우측 컬럼 상단 `.arow` 행, `data-to` 색상 반영 (done=green, fail=red)
- Phase Timeline: `.tl-track .seg` positional %, tl-axis tick div, `tl-now` 포인터
- Team: `.pane` card에 `pane-head` 4열 grid, `mini-btn primary` expand 버튼, `pane-preview` 마지막 3줄
- Subagents: `.subs` 내 `.sub` pill chip, `running` 상태 breathe 애니메이션

**영향받는 테스트:**
- `test_section_live_activity_*` → `.arow` + `data-to` 어트리뷰트 어서션
- `test_section_phase_timeline_*` → SVG 대신 `.tl-track .seg` div 존재 어서션, `tl-axis` 존재
- `test_render_pane_row_*`, `test_section_team_*` → `.pane-head` + `.pane-preview` 구조
- `test_render_subagent_row_*`, `test_section_subagents_*` → `.sub` + `data-state` 어트리뷰트

---

## 단계 4: phase-history 테이블 + drawer 스켈레톤 + JS 재작성

### 변경 대상 함수

| 함수 | 현재 시그니처 | 변경 내용 |
|------|-------------|---------|
| `_section_phase_history(tasks, features)` | `tasks, features → str` | `<ol class="phase-list">` → `.history <table>` 구조. 컬럼: `#/t/tid/ev/from→to/elapsed`. |
| `_drawer_skeleton()` | `() → str` | 기존 `.drawer-header`/`.drawer-body` → 레퍼런스의 `.drawer-head`/`.drawer-status`/`.drawer-pre` 구조. `aria-hidden="true"` 초기값 유지. |
| `_DASHBOARD_JS` (모듈 상수) | 기존 JS 문자열 | 아래 변경사항 반영하여 재작성. |

### 마크업 스펙

**phase-history table (단계 4 이후):**
```html
<div class="history" data-section="phases">
  <table>
    <thead>
      <tr>
        <th style="width:36px;">#</th>
        <th>Timestamp</th>
        <th>Task</th>
        <th>Event</th>
        <th>Transition</th>
        <th style="text-align:right;">Elapsed</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="idx">{01..10}</td>
        <td class="t">{at}</td>
        <td class="tid">{item_id}</td>
        <td class="ev">{event}</td>
        <td>
          <span class="from" style="color:var(--ink-4)">{from_status}</span>
          <span class="arr">→</span>
          <span class="to {done|running|failed|bypass}">{to_status}</span>
        </td>
        <td class="el" style="text-align:right;">{elapsed}</td>
      </tr>
    </tbody>
  </table>
</div>
```

**drawer 스켈레톤 (단계 4 이후):**
```html
<div class="drawer-backdrop" data-drawer-backdrop aria-hidden="true"></div>
<aside class="drawer"
       data-drawer
       role="dialog"
       aria-modal="true"
       aria-hidden="true"
       aria-labelledby="drawer-title">
  <header class="drawer-head">
    <div>
      <h3 id="drawer-title" data-drawer-title>Pane output</h3>
      <div class="meta" data-drawer-meta></div>
    </div>
    <button class="drawer-close" type="button" data-drawer-close aria-label="Close pane drawer">
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor"
           stroke-width="1.6" stroke-linecap="round">
        <path d="M2 2 L10 10 M10 2 L2 10"/>
      </svg>
    </button>
  </header>
  <div class="drawer-status">
    <span class="poll">polling · 2s</span>
    <span>· press <span class="kbd">Esc</span> to close</span>
  </div>
  <pre class="drawer-pre" data-drawer-pre></pre>
</aside>
```
- 초기 상태: `aria-hidden="true"` (CSS `transform: translateX(100%)` — open 시 `aria-hidden="false"` + `transform: translateX(0)`)

**`_DASHBOARD_JS` 주요 변경:**
- clock tick: `id="clock"` span을 ISO UTC 형식으로 1초 갱신 (기존 JS 유지)
- filter chips: `[data-section="kpi-chips"] .chip` → `[data-filter]` 이벤트 위임 → `body[data-filter]` 어트리뷰트 설정 (CSS `body[data-filter="running"] .trow:not([data-status="running"])` 규칙으로 숨김)
- auto-refresh toggle: `.refresh-toggle[aria-pressed]` 토글 + `R` 단축키 (기존 로직 유지)
- drawer open/close: `aria-hidden` 어트리뷰트 기반 (기존 `.open` 클래스 방식 → `aria-hidden="false"` 방식). `data-pane-expand` 이벤트 위임 유지.
- drawer Esc: `keydown Escape` 시 `closeDrawer()` (기존 로직 유지)
- focus-trap: `drawer.querySelectorAll('button, [href], [tabindex]:not([tabindex="-1"])')` 순환 (기존 로직 유지)
- `/api/pane/{id}` 폴링: 기존 `tickDrawer` 로직 유지. `data-drawer-pre` pre에 `textContent` 업데이트 (레퍼런스에서는 pre 내 span 컬러링이지만 서버 side에서는 plain text 유지 — 복잡도 절감).

### 단계 4 roll-forward 검증

**눈으로 확인:**
- phase history: `<table>` 렌더, `#` 인덱스 컬럼, `.to.done/.running/.failed/.bypass` 색상
- drawer: 우측에서 슬라이드 인, `aria-hidden="false"` 전환, backdrop blur, `.drawer-status` polling dot 표시
- clock: cmdbar의 `#clock` span이 매 초 ISO 포맷으로 갱신
- filter chips `aria-pressed` → `body[data-filter]` → `.trow` show/hide (CSS 주도)

**영향받는 테스트:**
- `test_section_phase_history_*` → `<table>` + `<thead>` + `<tbody>` 구조, `.idx`/`.tid`/`.ev`/`.arr`/`.to` 클래스
- `test_drawer_skeleton_*` → `.drawer-head`/`.drawer-status`/`.drawer-pre` 존재, `aria-hidden="true"` 초기값
- JS 동작 테스트 (있다면): `body[data-filter]` 어트리뷰트 기반 필터 검증

---

## 파일 계획

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | DASHBOARD_CSS 교체 + 모든 `_section_*`/`render_dashboard`/`_build_dashboard_body`/`_drawer_skeleton`/`_DASHBOARD_JS` 수정 | 수정 |
| `scripts/test_monitor_render.py` | 단계별 스냅샷·구조 어서션 갱신 | 수정 |

## 진입점 (Entry Points)

이 Feature는 `monitor-server.py`가 생성하는 HTML 대시보드의 CSS/마크업 이식 작업으로, 별도 라우터/메뉴 파일이 없는 단일 HTTP 서버 구조입니다.

- **사용자 진입 경로**: `python3 scripts/monitor-launcher.py` 실행 → `http://localhost:{PORT}` 브라우저 접속
- **URL / 라우트**: `http://localhost:4444/` (기본 포트, `--port` 옵션으로 변경 가능)
- **수정할 라우터 파일**: 해당 없음 (단일 파일 HTTP 핸들러 — `monitor-server.py`의 `do_GET` → `render_dashboard`)
- **수정할 메뉴·네비게이션 파일**: 해당 없음 (cmdbar 인라인 HTML, `_section_header`에서 렌더)
- **연결 확인 방법**: `python3 scripts/monitor-launcher.py` → `curl http://localhost:4444/` → HTTP 200 + `<!DOCTYPE html>` 응답 확인

## 주요 구조

1. **`DASHBOARD_CSS`** (모듈 상수): 레퍼런스 HTML의 전체 `<style>` 블록. `:root` 토큰 + reset + shell/cmdbar/grid/section-head/KPI/chip/wp/trow/arow/tl-track/pane/sub/history/drawer CSS.
2. **`_section_header(model)`**: cmdbar HTML 생성. `.brand`, `.meta` (project/docs/clock/interval), `.actions` (pulse + refresh-toggle).
3. **`_section_wp_cards(tasks, running_ids, failed_ids)`**: WP 카드 (SVG donut + `.wp-title` + `.trow` 행).
4. **`_section_live_activity(model)`**: `.arow` 행 (4열 grid: t/tid/evt[from→to]/el, `data-to` 어트리뷰트).
5. **`_section_phase_timeline(tasks, features)`**: `.tl-row`/`.tl-track .seg` CSS positional %.
6. **`_render_pane_row(pane, preview_lines)`**: `.pane` + `.pane-head` + `.pane-preview` 구조.
7. **`_render_subagent_row(sig)`**: `.sub` pill (`.sw` dot + task_id + `.n` count).
8. **`_section_phase_history(tasks, features)`**: `.history <table>` (# / t / tid / ev / from→to / elapsed).
9. **`_drawer_skeleton()`**: `.drawer-backdrop` + `aside.drawer` (.drawer-head + .drawer-status + .drawer-pre).
10. **`_DASHBOARD_JS`**: clock / filter chips (`body[data-filter]` CSS-driven) / auto-refresh / drawer open-close-Esc-focus-trap / `/api/pane/{id}` 폴링.

## 데이터 흐름

`render_dashboard(model: dict)` → 각 `_section_*` 함수가 `model`의 `wbs_tasks`/`features`/`tmux_panes`/`shared_signals`/`agent_pool_signals` 필드를 소비 → `_build_dashboard_body(s: dict)`가 `.shell > .grid` 레이아웃으로 조립 → `<!DOCTYPE html>` 완성 문서 반환 (서버가 HTTP 200으로 전송)

## 설계 결정

### phase-timeline: SVG → CSS positional 전환
- **결정**: `_timeline_svg()` SVG 방식을 CSS positional `.tl-track .seg` div 방식으로 교체
- **대안**: SVG 방식 유지 (`_timeline_svg`를 레퍼런스 스타일로 업데이트)
- **근거**: 레퍼런스 HTML이 CSS positional 방식을 사용하며, 테스트에서 DOM 구조 어서션이 SVG 내부 요소보다 div/class 기반이 훨씬 단순함. `_x_of()` 로직은 `% = (x / W) * 100`으로 재사용 가능.

### 구글 폰트 CDN 의존
- **결정**: `<head>`에 구글 폰트 `<link>` 추가
- **대안**: 폰트 없이 시스템 폰트 폴백만 사용
- **근거**: 레퍼런스 디자인의 핵심 비주얼 요소 (JetBrains Mono + Space Grotesk). 오프라인 환경에서는 CSS `--mono`/`--sans` 폴백 스택이 자동 적용되므로 서버 기동에는 영향 없음.

### filter chips: JS `display:none` → CSS `body[data-filter]` attribute
- **결정**: JS가 `body[data-filter="running"]` 어트리뷰트를 설정하고 CSS 규칙이 `.trow:not([data-status="running"])` 숨김 처리
- **대안**: JS가 개별 row에 `style.display` 적용 (기존 방식)
- **근거**: 레퍼런스 HTML 방식이며, DOM 교체(fetchAndPatch) 후에도 필터 상태가 CSS 레벨에서 자동 유지됨.

### `_section_sticky_header` 제거
- **결정**: `_section_sticky_header` 함수 삭제. cmdbar(`_section_header`)가 `position: sticky; top: 0`을 직접 보유.
- **대안**: 두 함수 병존 유지
- **근거**: 레퍼런스 HTML에 별도 sticky 헤더 없음. 코드 중복 제거.

## 선행 조건

- `dev-plugin Monitor.html`이 `/Users/jji/project/dev-plugin/dev-plugin Monitor.html`에 존재 (이미 확인됨)
- `scripts/monitor-server.py`의 데이터 레이어 (`scan_signals`, `scan_tasks`, `scan_features`, `list_tmux_panes`, `capture_pane`, 관련 dataclass) 변경 없음
- `scripts/test_monitor_render.py` 존재 및 현재 통과 상태 (단계별 갱신 전 기준)

## 리스크

- **HIGH**: 구글 폰트 CDN 필요 — 오프라인/방화벽 환경에서 폰트 미로드 시 레이아웃 shift 발생 가능. 폴백 스택으로 기능적 동작은 유지되나 비주얼 차이 발생.
- **HIGH**: `_section_sticky_header` 제거 시 기존 테스트에서 해당 함수를 직접 호출하는 케이스가 있으면 ImportError 수준 실패. 단계 1 시작 전 테스트 파일에서 참조 위치 확인 필요.
- **MEDIUM**: SVG donut → CSS stroke-dasharray 전환 시 `pathLength="100"` 없이 `r=15.9`의 실제 둘레(≈99.9)를 쓰면 오차 발생. `pathLength="100"`을 모든 circle에 일관 적용해야 함.
- **MEDIUM**: CSS positional timeline에서 `left + width > 100%`인 경우 오버플로우. `overflow: hidden`이 `.tl-track`에 적용되어 있으나, 계산 시 클램프 처리 필요.
- **MEDIUM**: `_render_pane_row` 시그니처 변경이 기존 테스트의 HTML 스냅샷과 충돌. 단계 3 전 스냅샷 갱신 필요.
- **LOW**: drawer `aria-hidden` 방식 전환 — 기존 `.open` 클래스 기반 JS가 잔존하면 충돌. `_DASHBOARD_JS` 교체와 동시에 완료되어야 함.
- **LOW**: `#clock` span의 시간대 표현 — 레퍼런스는 UTC 고정 포맷. 사용자 로컬 시간과 혼동 가능성 있으나 대시보드 특성상 UTC 표시가 적합.

## QA 체크리스트

### 단계 1
- [ ] `render_dashboard({})` 호출 시 `<!DOCTYPE html>` 문서 반환되고 서버 예외 없음
- [ ] 반환 HTML에 `class="cmdbar"` header 존재
- [ ] 반환 HTML에 `class="shell"` div 존재
- [ ] 반환 HTML에 `class="grid"` div 존재 (2열 그리드)
- [ ] `<head>`에 구글 폰트 `<link>` 태그 포함
- [ ] `DASHBOARD_CSS`에 `--bg: #0b0d10` 토큰 포함
- [ ] `DASHBOARD_CSS`에 `--run: #4aa3ff`, `--done: #4ed08a`, `--fail: #ff5d5d`, `--bypass: #d16be0`, `--pending: #f0c24a` 포함
- [ ] `_section_header` 반환 HTML에 `data-section="hdr"` 어트리뷰트 포함
- [ ] `_section_sticky_header` 함수 제거 후 `render_dashboard` 정상 동작

### 단계 2
- [ ] `_section_wp_cards(tasks, ...)` 반환 HTML에 `class="wp-donut"` + `<svg>` 존재
- [ ] WP donut SVG에 `pathLength="100"` circle이 5개 이상 (track + 4색) 존재
- [ ] `_render_task_row_v2(item, ...)` 반환 HTML에 `class="trow"` + `data-status` 어트리뷰트 존재
- [ ] `data-status="running"` 행에 `class="badge"` 텍스트가 "running" 포함
- [ ] `data-status="bypass"` 행에 `data-status="bypass"` 어트리뷰트 정확히 설정
- [ ] `_section_features` 반환 HTML이 `.trow` 구조 사용
- [ ] 기존 `_wp_donut_style` 함수 제거 후 테스트 케이스 갱신 및 통과
- [ ] 빈 tasks 입력 시 `_section_wp_cards`가 empty-state 반환 (예외 없음)

### 단계 3
- [ ] `_section_live_activity` 반환 HTML에 `class="arow"` div + `data-to` 어트리뷰트 존재
- [ ] `data-to="done"` / `data-to="failed"` / `data-to="running"` / `data-to="bypass"` 각각 정확히 설정
- [ ] `_section_phase_timeline` 반환 HTML에 `class="tl-track"` + `class="seg"` div 존재
- [ ] timeline에 `class="tl-axis"` + `class="tl-now"` div 존재
- [ ] `_render_pane_row` 반환 HTML에 `class="pane-head"` + `class="pane-preview"` 존재
- [ ] `data-pane-expand` 어트리뷰트가 pane_id 값으로 설정됨
- [ ] `_render_subagent_row` 반환 HTML에 `class="sub"` + `data-state` 어트리뷰트 존재
- [ ] 20개 이상 pane 입력 시 `pane-preview` 생략됨 (too-many 로직 유지)
- [ ] panes=None 입력 시 team 섹션이 info 메시지 반환 (예외 없음)

### 단계 4
- [ ] `_section_phase_history` 반환 HTML에 `<table>` + `<thead>` + `<tbody>` 존재
- [ ] tbody 각 행에 `class="idx"` / `class="t"` / `class="tid"` / `class="ev"` / `class="el"` td 존재
- [ ] `<span class="to done">` / `<span class="to running">` 등 전이 상태 클래스 정확히 설정
- [ ] `_drawer_skeleton()` 반환 HTML에 `class="drawer-backdrop"` + `aria-hidden="true"` 존재
- [ ] `_drawer_skeleton()` 반환 HTML에 `aside.drawer` + `class="drawer-head"` + `class="drawer-pre"` 존재
- [ ] drawer 초기 상태에서 `aria-hidden="true"` (JS 동작 전 CSS `translateX(100%)`)
- [ ] `_DASHBOARD_JS`에 `id="clock"` span 갱신 로직 포함
- [ ] `_DASHBOARD_JS`에 `body[data-filter]` 어트리뷰트 설정 로직 포함
- [ ] `_DASHBOARD_JS`에 `data-pane-expand` 클릭 → drawer open (`aria-hidden="false"`) 로직 포함
- [ ] `_DASHBOARD_JS`에 Esc 키 → drawer close 로직 포함
- [ ] `_DASHBOARD_JS`에 focus-trap (Tab/Shift+Tab 순환) 로직 포함
- [ ] `render_dashboard({})` 전체 문서에 `<script id="dashboard-js">` 포함
- [ ] 빈 phase_history 입력 시 `_section_phase_history`가 empty-state 반환 (예외 없음)

### 통합 / 엣지 케이스
- [ ] `wbs_tasks=[]`, `features=[]`, `tmux_panes=None`, `shared_signals=[]` 전체 빈 model에서 `render_dashboard` 정상 동작
- [ ] XSS: `item.title`에 `<script>alert(1)</script>` 입력 시 `html.escape` 적용으로 안전 출력
- [ ] 매우 긴 task_id / title (200자 이상) 입력 시 렌더 예외 없음
- [ ] `elapsed_seconds=None` / `elapsed_seconds=0` / 음수 입력 시 `_format_elapsed` → `"-"` / `"00:00:00"` 반환
- [ ] bypass + failed 동시 설정 시 `data-status="bypass"` 우선 (priority: bypass > failed > running > done > pending)
