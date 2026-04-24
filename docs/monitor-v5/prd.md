# PRD: dev-monitor v5

> **version**: 5.0.0-draft
> **start-date**: 2026-04-24
> **target-date**: 2026-05-22 (4주)
> **depth**: 3-level WBS (WP → Task)
> **선행 릴리스**: monitor-v4 (FR-01~FR-11 완료, AC-1~AC-28 수용)

## 1. 배경

`dev-monitor` v4 릴리스(DDTR 단계 배지 + Task hover 툴팁 + EXPAND 슬라이드 패널 + WP 머지 준비도 뱃지 + 글로벌 필터 바 + 모델 칩/에스컬레이션 플래그) 이후 누적된 UX 피드백과 `scripts/monitor-server.py`의 구조적 한계가 두 축으로 쌓였다:

**UX 측**
- **Task hover 툴팁이 모니터 오른쪽 끝 Task에서 뷰포트를 벗어나거나 가려진다**. 툴팁은 Task 행의 오른쪽에 붙어 뜨는데, 듀얼 모니터 환경이나 좁은 창에서 오른쪽 WP에 속한 Task 를 확인할 때 팝오버의 절반 이상이 화면 밖으로 밀려나 읽히지 않는다. 또한 hover 트리거는 의도치 않은 호버(스크롤 중·이동 중)에도 반응해 피로감이 크다.
- **WP 카드가 좌측 60%(`grid-template-columns: 3fr 2fr`)를 차지해 실시간 활동·팀 에이전트·서브에이전트 영역의 가시성이 낮다**. 병렬 실행 중에는 "지금 무엇이 돌고 있는지"가 중요한데, 오른쪽 실시간 영역이 좁아 팀 에이전트 pane preview 가 3줄만 보인다.
- **팀 에이전트 pane 카드의 preview (`max-height: 4.5em`) 가 3줄밖에 못 담아** 긴 로그 한 줄이 내려와도 이전 맥락을 알 수 없다. 실제 터미널을 다시 열어봐야 한다.
- **의존성 그래프에서 크리티컬 패스와 failed 노드가 같은 빨강(`var(--fail)`)으로 칠해진다**. 크리티컬 패스를 확인하려고 스캔하는데 실패 노드가 함께 빨강이라 한눈에 구분되지 않는다.
- **Task phase 배지가 텍스트만 있고 색상 단서가 약하다** (Design/Build/Test/Done 이 모두 비슷한 톤). 병렬 20+ Task 상황에서 상태를 훑기 어렵다.

**구조 측**
- `scripts/monitor-server.py` 가 **6,937줄 단일 파일**로, HTML/CSS/JS 가 Python 문자열 안에 인라인 되어 있다. 메모리 `project_monitor_server_inline_assets.md` 에 기록된 대로 **동시 머지 시 시각적 diff 가 거대해 무성(silent) 회귀가 발생한 적이 있다**. 이번 릴리스 이전에 분리하지 않으면 앞으로의 UI 변경마다 위험이 누적된다.
- `dev-monitor` 스킬 프롬프트(SKILL.md)·런처 관련 문서가 v1~v4 를 거치며 중복된 설명을 누적해 엔트리포인트가 흐려졌다.

**범위 밖 요청(별도 feature 로 분리)**
- "LLM 실수 로그" (CLAUDE.md 자동 주입) → `feat:log-mistake`
- "wbs 의존성 없는 기능을 feature 로 디스패치" → `feat:wbs-feat-dispatch`

## 2. 목표

**P0 (릴리스 차단)**

1. **FR-03 메인 그리드 비율 반전** — 메인 2컬럼 그리드를 `3fr : 2fr` 에서 **`2fr : 3fr`** 로 반전한다. WP 영역은 축소되고 실시간 활동·팀 에이전트·서브에이전트가 확장된다. WP 카드 `min-width` 는 축소된 컬럼에 맞춰 재조정되어 가로 스크롤이 생기지 않는다.
2. **FR-05 의존성 그래프 크리티컬 패스 색 분리** — 크리티컬 패스 노드는 앰버(`#f59e0b`) 테두리 + 배경 틴트로, failed 노드는 기존 `var(--fail)` 빨강을 유지한다. 범례(legend)가 두 상태를 별도로 표기한다.

**P1 (릴리스 병행)**

3. **FR-01 Task 정보 팝오버 이전** — hover 툴팁을 제거하고, Task 행의 **정보 아이콘(ⓘ) 클릭** 시 팝오버가 열리도록 바꾼다. 팝오버는 **Task 행 바로 위**에 표시하되 위쪽 여유가 부족하면 아래로 폴백한다. 디자인은 그림자·꼬리(tail)·폰트 스케일을 포함해 v4 대비 가독성을 높인다.
4. **FR-04 팀 에이전트 pane 카드 높이 2배** — pane 카드 padding 확대 + `pane-preview` `max-height: 4.5em` → `9em` 로 변경. `last 3 lines` 라벨은 `last 6 lines` 로 업데이트한다. 실제 표시 라인 수도 6줄 기준으로 조정한다.
5. **FR-06 Task phase 배지 색상 phase별 구분 + 스피너** — Design=액센트(blue)/Build=run(cyan)/Test=pending(yellow)/Done=done(green)/Failed=fail(red)/Bypass=purple 로 CSS 토큰을 배지에 일괄 적용한다. 진행 중 Task (`.running` signal) 배지 내부에 작은 스피너가 회전한다. **동일한 색·스피너 규칙이 의존성 그래프 노드에도 적용**되어 WP 카드와 dep-graph 가 시각적으로 일치한다.

