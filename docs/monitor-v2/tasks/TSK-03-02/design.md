# TSK-03-02: 접근성 속성 + prefers-reduced-motion - 설계

## 요구사항 확인
- WCAG 2.2 AA 수준을 목표로, 대시보드 전 영역에 `aria-*` 속성을 추가하고 포커스 관리를 구현한다.
- KPI 카드 숫자·필터 칩·auto-refresh 토글·expand 버튼 등 인터랙티브 요소를 키보드로 조작 가능하게 하고, SVG(`_kpi_spark_svg`, `_timeline_svg`)에 `<title>`/`<desc>`를 주입한다.
- `@media (prefers-reduced-motion: reduce)` 블록으로 pulse·fade-in·slide·transition 애니메이션을 모두 비활성화한다.

## 타겟 앱
- **경로**: N/A (단일 앱) — `scripts/monitor-server.py` 단일 파일 프로젝트
- **근거**: 모노레포 구조 없음. 전체 렌더 로직이 `scripts/monitor-server.py` 한 파일에 집중되어 있음.

## 구현 방향
- **최소 침습 원칙**: 기존 `_section_*` 렌더 함수와 `DASHBOARD_CSS`, `_DASHBOARD_JS`를 수정하는 방식. 신규 파일 불필요.
- **Python 렌더 함수 수정**: KPI 카드 숫자에 `aria-label="Running: 3"` 형태, 필터 칩·auto-refresh 토글·expand 버튼을 `<button>` 요소로 렌더, SVG 함수에 `<title>`/`<desc>` 삽입.
- **JS 포커스 관리**: `openDrawer()` 진입 시 `document.activeElement`를 모듈-스코프 변수(`_lastFocus`)에 저장. `closeDrawer()` 시 `.drawer-close` 포커스 이동 → 닫기 후 `_lastFocus.focus()` 복원. 드로어 열림 상태에서 `aria-hidden="false"`, 닫힘 상태에서 `aria-hidden="true"` 토글.
- **CSS 확장**: `DASHBOARD_CSS` 내 `@media (prefers-reduced-motion: reduce)` 블록을 확장 — pulse·fade-in·slide·drawer transition 전부 비활성화.

## 파일 계획

**경로 기준:** 프로젝트 루트 기준.

> 이 프로젝트는 라우터 파일과 별도의 네비게이션 파일이 없는 단일 Python HTTP 서버다. 진입점 라우터는 `MonitorHandler._route_root()`이며, 메뉴·네비게이션은 `_section_sticky_header()` 내 nav 링크 HTML이다. 두 역할 모두 `scripts/monitor-server.py` 안에 있다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | 메인 렌더 파일: `DASHBOARD_CSS`, `_DASHBOARD_JS`, `_section_kpi`, `_section_sticky_header`, `_kpi_spark_svg`, `_timeline_svg`, `_section_team`, `_drawer_skeleton` 수정 — aria 속성 + prefers-reduced-motion 추가 | 수정 |
| `scripts/monitor-server.py` | 라우터 역할: `MonitorHandler._route_root()` — 접근성 속성이 포함된 렌더 함수 호출 체인 유지 (코드 변경 없음, 수정된 렌더 함수가 자동 반영) | 수정 (라우터) |
| `scripts/monitor-server.py` | 내비게이션 역할: `_section_sticky_header()` 내 nav 앵커 링크 + 필터 칩 + auto-refresh 토글 버튼 — `<button>` 요소로 렌더 + `aria-label` 추가 | 수정 (nav) |

## 진입점 (Entry Points)

