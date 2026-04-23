# TSK-01-02: 실시간 활동 기본 접힘 + auto-refresh 생존 - 설계

## 요구사항 확인
- 실시간 활동(Live Activity) 섹션을 `<details data-fold-key="live-activity">` 로 래핑하고 `data-fold-default-open` 속성을 **부여하지 않음** → 첫 로드(localStorage 비어있음) 시 **기본 접힘** (PRD §5 AC-7).
- 사용자가 펼친 뒤 5초 auto-refresh(innerHTML 교체)와 하드 리로드(F5) 모두에서 `localStorage['dev-monitor:fold:live-activity']` 기반으로 fold 상태가 **복원**된다 (AC-8, AC-9).
- `patchSection('live-activity')` 는 `wp-cards` 와 동일하게 innerHTML 교체 후 `applyFoldStates` + `bindFoldListeners` 재실행 — 이때 fold 헬퍼는 TSK-00-01 에서 `data-fold-key` 기반 범용 헬퍼로 이미 일반화되어 있다고 가정(본 Task는 그 헬퍼를 재사용만).

## 타겟 앱
- **경로**: N/A (단일 앱 — dev-plugin 루트에서 `scripts/` + `skills/dev-monitor/vendor/` 로 구성되는 단일 모니터 서버)
- **근거**: `docs/monitor-v4/` 프로젝트는 `scripts/monitor-server.py` 한 프로세스가 SSR + API 를 모두 담당하는 단일 앱 구조. 루트 `package.json`/workspaces 없음.

## 구현 방향
- `scripts/monitor-server.py` 의 `_section_live_activity(model, heading)` 반환값을 기존 `_section_wrap("activity", ...)` 에서 **`<details class="activity-section" data-fold-key="live-activity"> <summary><h2>{heading}</h2></summary> <div class="panel"><div class="activity" aria-live="polite">…rows…</div></div> </details>`** 구조로 교체한다. `data-fold-default-open` 속성을 부여하지 않아 `readFold('live-activity', false)` 가 기본값 `false` 를 돌려준다.
- `render_dashboard` 에서 `sections["live-activity"]` 를 `<div data-section="live-activity">…</div>` 로 래핑하는 기존 코드(L4202-4206)는 그대로 유지 — 5초 polling 이 `patchSection('live-activity', newHtml)` 로 dispatch되도록 `data-section` 앵커는 보존한다.
- 인라인 JS `patchSection` 함수에 `name === 'live-activity'` 분기를 추가 (현재 `wp-cards` 분기와 동일 로직): innerHTML 교체 → `applyFoldStates(current)` → `bindFoldListeners(current)`.
- `applyFoldStates` / `bindFoldListeners` 는 TSK-00-01 에서 `[data-fold-key]` 범용 셀렉터로 일반화되어 있다고 전제. 본 Task는 **헬퍼 정의를 건드리지 않는다** (constraints: 중복 함수 정의 금지). 만약 병합 순서 상 TSK-00-01 이 아직 merge되지 않았다면 Build 단계에서 TSK-00-01 의 헬퍼 범용화를 전제로 테스트하고, 런타임 배선은 merge 후 E2E 로 최종 확인.
- `<details>` 네이티브 `toggle` 이벤트만 사용 (클릭 핸들러 직접 바인딩 금지) — `bindFoldListeners` 가 이미 `toggle` 리스너로 `writeFold` 를 호출하도록 TSK-00-01 설계에 포함됨.

## 파일 계획

**경로 기준:** 모든 파일 경로는 프로젝트 루트 기준으로 작성한다. 단일 앱 프로젝트.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | (1) `_section_live_activity(model, heading)` 내부에서 기존 `_section_wrap("activity", heading, body)` 호출을 제거하고 `<details class="activity-section" data-fold-key="live-activity">` 로 직접 래핑한 HTML 반환. `<summary>` 에 `<h2>{heading}</h2>` 포함. (2) 인라인 JS `patchSection` 에 `name === 'live-activity'` 분기 추가 — `wp-cards` 분기와 동일하게 innerHTML 교체 + `applyFoldStates(current)` + `bindFoldListeners(current)`. (3) `<style>` 블록에 `.activity-section > summary { … }` 최소 스타일 — 기존 `<section>.section-head h2` 와 시각적으로 동등하게 유지 (caret 기본 ▶/▼ 허용). | 수정 |
| `scripts/test_monitor_fold_live_activity.py` | 신규 pytest 모듈. 3개 테스트 케이스로 AC-7/8/9 + constraints 검증. `_section_live_activity` 직접 호출 + `render_dashboard` 통합 렌더 혼용. Python stdlib + pytest 만 사용. | 신규 |
| `scripts/test_monitor_render.py` | 기존 테스트 중 Activity 섹션이 `<section id="activity">` 형태로 렌더된다고 단언하는 케이스가 있다면(회귀) `<details class="activity-section" data-fold-key="live-activity">` 로 업데이트. 행 내부 구조(.arow, .t, .tid, .evt, .el, .log)는 **완전 불변** 이어야 하므로 행 단언은 수정 금지. | 수정 (회귀 방지 최소 수정) |

