# TSK-01-01: 단계 타임라인 섹션 제거 - 설계

## 요구사항 확인
- `scripts/monitor-server.py`에서 Phase Timeline(단계 타임라인) 섹션을 DOM/SSR/CSS/i18n/네비게이션 전층에서 완전히 제거한다 (PRD §2 P0-3, §4 S5, §5 AC-1).
- `_section_phase_timeline`·`_timeline_rows`·`_timeline_svg`·`_PHASE_TO_SEG`·`_TIMELINE_*` 상수 및 `data-section="phase-timeline"` 래퍼 제거 — 다른 섹션(wp-cards, live-activity, dep-graph, features, team, subagents)에 회귀 없이.
- `.tl-` 전용 CSS 블록(`.tl-row`, `.tl-track`, `.tl-axis`, `.tl-now`, `.timeline-svg .tl-*`, `.timeline-head`, `.panel.timeline`, `.timeline-more`)만 정확히 제거하고, 다른 의미의 접두어(`.task-`, `.trow-tooltip` 등)를 보존한다.

## 타겟 앱
- **경로**: N/A (단일 앱 — `scripts/monitor-server.py` 모놀리식 SSR 서버)
- **근거**: monitor-v4는 별도 앱 분리 없이 `scripts/monitor-server.py` 단일 파일에 HTML·CSS·JS가 인라인된 구조.

## 구현 방향
Phase Timeline 섹션을 **6개 경로에 걸쳐 일관되게 삭제**한다: (1) SSR 함수/헬퍼/상수, (2) `render_dashboard`의 section 조립 + 래핑 + body 주입, (3) 인라인 CSS `.tl-*`·`.timeline-*`·`.panel.timeline`, (4) i18n 테이블 2곳의 `phase_timeline` 키, (5) `_SECTION_ANCHORS` 튜플의 `"timeline"`, `_SECTION_EYEBROWS["timeline"]`, `_SECTION_DEFAULT_HEADINGS["timeline"]`, (6) sticky-header nav `<a href="#timeline">`. **dep-graph 색 매핑과 무관함을 사전 grep으로 검증**한 뒤 제거한다 (`_PHASE_TO_SEG`는 `_section_phase_timeline` 내부 로컬 상수, `.tl-dd/.tl-im/.tl-ts/.tl-xx`는 `.timeline-svg` scoped). 제거 후 남는 섹션은 WP Cards → Live Activity → Dep-Graph → Features → Team → Subagents 순으로 자연스럽게 연결된다.

## 파일 계획

**경로 기준:** 모든 파일 경로는 프로젝트 루트 기준으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | SSR 서버 + 라우터(`do_GET`) + 메뉴/네비게이션(sticky-header `<a href="#timeline">`). Phase Timeline 관련 SSR/CSS/i18n/nav/상수를 모두 제거 — **라우터 + 메뉴 + 섹션이 한 파일에 인라인된 모놀리식 SSR** | 수정 |
| `scripts/test_monitor_render.py` | L714 주석(우측 컬럼 섹션 설명에서 `phase-timeline` 제거) 및 L757·L762·L767·L772·L1290·L1294의 timeline 테스트 제거 + 새 회귀 테스트(`phase-timeline` 섹션 미존재, `.tl-` 패턴 부재) 추가 | 수정 |
| `scripts/test_monitor_render_tsk04.py` | `_timeline_rows` / `_section_phase_timeline` 단위 테스트 블록 제거 (L344 이하). 라이브 활동 관련 테스트는 보존 | 수정 |

> **모놀리식 SSR 구조**: monitor-server.py 한 파일이 라우터(`do_GET` 디스패치), 메뉴/네비게이션(sticky-header HTML 블록 L2275-L2281), CSS(`DASHBOARD_CSS` 상수), i18n 테이블, 각 섹션 렌더 함수를 모두 담고 있다. 별도 라우터/사이드바 파일이 존재하지 않으므로 "라우터 파일"과 "메뉴 파일"의 역할도 이 단일 파일에서 수행한다 (frontend 도메인 파일 계획 요건 충족).