- **사용자 진입 경로**: 브라우저에서 `http://localhost:7321` 접속 → 대시보드 메인 페이지(`/`) 로드 → Tab 키로 헤더·필터 칩·WP 카드 expand 버튼·드로어 순으로 포커스 탐색
- **URL / 라우트**: `http://localhost:7321/` (루트 경로)
- **수정할 라우터 파일**: `scripts/monitor-server.py`의 `MonitorHandler._route_root()` (1681번 라인 부근) — `_build_render_state()` → `render_dashboard()` 호출 체인이 수정된 렌더 함수를 자동으로 사용
- **수정할 메뉴·네비게이션 파일**: `scripts/monitor-server.py`의 `_section_sticky_header()` — 내부 nav 앵커 링크(`#kpi`, `#wbs` 등)와 필터 칩·auto-refresh 토글 버튼 렌더 (TSK-01-06 신규 함수 대상)
- **연결 확인 방법**: 브라우저에서 `http://localhost:7321` 접속 → Tab 키로 헤더 첫 번째 focusable 요소부터 드로어 닫기 버튼까지 순서대로 포커스 이동 확인 → 드로어 expand 버튼 Enter 키 → 드로어 열림 + `.drawer-close` 포커스 이동 → ESC 또는 닫기 버튼 → 트리거 버튼으로 포커스 복귀

## 주요 구조

| 수정 대상 | 변경 내용 | 책임 |
|-----------|-----------|------|
| `DASHBOARD_CSS` | `@media (prefers-reduced-motion: reduce)` 블록 확장: `.badge-run`, `.activity-row`, `.task-row.running .run-line` → `animation: none !important`; `.drawer` → `transition: none !important` | 모션 감소 미디어 쿼리 |
| `_kpi_spark_svg(buckets, color)` | `<svg>` 내부에 `<title>Sparkline: {label}</title><desc>최근 10분 phase 이벤트 추이</desc>` 삽입 | 스파크라인 SVG 스크린리더 지원 |
| `_timeline_svg(rows, span_minutes)` | `<svg>` 내부에 `<title>Phase Timeline</title><desc>Task별 phase 진행 타임라인</desc>` 삽입 | 타임라인 SVG 스크린리더 지원 |
| `_section_kpi(model)` | KPI 카드 숫자 요소에 `aria-label="Running: {n}"` 형태 추가; 필터 칩을 `<button class="chip" aria-pressed="..." data-filter="...">` 형태로 렌더 | KPI + 필터 접근성 |
| `_section_sticky_header(model)` | auto-refresh 토글을 `<button class="refresh-toggle" aria-pressed="true">◐ auto</button>` 형태로 렌더; nav 앵커 링크에 `aria-label` 속성 추가 | 헤더 접근성 |
| `_section_team(panes)` | pane expand 요소를 `<button class="expand-btn" data-pane-expand="{pane_id}" aria-label="show pane {pane_id}">` 형태로 렌더 | 팀 pane expand 키보드 지원 |
| `_drawer_skeleton()` | `<aside class="drawer" role="dialog" aria-modal="true" aria-hidden="true">` 및 `<button class="drawer-close" aria-label="close">✕</button>` 확인/유지 (TSK-01-06 구현 결과 검증) | 드로어 ARIA 역할 확인 |
| `_DASHBOARD_JS` (인라인 JS) | `_lastFocus` 모듈-스코프 변수 추가; `openDrawer()`: `_lastFocus = document.activeElement` 저장 → `drawer.setAttribute('aria-hidden','false')` → `drawerClose.focus()`; `closeDrawer()`: `drawer.setAttribute('aria-hidden','true')` → `_lastFocus && _lastFocus.focus()` | 드로어 포커스 관리 + aria-hidden 토글 |

## 데이터 흐름
`render_dashboard(model)` 호출 → 수정된 `_section_kpi(model)`, `_kpi_spark_svg()`, `_timeline_svg()`, `_section_sticky_header()`, `_section_team()`, `_drawer_skeleton()` 각각 aria 속성 포함 HTML 문자열 반환 → `<style>{DASHBOARD_CSS}</style>`(prefers-reduced-motion 블록 포함) + `<script>{_DASHBOARD_JS}</script>`(포커스 관리 포함) 조합 → 브라우저에서 Tab 키 탐색·스크린리더 읽기·모션 감소 미디어 쿼리가 모두 동작하는 완전한 HTML 문서 출력

