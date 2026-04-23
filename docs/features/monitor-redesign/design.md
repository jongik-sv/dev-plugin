# monitor-redesign: 설계

## 요구사항 확인

- `scripts/monitor-server.py`의 `render_dashboard` 함수가 생성하는 HTML/CSS/JS 대시보드를 `/Users/jji/project/dev-plugin/dev-plugin Monitor.html` 디자인 샘플과 동일하게 맞춘다.
- 핵심 3대 결함: ① 오른쪽 빈 공간(레이아웃/그리드 구조 오류) ② Task States/Work Packages/Live Activity 카드 디자인 열화 ③ 한국어/영어 토글이 화면에 렌더링되지 않는 버그.
- 서브프로젝트 선택 UI(`subproject-tabs`)는 디자인·동작·위치 변경 금지. 기존 구조 계약(섹션 heading, data attribute, KPI 카운트 로직) 유지 필수.

## 타겟 앱

- **경로**: N/A (단일 앱)
- **근거**: Python HTTP 서버 단일 파일 프로젝트; 별도 앱 분리 없음.

## 구현 방향

1. **레이아웃 최우선 수정** — `_build_dashboard_body`의 이중 래퍼(`.grid` > `.page`)를 제거하고 샘플과 동일하게 `.shell` > `cmdbar` > `kpi` > `.grid(.col-left, .col-right)` 구조로 단순화한다.
2. **CSS 전면 교체** — `DASHBOARD_CSS` 문자열을 샘플 HTML의 CSS(디자인 토큰/컴포넌트 스타일)로 교체하되, 기존 테스트가 참조하는 `.trow .badge`, `.kpi-strip`, `data-section` 관련 선택자를 유지한다.
3. **Task States(KPI) 카드** — `_section_kpi`의 HTML 출력 구조를 샘플과 일치시킨다 (`.kpi` 단일 클래스, `.num` 38px, `.spark` SVG 포함).
4. **WP 카드** — `_section_wp_cards`·`_render_task_row_v2`의 HTML 구조를 샘플 `.wp-head`(donut + wp-title + wp-meta), `.trow`(7-col grid) 구조로 교체한다.
5. **Live Activity** — `_section_live_activity`에서 출력하는 행 클래스를 샘플의 `.arow` 구조(`.t / .tid / .evt / .el`)로 교체한다.
6. **언어 토글 활성 표시 복원** — `_section_header`의 `lang_toggle_html`에 현재 `lang` 값에 따른 `aria-current="page"` / `.active` 클래스를 추가하고, CSS에 해당 active 스타일을 추가한다.
7. **_DASHBOARD_CSS_COMPAT 레거시 제거** — `_build_dashboard_body`의 `.page` / `.page-col-left` / `.page-col-right` 래퍼를 `.grid` / `.col`로 변경하고, 이중 래퍼 CSS도 정리한다.

---

## 레이아웃 비교 (최우선)

### 현재 구조 (버그)

```
DASHBOARD_CSS:
  .shell { max-width: 1440px; margin: 0 auto; padding: 0 20px; }  ← 동일
  .grid  { display: grid; grid-template-columns: minmax(0,3fr) minmax(0,2fr); gap: 28px; padding-top: 8px; }

_build_dashboard_body 조립 순서:
  <div class="shell">
    <header class="cmdbar">          ← OK
    <nav subproject-tabs>            ← OK
    <div data-section="sticky-header">  ← 불필요한 구형 헤더 중복
    <section kpi>                    ← OK
    <div class="grid">               ← .grid 열림
      <div class="page">             ← ⚠ .page 중첩 (grid=3fr/2fr → page=3fr/2fr 이중)
        <div class="page-col-left">
          ...wp-cards, features
        </div>
        <div class="page-col-right">
          ...live-activity, timeline, team, subagents
        </div>
      </div>
    </div>                           ← .grid 닫힘
    <div phase-history>
    <section dep-graph>
  </div>

_DASHBOARD_CSS_COMPAT:
  .page { display: grid; grid-template-columns: 3fr 2fr; gap: 1.25rem; }
  .page-col-left, .page-col-right { display:flex; flex-direction:column; gap:1rem; }
```

**문제**: `.grid`(3fr/2fr) 안에 `.page`(3fr/2fr)가 중첩된다. `.page`가 `.grid`의 단일 셀 하나를 차지하므로 2/5 폭만 사용된다. 오른쪽 40%가 빈 공간이 된다.

### 샘플 구조 (정답)

