# TSK-02-02: Task running 스피너 애니메이션 - 설계

## 요구사항 확인
- `_render_task_row_v2()` 의 `<div class="trow">` 에 `data-running="true|false"` 속성을 추가하고, 배지 옆에 `<span class="spinner" aria-hidden="true"></span>` 를 **모든 trow** 에 삽입한다 (PRD §2 P0-2, §5 AC-5).
- TSK-00-01 이 인라인 `<style>` 블록에 이미 정의한 `.spinner` 클래스와 `@keyframes spin` 을 그대로 재사용하고, `.trow[data-running="true"] .spinner { display: inline-block; }` 한 규칙만 신규 추가한다 (중복 정의 금지, constraints).
- 2초 SSR 폴링으로 `running_ids` 가 갱신되면 다음 렌더에서 `data-running` 이 자동 변경되어 스피너가 표시/소멸한다 (AC: signal 삭제 후 5초 폴링 이내 사라짐).

## 타겟 앱
- **경로**: N/A (단일 앱 — `scripts/monitor-server.py` 모놀리스 + `skills/dev-monitor/vendor/*` 벤더 JS)
- **근거**: Dev Config 의 `frontend` 도메인 설명대로 SSR 은 `monitor-server.py` 내부 함수에서 수행되며 모노레포 구조가 아니다.

## 구현 방향
- `_render_task_row_v2` 가 이미 `running_ids` 를 파라미터로 받아 `_trow_data_status` 로 `data-status` 를 결정하고 있으므로, 같은 `(item_id in running_ids)` 판정을 `data_running` 로 재사용한다. 중복 계산 없이 1줄 불린 계산 추가.
- trow 루트 `<div>` 속성에 `data-running="{true|false}"` 를 삽입한다. 기존 `data-status` 는 건드리지 않는다 (회귀 방지 — test_monitor_render.py 에 `data-status` 단언이 다수 존재).
- `<div class="badge">` 직후 (같은 `<div class="badge">…</div>` 바깥, `<div class="ttitle">` 이전) 에 `<span class="spinner" aria-hidden="true"></span>` 한 줄을 **항상** 삽입한다. CSS 가 `data-running="true"` 일 때만 노출시키므로, HTML 구조는 모든 trow 에서 동일해진다 (스냅샷 안정성).
- 인라인 `<style>` 블록에 규칙 `.trow[data-running="true"] .spinner { display: inline-block; }` 한 줄만 추가한다. `@keyframes spin` 과 `.spinner` 기본 스타일은 TSK-00-01 이 제공하므로 손대지 않는다.
- 배지 텍스트와 스피너의 가로 간격은 TSK-00-01 의 `.spinner` 기본 margin 을 따른다. 추가 margin 조정이 필요하면 `.badge .spinner { margin-left: 4px; }` 를 같은 인라인 CSS 블록에 덧붙인다 (기존 `.spinner` 전역 기본값을 덮어쓰지 않도록 선택자를 구체화).

## 파일 계획

**경로 기준:** 모든 파일 경로는 프로젝트 루트 기준으로 작성한다. 단일 앱 프로젝트이므로 접두어 없음.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `_render_task_row_v2()` 에 `data-running` 속성 + `<span class="spinner">` 삽입. 인라인 `<style>` 블록에 `.trow[data-running="true"] .spinner { display: inline-block; }` + `.badge .spinner { margin-left: 4px; }` 2행 추가. | 수정 |
| `scripts/test_monitor_render.py` | `TestRenderTaskRowV2` / 관련 테스트 클래스에 `test_task_row_has_spinner_when_running` + `test_task_row_spinner_hidden_when_not_running` 추가. HTML 에 `<span class="spinner"` 존재 + trow 루트 `data-running="true|false"` 단언. | 수정 |
| `scripts/test_monitor_render.py` | `test_task_row_spinner_has_aria_hidden` — 모든 trow 의 spinner span 에 `aria-hidden="true"` 존재. | 수정 |

> 이 Task 는 **backend 파일 1개 + 테스트 1개** 만 수정한다. 신규 파일 없음. `_render_task_row_v2` 외부 호출자(`_section_wp_cards`, `_section_features` 등)는 시그니처를 유지하므로 수정 불필요.

## 진입점 (Entry Points)

**대상**: `domain=frontend` — 대시보드 Task 행 UI.

