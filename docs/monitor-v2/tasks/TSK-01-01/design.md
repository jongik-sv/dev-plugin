# TSK-01-01: DASHBOARD_CSS 확장 - 설계

## 요구사항 확인
- `scripts/monitor-server.py`의 `DASHBOARD_CSS` 문자열(현재 63줄)을 v2 비주얼 재설계 스펙에 맞게 ~343줄로 확장한다. 400줄 상한 준수.
- 추가 대상: sticky 헤더, KPI 카드 팔레트(running/failed/bypass/done/pending 좌측 4px 컬러 바), 필터 칩 aria-pressed 스타일, 2단 grid(.page, 좌 3fr / 우 2fr), WP 카드 도넛(conic-gradient 80×80px), task-row 상태 컬러 바 + Running 애니메이션 라인, Live activity fade-in, Phase timeline SVG 클래스(tl-dd/im/ts/xx/fail), pane preview, 드로어(backdrop + slide-in 640px), 반응형 1280px/768px, prefers-reduced-motion.
- v1 CSS 변수(`--bg`, `--fg`, `--muted` 등) 네이밍 유지. 외부 폰트/CDN 금지. `@supports not (background: conic-gradient(...))` fallback 포함.

## 타겟 앱
- **경로**: N/A (단일 앱)
- **근거**: 단일 Python 파일(`scripts/monitor-server.py`) 내 인라인 CSS 문자열 블록만 교체하는 단일 파일 프로젝트.

## 구현 방향
- `DASHBOARD_CSS` 문자열 블록(line 669~732)을 교체하여 v2 스타일을 적용한다. 별도 파일 생성 없이 in-place 수정.
- v1에서 사용하는 CSS 변수(`:root { --bg … }`)와 기존 클래스 이름(`.badge-*`, `.task-row`, `.badge`, `.warn`, `.empty`, `.info`, `.pane-row`, `.pane-link`, `.phase-list`, `section` 등)은 모두 유지한다 — v1 렌더 함수가 이 클래스를 직접 참조하므로 이름 변경 시 런타임 오류 발생.
- 신규 클래스는 기존 클래스를 확장하는 방식으로 추가한다: `.page`, `.header-bar`, `.kpi-grid`, `.kpi-card`, `.kpi-card--run/fail/bypass/done/pending`, `.filter-chips`, `.chip`, `.wp-card`, `.donut`, `.progress-bar`, `.task-row--running`, `.task-row--failed`, `.task-status-bar`, `.activity-list`, `.activity-item`, `.tl-dd`, `.tl-im`, `.tl-ts`, `.tl-xx`, `.tl-fail`, `.pane-preview`, `.drawer`, `.drawer-backdrop`.
- CSS 총 줄 수를 400줄 이하로 유지하기 위해 선택자 압축(공통 속성 묶기)과 미디어 쿼리 블록 통합을 적용한다.

## 파일 계획

**경로 기준:** 프로젝트 루트 기준.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `DASHBOARD_CSS` 문자열 블록(line 669~732) 교체 — v2 CSS 적용 | 수정 |

> 이 Task는 CSS 문자열만 수정하며, 라우터/메뉴 배선 변경 없음. `DASHBOARD_CSS`는 `render_dashboard()` → line 1120 `f'  <style>{DASHBOARD_CSS}</style>\n'`으로 이미 인라인 삽입되므로 배선 수정 불필요.

## 진입점 (Entry Points)

이 Task는 `domain=frontend`이나 신규 페이지/라우트를 추가하지 않는다. CSS 스타일만 교체하는 작업이므로 라우터 파일/메뉴 파일 수정이 없다.

- **사용자 진입 경로**: 브라우저에서 `http://localhost:7321/` 접속 (v1과 동일, 경로 변경 없음)
- **URL / 라우트**: `/`
- **수정할 라우터 파일**: 없음 — `MonitorHandler.do_GET`의 기존 `/` 경로 핸들러가 `render_dashboard()`를 호출하는 구조 유지. `DASHBOARD_CSS`는 `render_dashboard()` 내부 line 1120에서 `<style>` 태그로 삽입됨.
- **수정할 메뉴·네비게이션 파일**: 없음 — 이 Task는 CSS 문자열만 수정.
- **연결 확인 방법**: E2E에서 `http://localhost:7321/` 접속 후 페이지 `<style>` 태그 내 신규 CSS 클래스(`.kpi-card`, `.page`, `.drawer` 등) 존재 여부 확인.