```html
<!-- dev-plugin Monitor.html 의 실제 HTML (line 925~) -->
<div class="shell">
  <header class="cmdbar">…</header>
  <section data-section="kpi">…</section>
  <div class="grid">            <!-- grid-template-columns: minmax(0,3fr) minmax(0,2fr) -->
    <div class="col">           <!-- left col -->
      <section wp-cards>…</section>
      <section features>…</section>
    </div>
    <div class="col">           <!-- right col -->
      <section live-activity>…</section>
      <section phase-timeline>…</section>
      <section team>…</section>
      <section subagents>…</section>
    </div>
  </div>
  <!-- phase-history, dep-graph (full-width) -->
</div>
```

### 수정할 CSS / Python 코드

| 항목 | 현재 값 | 바꿀 값 (샘플 기준) |
|------|---------|-------------------|
| `.shell` max-width | 1440px | 1440px (동일, 유지) |
| `.shell` padding | `0 20px 0` | `0 20px 0` (동일, 유지) |
| `.grid` grid-template-columns | `minmax(0,3fr) minmax(0,2fr)` | `minmax(0,3fr) minmax(0,2fr)` (동일) |
| `.grid` gap | 28px | 28px (동일) |
| `.page` (CSS) | `display:grid; grid-template-columns:3fr 2fr` | **삭제** (래퍼 자체를 제거) |
| `.page-col-left/.page-col-right` (CSS) | `display:flex; flex-direction:column; gap:1rem` | **삭제** |
| `_build_dashboard_body` 래퍼 | `<div class="grid"><div class="page"><div class="page-col-left">` | `<div class="grid"><div class="col">` |
| `.col` CSS | 없거나 부재 | `min-width:0; display:flex; flex-direction:column; gap:0` |
| `sticky-header` (구형 헤더) | 렌더링됨 | **제거** (cmdbar가 대체, 중복) |

**핵심 변경 코드 (Python)**:

```python
# _build_dashboard_body: .page/.page-col-left/.page-col-right → .col
return "".join([
    '<div class="shell">\n',
    s["header"], "\n",          # cmdbar
    tabs_html,                   # subproject-tabs (불변)
    s["kpi"], "\n",
    '  <div class="grid">\n',
    '    <div class="col">\n',   # ← .page-col-left 대체
    wbs_landing_pad,
    s["wp-cards"], "\n",
    s["features"], "\n",
    '    </div>\n',
    '    <div class="col">\n',   # ← .page-col-right 대체
    s["live-activity"], "\n",
    s["phase-timeline"], "\n",
    s["team"], "\n",
    s["subagents"], "\n",
    '    </div>\n',
    '  </div>\n',
    s["phase-history"], "\n",
    s["dep-graph"], "\n",
    '</div>\n',
])
```

> `sticky-header` 블록은 `_build_dashboard_body`에서 제거한다. cmdbar(`header_html`)가 모든 역할을 이미 담당하고 있으며, sticky-header는 구형 v1 잔재다. 단 `data-section="sticky-header"` div를 테스트가 직접 체크하지 않으므로 안전하게 제거 가능 (테스트 확인 완료).

---

## 디자인 토큰 (샘플 기준)

샘플 HTML의 `:root` CSS 변수 전체 목록:

**surfaces**:
| 변수 | 값 | 용도 |
|------|-----|------|
| `--bg` | `#0b0d10` | 페이지 배경 |
| `--bg-1` | `#0f1216` | 카드 배경 |
| `--bg-2` | `#141820` | 중간 레이어 |
| `--bg-3` | `#1a1f28` | 입력/버튼 배경 |
| `--line` | `#1f2530` | 기본 테두리 |
| `--line-2` | `#2a3140` | 강조 테두리 |
| `--line-hi` | `#3a4456` | 하이라이트 선 |

**text**:
| 변수 | 값 |
|------|-----|
| `--ink` | `#e8ecf1` |
| `--ink-2` | `#aeb5c1` |
| `--ink-3` | `#6b7480` |
| `--ink-4` | `#464e5a` |

**accents**:
| 변수 | 값 |
|------|-----|
| `--accent` | `#c89b6a` (warm amber) |
| `--accent-hi` | `#e6b884` |
| `--accent-dim` | `#7a5e3f` |

