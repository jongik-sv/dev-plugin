# TSK-03-01: 반응형 미디어 쿼리 (1280px / 768px) - 설계

## 요구사항 확인
- `scripts/monitor-server.py`의 `DASHBOARD_CSS` 문자열에 두 개의 미디어 쿼리 블록을 추가한다: `@media (max-width: 1279px)` (태블릿 1단 레이아웃)와 `@media (max-width: 767px)` (모바일 특수 처리).
- 데스크톱(≥1280px)에서는 2단 grid(좌 3fr / 우 2fr), 태블릿(768~1279px)에서는 1단으로 KPI → WP → Features → Activity → Timeline → Team → Subagent 순서, 모바일(<768px)에서는 KPI 카드 가로 스크롤 + Phase Timeline `<details>` 기본 접힘 + 도넛 숨김·숫자만.
- CSS 추가 ≤ 50줄 제약 준수. 기존 CSS 변수/클래스 네이밍 유지.

## 타겟 앱
- **경로**: N/A (단일 앱)
- **근거**: dev-plugin은 단일 Python 스크립트(`scripts/monitor-server.py`)가 모든 HTML/CSS를 인라인으로 렌더링하는 단일 앱 프로젝트.

## 구현 방향
- `DASHBOARD_CSS` 문자열 끝(현재 732행의 `"""` 앞)에 미디어 쿼리 2블록을 추가한다.
- 데스크톱 2단 레이아웃을 위해 `render_dashboard`가 생성하는 `<body>` 내부에 `.dashboard-grid` 컨테이너를 추가해야 한다. `render_dashboard`에서 좌측 컬럼(`#wbs`, `#features`)과 우측 컬럼(`#team`, `#subagents`, `#phases`) 섹션을 각각 `<div class="col-left">` / `<div class="col-right">` 으로 감싸고, 이 두 div를 `<div class="dashboard-grid">`로 묶는다.
- 모바일에서 Phase Timeline(`#phases`) 기본 접힘은 `render_dashboard` 내 inline JS 1줄로 처리 (`if (window.innerWidth < 768) { var d = document.querySelector('.phases-collapsible'); if(d) d.removeAttribute('open'); }`). CSS만으로는 `open` 속성을 제어할 수 없음.
- 도넛 차트는 TSK-03-01 범위 외 별도 Task에서 구현 예정이므로, 모바일 도넛 숨김 CSS 규칙(`.donut { display: none; }`)만 미리 추가하여 후속 Task와 충돌 없이 연결되도록 준비한다.

## 파일 계획

**경로 기준:** 프로젝트 루트 기준.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `DASHBOARD_CSS`에 미디어 쿼리 2블록 + grid/col CSS 추가; `render_dashboard`에 `.dashboard-grid`/`.col-left`/`.col-right` 래퍼 HTML 삽입; 모바일 Phase Timeline `open` 제거 inline JS 추가 | 수정 |

> 라우터/메뉴 파일 없음 — 이 프로젝트는 단일 Python HTTP 서버, SPA 라우터 없음.

## 진입점 (Entry Points)

- **사용자 진입 경로**: 브라우저에서 `http://localhost:{port}/` 접속 → 대시보드 페이지 로드 (뷰포트에 따라 레이아웃 자동 전환)
- **URL / 라우트**: `/` (루트 엔드포인트 — `render_dashboard`가 반환하는 HTML)
- **수정할 라우터 파일**: 해당 없음 (단일 HTTP 핸들러, 라우팅 테이블 변경 불필요)
- **수정할 메뉴·네비게이션 파일**: 해당 없음 (top-nav는 anchor 링크, 신규 페이지 아님)
- **연결 확인 방법**: 브라우저에서 `/` 접속 후 Chrome DevTools 뷰포트를 1440 → 1024 → 390으로 변경하여 레이아웃 전환 확인

## 주요 구조

- **`DASHBOARD_CSS` 미디어 쿼리 추가 부분**:
  - `@media (max-width: 1279px)` 블록: `.dashboard-grid` → `grid-template-columns: 1fr` (1단 전환)
  - `@media (max-width: 767px)` 블록: `.kpi-row` → `overflow-x: auto; scroll-snap-type: x mandatory`, `.donut` → `display: none`
- **`.dashboard-grid`**: `display: grid; grid-template-columns: 3fr 2fr; gap: 1rem` — 데스크톱 2단 컨테이너 (≥1280px)
- **`.col-left`**: `#wbs` + `#features` 섹션을 묶는 좌측 컬럼 div
- **`.col-right`**: `#team` + `#subagents` + `#phases` 섹션을 묶는 우측 컬럼 div
- **`render_dashboard` 수정**: `_section_header(model)` 은 grid 밖(전폭), 나머지 섹션을 left/right로 분리하여 `.dashboard-grid` 컨테이너에 조합

