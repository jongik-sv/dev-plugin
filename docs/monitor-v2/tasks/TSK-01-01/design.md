# TSK-01-01: DASHBOARD_CSS 확장 - 설계

## 요구사항 확인

- v1의 `DASHBOARD_CSS` 문자열(63줄)을 ~343줄로 확장하되 400줄 상한을 준수한다.
- Sticky 헤더·KPI 카드 팔레트(5가지 상태 좌측 4px 컬러 바)·필터 칩(`aria-pressed`)·2단 grid 레이아웃·WP 도넛(conic-gradient)·progress bar·task-row 컬러 바·Running 애니메이션·Live activity fade-in·Phase timeline SVG 클래스·pane preview·사이드 드로어를 추가한다.
- 반응형 브레이크포인트(1280px/768px) 및 `prefers-reduced-motion` 지원, 외부 CDN·폰트 금지, v1 CSS 변수명 유지.

## 타겟 앱

- **경로**: N/A (단일 앱 — 모든 코드는 `scripts/monitor-server.py` 한 파일에 인라인)
- **근거**: 이 프로젝트는 단일 Python 파일(`monitor-server.py`)에 HTML/CSS/JS가 인라인으로 내장되는 구조이다.

## 구현 방향

- `monitor-server.py`의 `DASHBOARD_CSS` 문자열(라인 669–732)을 in-place 교체한다. Python 문법 오류 없이 CSS만 변경하면 되므로 `py_compile` 테스트를 통과한다.
- 추가할 CSS 블록은 TRD §4.2.1에 명시된 패턴을 그대로 따른다: layout grid → sticky header → KPI cards → filter chips → WP donut → task-row bars → live activity → timeline SVG classes → pane preview → drawer → media queries → reduced-motion.
- `@supports not (background: conic-gradient(...))` fallback을 포함해 구형 Safari에서 도넛이 단색 배경으로 gracefully degrade되도록 한다.
- v1 CSS 변수(`--bg`, `--fg`, `--muted`, `--border`, `--panel`, `--accent`, `--warn`, `--blue`, `--purple`, `--green`, `--gray`, `--orange`, `--red`, `--yellow`, `--light-gray`)는 이름·값 모두 그대로 유지한다.

## 파일 계획

**경로 기준:** 모든 파일 경로는 프로젝트 루트 기준.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `DASHBOARD_CSS` 문자열 교체 (라인 669–732 → 확장 버전 ~343줄) | 수정 |

> 이 Task는 CSS 문자열 교체만 다룬다. 신규 `_section_*` 렌더 함수(TSK-01-02/03/04/05)와 클라이언트 JS(TSK-01-06)는 별도 Task에서 구현되며, CSS 클래스는 미리 정의해두어 후행 Task가 바로 사용할 수 있게 한다.

## 진입점 (Entry Points)

**이 Task의 CSS는 신규 페이지가 아닌 공통 컴포넌트 레이어(인라인 스타일시트)다 — 적용될 상위 페이지는 `/` (대시보드)이다.**

- **사용자 진입 경로**: 브라우저에서 `/dev-monitor`로 서버를 기동한 뒤 `http://localhost:{PORT}/` 접속 (대시보드 루트)
- **URL / 라우트**: `/` — `render_dashboard(model)` → `<style>{DASHBOARD_CSS}</style>` 삽입
- **수정할 라우터 파일**: `scripts/monitor-server.py` — `DASHBOARD_CSS` 상수를 교체하면 `render_dashboard()`가 자동으로 새 CSS를 `<style>` 태그에 삽입한다 (라인 1120: `f'  <style>{DASHBOARD_CSS}</style>\n'`). 별도 라우터 배선 수정 불필요.
- **수정할 메뉴·네비게이션 파일**: `scripts/monitor-server.py` — 대시보드는 단일 페이지이므로 별도 메뉴/사이드바 파일이 없다. CSS 클래스 추가로 상단 필터 칩(`.chip`)이 v2 내비게이션 요소로 동작한다.
- **연결 확인 방법**: `python3 scripts/monitor-launcher.py --port 7321 --docs docs` → 브라우저에서 `http://localhost:7321/` 접속 → sticky 헤더·KPI 카드·필터 칩이 렌더링됨 확인.