**P2 (릴리스 후속·병행 가능)**

6. **FR-02 Task EXPAND 슬라이드 패널 강화** — EXPAND(↗) 클릭 시 여는 기존 슬라이드 패널(v4 AC-12)의 **상단에 "진행 요약 헤더"** 를 신설한다. 헤더에는 현재 status 배지 + elapsed + 최근 `phase_history` 이벤트 3건이 **시간 역순**으로 렌더된다. 헤더는 sticky 하여 패널 본문 스크롤 시에도 보인다. 본문의 wbs / state.json / 아티팩트 / 로그 섹션 구조는 유지한다. 기존 `/api/task-detail` 스키마를 재사용하며 새 엔드포인트를 만들지 않는다.
7. **FR-07 monitor-server.py 모듈·정적 에셋 분리** — 6,937줄 모놀리스를 다음으로 분할한다:
   - CSS 인라인 → `scripts/monitor-server/static/style.css`
   - JS IIFE → `scripts/monitor-server/static/app.js` (`graph-client.js` 등 기존 분리된 것은 경로 이동만)
   - Python 렌더 함수 중복 통합 (`_section_subagents` / `_section_team` 등 유사 구조 통합, `_render_task_row` 경로 재정리)
   - HTTP 라우팅 분리 (단일 `do_GET` → `scripts/monitor-server/handlers/` 모듈)
   - 정적 에셋 서빙 엔드포인트(`/static/*`) 추가 — Python stdlib `http.server` 기반, MIME 타입 추론 포함
   - **증분 분할**: 한 번의 거대 커밋이 아니라 CSS → JS → Python 라우팅 → 렌더 함수 순의 **4개 이상 별도 커밋**으로 나눈다.
8. **FR-08 프롬프트·문서 중복 제거** — `skills/dev-monitor/SKILL.md` 포함 여부를 먼저 조사(FR-07 와 동일 브랜치에서 scope 확정)하여 대상 한정 후, v1~v4 누적 중복 설명을 제거하고 최신 버전 기준의 단일 레퍼런스로 정리한다. SKILL.md 는 한 화면(약 200줄) 이하를 목표로 한다.

## 3. 비목표

- **새 대시보드 시각 테마 개편**(색 팔레트 전면 변경) — v4 팔레트 유지, v5 는 phase 별 의미색 매핑만.
- **글로벌 필터 바 확장**(저장된 프리셋, URL 공유 템플릿 등) — v4 AC-27/AC-28 범위 유지.
- **EXPAND 패널 인라인 편집** — read-only 유지 (v4 비목표 계승).
- **실시간 활동 / WP 카드 fold 동작 변경** — v4 AC-7~AC-9 유지, v5 에서 건드리지 않음.
- **Dep-Graph 엔진 교체**(Cytoscape → 다른 라이브러리) — 기존 `graph-client.js` 유지, 스타일 토큰만 변경.
- **WP 카드 모바일 반응형** — 데스크톱(≥1280px) 기준으로만 레이아웃 검증.
- **Windows psmux 경로에서 monitor-server 동작성 변경** — monitor-server 는 순수 Python HTTP 서버라 영향 적음을 유지하되, Windows 에서 `static/` 서빙 경로가 `pathlib` 로 해석되는지만 회귀 검증.
- **새 API 엔드포인트 추가** — 전 기능이 기존 `/api/graph`, `/api/task-detail`, `/api/merge-status` 로 커버됨. **FR-07 의 `/static/*` 엔드포인트는 신규 API 가 아니라 에셋 서빙**이므로 예외.
- **LLM 실수 로그, WBS 독립 feature 디스패치** — 별도 feature 프로젝트로 분리됨 (§1 참조).

## 4. 사용자 시나리오

### S1. 우측 끝 Task 정보를 아이콘 클릭으로 안전하게 확인 (P1 FR-01)

사용자가 v4 에서 오른쪽 끝 WP 카드의 `TSK-05-03` 에 hover 했다. v4 에서는 툴팁이 뷰포트 오른쪽 경계를 넘어 절반이 잘렸다.

v5 에서는 Task 행에 (ⓘ) 아이콘이 있다. 클릭하면 팝오버가 **해당 Task 행 바로 위**에 뜨고, 꼬리(tail)가 행을 가리킨다. 화면 상단에 여유가 부족한 맨 위 Task 는 자동으로 **아래로 폴백**되어 렌더된다. 팝오버에는 그림자(`box-shadow`)와 명확한 폰트 크기 계층이 적용되어 v4 대비 읽기 쉽다. ESC 또는 외부 클릭으로 닫힌다. hover 는 더 이상 팝오버를 열지 않는다.

### S2. 한 화면에서 WP + 실시간 진행을 동시에 파악 (P0 FR-03)

사용자가 `/dev:dev-team monitor-v5` 로 20 Task 를 병렬 실행 중이다. v4 에서는 WP 카드가 좌측 60% 를 차지해 오른쪽 실시간 활동 / 팀 에이전트 / 서브에이전트 영역이 비좁아 pane preview 가 3줄만 보였다.