## 데이터 흐름
입력: `render_dashboard(model)` 호출 → 처리: 기존 `_section_*` HTML을 `.col-left`/`.col-right` div로 그룹화 후 `.dashboard-grid`로 감쌈; `DASHBOARD_CSS`에 미디어 쿼리 포함 → 출력: 반응형 레이아웃 HTML 문서 (CSS/JS 모두 인라인)

## 설계 결정 (대안이 있는 경우만)

- **결정**: `render_dashboard`에서 `col-left`/`col-right` div 래퍼를 Python 문자열 연결로 직접 추가
- **대안**: 각 `_section_*` 함수에 컬럼 div 래퍼를 내장
- **근거**: 각 `_section_*` 함수는 단독 호출·단독 테스트를 전제로 설계되어 있으므로, 컬럼 래퍼는 조합 레이어(`render_dashboard`)에서만 처리하는 것이 관심사 분리에 맞음.

- **결정**: 모바일 Phase Timeline 기본 접힘을 inline JS 1줄로 처리
- **대안**: 서버 사이드에서 User-Agent 감지 후 `open` 속성 제거
- **근거**: UA 스니핑은 서버 복잡도를 높이고 오탐이 잦음. Inline JS는 50줄 CSS 제약을 침범하지 않으면서 브라우저 폭을 정확히 감지함.

- **결정**: `#header` section은 `.dashboard-grid` 밖(전폭), grid 안에는 col-left(wbs+features)와 col-right(team+subagents+phases)만
- **대안**: header를 grid 첫 행으로 포함 (`grid-column: 1 / -1`)
- **근거**: PRD 와이어프레임에서 헤더·KPI는 전폭 영역, 2단 분할은 그 아래부터 시작. grid 외부에 두면 전폭 처리가 더 단순함.

## 선행 조건
- TSK-01-06 (기존 `render_dashboard` + `DASHBOARD_CSS` 구현 완료) — 현재 `scripts/monitor-server.py` 732행에 `DASHBOARD_CSS`, 1080행에 `render_dashboard` 함수가 이미 존재함을 확인.

## 리스크
- **MEDIUM**: `render_dashboard`의 `sections` 조합이 현재 단순 `"\n".join(sections)`인데, col-left/col-right div 삽입 시 HTML 문자열 분기가 생겨 태그 누락 위험이 있음. 구현 시 여닫기 태그 정확성 주의.
- **LOW**: CSS `order` 속성 없이 col-left가 col-right보다 앞에 오므로 1단 모드에서 순서가 WP → Features → Team → Subagents → Phases로 자연스럽게 PRD 요구(KPI → WP → Features → Activity → Timeline → Team → Subagent)와 일치함. KPI는 header에 포함되어 항상 최상단.
- **LOW**: `DASHBOARD_CSS` 추가 분량이 ≤50줄 제약 내인지 구현 시 확인 필요. 미디어 쿼리 2블록 + grid/col CSS는 25~35줄 예상.

## QA 체크리스트
dev-test 단계에서 검증할 항목.

- [ ] (정상 - 데스크톱) 뷰포트 1440px에서 `.dashboard-grid`가 `grid-template-columns: 3fr 2fr` 2단 레이아웃으로 표시됨
- [ ] (정상 - 태블릿) 뷰포트 1024px에서 `.dashboard-grid`가 1단으로 전환되고 `.col-left`(WBS+Features)가 `.col-right`(Team+Subagents+Phases)보다 위에 위치함
- [ ] (정상 - 모바일) 뷰포트 390px에서 `.kpi-row` 컨테이너에 가로 스크롤이 발생함
- [ ] (정상 - 모바일) 뷰포트 390px에서 Phase Timeline `<details>` 가 기본 접힘 상태(`open` 속성 없음)로 렌더링됨
- [ ] (정상 - 모바일) 뷰포트 390px에서 `.donut` 요소가 `display: none`으로 숨겨짐 (도넛 구현 후 검증)
- [ ] (엣지) 뷰포트 1279px (경계값)에서 1단 레이아웃이 적용됨 (`max-width: 1279px` 미디어 쿼리 경계)
- [ ] (엣지) 뷰포트 767px (경계값)에서 KPI 가로 스크롤이 활성화됨 (`max-width: 767px` 경계)
- [ ] (에러) 의도하지 않은 가로 스크롤이 1024px / 1440px 뷰포트에서 발생하지 않음
- [ ] (통합) 기존 CSS 변수(`--bg`, `--fg`, `--border` 등)와 클래스 네이밍이 변경되지 않고 유지됨
- [ ] (통합) `DASHBOARD_CSS`에 추가되는 줄 수가 50줄 이하임

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**
- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 (URL 직접 입력 금지) — 이 Task는 신규 페이지 없음; `/` 루트 대시보드 접속 후 DevTools 뷰포트 조절로 검증
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다 — 각 뷰포트(1440/1024/390)에서 주요 section이 렌더링되고 Phase Timeline 토글이 동작함