## 설계 결정 (대안이 있는 경우만)

- **결정**: 필터 칩을 `<button>` 요소로 교체
- **대안**: `<span tabindex="0" role="button">` 패턴
- **근거**: `<button>`은 기본 focusable, Enter/Space 키 이벤트 기본 동작, `aria-pressed` 지원 내장으로 `tabindex` + `role` 수동 조합보다 견고. TRD §8에 `<button>`으로 명시.

- **결정**: `openDrawer` 진입 시 모듈-스코프 `var _lastFocus` 변수로 포커스 저장
- **대안**: `state` 객체 내 `state.lastFocus` 필드에 저장
- **근거**: 드로어는 동시에 하나만 열리므로 단일 변수로 충분. `state` 객체 오염 최소화.

- **결정**: `aria-hidden` 토글로 드로어 열림/닫힘을 보조기술에 명시적으로 전달
- **대안**: `class="open"` CSS 만으로 상태 표현
- **근거**: CSS `display:none`만으로는 일부 스크린리더에서 콘텐츠를 숨기지 못할 수 있음. `aria-hidden="true/false"` 명시적 토글로 보조기술 접근 제어.

## 선행 조건
- **TSK-01-06** (`render_dashboard` 재조립 + sticky header + 드로어 골격): 이 Task가 `_section_sticky_header`, `_drawer_skeleton`, `_section_kpi`, `_kpi_spark_svg`, `_timeline_svg`, `_DASHBOARD_JS` 등 v2 렌더 함수를 신규 구현한다. TSK-03-02는 그 결과물에 접근성 속성을 추가하는 후속 Task이므로 TSK-01-06 병합 후 실행해야 한다.
- TSK-02-01·TSK-02-02·TSK-02-03 (JS 폴링·필터·드로어 제어): 드로어 포커스 관리 통합 테스트는 이 Task들이 완료된 후 가능. 단, Python 렌더 함수의 aria 속성 주입 자체는 독립적으로 구현 가능.

## 리스크
- **HIGH**: TSK-01-06이 미완료 상태 — `_section_kpi`, `_kpi_spark_svg`, `_timeline_svg`, `_section_sticky_header`, `_DASHBOARD_JS` 함수가 현재 `scripts/monitor-server.py`에 없음. dev-build는 TSK-01-06 산출물 병합 후에 실행해야 한다.
- **MEDIUM**: 필터 칩의 현재 HTML 요소 타입이 TSK-02-02 구현에서 `<div>`/`<span>`으로 생성될 경우, `<button>` 교체 시 user-agent 기본 스타일(border, padding, background)이 `.chip` CSS와 충돌할 수 있음 — `button.chip { appearance: none; background: transparent; border: 1px solid var(--border); }` 등 리셋 CSS가 필요할 수 있음.
- **MEDIUM**: `closeDrawer()` 호출 시 `_lastFocus`가 `null` 또는 DOM에서 제거된 요소일 수 있음 — `_lastFocus && typeof _lastFocus.focus === 'function' && _lastFocus.focus()` 가드 필요.
- **LOW**: `prefers-reduced-motion` CSS 블록이 TSK-01-06에서 이미 추가되었을 가능성 있음 (TRD §4.2.1 예시에 포함). dev-build 시 중복 여부 확인 후 확장 또는 스킵.
- **LOW**: Lighthouse a11y 점수 ≥ 90 달성을 위해 색상 대비 추가 조정이 필요할 수 있음. TRD §8 및 PRD §5.3에서 기존 GitHub 다크 팔레트가 WCAG AA를 대체로 충족한다고 명시.

## QA 체크리스트
dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