> 본 Task는 frontend domain이지만 "진입점" 의미에서 **비-페이지 UI** (대시보드 내 섹션)이므로 아래 "진입점" 섹션은 섹션 클릭 동선으로 구체화한다.

## 진입점 (Entry Points)

- **사용자 진입 경로**: 대시보드 메인(`/?subproject=monitor-v4`) 로드 → 화면 우측(또는 레이아웃상 col-right) 의 **"실시간 활동" / "Live Activity"** 섹션 헤더(`<summary>` 내부 `<h2>`) 를 **클릭** 하여 펼침/접음 토글
- **URL / 라우트**: `/` (쿼리 `?subproject=monitor-v4&lang=ko|en` 포함). v4 대시보드는 SPA 가 아니므로 별도 sub-route 없음 — 동일 페이지 내 섹션 DOM 으로만 진입
- **수정할 라우터 파일**: `scripts/monitor-server.py` 의 `render_dashboard(...)` (기존 경로 배선 그대로). `sections["live-activity"]` 주입 위치(L4189-4190) 및 `<div data-section="live-activity">` 래퍼(L4202-4206) **불변** — `_section_live_activity` 반환 HTML 만 교체되면 라우팅 측 변경 없음
- **수정할 메뉴·네비게이션 파일**: `scripts/monitor-server.py` 의 `_SECTION_ANCHORS` 튜플(L999) 및 `_SECTION_EYEBROWS["activity"]` (L2197), `_SECTION_DEFAULT_HEADINGS["activity"]` (L2207) — **앵커 이름 `activity` 는 변경하지 않는다** (기존 `<a href="#activity">` 네비 링크 호환). 단, `<section id="activity">` → `<details class="activity-section">` 으로 시맨틱이 바뀌므로 in-page anchor 스크롤 회귀를 QA 체크리스트에 포함
- **연결 확인 방법**: 브라우저에서 대시보드 로드 → "실시간 활동" 섹션의 `<summary>` 헤더 클릭 → 펼침 상태에서 5초 대기 → 내부 `.activity` 행이 DOM-patch 되고 `<details>` 는 `open` 속성을 유지하는지 확인. `<h2>` 텍스트 "실시간 활동"(ko) / "Live Activity"(en) 를 기준으로 locator 작성. URL 직접 입력(`page.goto('/#activity')`) 은 reachability gate 위반이므로 사용 금지 — lang 스위치는 동일 페이지 내 `<nav class="lang-toggle">` 경유로 테스트한다

## 주요 구조
- `_section_live_activity(model, heading)` (scripts/monitor-server.py L3365~L3443) — 반환 HTML 을 `<section id="activity">` 래퍼에서 `<details class="activity-section" data-fold-key="live-activity"><summary><h2>…</h2></summary><div class="panel"><div class="activity" aria-live="polite">…</div></div></details>` 로 교체. 내부 row 렌더 로직(`_render_arow` 에 해당하는 기존 row_htmls 조립) 은 **완전 불변**
- `patchSection(name, newHtml)` (scripts/monitor-server.py 인라인 JS, L3837~) — `name === 'wp-cards'` 분기 바로 위/아래에 `name === 'live-activity'` 분기 추가. 로직은 wp-cards 와 동일 (`innerHTML = newHtml; applyFoldStates(current); bindFoldListeners(current)`)
- `applyFoldStates(root)` / `bindFoldListeners(root)` — **본 Task에서 수정하지 않음**. TSK-00-01 이 `[data-fold-key]` 범용 셀렉터로 일반화했다고 전제. 이들은 `readFold(key, default)` 를 호출하며, `default` 는 `el.hasAttribute('data-fold-default-open')` 결과
- `_SECTION_EYEBROWS["activity"]` 의 eyebrow/aside 메타데이터 — `<details>` 바깥/헤더 위치가 바뀌므로 eyebrow ("stream") + aside ("last 20 events · ...") 는 `<summary>` 내부에 함께 렌더하거나, 시각 우선순위상 **생략 허용**. 디자인 결정 항목에서 논의