## 주요 구조

1. **`:root` 변수 블록** — v1의 15개 CSS 변수 유지, `--pct-done-end`/`--pct-run-end` CSS 커스텀 프로퍼티 추가 (도넛 conic-gradient에서 JS가 인라인 style로 주입)
2. **`.page` grid** — `display: grid; grid-template-columns: 3fr 2fr` (좌측 WP+Features / 우측 Live+Timeline+Team+Subagents)
3. **`.sticky-hdr` + `.kpi-row` + `.kpi-card.{running|failed|bypass|done|pending}`** — 상단 고정 헤더 + 5장 KPI 카드 (좌측 4px 컬러 바)
4. **`.chip[aria-pressed]`** — 필터 칩 상태 스타일 (선택 시 `--accent` 배경)
5. **`.wp-donut` + `@supports not (background: conic-gradient(...))` fallback** — CSS conic-gradient 도넛 + 구형 Safari 단색 fallback
6. **`.task-row::before` + `.task-row.{done|running|failed|bypass|pending}::before`** — task-row 좌측 4px 컬러 바 (position:relative 컨텍스트)
7. **`.task-row.running .run-line` + `@keyframes slide`** — Running row 애니메이션 오버레이 바
8. **`.activity-row` + `@keyframes fade-in`** — Live activity 이벤트 행 페이드인
9. **`.timeline-svg .tl-{dd|im|ts|xx|fail}`** — Phase timeline SVG rect 색상 클래스
10. **`.pane-preview`** — pane 인라인 미리보기 (monospace, max-height 4.5em)
11. **`.drawer-backdrop` + `.drawer` + `.drawer.open`** — 사이드 드로어 오버레이 (slide-in 640px, 모바일 100vw)
12. **`@media (max-width: 1279px)` / `(max-width: 767px)`** — 반응형 1단 전환, 모바일 KPI 가로 스크롤
13. **`@media (prefers-reduced-motion: reduce)`** — 모든 애니메이션 비활성화

## 데이터 흐름

`DASHBOARD_CSS` 상수 교체(Python 문자열) → `render_dashboard(model)` 함수가 HTML `<style>` 태그에 삽입 → 브라우저가 CSS 클래스를 적용하여 v2 UI를 표시. CSS 자체는 순수 선언이므로 런타임 데이터 흐름과 무관.

## 설계 결정 (대안이 있는 경우만)

- **결정**: `@supports not (background: conic-gradient(...))` fallback을 `wp-donut`에 단색 배경(`var(--panel)`)으로 제공한다.
- **대안**: SVG `<circle>` stroke-dasharray로 도넛 구현 (JavaScript 의존 없음, 구형 브라우저 호환성 완전).
- **근거**: PRD §2.2 "차트 라이브러리 금지"와 "외부 CDN 금지" 조건을 유지하면서도 승인 기준(`@supports` fallback)을 가장 단순하게 만족한다. SVG 방식은 Python 렌더 함수 변경 범위가 TSK-01-01을 넘어선다.

- **결정**: `task-row::before`(좌측 컬러 바)는 `position: absolute`로 구현하고 부모 `.task-row`에 `position: relative`를 추가한다.
- **대안**: 별도 `<div class="color-bar">` 요소를 HTML에 삽입 (마크업 변경 필요).
- **근거**: HTML 마크업 변경은 `_section_wbs` 렌더 함수 수정을 동반하므로 TSK-01-01 범위를 초과한다. CSS `::before` pseudo-element는 순수 CSS로 해결 가능.

## 선행 조건

- `TSK-00-01` 완료 — `scripts/monitor-server.py`의 v1 구조(DASHBOARD_CSS 라인 위치, `_section_*` 렌더 함수 시그니처)가 확정된 상태여야 한다.

## 리스크