v5 에서는 그리드가 `2fr : 3fr` 로 바뀌어 왼쪽 WP 는 축소되고 오른쪽 실시간 영역이 확장된다. 팀 에이전트 카드 3개가 나란히 넓게 펼쳐지고, 각 pane preview 가 6줄씩 보인다 (FR-04). WP 카드는 `min-width` 가 재조정되어 가로 스크롤 없이 Task 행이 읽힌다.

### S3. 팀 에이전트 pane 로그를 6줄 깊이로 읽기 (P1 FR-04)

사용자가 `Worker-02` pane 에서 현재 테스트 출력이 어떻게 흐르고 있는지 보고 싶다. v4 에서는 `last 3 lines` 라벨 아래 3줄만 보여 `FAILED test_xxx` 라는 마지막 줄만 보였고 실패 원인(assertion diff) 은 잘렸다.

v5 에서는 `last 6 lines` 가 표시되어 assertion diff 와 파일 경로까지 한 화면에 나온다. pane 카드 padding 이 커져 시각적 여백도 확보된다.

### S4. 의존성 그래프에서 크리티컬 패스와 실패를 구분 (P0 FR-05)

사용자가 50 Task 프로젝트의 Dep-Graph 를 훑는다. v4 에서는 크리티컬 패스 노드(`.critical-path`) 와 failed 노드(`.node-failed`) 가 둘 다 `var(--fail)` 빨강이라, 한눈에 "지금 망가진 노드" 와 "시간이 오래 걸려 전체 일정을 좌우하는 노드" 를 구분할 수 없었다.

v5 에서는 크리티컬 패스 노드가 앰버(`#f59e0b`) 테두리 + 배경 틴트로 표시되고, failed 노드는 빨강을 유지한다. 범례(legend) 에 두 상태가 별도 줄로 기재된다. 사용자는 한눈에 "크리티컬 패스 상의 노드 5개 중 1개가 failed" 임을 파악해 우선순위를 조정한다.

### S5. Phase 배지 색상으로 20 Task 상태를 훑기 (P1 FR-06)

병렬 20 Task 상황. v4 에서는 Task 배지가 모두 비슷한 회색·흰색 톤이라, 20개 중 Design 단계 몇 개 / Build 몇 개 / Test 몇 개 / Done 몇 개인지 숫자 세기가 번거로웠다.

v5 에서는 배지가 phase 별 색으로 나뉜다:
- `[Design]` 파랑
- `[Build]` 시안
- `[Test]` 노랑
- `[Done]` 녹색
- `[Failed]` 빨강
- `[Bypass]` 보라

진행 중 Task (`.running` signal 있음) 는 배지 안에 회전 스피너가 돈다. **같은 색 규칙이 의존성 그래프 노드에도 적용**되어 WP 카드와 Dep-Graph 가 시각적으로 일치한다. 사용자는 배지 색 분포만으로 "지금 Test 단계가 몰려 있다" 를 파악한다.

### S6. EXPAND 패널에서 진행 요약을 즉시 확인 (P2 FR-02)

사용자가 `TSK-03-02` 의 `↗` 을 눌러 슬라이드 패널을 연다. v4 에서는 패널 최상단에 `TSK-03-02 / WP-03 / fullstack / opus` 메타만 보였고, 현재 status 와 elapsed 를 보려면 `§ state.json` 섹션을 펼쳐야 했다.

v5 에서는 패널 상단에 **진행 요약 헤더**가 sticky 로 붙는다:

```
[Build] ⟳   elapsed 4m 12s
recent phase:
  • 14:32:11  build_failed        (im→im,  2m 03s)
  • 14:30:08  build_start         (dd→im,  -)
  • 14:28:12  design_complete     (dd→dd,  1m 56s)
```

사용자는 헤더만 보고 "빌드 실패가 발생해 멈췄다" 를 즉시 파악, 하단 섹션(wbs / state / 아티팩트 / 로그)을 필요한 순서로 스크롤한다. 헤더는 본문 스크롤에도 고정되어 맥락이 유지된다. `/api/task-detail` 스키마는 변경되지 않으므로 기존 응답의 `state.last`, `state.phase_history`, `state.elapsed_seconds` 로 헤더를 구성한다.

### S7. monitor-server.py 분할 후 동시 머지 회귀 방지 (P2 FR-07)

`WP-05-monitor-v5` 에서 두 명이 동시에 작업한다. A 는 FR-01 팝오버 CSS 변경, B 는 FR-03 그리드 비율 변경. v4 라면 둘 다 `monitor-server.py` 의 인라인 CSS 문자열을 수정해 머지 충돌 + 시각적 diff 가 6,000 줄 중 어디인지 찾기 어려웠다.

v5 이후에는 A 는 `static/style.css` 의 팝오버 섹션을, B 는 같은 파일의 그리드 섹션을 수정한다. 머지 시 자동 머지가 가능한 선에서 해결되며, 충돌이 나도 CSS 섹션 단위로 시각 diff 가 명확하다. Python 쪽은 라우팅/렌더가 `handlers/` 로 쪼개져 있어 동시 편집 면적이 줄었다.

### S8. dev-monitor SKILL.md 가 한 화면으로 읽힌다 (P2 FR-08)