## 진입점 (Entry Points)

본 Task는 **기존 섹션의 제거**로 신규 페이지/신규 메뉴/신규 라우트를 추가하지 않는다. 아래는 영향 받는 기존 진입점 기술.

- **사용자 진입 경로**: 브라우저에서 `dev-monitor` 서버 기동 → 상단 sticky-header 네비게이션의 `Timeline` 링크가 **사라졌음**을 확인. 기존 대시보드 스크롤 시 WP Cards → Live Activity → Dep-Graph → Features → Team → Subagents 순서로 섹션이 연결되며, 그 사이에 Phase Timeline 블록이 존재하지 않아야 한다.
- **URL / 라우트**: `http://localhost:7321/?subproject=monitor-v4` (WBS `entry-point` 필드 그대로). 라우트 자체는 변경 없음 — 경로별 핸들러가 반환하는 HTML 내용만 변경.
- **수정할 라우터 파일**: `scripts/monitor-server.py`의 `do_GET`/`render_dashboard` 함수 (L4180 `sections` dict). `sections["phase-timeline"] = _section_phase_timeline(...)` 항목 삭제 + L4207-L4211의 별도 wrap 블록 삭제. 본 프로젝트는 **라우터가 같은 파일에 인라인**이므로 별도 `routes.ts`/`App.tsx` 계열 파일이 없다.
- **수정할 메뉴·네비게이션 파일**: `scripts/monitor-server.py`의 sticky-header nav HTML (L2275-L2281). 구체 수정 위치: L2280의 `'<a href="#timeline">Timeline</a>'` 리터럴 제거. 동시에 `_SECTION_ANCHORS` 튜플(L999)에서 `"timeline"` 제거 — 이 튜플이 앵커 화이트리스트 역할.
- **연결 확인 방법**: dev-test 단계에서 `render_dashboard(...)` 반환 HTML을 문자열 단언으로 검증 — `data-section="phase-timeline"` 부재 + `href="#timeline"` 부재 + `.tl-` 접두 CSS 클래스 부재. 네거티브 케이스이므로 E2E 클릭 시퀀스 대신 pytest unit 단언으로 충분하다 (dev-test reachability gate는 신규 페이지 도달 가능성 검증용이며, 본 Task는 **기존 요소 제거** 성격이라 해당 gate 미적용).

## 주요 구조

제거할 식별자 (grep 검증 대상):

| 카테고리 | 식별자 | 위치 (line 추정) |
|----------|--------|-----------------|
| SSR 함수 | `_section_phase_timeline` | L3614-L3729 |
| SSR 헬퍼 | `_timeline_rows`, `_timeline_svg`, `_x_of` (`_x_of`는 timeline 전용일 경우만 — grep으로 타 호출 확인) | L3472-L3611 |
| 상수 | `_TIMELINE_MAX_ROWS`, `_TIMELINE_SPAN_MINUTES` | L3282-L3283 |
| 로컬 상수 | `_PHASE_TO_SEG` (`_section_phase_timeline` 내부) | L3649 |
| 섹션 조립 | `sections["phase-timeline"] = _section_phase_timeline(...)` 및 `"phase-timeline"` 별도 wrap 블록 (L4207-L4211) | L4191-L4192, L4207-L4211 |
| i18n 키 | `_I18N["ko"]["phase_timeline"]` / `_I18N["en"]["phase_timeline"]` (두 i18n dict 모두) | L59, L67, L1012, L1029 |
| 섹션 메타 | `_SECTION_ANCHORS` 튜플의 `"timeline"`, `_SECTION_EYEBROWS["timeline"]`, `_SECTION_DEFAULT_HEADINGS["timeline"]` | L999, L2198, L2208 |
| 네비게이션 | sticky-header `<a href="#timeline">Timeline</a>` | L2280 |
| CSS | `.timeline{...}`, `.timeline-head`, `.tl-row`, `.tl-row .lbl`, `.tl-track`, `.tl-track .seg-*`, `.tl-axis`, `.tl-axis .tick`, `.tl-axis .tlabel`, `.tl-now`, `.tl-now::before`, 주석 `/* 7b. Phase Timeline SVG */` 블록 (`.timeline-svg`, `.timeline-svg .tl-dd/.tl-im/.tl-ts/.tl-xx/.tl-fail`), `.timeline-more` | L1639-L1688, L3699 근처 CSS 참조 |