**phase palette**:
| 변수 | 값 |
|------|-----|
| `--run` | `#4aa3ff` |
| `--run-glow` | `rgba(74,163,255,.18)` |
| `--done` | `#4ed08a` |
| `--done-glow` | `rgba(78,208,138,.16)` |
| `--fail` | `#ff5d5d` |
| `--fail-glow` | `rgba(255,93,93,.16)` |
| `--bypass` | `#d16be0` |
| `--bypass-glow` | `rgba(209,107,224,.16)` |
| `--pending` | `#f0c24a` |
| `--pending-glow` | `rgba(240,194,74,.16)` |

**typography**:
| 변수 | 값 |
|------|-----|
| `--mono` | `"JetBrains Mono", ui-monospace, ...` |
| `--sans` | `"Space Grotesk", ui-sans-serif, ...` |
| `--display` | `"Space Grotesk", ui-sans-serif, ...` |
| `--radius` | `4px` |
| `--radius-lg` | `6px` |

> 현재 `DASHBOARD_CSS`의 토큰은 위 값과 동일하다(이미 샘플 토큰을 일부 반영). 차이점은 `--font-body: 14px`, `--font-mono: 14px`, `--font-h2: 17px`가 현재 코드에 추가 선언되어 있다 — 이를 유지하면 된다. 샘플은 같은 값을 직접 px로 사용한다.

---

## 현재 vs 샘플 컴포넌트 비교

### Task States 카드 (KPI Strip)

| 항목 | 현재 | 샘플 | 바꿀 것 |
|------|------|------|---------|
| 컨테이너 클래스 | `<div class="kpi-row kpi-strip">` | `<div class="kpi-strip">` | `kpi-row` 추가 클래스 제거 |
| 개별 카드 클래스 | `<div class="kpi-card {kind} kpi kpi--{suffix}">` | `<div class="kpi kpi--run">` | `kpi-card {kind}` 접두어 제거 |
| label span | `<span class="kpi-label label">` | `<div class="label">` | span → div, 이중 클래스 → `class="label"` |
| num span | `<span class="kpi-num num">` | `<div class="num">` | span → div, `class="num"` |
| delta | 없음 | `<div class="delta">+N / 10m</div>` | delta div 추가 (정적 텍스트 OK) |
| sparkline | `<svg class="kpi-sparkline">` | `<svg class="spark">` | 클래스명 `spark`로 변경 |
| section 클래스 | `<section class="kpi-section" data-section="kpi">` | `<section data-section="kpi">` | `kpi-section` 클래스 제거 |
| chip container | `<div class="chip-group chips">` | `<div class="chips">` | `chip-group` 제거 |

**현재 `_section_kpi` 출력 문제점**: `kpi-row`/`kpi-card`/`kpi-label`/`kpi-num`/`kpi-sparkline`/`kpi-section`/`chip-group` 등 구형 CSS 클래스가 혼재하여 샘플 CSS의 `.kpi`/`.kpi .label`/`.kpi .num`/`.spark` 셀렉터와 충돌 또는 미매칭.

### Work Packages 카드

| 항목 | 현재 | 샘플 | 바꿀 것 |
|------|------|------|---------|
| 카드 구조 | `<div class="wp-card">` 안에 `<details class="wp wp-tasks">` | `<details class="wp">` + 내부 `<details class="wp-tasks">` 분리 | wp-card div 제거, details.wp + details.wp-tasks 이중 구조로 변경 |
| summary 내부 | `wp-head`를 `<summary>` 안에 직접 | `<summary style="list-style:none; display:block;"><div class="wp-head">…` | 동일 구조로 조정 |
| donut SVG | `viewBox="0 0 40 40"` r=16 | `viewBox="0 0 36 36"` r=15.9 cx=18 cy=18 | viewBox/r/cx/cy 수정 |
| pct 레이블 | `{pct}<small>%</small>` | `{pct}<small>PCT</small>` | `%` → `PCT` |
| wp-meta | `<span class="big">{total} tasks</span>` 만 있음 | `<span class="big">{n} tasks</span><br>started/queued<br>{time}` 형태 | 시작 시간 표시 추가 (`started_at` 활용) |
| task row | `<div class="task-row {state} …">` | `<div class="trow" data-status="{state}">` | `task-row` → `trow`, data-status 속성 |
| task row 자식 | `class="badge"` div (플레인 텍스트), `run-line` div 추가 | `.statusbar` + `.tid` + `.badge` + `.ttitle` + `.elapsed` + `.retry` + `.flags` | run-line 제거, trow hidden div 제거, ttitle에 `.path` span 추가 고려 |
| wp-counts 색상 | `.c[data-k="run"] b { color: var(--run); }` CSS 없음 | `.c[data-k="run"] b { color: var(--run); }` | wp-counts 색상 CSS 추가 |
| progress bar | `<div class="wp-progress"><div class="wp-progress-bar" …>` 레거시 | `.bar > .b-done, .b-run, .b-fail, .b-byp, .b-pnd` | legacy progress 제거, bar 구조만 유지 |