신규 기여자가 `/dev-monitor` 의 역할을 이해하려고 SKILL.md 를 연다. v4 에서는 v1~v4 누적된 "이전 버전에서는..." 설명이 반복되어 500 줄을 넘겼다. v5 에서는 최신 구현 기준의 단일 레퍼런스로 정리되어 약 200 줄로 줄어든다. 구버전 이력은 `docs/monitor-vN/prd.md` 에 남겨두고 SKILL.md 에서는 현재 동작만 기술한다.

### S9. dev-plugin 자체 서브프로젝트 워크플로 검증 (메타 목적)

`docs/monitor-v5/` 는 `docs/monitor-v4/` 에 이은 두 번째 대형 서브프로젝트 운용 사례다. `/dev-team monitor-v5` 실행 시:

- tmux window 이름이 `WP-XX-monitor-v5` 패턴.
- signal scope 가 `dev-plugin-monitor-v5` 패턴.
- 대시보드 서브프로젝트 탭에 `monitor-v5` 가 `discover_subprojects()` 로 자동 노출된다.
- monitor-v4 의 완료 Task 들은 monitor-v5 탭에서 보이지 않는다 (스코프 격리 검증).

메타 검증 항목으로만 다루며 별도 AC 는 두지 않는다.

## 5. 기능 요구사항

### FR-01: Task 팝오버 — hover 제거 + 아이콘 클릭 + 위쪽 배치 [P1]

**현재 동작 (v4)**
- Task 행 전체 mouseenter 시 300ms 이내에 `#trow-tooltip` 이 Task 행의 **오른쪽에 absolute 포지션**으로 렌더. mouseleave 시 숨김.
- 오른쪽 끝 WP 의 Task 에서 툴팁이 뷰포트를 벗어남.

**목표 동작 (v5)**
- Task 행에 `<button class="task-info-btn" aria-label="작업 정보">ⓘ</button>` 을 추가. **클릭**으로만 팝오버 열림.
- 팝오버 기본 위치: Task 행 **바로 위**(top). 꼬리(tail) 가 행 중앙을 가리킴. 화면 상단 여유가 부족하면 자동으로 **아래로 폴백**. 좌우는 화면 경계를 넘지 않도록 clamp.
- 디자인: 그림자(`box-shadow: 0 8px 24px rgba(0,0,0,0.18)`), 2 단계 폰트 스케일(타이틀/본문), 꼬리 삼각형, 내부 패딩 확대.
- 닫기: 외부 클릭 / ESC / 같은 (ⓘ) 재클릭.
- hover 는 팝오버를 열지 않는다.

**인수 조건**
- AC-FR01-a: Task 행에 `.task-info-btn` 요소가 존재하고 `aria-label` 을 가진다.
- AC-FR01-b: mouseenter 만으로는 팝오버가 열리지 않는다 (`#trow-tooltip.display == 'none'` 유지).
- AC-FR01-c: (ⓘ) 클릭 시 팝오버가 열리고 기본 위치는 Task 행 상단. 팝오버 `getBoundingClientRect().bottom <= row.getBoundingClientRect().top + 4` (꼬리 포함 허용 오차).
- AC-FR01-d: 화면 상단 여유가 팝오버 높이 미만일 때 팝오버가 행 하단으로 이동한다 (`top > row.bottom`).
- AC-FR01-e: ESC / 외부 클릭 / 같은 (ⓘ) 재클릭으로 닫힌다.
- AC-FR01-f: v4 의 hover 기반 E2E 테스트(`test_task_tooltip_hover`)가 **click 기반으로 마이그레이션**되어 통과한다. hover 만으로 열리는 옛 테스트는 삭제.

### FR-02: Task EXPAND 슬라이드 패널 — 진행 요약 헤더 [P2]

**현재 동작 (v4)**
- 패널 상단에 `TSK-ID / WP-ID / source / model` 메타만 표시.
- 진행 상태는 `§ state.json` 섹션을 펼쳐야 보인다.

**목표 동작 (v5)**
- 패널 상단에 sticky 진행 요약 헤더 추가:
  - 현재 phase 배지 (FR-06 색 적용) + `.running` 스피너 (있으면)
  - `elapsed` (hh:mm:ss 또는 n분 n초)
  - 최근 `phase_history` 이벤트 **3건**, 시간 역순, `{at} {event} ({from}→{to}, {elapsed})` 형식
- 헤더는 `position: sticky; top: 0` 로 패널 스크롤에도 고정.
- 본문 4섹션(wbs/state/아티팩트/로그) 구조 유지.
- `/api/task-detail` 스키마 변경 없음 — 기존 `state.last`, `state.phase_history`, `state.elapsed_seconds` 로 구성.

**인수 조건**
- AC-FR02-a: 패널 DOM 에 `<header class="task-panel-summary">` 요소가 존재한다.
- AC-FR02-b: 헤더에 현재 phase 배지(FR-06 색 토큰 적용) + `elapsed` 텍스트가 포함된다.
- AC-FR02-c: 헤더에 `phase_history` 최근 3건이 최신순으로 렌더된다 (`phase_history.length < 3` 이면 실제 개수만).
- AC-FR02-d: 패널 본문을 스크롤해도 헤더 가시성이 유지된다 (`getComputedStyle(header).position === 'sticky'`).
- AC-FR02-e: `/api/task-detail` 응답 스키마가 v4 와 동일하다 (신규 필드 없음, regression 없음).

### FR-03: 메인 그리드 비율 반전 `3fr:2fr` → `2fr:3fr` [P0]