> **비-페이지 UI**: CSS 문자열 확장이므로 라우터/메뉴 배선 항목이 해당 없음. 적용될 상위 페이지: `http://localhost:7321/` (대시보드 루트). E2E에서 이 URL로 접속하여 CSS 클래스 렌더링을 검증한다.

## 주요 구조

- **`:root` 변수 블록**: v1 변수(`--bg`, `--fg`, `--muted`, `--border`, `--panel`, `--accent`, `--warn`, `--blue`, `--purple`, `--green`, `--gray`, `--orange`, `--red`, `--yellow`, `--light-gray`) 유지 + 신규 변수 추가(`--kpi-run: var(--orange)`, `--kpi-fail: var(--red)`, `--kpi-bypass: var(--yellow)`, `--kpi-done: var(--green)`, `--kpi-pending: var(--light-gray)`, `--drawer-width: 640px`).
- **레이아웃 블록 (`.page`)**: CSS Grid `grid-template-columns: 3fr 2fr; gap: 1.5rem`. `@media(max-width:1279px)`에서 `grid-template-columns: 1fr`로 fallback.
- **KPI 카드 블록 (`.kpi-card`, `.kpi-card--run/fail/bypass/done/pending`)**: 좌측 4px 컬러 바(`border-left: 4px solid`). `.kpi-card--run`은 `@keyframes pulse` 적용.
- **필터 칩 블록 (`.chip`, `.chip[aria-pressed="true"]`)**: `aria-pressed` 상태 스타일(배경색·테두리·font-weight 변경).
- **WP 도넛 블록 (`.donut`)**: `width: 80px; height: 80px; border-radius: 50%; conic-gradient`. `@supports not (background: conic-gradient(red 0deg))` fallback: solid `var(--green)` 배경으로 대체.
- **task-row 상태 바 (`.task-status-bar`, `.task-row--running`, `.task-row--failed`)**: `border-left: 4px solid`. Running row는 `@keyframes slide-in` 애니메이션 오버레이.
- **드로어 (`.drawer`, `.drawer-backdrop`)**: `.drawer` — `position: fixed; right: 0; top: 0; height: 100%; width: var(--drawer-width); transform: translateX(100%); transition: transform 0.25s ease`. 열림 상태(`.drawer.open`): `transform: translateX(0)`. `.drawer-backdrop` — `position: fixed; inset: 0; background: rgba(0,0,0,.45)`.
- **반응형 + 접근성**: 2개 미디어 쿼리 블록 통합(`@media (max-width:1279px)`, `@media (max-width:767px)`). `@media (prefers-reduced-motion: reduce)` 블록에서 `animation: none`, `transition: none`.

## 데이터 흐름

입력: `DASHBOARD_CSS` 문자열 상수(Python) → 처리: `render_dashboard()` → `f'<style>{DASHBOARD_CSS}</style>'` 삽입 (line 1120) → 출력: `GET /` 응답 HTML의 `<head>` 내 인라인 `<style>` 태그.

## 설계 결정 (대안이 있는 경우만)

- **결정**: `@supports not (background: conic-gradient(...))` fallback을 단일 `@supports` 블록으로 구현. fallback은 단색 `var(--green)` 배경 적용.
- **대안**: 도넛을 SVG `<circle>` stroke-dasharray로 구현 (conic-gradient 불필요).
- **근거**: PRD 요구사항이 `conic-gradient` 명시이므로 CSS-first 구현 우선. fallback은 구형 Safari 대응 최소 요건. SVG 전환은 TSK-01-02 이후 렌더 함수에서 결정 사항.

- **결정**: 신규 CSS 변수(`--kpi-run` 등)를 `:root`에 추가하되 기존 색상 변수(`--orange`, `--red` 등)를 참조.
- **대안**: KPI 카드에서 기존 `--orange` 등을 직접 참조.
- **근거**: KPI 카드 팔레트가 향후 독립적으로 조정될 가능성에 대비해 별도 변수로 분리하면 유지보수 용이.

- **결정**: 드로어 너비를 CSS 변수 `--drawer-width: 640px`로 정의.
- **대안**: 하드코딩 `640px`.
- **근거**: `@media (max-width: 767px)` 블록에서 `--drawer-width: 100vw`로 한 줄 덮어쓰기만으로 모바일 전환 가능.

## 선행 조건