- **사용자 진입 경로**: `브라우저에서 http://localhost:7321 접속 → 메인 페이지의 '작업 패키지' 섹션의 WP 카드 펼치기(details/summary 토글) → WP 내부 Task 행(.trow) 중 실행 중인 항목의 배지 우측에 회전 스피너 표시`
- **URL / 라우트**: `http://localhost:7321/` (기본 대시보드 라우트, `?lang=ko|en` 쿼리 지원). monitor-server.py `do_GET` 의 `/` 분기 → `render_dashboard()` → `_section_wp_cards()` → `_render_task_row_v2()` 체인.
- **수정할 라우터 파일**: `scripts/monitor-server.py` 의 `_render_task_row_v2()` 함수 (line 2735 전후). 라우팅 자체(do_GET 디스패치)는 변경하지 않고, 라우터가 호출하는 렌더 함수만 수정. `render_dashboard` 내부 호출 체인은 그대로 유지.
- **수정할 메뉴·네비게이션 파일**: `scripts/monitor-server.py` 내부 `_section_wp_cards()` (line 2776~) 와 `_section_features()` (line 2888~). 두 함수가 `_render_task_row_v2` 를 호출하는 유일한 메뉴(섹션) 진입점이므로, 함수 시그니처를 유지하여 **호출부는 변경 없음**. (WP 카드 섹션 + Features 섹션 모두 자동으로 스피너 기능 상속.)
- **연결 확인 방법**: `브라우저에서 http://localhost:7321 접속 → WP 카드를 클릭하여 펼침 → .running signal 이 존재하는 Task 의 trow 에 회전 스피너 표시 확인 → 터미널에서 해당 .running signal 파일 삭제 → 5초 폴링 이내 스피너 사라짐 확인`. URL 직접 입력(page.goto)만으로는 실행중 signal 상태를 재현할 수 없으므로, E2E 는 signal 파일 생성 → 페이지 방문 → 스피너 존재 단언 → signal 삭제 → 폴링 후 재단언 순서로 작성.

## 주요 구조

- `_render_task_row_v2(item, running_ids, failed_ids, lang)` — 기존 함수. (1) `data_running = "true" if item_id in running_ids else "false"` 1줄 추가, (2) 루트 `<div class="trow"` 에 `data-running="{data_running}"` 속성 삽입, (3) 기존 `<div class="badge">…</div>` 직후에 `<span class="spinner" aria-hidden="true"></span>` 한 줄 삽입.
- `_trow_data_status(item, running_ids, failed_ids)` — 기존 헬퍼. 수정 없음. `data-running` 판정은 `_render_task_row_v2` 내부에서 별도 계산 (중복 계산 허용 — `running_ids.__contains__` 은 O(1)).
- 인라인 CSS 블록 (monitor-server.py 내 `<style>` 문자열) — `.trow[data-running="true"] .spinner { display: inline-block; }` + `.badge .spinner { margin-left: 4px; }` 2행 추가. 기존 `.trow[data-status="…"] .badge` 규칙들과 동일한 섹션에 배치.

## 데이터 흐름
`.running` signal 스캔 (monitor-server.py scan) → `running_ids: set[str]` → `_section_wp_cards(..., running_ids, ...)` → `_render_task_row_v2(item, running_ids, ...)` → HTML 내 `<div class="trow" data-running="true">… <span class="spinner">…</span>` → 브라우저 CSS `data-running="true"` 조건부 `display: inline-block` → 스피너 회전 (TSK-00-01 의 `@keyframes spin`).

## 설계 결정

- **결정**: 스피너 `<span>` 을 **모든 trow 에 항상 삽입**하고 CSS `data-running="true"` 에서만 노출한다.
- **대안**: `running` 상태일 때만 조건부로 `<span>` 을 삽입.
- **근거**: PRD/WBS requirements 가 "**모든 trow** 에 삽입(CSS 로 노출 제어)"를 명시. HTML 구조 일관성 → 스냅샷 테스트/DOM 단언 단순화 + auto-refresh 의 innerHTML 교체 후에도 구조 안정. 조건부 삽입은 DOM 구조 diff 가 커져 무성 회귀 위험.

- **결정**: `data-running` 을 trow 루트 `<div>` 에 두고 `.spinner` 는 `<div class="badge">` 의 **형제(sibling)** 로 배치한다 (CSS 선택자: `.trow[data-running="true"] .spinner`).
- **대안**: `<span class="spinner">` 를 `<div class="badge">` 의 **자식(내부)** 으로 넣고 `.trow[data-running="true"] .badge .spinner` 로 선택.
- **근거**: WBS note 는 "배지 옆 `<span class="spinner">`" 을 명시. 형제 배치로 배지 레이아웃(테두리/배경)에 영향을 주지 않고, `.badge` 의 기존 `color`/`border-color` 상태 override 에도 스피너 색상은 TSK-00-01 의 `border-top-color` 로 독립 관리. ui-spec `| Design ⟳ |` 에서 ⟳ 은 배지 pill 바깥 right 4px 위치로 해석.

## 선행 조건