**보존할 식별자** (오삭제 금지):
- `.trow-tooltip`, `.task-*`, `#trow-tooltip` — tooltip 전용.
- `_section_phase_history` 및 `"phase-history"` 섹션 — 본 Task 범위 외.
- `_section_live_activity` — 본 Task 범위 외.

## 데이터 흐름
입력: `scripts/monitor-server.py` 소스 전문 → 처리: 위 식별자 19개 제거 + 관련 CSS/nav/i18n/anchor 일괄 삭제 → 출력: `render_dashboard()`가 `phase-timeline` 섹션을 생성하지 않는 빌드. 렌더 HTML에 `data-section="phase-timeline"` · `tl-row` · `_PHASE_TO_SEG` 참조 없음. 기존 sections tuple에서 `"phase-timeline"`을 완전히 제거하므로 wrap 루프(L4200)는 수정 불필요하나, L4207-L4211의 별도 wrap 블록은 반드시 삭제.

## 설계 결정 (대안이 있는 경우만)
- **결정**: 섹션을 완전 삭제한다 (함수·상수·CSS·i18n·nav 동시 제거).
- **대안**: (a) 섹션은 유지하고 `render_dashboard`에서 호출만 스킵 — 데드 코드가 남아 유지보수 비용·시각 토큰 누수. (b) `_section_phase_timeline`만 빈 문자열 반환하도록 스텁화 — CSS/i18n/nav 잔존으로 AC-1(tl- 패턴 부재)을 만족하지 못함.
- **근거**: PRD AC-1은 "DOM에서 완전히 제거" + "grep 결과 빈 줄"을 요구 → 완전 삭제가 유일 해. 스텁/플래그 방식은 수용 기준을 위반.

- **결정**: Python unit test(`test_monitor_render.py`)에서 회귀 검증하고 E2E는 추가하지 않는다.
- **대안**: Playwright E2E 시나리오로 `data-section="phase-timeline"` 부재를 확인.
- **근거**: 본 Task는 요소 "부재"를 단언하는 네거티브 케이스. SSR 렌더 함수 `render_dashboard(...)` 결과 문자열에 대한 pytest 단언으로 더 빠르고 결정적으로 검증 가능. E2E는 monitor-v4 다른 Task들이 이미 포괄.

## 선행 조건
- 없음 (WBS `depends: -`).
- 외부 라이브러리 변경 없음 — Python 3 stdlib만 사용하는 기존 구조 유지.