### Live Activity

| 항목 | 현재 | 샘플 | 바꿀 것 |
|------|------|------|---------|
| 행 클래스 | `<div class="activity-row">` | `<div class="arow">` | `activity-row` → `arow` |
| 행 자식 span 클래스 | `.a-time`, `.a-id`, `.a-event`, `.a-detail`, `.a-elapsed` | `.t`, `.tid`, `.evt`, `.el` | 클래스명 변경 |
| evt 내부 구조 | 없음(단일 span) | `<span class="evt"><span class="arrow">→</span><span class="from">…</span><span class="arrow">→</span><span class="to">…</span></span>` | evt 내부 분리 구조 추가 |
| hidden arow | `<div class="arow" … hidden>` (테스트용 유지용) | 없음 | 제거 가능 (테스트 확인 필요) |
| panel wrap | `<div class="panel"><div class="activity" …>` | 동일 | 유지 |

**주의**: 기존 테스트(`test_monitor_render.py`)에서 `data-section="activity"`, `class="activity"` 등을 확인한다. `arow` 클래스 확인 테스트가 있는지 점검 필요. 현재 코드는 `<div class="arow" … hidden>` hidden 더미를 삽입하는데, 이를 삭제하면 테스트가 깨질 수 있어 확인 후 결정한다.

---

## 언어 토글 복원 방안

### 현황 분석

`_section_header` 함수(line 1915~1993)에 `lang_toggle_html`이 이미 구현되어 있다:

```python
lang_toggle_html = (
    f'<nav class="lang-toggle">'
    f'<a href="{href_ko}">한</a>'
    f' <a href="{href_en}">EN</a>'
    f'</nav>\n'
)
```

CSS에도 `.cmdbar .lang-toggle`과 `.cmdbar .lang-toggle a` 스타일이 있다. 그러나 **현재 렌더링된 화면에서 토글이 안 보이는 이유**는 두 가지다:

1. **active 링크 구분이 없음** — 현재 `lang`에 해당하는 링크에 `aria-current` / `.active` 클래스가 없어 사용자가 현재 언어를 구분할 수 없다.
2. **`_DASHBOARD_CSS_COMPAT`이 `DASHBOARD_CSS`와 합산된 후 minify 처리** — 이 과정에서 `.cmdbar .lang-toggle a` 스타일이 올바르게 적용되지 않는 상황이 발생할 가능성. 브라우저 검사 필요.

### 복원 설계

**i18n 데이터 구조** (변경 없음): 기존 `_I18N` dict (`_normalize_lang`, `_t` 함수) 이미 구현되어 있음.

**토글 UI 위치**: cmdbar 우측 actions 블록 (`<div class="actions">`) 안, `<span class="pulse">` 앞.

**수정 코드**:

```python
# _section_header에서 lang_toggle_html 생성 부분 수정
ko_current = ' aria-current="page" class="active"' if lang == "ko" else ""
en_current = ' aria-current="page" class="active"' if lang == "en" else ""
lang_toggle_html = (
    f'<nav class="lang-toggle">'
    f'<a href="{href_ko}"{ko_current}>한</a>'
    f' <a href="{href_en}"{en_current}>EN</a>'
    f'</nav>\n'
)
```

**CSS 추가 (DASHBOARD_CSS 내)**:
```css
.cmdbar .lang-toggle a.active,
.cmdbar .lang-toggle a[aria-current="page"] {
  color: var(--accent-hi);
  border-color: var(--accent-dim);
  background: rgba(200,155,106,0.08);
}
```

---

## 파일 계획

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | DASHBOARD_CSS, `_build_dashboard_body`, `_section_kpi`, `_section_wp_cards`, `_render_task_row_v2`, `_section_live_activity`, `_section_header` 수정 | 수정 |
| `scripts/test_monitor_render.py` | 기존 구조 계약 유지 확인 + 신규 테스트 추가 | 수정 |
| `scripts/test_monitor_kpi.py` | KPI 클래스명 변경에 따른 테스트 수정 + 신규 | 수정 |

## 진입점 (Entry Points)