- **MEDIUM**: `task-row::before` pseudo-element가 `position: absolute`를 사용하므로, 부모 `.task-row`에 `position: relative`를 추가해야 한다. 현재 v1 `.task-row`는 `display: grid`만 있고 `position` 미지정이다. 이 변경이 기존 그리드 레이아웃을 깨지 않는지 확인 필요.
- **MEDIUM**: CSS 라인 수 상한 400줄. 추가 내용이 57줄 초과 여유를 남기지만, 미디어 쿼리/주석이 늘어날 경우 접근한다. `wc -l` 또는 파이썬으로 CSS 문자열 내 줄 수를 검증한다.
- **LOW**: `conic-gradient` CSS 커스텀 프로퍼티(`--pct-done-end`, `--pct-run-end`)는 JS가 인라인 style로 `element.style.setProperty()`를 통해 주입해야 한다. CSS만으로는 동적 값 계산 불가 — 후행 TSK에서 JS 구현 필수.
- **LOW**: `.drawer`의 `display: none → flex` 전환과 `transform: translateX` 병행 사용 시, 일부 구형 브라우저에서 `display: none` 상태의 transition이 무시된다. JS에서 클래스 토글 타이밍을 `requestAnimationFrame`으로 분리해야 한다 (후행 TSK 범위).

## QA 체크리스트

- [ ] `python3 -m py_compile scripts/monitor-server.py` 명령이 에러 없이 통과한다 (CSS 교체 후 Python 문법 오류 없음).
- [ ] `DASHBOARD_CSS` 문자열의 줄 수가 400 이하임을 `len(DASHBOARD_CSS.splitlines())` 또는 `wc -l`로 확인한다.
- [ ] `@supports not (background: conic-gradient(...)) { .wp-donut { background: var(--panel); } }` 블록이 CSS 문자열에 포함된다.
- [ ] v1 CSS 변수 15개(`--bg`, `--fg`, `--muted`, `--border`, `--panel`, `--accent`, `--warn`, `--blue`, `--purple`, `--green`, `--gray`, `--orange`, `--red`, `--yellow`, `--light-gray`)가 `:root` 블록에 모두 존재하고 값이 v1과 동일하다.
- [ ] `.kpi-card.running`, `.kpi-card.failed`, `.kpi-card.bypass`, `.kpi-card.done`, `.kpi-card.pending` 각 클래스에 좌측 4px 컬러 바(`border-left: 4px solid var(--{color})`)가 정의되어 있다.
- [ ] `.chip[aria-pressed="true"]` 선택자가 CSS에 존재하고 활성 스타일(`background: var(--accent)`)이 적용된다.
- [ ] `.page` 레이아웃이 `grid-template-columns: 3fr 2fr`로 설정된다.
- [ ] `@media (max-width: 1279px)` 에서 `.page`가 `grid-template-columns: 1fr`로 전환된다.
- [ ] `@media (max-width: 767px)` 블록이 존재하고 KPI 가로 스크롤 및 모바일 조정이 포함된다.
- [ ] `@media (prefers-reduced-motion: reduce)` 블록에서 `.badge-run`, `.run-line`, `.activity-row`, `.drawer`의 animation/transition이 비활성화된다.
- [ ] `.timeline-svg .tl-dd`, `.tl-im`, `.tl-ts`, `.tl-xx`, `.tl-fail` 클래스가 각각 `--blue`, `--purple`, `--green`, `--gray`, `fill: url(#hatch)`로 정의된다.
- [ ] `.drawer` 기본 너비가 `640px`이고, `@media (max-width: 767px)` 에서 `100vw`로 전환된다.
- [ ] `.drawer-backdrop.open`과 `.drawer.open` 클래스가 각각 `display: block`과 `display: flex; transform: translateX(0)`으로 정의된다.
- [ ] `.task-row`에 `position: relative`가 추가되고, `::before` pseudo-element가 `position: absolute; left: 0; width: 4px`로 정의된다.
- [ ] `.task-row.running .run-line`에 `@keyframes slide` 애니메이션이 연결된다.
- [ ] (클릭 경로) 브라우저에서 `http://localhost:7321/` 접속 시 sticky 헤더가 스크롤 후에도 상단에 고정된 채로 표시된다.
- [ ] (화면 렌더링) 브라우저에서 KPI 카드 5장, 필터 칩, `.page` 2단 레이아웃이 실제 렌더링되며, 필터 칩 클릭 시 `aria-pressed` 토글 스타일이 적용된다.