## 리스크
- **MEDIUM — 중괄호 매칭**: 인라인 `<style>` 문자열 중간의 CSS 블록을 제거할 때 `{...}` 쌍이 깨지면 CSS 전체가 깨진다. 삭제 후 반드시 `python3 -m py_compile scripts/monitor-server.py`로 파일 문법 검증 + 서버 수동 기동해 네트워크 응답 HTML을 브라우저로 육안 확인.
- **MEDIUM — 오삭제**: `.tl-`로 시작하는 무관 클래스가 실제로 없음을 사전 grep(`grep -n "\.tl[a-z-]*"`) 으로 확인. 현재 스캔에서 `tl-dd/im/ts/xx/fail`(`.timeline-svg` scoped), `tl-row/track/axis/now/ticks` 외 다른 `.tl-`은 발견되지 않음 — 제거 전 재확인.
- **MEDIUM — _x_of 공유 여부**: `_x_of`(L3520) 함수가 `_timeline_svg` 외 호출이 있는지 grep으로 재확인. 타 호출이 있으면 보존, 없으면 같이 제거 (죽은 코드 누적 방지).
- **LOW — 기존 테스트 파일 동시 수정**: `test_monitor_render.py` / `test_monitor_render_tsk04.py`의 timeline 단위 테스트는 dev-test 단계가 아닌 **dev-build/TDD 단계에서 제거 대상**. dev-build가 이 파일을 수정하지 않으면 빌드 후 기존 테스트가 `_section_phase_timeline` AttributeError로 실패하므로 파일 계획에 명시 (위 표 참조).
- **LOW — 시각 회귀 (무성)**: monitor-server.py는 ~5600줄 모놀리스라 다른 PR과 동시 머지 시 무성 시각 회귀 위험(MEMORY 기록). 본 Task는 "부재" 검증 테스트를 dev-build가 먼저 작성하므로 회귀 자석으로 기능.

## QA 체크리스트
dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

- [ ] (AC-1 직접) `render_dashboard(...)` 반환 HTML에 `data-section="phase-timeline"` 문자열이 존재하지 않는다.
- [ ] (grep 정합성) `grep -n "_PHASE_TO_SEG\|_timeline_rows\|_timeline_svg\|_section_phase_timeline\|_TIMELINE_SPAN_MINUTES\|_TIMELINE_MAX_ROWS\|tl-row\|tl-track\|tl-axis\|tl-now\|panel\\.timeline\|timeline-head\|timeline-svg\|timeline-more" scripts/monitor-server.py` 결과가 **0줄**.
- [ ] (인라인 CSS) 렌더 HTML의 `<style>` 블록에 `.tl-` 접두 셀렉터가 부재.
- [ ] (i18n 청소) `_t("ko", "phase_timeline")` 호출 시 key fallback 동작(return `"phase_timeline"`), 즉 i18n 테이블 두 곳에서 키가 제거됨.
- [ ] (nav 청소) sticky-header HTML에 `<a href="#timeline">` 앵커가 없다.
- [ ] (section anchors) `_SECTION_ANCHORS`에 `"timeline"`이 없으며, `_SECTION_EYEBROWS`/`_SECTION_DEFAULT_HEADINGS`에도 `timeline` 키가 없다.
- [ ] (회귀 — wp-cards) 기존 `test_monitor_render.py`의 wp-cards/features/team/subagents/live-activity/dep-graph/phase-history 관련 테스트가 모두 통과한다.
- [ ] (회귀 — dep-graph 색 매핑) `_section_dep_graph` 렌더 출력이 변경 전과 동일한 CSS 클래스 집합(`state-done/running/pending/failed/bypass` 등)을 포함한다 — `_PHASE_TO_SEG` 제거가 dep-graph 배색에 영향 없음을 확인.
- [ ] (문법) `python3 -m py_compile scripts/monitor-server.py` 종료 코드 0.
- [ ] (엣지 — 빈 tasks) `render_dashboard`에 빈 tasks/features를 전달해도 AttributeError 없이 HTML을 반환한다 (예전 `_section_phase_timeline` 빈-state 분기 삭제에 따른 회귀 체크).
- [ ] (엣지 — i18n) `?lang=en`과 `?lang=ko` 두 경우 모두 위 조건을 동일하게 만족.
- [ ] (통합) `pytest -q scripts/` 전체 테스트가 통과한다 (기존 `test_monitor_render.py` / `test_monitor_render_tsk04.py`의 timeline 관련 테스트는 본 Task에서 **같이 제거**되므로 실패로 남지 않는다).

**fullstack/frontend Task 필수 항목** — 본 Task는 "섹션 제거" 성격상 신규 클릭 경로/화면이 없어 reachability gate가 적용되지 않는다. 대신 위 AC-1/grep/nav/section-anchors 항목들이 동등한 수용 기준 역할을 한다.