## 데이터 흐름
- 서버: `render_dashboard(model, lang, ...)` → `_section_live_activity(model, heading=_t(lang,"live_activity"))` → `<details data-fold-key="live-activity">…</details>` 문자열 → `<div data-section="live-activity">` 래퍼에 삽입 → HTML 응답
- 클라이언트(초기 로드): 브라우저가 HTML 파싱 → `applyFoldStates(document)` 1회 호출 → `readFold('live-activity', false)` 가 localStorage 값(`open`/`closed`/null) 을 해석하여 `<details>` 의 `open` 속성 설정 → `bindFoldListeners(document)` 가 `toggle` 이벤트 리스너 1회 바인딩
- 클라이언트(5초 polling): `fetchAndPatch` → `patchSection('live-activity', newInnerHtml)` → `current.innerHTML = newInnerHtml` → `applyFoldStates(current)` → `bindFoldListeners(current)` → 사용자 토글 상태 복원 + 리스너 재바인딩 (`el._foldBound` 가드로 중복 바인딩 방지)
- 사용자 토글: `<details>` 네이티브 `toggle` 이벤트 발화 → `bindFoldListeners` 등록 리스너가 `writeFold('live-activity', el.open)` 호출 → `localStorage` 갱신

## 설계 결정 (대안이 있는 경우만)
- **결정**: `<details>` 를 `<section id="activity">` 를 **대체** 하는 루트 엘리먼트로 사용 (즉, `_section_wrap("activity", ...)` 호출을 제거하고 `<details>` 가 섹션 루트가 됨)
- **대안**: `<section id="activity">` 바깥 래퍼는 유지하고 그 내부에 `<details>` 를 중첩하는 방식
- **근거**: TRD §3.2 예시 코드가 `<details>` 를 최상위로 둔다. 또한 `<details data-fold-key="live-activity">` 가 `[data-fold-key]` 셀렉터로 직접 잡혀야 `applyFoldStates` 재사용 계약이 성립. 중첩 시 `<section>` 기존 `.section-head` 높이 때문에 접힘 효과의 시각적 이득(세로 공간 절약 — S5 시나리오)이 반감된다. 대신 `<a href="#activity">` in-page link 호환을 위해 **`<details id="activity">` 로 id 를 이전 배치** 하여 기존 네비 링크를 무회귀로 유지

## 선행 조건
- **TSK-00-01 선행 필수**: `applyFoldStates` / `bindFoldListeners` 의 `[data-fold-key]` 범용화 + `readFold(key, default)` / `writeFold(key, open)` 키-prefix 헬퍼. 본 Task 는 이들 함수를 재사용만 하며 **중복 정의 금지** (constraints). Build 단계에서 TSK-00-01 이 아직 merge 전이면 해당 헬퍼가 아직 `details[data-wp]` 셀렉터만 잡을 가능성이 있으므로, 테스트 작성 전 **TSK-00-01 의 state.json 이 `[xx]` 인지 확인** 후 진행하거나, 설계 단계에서는 TSK-00-01 후속 merge를 전제로 설계만 확정한다
- Python 3 stdlib + pytest (기존 테스트 프레임워크 그대로)
- 브라우저 `<details>` 네이티브 지원 (IE 제외 모든 모던 브라우저 — dev-monitor 지원 범위 내)

## 리스크
- **HIGH**: `<section id="activity">` → `<details id="activity">` 로 루트 시맨틱 변경 시 기존 `<a href="#activity">Activity</a>` in-page 네비 링크의 scroll-to 동작이 `<details>` 의 접힘 상태와 충돌 가능성. 브라우저가 접힌 `<details>` 로 스크롤하면 `<summary>` 위치로만 이동하고 내용이 안 보임 — **의도된 동작** (AC-7 의 기본 접힘). QA 체크리스트에 "in-page anchor 네비 → `<summary>` 위치로 스크롤 + 내용은 접힌 상태" 를 명시 검증
- **MEDIUM**: `_SECTION_EYEBROWS["activity"]` 의 eyebrow ("stream") + aside ("last 20 events · ...") 가 `<section>` 의 `.section-head` 에 의존. `<details>` 로 전환 시 해당 메타 HTML 을 `<summary>` 내부로 옮길지/생략할지 결정 필요. 제안: `<summary><h2>{heading}</h2><div class="section-meta"><span class="eyebrow">{eyebrow}</span><span class="aside">{aside}</span></div></summary>` — 기존 CSS `.section-head` 셀렉터는 재사용 불가능하므로 `.activity-section > summary` 로 한정해서 최소 override
- **MEDIUM**: 5초 polling 중 사용자가 `<summary>` 클릭으로 토글하는 경합. `patchSection` 이 먼저 `innerHTML = newHtml` 을 실행하면 사용자 클릭이 무효화될 수 있음. 완화: `applyFoldStates(current)` 가 바로 뒤따라 실행되므로 최종 상태는 localStorage 기반 → 사용자의 **최근 의도**가 `toggle` 이벤트로 이미 `writeFold` 되었다면 복원됨. 단, 폴링과 사용자 클릭이 **동일 tick** 에 경합하면 사용자 의도가 유실될 수 있어 E2E 에서 "펼친 직후 즉시 refresh 트리거" 케이스는 **5초 대기 후 관찰** 로 완화
- **LOW**: `_section_wrap("activity", heading, body)` 제거로 `<section>` 클래스 셀렉터(CSS) 에 "activity" 가 걸려 있던 스타일이 있다면 회귀 가능. 사전 `grep -n "section.*activity\|#activity[^\-]" scripts/monitor-server.py` 로 확인 후 필요 시 `.activity-section` 으로 이관
- **LOW**: `<details>` 의 `open` 속성이 없는 초기 상태에서도 내부 `.activity` 의 `aria-live="polite"` 가 스크린 리더에 읽히는지 — 접근성 체크 추가