### 정상 케이스 (Python 렌더 단위 테스트)
- [ ] `_section_kpi(model)` 출력에 `aria-label="Running: N"` (N은 실제 카운트) 형태 속성이 KPI 숫자 요소에 포함된다
- [ ] `_section_kpi(model)` 출력의 필터 칩이 `<button` 태그로 시작하고 `aria-pressed` 속성을 가진다
- [ ] `_section_sticky_header(model)` 출력의 auto-refresh 토글이 `<button class="refresh-toggle"` 태그이며 `aria-pressed` 속성을 포함한다
- [ ] `_kpi_spark_svg(buckets, color)` 출력이 `<svg` 태그를 포함하며 그 내부에 `<title>` 태그와 `<desc>` 태그가 존재한다
- [ ] `_timeline_svg(rows, span_minutes)` 출력이 `<svg` 태그를 포함하며 그 내부에 `<title>` 태그와 `<desc>` 태그가 존재한다
- [ ] `_drawer_skeleton()` 출력에 `role="dialog"`, `aria-modal="true"`, `aria-hidden="true"`가 모두 포함된다
- [ ] `_drawer_skeleton()` 출력의 닫기 버튼이 `<button class="drawer-close"` 태그이며 `aria-label="close"` 속성을 포함한다
- [ ] `_section_team(panes)` 출력의 expand 버튼이 `<button` 태그이며 `data-pane-expand` 속성을 가진다

### CSS 검증 (렌더 단위 테스트)
- [ ] `DASHBOARD_CSS` 문자열에 `@media (prefers-reduced-motion: reduce)` 블록이 존재하며, 그 블록 내에 `animation: none` 선언이 포함된다
- [ ] `@media (prefers-reduced-motion: reduce)` 블록 내에 `.drawer` 규칙에 `transition: none` 선언이 포함된다
- [ ] `@media (prefers-reduced-motion: reduce)` 블록이 `.badge-run`, `.activity-row`, `.task-row.running .run-line` 중 하나 이상의 클래스에 `animation: none !important` 선언을 포함한다

### E2E / 브라우저 검증
- [ ] (클릭 경로) 브라우저에서 `http://localhost:7321` 접속 → Tab 키로 헤더 첫 번째 focusable 요소에 포커스 이동이 확인된다
- [ ] (화면 렌더링) 필터 칩 4개(`[All] [Running] [Failed] [Bypass]`)가 `<button>` 요소로 렌더링되고, Tab·Enter 키로 클릭 가능하다
- [ ] Tab 키로 헤더 → 필터 칩 → WP 카드 expand 버튼 → 드로어 열기 순서로 포커스가 이동한다
- [ ] pane expand 버튼에 포커스 후 Enter 키를 누르면 드로어가 열리고, 포커스가 `.drawer-close` 버튼으로 이동한다
- [ ] 드로어에서 ESC 키를 누르거나 `.drawer-close` 버튼을 클릭하면 드로어가 닫히고 포커스가 expand 버튼(트리거 요소)으로 복귀한다
- [ ] 드로어 열림 상태에서 `<aside class="drawer">` 요소의 `aria-hidden` 속성이 `"false"`이고, 닫힘 상태에서 `"true"`이다
- [ ] Chrome DevTools에서 Lighthouse a11y 감사 실행 시 점수 ≥ 90 (axe-core 기반)
- [ ] OS 설정에서 `prefers-reduced-motion` 활성화 후 `http://localhost:7321` 접속 시 `.badge-run` 애니메이션(pulse)이 정지된 상태로 표시된다

### 엣지 케이스
- [ ] `openDrawer()` 호출 전 `document.activeElement`가 `null` 또는 `document.body`일 때, `closeDrawer()` 후 포커스 복원 시도가 에러 없이 no-op로 처리된다
- [ ] KPI 카운트가 0인 경우 `aria-label="Running: 0"` 형태가 올바르게 렌더링된다
- [ ] `_kpi_spark_svg([], color)` — buckets가 빈 리스트일 때 `<svg>`와 `<title>` 포함 유효한 SVG 문자열이 반환된다 (빈 상태 에러 없음)