- **TSK-00-01** (공용 spinner CSS + 범용 fold 헬퍼) — `@keyframes spin`, `.spinner` 기본 스타일 제공. wbs.md status 는 현재 `[ ]` 이지만 design 은 독립 진행 가능(설계는 헬퍼 존재 가정만 문서화). Build 단계는 TSK-00-01 완료 대기 필요 (depends 명시).
- **TSK-02-01** (Task DDTR 단계 배지) — 배지 옆 `<span class="spinner">` 자리 마련. 현재 `_render_task_row_v2` 는 이미 `<div class="badge">` 를 렌더링하므로 TSK-02-01 완료 여부와 무관하게 trow 구조에 삽입 가능. 단, TSK-02-01 이 배지 내부에 별도 `<span>` 을 추가한다면 병합 시 순서 조정 필요.

## 리스크

- **MEDIUM**: `test_monitor_render.py` 에 `data-status` 단언과 trow HTML 스냅샷이 다수 존재. `data-running` 속성 추가로 **기존 스냅샷 테스트가 깨질 수 있음**. Build 단계에서 해당 테스트를 조사하여 `assertIn("data-running=", html)` 관점으로 보강하거나, 스냅샷 대신 속성 기반 단언으로 전환. (feedback_design_regression_test_lock: "옛 디자인 클래스/색상값을 단언하는 테스트는 회귀 자석으로 작동" — 이번 변경은 layout-skeleton 확장이므로 기존 snapshot 이 있으면 구조 기반으로 리팩토링.)
- **MEDIUM**: TSK-00-01 이 제공하는 `.spinner` 기본 `display: none` 이 `<span>` (인라인 요소)에도 적용되어야 함. TSK-00-01 설계가 `.spinner { display: none }` 을 전역으로 깔았다면 `data-running="true"` override 로 `display: inline-block` 가 작동. 만약 TSK-00-01 이 `.spinner` 를 `div` 전제로 디자인했다면 `<span>` 에서 `border`/`width` 가 반영되지 않을 수 있음 — Build 단계에서 TSK-00-01 의 실제 CSS 를 확인하고 필요 시 `.badge .spinner { display: inline-block; vertical-align: middle; }` 을 추가.
- **LOW**: 스피너 `aria-hidden="true"` 로 스크린 리더가 읽지 않음(AC 충족). 단, 실행중 상태를 청각 사용자에게 전달할 방법이 없으므로 배지 텍스트(`running`)가 이미 상태를 전달 — 별도 `aria-label` 불필요.
- **LOW**: 모든 trow 에 스피너 `<span>` 을 렌더하므로 DOM 노드 수가 Task 당 1개씩 증가. 대시보드가 수백 Task 를 동시에 렌더하는 극단 케이스에서 1KB 미만의 HTML 증가 — 성능 영향 무시 가능.

## QA 체크리스트

dev-test 단계에서 검증할 항목. 각 항목은 pass/fail 로 판정 가능하다.

- [ ] (정상 케이스 — running) `running_ids` 에 포함된 Task 의 trow HTML 에 `data-running="true"` 속성 + `<span class="spinner"` 존재.
- [ ] (정상 케이스 — not running) `running_ids` 에 미포함된 Task 의 trow HTML 에 `data-running="false"` + `<span class="spinner"` 존재 (CSS 로 숨김).
- [ ] (엣지 케이스 — 빈 set) `running_ids=set()` 일 때 모든 trow 가 `data-running="false"`.
- [ ] (엣지 케이스 — 모두 running) 모든 Task id 가 `running_ids` 에 있을 때 모든 trow 가 `data-running="true"`.
- [ ] (에러 케이스 — bypassed + running) `bypassed=True` 이며 동시에 `running_ids` 포함인 경우: `data-status="bypass"` 유지하면서 `data-running="true"` 도 병행 (두 속성 독립).
- [ ] (접근성) 모든 `<span class="spinner">` 에 `aria-hidden="true"` 속성 존재.
- [ ] (CSS 중복 금지) 렌더된 HTML/인라인 `<style>` 블록에 `@keyframes spin` 이 정확히 1회 등장.
- [ ] (통합 케이스) `_section_wp_cards` 와 `_section_features` 모두 `_render_task_row_v2` 를 호출하므로 두 섹션의 HTML 에서 동일하게 `data-running` + spinner 존재.

**frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**

- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 (URL 직접 입력 금지) — 브라우저 http://localhost:7321 접속 후 WP 카드(`<details class="wp">`)를 클릭하여 펼침 → Task 행이 표시됨.
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다 — `.running` signal 파일 생성 → 5초 이내 해당 Task 의 spinner 가 회전 표시 → signal 삭제 → 5초 이내 spinner 사라짐. `getBoundingClientRect()` 로 가시 영역 확인 + `animation-name: spin` computed style 단언.