**현재 동작 (v4)**
- CSS: `main { grid-template-columns: 3fr 2fr; }`. 왼쪽 WP 60%, 오른쪽 실시간 영역 40%.

**목표 동작 (v5)**
- `main { grid-template-columns: 2fr 3fr; }`. 왼쪽 WP 40%, 오른쪽 실시간 영역 60%.
- WP 카드 `min-width` 를 축소된 컬럼에 맞춰 재조정 (예: `min-width: 380px` → 필요 시 조정) — 가로 스크롤이 발생하지 않도록.
- 기존 fold/필터/WP 머지 뱃지 레이아웃이 새 폭에서도 정상 표시되어야 함.

**인수 조건**
- AC-FR03-a: `main` 요소 computed `grid-template-columns` 가 `2fr 3fr` 비율을 반영한다 (실제 픽셀 값은 뷰포트 폭에 따라 다름, 비율 검증).
- AC-FR03-b: 1280px 뷰포트 기준 WP 영역 폭이 메인 컨테이너 폭의 약 40% (±3%) 이다.
- AC-FR03-c: WP 카드 내부에 가로 스크롤바가 생기지 않는다 (Task 행 텍스트가 잘려도 overflow 허용, 스크롤바 아님).
- AC-FR03-d: 팀 에이전트/서브에이전트/실시간 활동 섹션이 확장된 폭을 활용해 더 넓게 렌더된다.

### FR-04: 팀 에이전트 pane 카드 높이 2배 [P1]

**현재 동작 (v4)**
- `.pane-preview { max-height: 4.5em; }` (약 3줄)
- 라벨: `last 3 lines`
- 카드 padding: 기본값

**목표 동작 (v5)**
- `.pane-preview { max-height: 9em; }` (약 6줄)
- 라벨: `last 6 lines`
- 카드 padding 확대 (상하 좌우 +4~8px 수준)
- 서버 측 `tail` 수집도 6줄 반환으로 조정 (기존 `pane-tail N` 인자 조정)

**인수 조건**
- AC-FR04-a: `.pane-preview` computed `max-height` 가 `9em` 이상.
- AC-FR04-b: 라벨 텍스트가 `last 6 lines` (ko: `최근 6줄`).
- AC-FR04-c: 서버가 pane tail 6줄을 반환한다 (단위 테스트로 `tail_lines=6` 검증).
- AC-FR04-d: 카드 padding 이 v4 대비 확대되어 computed `padding` 총합이 증가한다.

### FR-05: 의존성 그래프 크리티컬 패스/failed 색 분리 [P0]

**현재 동작 (v4)**
- 크리티컬 패스 노드 CSS: `border-color: var(--fail)` — 빨강
- failed 노드 CSS: `background: var(--fail)` — 빨강
- 같은 토큰으로 칠해져 구분 불가

**목표 동작 (v5)**
- 크리티컬 패스 노드: 테두리 앰버(`#f59e0b`) + 옅은 앰버 배경 틴트(`rgba(245, 158, 11, 0.12)`)
- failed 노드: 기존 `var(--fail)` 빨강 유지
- 두 클래스가 동시 적용될 수 있음 (크리티컬 패스 + failed): failed 색이 우선 (specificity 명시)
- Dep-Graph 범례에 두 상태가 **별도 항목**으로 표기

**인수 조건**
- AC-FR05-a: 크리티컬 패스 노드의 computed `border-color` 가 `#f59e0b` 계열 RGB.
- AC-FR05-b: failed 노드의 computed `background-color` 가 `var(--fail)` 계열 RGB (v4 유지).
- AC-FR05-c: 동시 적용 시 failed 색이 우선된다 (단위 테스트로 CSS specificity 검증).
- AC-FR05-d: Dep-Graph 범례 DOM 에 `크리티컬 패스` 와 `실패` 가 별도 `<li>`/`<div>` 로 존재한다.

### FR-06: Task phase 배지 색상 phase별 구분 + 스피너 + Dep-Graph 적용 [P1]

**현재 동작 (v4)**
- 배지 텍스트만 phase 에 따라 바뀜 (`Design`/`Build`/`Test`/`Done`/`Failed`/`Bypass`)
- 색 토큰은 대부분 공통 회색 계열
- 진행 중 스피너는 배지 **옆**에 별도 요소 (`.spinner`, v4 AC-5)
- Dep-Graph 노드는 별도 상태 색 체계

**목표 동작 (v5)**
- phase 별 색 토큰 매핑:
  - Design → `var(--accent)` (파랑)
  - Build → `var(--run)` (시안/청록)
  - Test → `var(--pending)` (노랑)
  - Done → `var(--done)` (녹색)
  - Failed → `var(--fail)` (빨강)
  - Bypass → `#a855f7` 또는 `var(--bypass)` (보라) — 신규 토큰
- 배지 CSS: `.phase-badge[data-phase="design"] { background: var(--accent-tint); color: var(--accent); }` 형식
- 진행 중(`.running` signal) 스피너는 배지 **내부**에 위치 (v4 의 배지 옆에서 배지 안으로 이동).
- **Dep-Graph 노드도 동일한 토큰** 으로 칠해진다 (status → phase 매핑: `[dd]=design`, `[im]=build`, `[ts]=test`, `[xx]=done`). failed / bypass 는 기존 경로 유지.