- TSK-00-01 완료: v1 `monitor-server.py` 기능이 정상 동작하는 상태에서 CSS만 교체해야 함. v1 렌더 함수(`_section_header`, `_section_wbs`, `_section_team` 등)가 이 CSS의 클래스 이름을 사용함.

## 리스크

- **MEDIUM**: CSS 줄 수 상한(400줄). 선택자 묶기 및 미디어 쿼리 통합 없이 작성하면 400줄을 초과한다. 구현 시 `len(DASHBOARD_CSS.split('\n'))` 검증 필요.
- **MEDIUM**: 기존 `.task-row` 그리드 컬럼 비율(`9rem 8rem 1fr 6rem 4rem 1.5rem`)을 유지하면서 `border-left` 4px를 추가하면 열 정렬이 어긋날 수 있다. `padding-left: 8px` 조정 또는 `box-shadow: inset 4px 0` 대안 검토.
- **MEDIUM**: `prefers-reduced-motion` 미디어 쿼리 미적용 시 접근성 검수 실패. `@keyframes pulse`, `@keyframes slide-in`, fade-in 모두 `prefers-reduced-motion: reduce` 블록 안에서 `animation: none`으로 재정의해야 함.
- **LOW**: 구형 Safari(< 12.1)가 `@supports not` 구문 자체를 인식하지 못하는 경우 → 긍정형 `@supports (background: conic-gradient(red 0deg))` 패턴으로 교체 고려.

## QA 체크리스트

- [ ] `python3 -m py_compile scripts/monitor-server.py` 통과 (SyntaxError 없음).
- [ ] `len(DASHBOARD_CSS.strip().split('\n'))` ≤ 400 확인.
- [ ] `DASHBOARD_CSS` 내 `@supports not (background: conic-gradient(` 문자열 포함.
- [ ] `:root` 블록에 v1 변수 `--bg`, `--fg`, `--muted`, `--border`, `--panel`, `--accent`, `--warn`, `--blue`, `--purple`, `--green`, `--gray`, `--orange`, `--red`, `--yellow`, `--light-gray` 전부 존재.
- [ ] `.kpi-card--run`, `.kpi-card--fail`, `.kpi-card--bypass`, `.kpi-card--done`, `.kpi-card--pending` 클래스 정의 (좌측 4px 컬러 바 포함).
- [ ] `.chip[aria-pressed="true"]` 스타일 정의 (배경·테두리·폰트 변경).
- [ ] `.page` CSS Grid `grid-template-columns: 3fr 2fr` 정의.
- [ ] `.donut` `width: 80px; height: 80px` + conic-gradient 정의.
- [ ] `.drawer` `width: var(--drawer-width)` + `position: fixed; right: 0` 정의.
- [ ] `.drawer-backdrop` `position: fixed; inset: 0` 정의.
- [ ] `@media (max-width: 1279px)` 블록 — `.page` 1단 전환.
- [ ] `@media (max-width: 767px)` 블록 — KPI 가로 스크롤, `.kpi-grid` `overflow-x: auto`.
- [ ] `@media (prefers-reduced-motion: reduce)` 블록 — `animation: none`, `transition: none` 재정의.
- [ ] v1 기존 클래스(`.badge`, `.badge-dd`, `.badge-im`, `.badge-ts`, `.badge-xx`, `.badge-run`, `.badge-fail`, `.badge-bypass`, `.badge-pending`, `.task-row`, `.pane-row`, `.pane-link`, `.phase-list`, `.warn`, `.empty`, `.info`) 모두 유지되어 v1 렌더 함수 오류 없음.
- [ ] Phase timeline SVG 클래스 `.tl-dd`, `.tl-im`, `.tl-ts`, `.tl-xx`, `.tl-fail` 색상 정의.
- [ ] `.activity-item` fade-in 애니메이션 정의 (`@keyframes fade-in`).
- [ ] `.pane-preview` 스타일 정의 (배경 패널, monospace 폰트, 3줄 미리보기).

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**
- [ ] (클릭 경로) 브라우저에서 `http://localhost:7321/` 에 접속하여 대시보드 페이지가 로드된다 (신규 메뉴 연결 없음 — 기존 진입점 유지).
- [ ] (화면 렌더링) 대시보드 `<head>` 내 `<style>` 태그에 `.kpi-card`, `.page`, `.drawer` 클래스 CSS가 포함되어 있고, 브라우저에서 실제 스타일이 적용된다.