## QA 체크리스트
dev-test 단계에서 검증할 항목. 각 항목은 pass/fail 로 판정 가능해야 한다.

- [ ] (정상) `render_dashboard()` 반환 HTML 에 `<details` + `class="activity-section"` + `data-fold-key="live-activity"` 가 존재하고, `open` 속성은 **부재** (AC-7 / test_live_activity_wrapped_in_details)
- [ ] (정상) `_section_live_activity(model, heading)` 반환 HTML 에 기존 `.arow` 행들이 회귀 없이 포함되어 렌더됨 (`.t`, `.tid`, `.evt`, `.el` 필드 모두 보존)
- [ ] (엣지) rows 가 빈 리스트일 때도 `<details data-fold-key="live-activity">` 루트는 렌더되며 내부는 `<p class="empty">no recent events</p>` 상당의 플레이스홀더로 표시
- [ ] (엣지) `data-fold-default-open` 속성이 **없음** → 첫 로드 시 `readFold('live-activity', false)` 결과가 `false` 로 해석되어 `<details>` 에 `open` 미부여 (DOM 시뮬레이션: localStorage 비어있는 상태에서 `applyFoldStates(root)` 호출 후 단언)
- [ ] (통합) patchSection 시뮬레이션 — `<details data-fold-key="live-activity" open>` 인 DOM 에서 `innerHTML` 을 새 HTML 로 교체 후 `applyFoldStates` + `bindFoldListeners` 재호출 시 `open` 속성이 **복원** 됨 (AC-8 / test_patch_section_live_activity_restores_fold)
- [ ] (통합) `localStorage.setItem('dev-monitor:fold:live-activity', 'closed')` 후 페이지 재로드 시 `<details>` 가 `open` 없이 렌더되는 것을 `applyFoldStates` 단독 호출로 재현 (AC-9 / test_live_activity_default_closed fallback)
- [ ] (에러) `_section_live_activity` 에 `model=None` 또는 `model={}` 전달 시 기존 동작(`_live_activity_rows` 가 빈 리스트 반환) 과 동일하게 안전하게 처리되고 `<details>` 루트는 유지
- [ ] (회귀) 기존 `test_monitor_render.py` 내 Activity 섹션 관련 단언이 `<details>` 구조에 맞춰 업데이트되었고, 그 외 WP/KPI/Features/Phase-history 등 다른 섹션 회귀 없음 (`pytest -q scripts/` 통과)
- [ ] (회귀) `data-fold-default-open` 속성을 가진 `<details data-fold-key="wp-...">` (wp-cards) 의 기본 열림 동작이 회귀 없이 유지됨 — `applyFoldStates` 범용화 후에도 default-open 분기 보존

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**
- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 (URL 직접 입력 금지) — 구체적으로: 대시보드 `/` 로드 후 "실시간 활동" `<summary>` 헤더 클릭 → `<details>` 가 `open` 속성 획득 → 내부 `.activity` 컨테이너가 `display` 되어 `.arow` 행 1개 이상이 viewport 내에 표시됨을 locator 기반 단언
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다 — 구체적으로: 펼친 상태에서 5초 대기 → `<details>` 가 여전히 `open` 유지 (AC-8 의 E2E test_activity_fold_survives_refresh), 이후 `<summary>` 재클릭 시 접히고 `localStorage['dev-monitor:fold:live-activity']` 가 `'closed'` 로 갱신됨 (DevTools Application 탭 / `page.evaluate` 로 확인)