**인수 조건**
- AC-FR06-a: 배지 DOM 에 `data-phase="{design|build|test|done|failed|bypass}"` 속성이 존재한다.
- AC-FR06-b: 각 phase 배지의 computed `background-color` 와 `color` 가 해당 토큰과 일치한다 (6 phase 에 대해 각각 검증).
- AC-FR06-c: `.running` signal 존재 Task 배지 내부에 `.phase-badge .spinner` 요소가 있고 CSS animation 이 적용된다 (v4 의 외부 `.spinner` 는 제거되거나 배지 내부로 이전).
- AC-FR06-d: Dep-Graph 노드의 색이 status → phase 매핑에 따라 phase 토큰과 일치한다 (`[dd]` 노드가 accent 색, `[im]` 노드가 run 색 등).
- AC-FR06-e: Bypass 토큰(`var(--bypass)` 또는 `#a855f7`)이 CSS 전역 변수로 정의된다.

### FR-07: monitor-server.py 모듈·정적 에셋 분리 [P2]

**현재 동작 (v4)**
- `scripts/monitor-server.py` 6,937줄 단일 파일. HTML/CSS/JS 가 Python 문자열로 인라인.
- HTTP 라우팅이 단일 `do_GET` 메서드에 60+ 분기.
- 렌더 함수들이 `_section_subagents` / `_section_team` 등 유사 구조로 중복.

**목표 동작 (v5)**
- 새 구조:
  ```
  scripts/monitor-server/
    __init__.py
    server.py          # 엔트리포인트 (ThreadingHTTPServer)
    handlers/
      __init__.py
      api.py           # /api/* 라우팅
      static.py        # /static/* 에셋 서빙
      pages.py         # / (index) 렌더
    render/
      __init__.py
      sections.py      # _section_* 통합
      task_row.py      # _render_task_row
      graph.py         # graph payload 빌더
    static/
      style.css        # 기존 인라인 CSS
      app.js           # 기존 인라인 JS (IIFE)
      graph-client.js  # 이미 분리된 것 이동
  scripts/monitor-server.py   # shim — scripts/monitor-server.server:main 로 forwarding (하위 호환)
  ```
- `/static/*` 엔드포인트: 요청 경로를 `static/` 하위로 제한(path traversal 차단), MIME 은 `mimetypes.guess_type` 사용.
- 기존 `monitor-launcher.py` 의 subprocess 호출 인터페이스(`--port`, `--docs`) 는 그대로 유지.
- **증분 분할 원칙**: 최소 4개 이상의 별도 커밋/PR 으로 나눈다:
  1. CSS 추출 + `/static/style.css` 엔드포인트
  2. JS 추출 + `/static/app.js` 엔드포인트
  3. 렌더 함수 모듈화 (`render/`)
  4. 핸들러/라우팅 모듈화 (`handlers/`)
- 각 단계 후 기존 E2E 및 단위 테스트 전부 green 상태 확인.
- 파일 크기 상한: 각 모듈 파일 최대 **800줄** (기존 6,937줄 대비 ≥ 85% 감소).

**인수 조건**
- AC-FR07-a: `scripts/monitor-server/` 디렉토리가 존재하고 `server.py` / `handlers/` / `render/` / `static/` 가 생성된다.
- AC-FR07-b: 기존 `scripts/monitor-server.py` 가 존재하며, 실행 시 `scripts/monitor-server/server.py:main` 으로 forwarding 한다 (하위 호환).
- AC-FR07-c: 각 Python 모듈 파일이 800줄 이하.
- AC-FR07-d: `GET /static/style.css` 가 200 + `text/css` MIME 으로 응답한다. `GET /static/app.js` 는 `application/javascript`.
- AC-FR07-e: `GET /static/../../../etc/passwd` 형태의 path traversal 시도가 404 또는 403 으로 차단된다.
- AC-FR07-f: v4 의 모든 기존 API 엔드포인트(`/api/graph`, `/api/task-detail`, `/api/merge-status`)가 동일 스키마로 응답한다.
- AC-FR07-g: Git 히스토리에 **4개 이상 별도 커밋**이 남는다 (CSS/JS/렌더/라우팅). squash merge 시에도 커밋 트레일러에 단계 표기.
- AC-FR07-h: Windows 에서 `static/` 서빙 경로가 `pathlib.Path` 로 해석되어 경로 분리자 이슈 없이 응답한다 (CI 가 Windows runner 없다면 psmux 환경 수동 검증 노트).

### FR-08: 프롬프트·문서 중복 제거 [P2]

**현재 동작 (v4)**
- `skills/dev-monitor/SKILL.md` 가 v1~v4 누적 설명으로 길어짐 (정확한 줄 수는 FR-08 선행 조사에서 확인).
- monitor-server 관련 참고 문서(`docs/monitor-v*/README` 등)가 버전별로 유사 문장을 반복.

**목표 동작 (v5)**
- FR-08 시작 시점에 **범위 조사**: `skills/dev-monitor/SKILL.md`, `docs/monitor-v*/` 하위 파일, `scripts/monitor-launcher.py` docstring 중 실제 중복이 있는 파일을 식별해 대상 목록을 확정한다.
- 대상별 정리:
  - `skills/dev-monitor/SKILL.md`: 최신 구현 기준의 단일 레퍼런스. 구버전 이력 제거(또는 "참고: `docs/monitor-vN/prd.md`" 한 줄로 대체). 목표 약 200줄 이하.
  - 기타 대상: 현행 사용되지 않는 중복 섹션 제거.