- **사용자 진입 경로**: `python scripts/monitor-launcher.py` 실행 → 브라우저에서 `http://localhost:7322/?subproject=monitor-v3` 접속
- **URL / 라우트**: `http://localhost:7322/` 또는 `http://localhost:7322/?subproject={SP}`
- **수정할 라우터 파일**: `scripts/monitor-server.py` — `render_dashboard` 함수 및 그 하위 render 함수들 (Python inline HTML/CSS/JS 문자열)
- **수정할 메뉴·네비게이션 파일**: N/A (SPA 단일 페이지, 라우터 없음)
- **연결 확인 방법**: 브라우저에서 cmdbar 우측 `한/EN` 버튼 클릭 → URL `?lang=ko` / `?lang=en`으로 변경되고 현재 언어 링크에 amber highlight 표시

## 주요 구조

| 함수/컴포넌트 | 책임 |
|-------------|------|
| `DASHBOARD_CSS` (문자열 상수) | 전체 디자인 토큰 + 컴포넌트 CSS. 샘플 CSS로 교체. 기존 구조 계약 선택자 유지 |
| `_build_dashboard_body(s)` | `.shell` 최상위 래퍼 조립. `.grid > .col` 2열 구조. `sticky-header` 제거, `.page` 이중 래퍼 제거 |
| `_section_kpi(model)` | KPI strip 렌더. 클래스명 정리 (`kpi-card`→없음, `kpi-label`→`label`, `kpi-num`→`num`, `kpi-sparkline`→`spark`) |
| `_section_wp_cards(tasks, …)` | WP 카드 그룹. `<details class="wp">` + `<details class="wp-tasks">` 이중 구조. `wp-card` div 제거 |
| `_render_task_row_v2(item, …)` | `<div class="trow" data-status="…">` 행. `task-row` → `trow`, `run-line` hidden 제거 |
| `_section_live_activity(model)` | `activity-row` → `arow`, 자식 span 클래스 `.t/.tid/.evt/.el`로 변경 |
| `_section_header(model, lang, …)` | cmdbar + lang-toggle active 표시 추가 |

## 데이터 흐름

`render_dashboard(model, lang, subproject)` → 각 `_section_*` 함수 호출 → HTML 문자열 반환 → `_build_dashboard_body`에서 `.shell > .grid > .col` 구조로 조립 → `<!DOCTYPE html>` 완성 문서 반환.

## 설계 결정

- **결정**: `DASHBOARD_CSS`를 샘플 HTML의 CSS로 전면 교체하되, `_DASHBOARD_CSS_COMPAT` 레거시 블록은 필요한 선택자만 남기고 삭제.
- **대안**: 기존 CSS에 샘플 클래스만 덧씌우기(overriding).
- **근거**: 이중 CSS 충돌(`.kpi-card` vs `.kpi`, `.activity-row` vs `.arow`)이 근본 원인이므로 전면 교체가 더 안전하다. 테스트가 의존하는 선택자만 유지하면 계약 위반 없음.

- **결정**: `_render_task_row_v2` 출력의 `<div class="trow" data-status="…" hidden>` 더미 제거.
- **대안**: 유지.
- **근거**: 테스트 파일 검색 결과 이 hidden div를 직접 assertIn하는 테스트 없음. `data-section` / `data-status` 계약은 실제 표시 div에서 검증된다.

- **결정**: `sticky-header`(구형 v1 헤더) 블록을 `_build_dashboard_body`에서 제거.
- **대안**: 유지.
- **근거**: cmdbar가 완전히 대체. `data-section="sticky-header"` 를 assertIn하는 테스트가 없어 안전하다 (test_monitor_render.py의 `test_six_sections_render`가 확인하는 항목 목록에 sticky-header 없음).

## 선행 조건

없음. Python stdlib 전용, 외부 의존성 없음.

## 리스크

- **HIGH**: `_section_kpi` 클래스명 변경 시 `test_monitor_kpi.py`의 `_section_kpi` 출력 검사 테스트가 깨질 수 있음. 변경 전 테스트 코드를 꼼꼼히 확인하고, 클래스명 변경에 맞춰 테스트도 함께 수정해야 한다.
- **HIGH**: `_render_task_row_v2`의 `task-row` → `trow` 클래스 변경 시 `data-section` 관련 JS 셀렉터(`document.querySelectorAll('.task-row')` 등)가 있으면 깨짐. `_DASHBOARD_JS` 스크립트에서 `.task-row` 참조 여부 확인 필수.
- **MEDIUM**: `_DASHBOARD_CSS_COMPAT` 제거 시 `.wp-donut` CSS 변수(`--pct-done-end`, `--pct-run-end`) 스타일이 같이 제거되면 안 됨 — 이 변수는 `_wp_donut_style`이 생성하며 CSS에도 별도 참조 없으므로 SVG 방식이 이미 이를 대체함. 단 제거 후 시각 확인 필요.
- **MEDIUM**: `activity-row` → `arow` CSS 클래스명 변경 시 `_DASHBOARD_JS` 안의 JS 셀렉터 확인 필요.
- **LOW**: `pane-preview::before { content: "▸ last 3 lines" }` — 현재 코드는 이 CSS가 있고 샘플도 동일하므로 문제 없음.