- 구버전 PRD (`docs/monitor-v1/`~`docs/monitor-v4/`) 는 보존 (역사적 가치).

**인수 조건**
- AC-FR08-a: FR-08 브랜치 초기 커밋에 "범위 조사 결과" 노트가 포함된다 (조사한 파일 목록 + 중복 문장 카운트).
- AC-FR08-b: `skills/dev-monitor/SKILL.md` 의 줄 수가 v4 대비 유의미하게 감소 (목표 200줄 이하).
- AC-FR08-c: `/dev-monitor` 스킬 트리거(자연어 + 슬래시) 동작이 회귀 없이 유지된다 (기존 단위 테스트 pass).
- AC-FR08-d: `docs/monitor-v1/` ~ `docs/monitor-v4/` 파일은 삭제되지 않는다 (보존 확인).

## 6. 비기능 요구사항

| 영역 | 요구사항 |
|------|---------|
| **성능** | 대시보드 폴링 주기 5초 유지 (v4 기준). FR-07 분할 후에도 첫 렌더 응답 시간(TTFB) 이 v4 대비 +200ms 이내. |
| **성능** | 정적 에셋(`/static/*`) 은 `Cache-Control: max-age=60` 헤더 부여 (개발 중 빈번한 수정 고려). |
| **접근성** | FR-01 팝오버는 키보드 Enter/Space 로 열고 ESC 로 닫을 수 있다 (v4 는 마우스 전용이었음 — v5 에서 키보드 열기 지원 추가). |
| **접근성** | FR-06 phase 색상은 WCAG AA contrast 를 만족한다 (배경 틴트 vs 텍스트 ≥ 4.5:1). |
| **유지보수성** | FR-07 분할 후 각 Python 모듈 ≤ 800줄, CSS ≤ 1,500줄, JS ≤ 2,000줄 (현 app.js 규모 기준 조정 가능). |
| **유지보수성** | 테스트 커버리지: 기존 `scripts/test_monitor_*.py` 의 모든 테스트가 새 경로(`scripts/monitor-server/`)에서 import 되어 통과. |
| **플랫폼** | macOS / Linux / Windows(psmux + 순수 Python HTTP) 에서 동일하게 동작. `static/` 서빙은 `pathlib` 기반으로 경로 구분자 이슈 없음. |
| **런타임 의존성** | Python 3 stdlib only. 외부 pip 패키지 추가 금지. |
| **토큰 예산** | 본 릴리스는 워커 프롬프트에 영향 없음 (대시보드 전용). LLM 추가 토큰 소비 0 (FR-08 의 SKILL.md 단축은 오히려 절감). |
| **보안** | `/static/*` 은 `scripts/monitor-server/static/` 디렉토리 외부 접근 차단 (path traversal 방어). |

## 7. 마일스톤·우선순위

| 주차 | 목표 | FR |
|------|------|-----|
| W1 | P0 완료 — 레이아웃/색상 즉시 효과 | FR-03, FR-05 |
| W2 | P1 시작 — 인터랙션/카드 크기 | FR-01, FR-04, FR-06 |
| W3 | P2 착수 — EXPAND 강화 + 리팩토링 스텝 1-2 | FR-02, FR-07 (CSS/JS 추출) |
| W4 | P2 완결 — 리팩토링 스텝 3-4 + 문서 정리 | FR-07 (렌더/라우팅), FR-08 |

**우선순위 합계**: FR 8건 — P0 2건, P1 3건, P2 3건.

## 8. 제약 사항

- **e2e 테스트 마이그레이션 (FR-01)**: v4 의 `test_task_tooltip_hover` (hover → 팝오버 표시) 는 FR-01 에서 **click 기반 테스트로 마이그레이션** 필요. hover 단언이 남아 있으면 즉시 회귀로 감지된다. 마이그레이션 미완료 상태로 FR-01 을 릴리스할 수 없다.
- **동시 머지 회귀 방지 (FR-07)**: 리팩토링은 **증분 분할**(CSS/JS/렌더/라우팅 최소 4커밋)로 진행한다. 단일 거대 PR 금지. 각 스텝 후 기존 테스트 green 확인 없이는 다음 스텝 진행 금지. 메모리 `project_monitor_server_inline_assets.md` 의 경고 사례를 재발시키지 않는다.
- **Windows / psmux 지원 유지**: monitor-server 는 순수 Python HTTP 서버라 영향이 적지만, FR-07 의 `/static/*` 경로 해석은 `pathlib.Path` 로 이뤄져야 하며 문자열 `os.path.join` 금지. `open(..., "w", encoding="utf-8", newline="\n")` 규칙(CLAUDE.md) 준수.
- **Python 3 stdlib only**: 외부 pip 의존성 도입 금지. 정적 에셋 서빙도 `http.server` + `mimetypes` 조합으로 처리.
- **기존 API 호환성**: `/api/graph`, `/api/task-detail`, `/api/merge-status` 응답 스키마를 변경하지 않는다 (v4 클라이언트 도구와의 호환성). 새 필드 추가는 허용하나 기존 필드 제거/이름 변경 금지.
- **스킬 트리거 보존 (FR-08)**: `dev-monitor` SKILL.md 단축 시 `description` 필드의 자연어 트리거 키워드(모니터링/대시보드/monitor 등)를 제거해서는 안 된다 (CLAUDE.md 의 NL 트리거 규칙).
- **dev-monitor SKILL.md 범위 확정 선행 (FR-08)**: FR-08 은 "조사 후 범위 한정" 을 선행 단계로 포함한다. 조사 없이 파일 전체를 재작성하지 않는다 (플랜 문서의 리스크 항목 대응).

## 9. 수용 기준 (종합)

각 FR 의 인수 조건은 §5 에 정의됨. 아래는 릴리스 차단 기준의 집약:

| # | 기준 | 우선순위 | 검증 방법 |
|---|------|---------|---------|
| AC-1 | FR-03 메인 그리드가 `2fr:3fr` 비율로 렌더된다 | P0 | 단위 테스트 + 브라우저 inspect (1280px) |
| AC-2 | FR-03 WP 카드에 가로 스크롤이 생기지 않는다 | P0 | E2E `test_wp_card_no_horizontal_scroll` |
| AC-3 | FR-05 크리티컬 패스 노드가 앰버, failed 노드가 빨강으로 **별도 색** 렌더 | P0 | 단위 테스트 `test_graph_critical_path_amber_failed_red` |
| AC-4 | FR-05 Dep-Graph 범례에 두 상태가 별도 항목으로 존재 | P0 | 단위 테스트 `test_graph_legend_has_critical_and_failed` |
| AC-5 | FR-01 Task 팝오버가 hover 로 열리지 않고, (ⓘ) 클릭 시 행 **상단** 에 열린다 | P1 | E2E `test_task_popover_click_only_above_row` |
| AC-6 | FR-01 상단 여유 부족 시 팝오버가 하단으로 폴백 | P1 | E2E `test_task_popover_flips_below` |
| AC-7 | FR-01 v4 `test_task_tooltip_hover` 가 click 기반으로 마이그레이션되어 통과 | P1 | 테스트 파일 diff 검증 |
| AC-8 | FR-04 pane preview `max-height: 9em`, 라벨 `last 6 lines` | P1 | 단위 테스트 `test_pane_preview_6_lines` |
| AC-9 | FR-06 배지에 `data-phase` 속성 + phase 별 색 토큰 적용 | P1 | 단위 테스트 `test_phase_badge_color_tokens` |
| AC-10 | FR-06 `.running` Task 배지 **내부** 에 스피너 요소 | P1 | 단위 테스트 `test_running_spinner_inside_badge` |
| AC-11 | FR-06 Dep-Graph 노드 색이 status → phase 토큰과 일치 | P1 | 단위 테스트 `test_graph_node_phase_color_tokens` |
| AC-12 | FR-02 EXPAND 패널에 sticky 진행 요약 헤더 존재, `phase_history` 최근 3건 렌더 | P2 | 단위 테스트 `test_task_panel_summary_header` |
| AC-13 | FR-02 `/api/task-detail` 스키마 변경 없음 | P2 | 단위 테스트 `test_api_task_detail_schema_unchanged` |
| AC-14 | FR-07 `scripts/monitor-server/` 디렉토리 + 모듈 분할, 각 파일 ≤ 800줄 | P2 | 정적 체크 스크립트 `test_monitor_server_file_sizes` |
| AC-15 | FR-07 `/static/style.css`, `/static/app.js` 가 200 + 올바른 MIME 응답 | P2 | 단위 테스트 `test_static_assets_served` |
| AC-16 | FR-07 `/static/../../` path traversal 시도가 403/404 로 차단 | P2 | 단위 테스트 `test_static_path_traversal_blocked` |
| AC-17 | FR-07 분할 중/후 기존 단위·E2E 테스트 regression 없음 | P2 | `pytest -q scripts/` 전체 green |
| AC-18 | FR-07 Git 히스토리에 최소 4개 분할 커밋 존재 (CSS/JS/렌더/라우팅) | P2 | `git log --oneline` 수동 검증 |
| AC-19 | FR-08 SKILL.md 줄 수 감소 + `/dev-monitor` 자연어 트리거 동작 유지 | P2 | 트리거 단위 테스트 + wc -l 비교 |
| AC-20 | v4 의 AC-1 ~ AC-28 은 전원 regression 없이 유지 | 전체 | `pytest -q scripts/` |

## 10. 릴리스 조건

- 모든 P0 수용 기준(AC-1 ~ AC-4) 충족.
- P1 수용 기준(AC-5 ~ AC-11) 충족 또는 릴리스 후 hotfix 합의.
- P2 수용 기준(AC-12 ~ AC-19) 충족 또는 후속 릴리스로 분할 합의.
- v4 기존 수용 기준(AC-20) 전원 regression 없음.
- `~/.claude/plugins/marketplaces/dev-tools/` 에 변경 동기화 완료 (CLAUDE.md 규약).
- `docs/monitor-v5/` 가 자체 서브프로젝트로 `discover_subprojects()` 에 인식되어 대시보드 탭에 노출된다 (메타 검증).
- **토큰 예산**: 워커 추가 토큰 0 (대시보드 전용 릴리스, LLM 프롬프트 미개입). FR-08 의 SKILL.md 단축으로 오히려 절감.
- **구조 건전성**: FR-07 후 `scripts/monitor-server/` 하위 Python 모듈 최대 800줄 규칙 + CSS/JS 상한 준수. 위반 시 릴리스 차단.