## QA 체크리스트

**레이아웃/그리드**:
- [ ] 브라우저(1440px 폭 이상)에서 오른쪽에 빈 공간이 없고 좌/우 컬럼이 각각 60%/40%를 꽉 채운다.
- [ ] `<div class="grid">` 직하에 `<div class="col">` 2개가 존재하고, `.page` / `.page-col-left` / `.page-col-right` div가 없다.
- [ ] 1280px 이하에서 반응형으로 1열 레이아웃으로 전환된다(`@media (max-width: 1280px) { .grid { grid-template-columns: 1fr; } }`).

**KPI Strip (Task States)**:
- [ ] `.kpi-strip`이 `<section data-section="kpi">` 안에 존재한다 (기존 계약 유지).
- [ ] 각 KPI 카드가 `<div class="kpi kpi--run">` 형식(추가 클래스 없음)으로 렌더된다.
- [ ] `.kpi .num`이 38px 폰트로 렌더된다 (CSS `.kpi .num { font-size: 38px }`).
- [ ] `.kpi .spark` SVG가 각 카드에 포함된다.
- [ ] Filter chips가 `<div class="chips" data-section="kpi-chips">` 안에 있다.

**Work Packages**:
- [ ] WP 카드가 `<div class="wp-card">` 없이 `<details class="wp">` 직접 렌더된다.
- [ ] `.wp-head`의 donut SVG가 `viewBox="0 0 36 36"` 기준으로 렌더된다.
- [ ] task row가 `<div class="trow" data-status="done|running|failed|bypass|pending">` 형식이다.
- [ ] `<div class="run-line">` 및 `data-status hidden` 더미 div가 없다.

**Live Activity**:
- [ ] activity 행이 `<div class="arow" data-to="…">` 형식으로 렌더된다.
- [ ] `.arow .t`, `.arow .tid`, `.arow .evt`, `.arow .el` 자식 클래스가 존재한다.
- [ ] `.evt` 내부에 `<span class="arrow">→</span>`, `<span class="from">`, `<span class="to">` 구조가 있다.
- [ ] `data-section="activity"` 섹션이 존재한다 (기존 계약).

**언어 토글**:
- [ ] cmdbar에 `<nav class="lang-toggle">` 가 존재한다.
- [ ] `?lang=ko` 접속 시 `한` 링크에 `aria-current="page"` 또는 `.active`가 있다.
- [ ] `?lang=en` 접속 시 `EN` 링크에 `aria-current="page"` 또는 `.active`가 있다.
- [ ] 언어 토글 클릭 시 subproject 쿼리 파라미터가 URL에 보존된다.

**기존 구조 계약 유지**:
- [ ] `render_dashboard` 반환값이 `<!DOCTYPE html>` 로 시작한다.
- [ ] `data-section="hdr"`, `<section id="wp-cards"`, `<section id="features"`, `<section id="team"`, `<section id="subagents"`, `data-section="phases"` 모두 존재한다 (SectionPresenceTests).
- [ ] `<meta http-equiv="refresh">` 가 없다 (MetaRefreshTests).
- [ ] error task에 `<div class="badge" title=...>error</div>` 렌더 (ErrorBadgeTests).
- [ ] `.trow .badge` CSS 선택자가 DASHBOARD_CSS에 존재한다.
- [ ] XSS 문자열이 html.escape 처리된다.

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate)**:
- [ ] (클릭 경로) `python scripts/monitor-launcher.py` 실행 후 브라우저에서 `http://localhost:7322/` 접속 → 대시보드 렌더링 확인
- [ ] (화면 렌더링) cmdbar, KPI strip, WP 카드, Live Activity, 언어 토글이 브라우저에서 실제 표시되고 기본 상호작용(auto-refresh 토글, 필터 chip 클릭, KPI 클릭)이 동작한다.
