# TSK-04-02: FR-01 Task 팝오버 — hover 제거 + ⓘ 클릭 + 위쪽 배치 + 폴백 - 설계

## 요구사항 확인
- Task 행의 hover 기반 툴팁(`setupTaskTooltip` + `#trow-tooltip`)을 제거하고, 새 ⓘ 버튼(`button.info-btn`) 클릭 시 body 직계 싱글톤 팝오버(`#trow-info-popover`)가 **행 위쪽**(상단 여유 부족 시 아래로 폴백)에 열린다.
- 열기/닫기 경로: 클릭 토글 / 외부 클릭 / ESC(+ `openBtn.focus()` 복원) / 스크롤·리사이즈. `aria-expanded` 동기화 + `<button>` 기본 키보드 지원(Enter/Space).
- v4 hover E2E 테스트는 click 기반으로 마이그레이션하고 hover 단언은 즉시 회귀 대상이므로 전량 삭제. 콘텐츠 렌더러는 기존 `renderTooltipHtml(data)` 그대로 재사용(내부 배지/state 요약 구조 변경 금지).

## 타겟 앱
- **경로**: N/A (단일 앱 — `scripts/monitor-server.py` + 정적 자산 패키지 `scripts/monitor_server/`)
- **근거**: `dev-monitor` v5 본 프로젝트는 플러그인 내 단일 HTTP 대시보드로, `docs/monitor-v5/trd.md §2` 변경 파일 표가 모든 편집을 `scripts/monitor-server.py`와 `scripts/monitor_server/**` 범위로 제한한다.

## 구현 방향
1. **DOM 삽입**: `renderers/wp.py`의 `_render_task_row_v2()`가 행 우측(`.flags` 뒤, `.expand-btn` 앞)에 `<button class="info-btn" aria-label="상세" aria-expanded="false" aria-controls="trow-info-popover">ⓘ</button>`을 항상 렌더한다. `data-state-summary` 속성(기존 TSK-02-03 유산)은 팝오버 콘텐츠 입력으로 재사용하므로 유지.
2. **싱글톤 팝오버**: `renderers/panel.py`가 body 직계 한 번만 주입하는 `<div id="trow-info-popover" role="dialog" hidden></div>`를 제공한다. 기존 `_trow_tooltip_skeleton()`의 `<div id="trow-tooltip">` 스켈레톤은 삭제. 5초 폴링은 `data-section` 내부만 교체하므로 팝오버 DOM은 살아남는다.
3. **CSS**: `static/style.css`에서 `#trow-tooltip` 블록 전량 삭제 + `.info-btn` / `.info-popover` 규칙 신설. `.info-popover`는 `position:absolute` + `box-shadow:0 8px 24px rgba(0,0,0,0.18)` + 2단계 폰트 스케일 + 꼬리 삼각형(`::before`/`::after` pseudo-element, 기본 아래 방향·폴백 시 위 방향 `data-placement="below"` 토글) + `z-index:100` 유지.
4. **JS**: `static/app.js`에서 `setupTaskTooltip` IIFE 제거 + `setupInfoPopover` IIFE 추가. TRD §7.1 `positionPopover`/`setupInfoPopover` 코드를 그대로 이식하되, 콘텐츠 렌더러 이름만 `renderInfoPopoverHtml`(내부 구현은 `renderTooltipHtml` 재사용 — 기존 `<dl>` + `phase-models <dl>` 구조 유지)로 한다.
5. **테스트**: `scripts/test_monitor_info_popover.py` 신규(단위: DOM 구조/ARIA/JS 문자열 매칭) + `scripts/test_monitor_e2e.py`에 `test_task_popover_click` 추가(실제 클릭/ESC/폴백 시나리오, Playwright 혹은 urllib + 가짜 hover 단언 제거).

## 파일 계획

**경로 기준:** 모든 파일 경로는 **프로젝트 루트 기준**으로 작성한다. 단일 앱이지만 혼동 방지를 위해 `scripts/` 접두어를 명시한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor_server/renderers/wp.py` | `_render_task_row_v2()`에 `.info-btn` 버튼 삽입(`.flags` 뒤, `.expand-btn` 앞). `data-state-summary` 속성 유지. | 수정 |
| `scripts/monitor_server/renderers/panel.py` | body 직계 싱글톤 `<div id="trow-info-popover" role="dialog" hidden></div>` 렌더 함수(`_info_popover_skeleton()`) 제공. 기존 `_trow_tooltip_skeleton()` 호출 삭제. | 수정 |
| `scripts/monitor_server/renderers/__init__.py` | `render_dashboard(...)` 조립 시 `_info_popover_skeleton()`을 body 직계에 1회 포함. `_trow_tooltip_skeleton()` 호출 제거. | 수정 |
| `scripts/monitor_server/static/style.css` | `#trow-tooltip` 규칙 전량 삭제 + `.info-btn`, `.info-popover`, `.info-popover::before/::after`(꼬리), `.info-popover[data-placement="below"]` 규칙 추가. `--phase-*` 변수 재사용. | 수정 |
| `scripts/monitor_server/static/app.js` | `setupTaskTooltip` IIFE 및 `renderTooltipHtml` 외부 호출부 전량 제거. `setupInfoPopover` IIFE + `positionPopover()` + `renderInfoPopoverHtml()`(옛 `renderTooltipHtml` 본문 재사용) 추가. | 수정 |
| `scripts/monitor-server.py` | 엔트리 shim — 위 패키지 변경이 반영되도록 DASHBOARD_CSS 인라인 블록의 `#trow-tooltip` 규칙과 `setupTaskTooltip` IIFE 문자열을 동시 삭제(TSK-01-03/TSK-02-01 미완료 시 fallback). 분할 완료 후에는 no-op. | 수정 |
| `scripts/test_monitor_info_popover.py` | 단위: ⓘ 버튼 DOM 존재/ARIA/초기값, 팝오버 싱글톤 DOM, CSS 규칙(`#trow-tooltip` 부재 + `.info-popover` 존재), JS IIFE 문자열(`setupInfoPopover` 포함, `setupTaskTooltip` 부재) 검증. `renderInfoPopoverHtml` 명칭 grep. | 신규 |
| `scripts/test_monitor_e2e.py` | `test_task_tooltip_hover` 계열 테스트(1143–1204 라인대) 삭제. 동일 라인에 `test_task_popover_click`(클릭 시 `#trow-info-popover[hidden]` 해제 + `bottom ≤ row.top + 4`), `test_task_popover_flips_below_when_top_insufficient`, `test_task_popover_esc_closes_and_refocuses`, `test_task_popover_outside_click_closes`, `test_task_popover_re_click_toggles`, `test_task_popover_aria_expanded_sync` 신설. `test_task_tooltip_setupTaskTooltip_in_script`를 `test_task_popover_setupInfoPopover_in_script`로 치환. | 수정 |

## 진입점 (Entry Points)

- **사용자 진입 경로**: 브라우저에서 `http://localhost:7321/` 접속 → 우측 "WP 카드" 섹션에서 임의 Task 행의 **오른쪽 끝 ⓘ 버튼 클릭**. (hover 경로는 제거됨.)
- **URL / 라우트**: `/` (대시보드 루트). API 상호작용 없음(팝오버 콘텐츠는 SSR 시점 `data-state-summary` JSON에서 파생). `/static/style.css?v={pkg_version}`, `/static/app.js?v={pkg_version}` 서빙은 TSK-01-03 백본 그대로 사용.
- **수정할 라우터 파일**: `scripts/monitor_server/renderers/__init__.py`의 `render_dashboard(model, lang, sps, sp)` — body 조립 부분에 `_info_popover_skeleton()` 포함. `scripts/monitor-server.py`의 `Handler.do_GET('/')` 분기는 이미 `render_dashboard` 호출만 위임하므로 추가 수정 없음.
- **수정할 메뉴·네비게이션 파일**: 본 Task는 신규 페이지가 아닌 기존 Task 행(WP 카드 내부) 내 **인라인 UI 요소 추가**이므로 사이드바/메뉴 파일은 해당 없음. 대신 **"메뉴 대체 역할"**: `scripts/monitor_server/renderers/wp.py::_render_task_row_v2()`가 행 수준의 "상세 보기" 진입점을 제공한다(⚠ 파일 계획 표에 포함됨).
- **연결 확인 방법**: E2E 시나리오 —
  1. `GET /`로 HTML 수신 → `.trow button.info-btn[aria-expanded="false"]` 셀렉터로 버튼 존재 확인(Playwright 미사용 시 regex grep으로 대체).
  2. Playwright 사용 테스트(`test_task_popover_click`): 페이지 로드 → `.trow .info-btn` 첫 번째 클릭 → `#trow-info-popover:not([hidden])` 대기 → `getBoundingClientRect()` 비교로 `popover.bottom <= row.top + 4` 단언.
  3. `page.goto` 이후 **클릭만으로 팝오버 표시**까지 도달 — `page.evaluate('() => document.getElementById("trow-info-popover").hidden')` 결과 `false` 확인.

## 주요 구조

- **`_render_task_row_v2(item, running_ids, failed_ids, lang)`** (`renderers/wp.py`) — 기존 7-grid `.trow` 구조를 유지하고 `flags_inner` 직후·`expand_btn` 앞에 `info_btn` HTML 조각을 삽입. `aria-controls="trow-info-popover"` 고정.
- **`_info_popover_skeleton()`** (`renderers/panel.py` 신규) — `<div id="trow-info-popover" role="dialog" hidden></div>` 1줄 반환. 기존 `_trow_tooltip_skeleton()`의 호출부를 대체하며, 함수 자체는 미사용이 되므로 동시에 삭제해 dead code를 남기지 않는다.
- **`setupInfoPopover` IIFE** (`static/app.js`) — 싱글톤 `openBtn` 상태, `document` 레벨 click delegation(캡처 단계 아님 — `e.stopPropagation()`로 외부 클릭 path 차단), `keydown` ESC 처리, `scroll`(capture=true) + `resize` 자동 닫기. 내부 헬퍼:
  - `close()` — `openBtn.setAttribute('aria-expanded','false')` + `pop.hidden=true` + `openBtn=null`.
  - `renderInfoPopoverHtml(data)` — 옛 `renderTooltipHtml(data)` 그대로 이식(함수 이름만 변경). `<dl>`(status/last event/at/elapsed/recent phases) + `renderPhaseModels(pm, escalated, retry_count)` 두 섹션 DocumentFragment 반환. `pop.innerHTML = ''` 후 `pop.appendChild(...)`로 교체(innerHTML=fragment 불가 패턴 회피).
- **`positionPopover(btn, pop)`** (`static/app.js`) — TRD §7.1 코드 그대로. 배치 후 `pop.setAttribute('data-placement', top < r.bottom + window.scrollY + 8 ? 'above' : 'below')`를 추가하여 CSS가 꼬리 방향을 결정.

## 데이터 흐름

사용자 클릭 (`.info-btn`) → `setupInfoPopover` delegated handler → 부모 `.trow[data-state-summary]`의 JSON 파싱 → `renderInfoPopoverHtml(data)` fragment 조립 → `#trow-info-popover.innerHTML` 교체 → `positionPopover(btn, pop)`로 좌표 세팅 → `btn.aria-expanded="true"` + `pop.hidden=false`. 닫기 트리거(ESC/외부 클릭/재클릭/scroll/resize) → `close()` → `openBtn.focus()`(ESC 한정).

## 설계 결정 (대안이 있는 경우만)

- **결정 1**: `.info-btn`을 `.flags` 뒤·`.expand-btn` 앞에 배치. **대안**: Task 이름 왼쪽(`.tid` 앞). **근거**: 배지/스피너/retry/flags 동작 영역과 시각적으로 분리되어 있고, `.expand-btn`(↗)과 동일한 "행 우측 액션 존" 컨벤션(TSK-02-02 확립)을 유지해 키보드 Tab 순서가 의미상 정렬됨.
- **결정 2**: `pop.innerHTML=''` 후 `appendChild(fragment)` (옛 `renderTooltipHtml` 재사용). **대안**: 문자열 템플릿으로 재작성. **근거**: AC-FR01-f가 "hover 테스트만 제거하고 콘텐츠 구조 유지"를 요구하므로 렌더러 로직을 바꾸면 회귀 위험. 함수 이름만 `renderInfoPopoverHtml`로 바꿔 WBS 요구사항(이름 변경)을 충족.
- **결정 3**: 스크롤/리사이즈 시 자동 닫기(TRD §7.1 코드). **대안**: 재위치 계산. **근거**: 상태 기계 단순화 + 팝오버가 작아 사용자가 스크롤하면 관심이 바뀐 것으로 간주. 재클릭 한 번이면 즉시 복구.
- **결정 4**: `data-placement` 속성으로 꼬리 방향 제어. **대안**: JS에서 꼬리 DOM 직접 스타일링. **근거**: CSS ::before/::after로 완결되어 JS 책임 축소, 테마 교체 시 CSS만 수정.

## 선행 조건

- **TSK-01-03** (`scripts/monitor_server/static/app.js` 분리) — status `[ ]`. 미완료 시 본 Task는 monitor-server.py 인라인 `<script>` 문자열을 직접 편집하는 fallback을 사용하되, 동일 IIFE 경계(`(function setupInfoPopover(){ ... })();`)를 유지한다. fallback 경로도 acceptance를 모두 만족시킨다.
- **TSK-02-01** (`scripts/monitor_server/renderers/wp.py`, `panel.py` 패키지 분리) — status `[ ]`. 미완료 시 `_render_task_row_v2`(renderers/wp.py 상당) + `_trow_tooltip_skeleton` 호출부(renderers/panel.py 상당)를 monitor-server.py 내 해당 함수에서 직접 편집하는 fallback을 사용. 분리 완료 후에는 패키지 파일로 이관.
- 외부 라이브러리: 없음(`http.server` stdlib + 바닐라 JS ES5).
- 브라우저 API: `Element.getBoundingClientRect()`, `Element.closest()`, `KeyboardEvent.key`, `DocumentFragment` — 모두 IE11 이후 표준.

## 리스크

- **HIGH** — `data-state-summary` JSON에 single-quote가 이미 있는 레코드(기존 `test_monitor_e2e::test_task_info_popover_json_valid` 경로와 겹침)에서 `JSON.parse()` 실패 시 `return`으로 조용히 종료하여 사용자가 "왜 안 열리지?" 혼란. **완화**: `catch(err) { console.warn('trow-info-popover: JSON parse failed', err); return; }` 형태로 최소 1회 경고 로깅.
- **HIGH** — `setupInfoPopover`가 `document.addEventListener('click', ...)` 캡처=false로 등록되므로 `.info-btn`의 `<button>` 기본 동작이 폼 제출을 일으킬 위험. **완화**: `renderers/wp.py`에서 `type="button"` 속성 필수화(기본값 submit 회피).
- **MEDIUM** — 5초 폴링이 `data-section` 내부 `.trow` innerHTML을 교체할 때 `openBtn` 참조가 detached DOM이 됨. 클릭 이후 폴링 사이에 방치되면 다음 외부 클릭 시 `openBtn.setAttribute()`는 성공하나 화면엔 아무 변화가 없음. **완화**: `close()` 도입부에 `if (!document.contains(openBtn)) { pop.hidden=true; openBtn=null; return; }` 가드 추가.
- **MEDIUM** — `test_task_tooltip_*` E2E가 DASHBOARD_CSS 인라인 문자열의 `#trow-tooltip` 존재를 단언하므로 CSS 삭제 시 즉시 red. **완화**: 본 Task에서 hover 단언 테스트를 같은 커밋에서 삭제(회귀 자석 방지 — `feedback_design_regression_test_lock`).
- **LOW** — ESC 시 `openBtn.focus()` 호출이 이미 `close()`에서 `openBtn=null` 이후라 실패. TRD 코드는 `close()` 전에 `openBtn.focus()`를 해야 하는데, §7.1 순서는 `close(); openBtn.focus();` — 구현 시 `close()` 전에 로컬 변수로 저장 필요. **완화**: `setupInfoPopover` IIFE 내 키 핸들러를 `var btn=openBtn; close(); btn && btn.focus();` 패턴으로 명시.

## QA 체크리스트

dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

- [ ] (정상) 대시보드 루트 `/` GET 응답 HTML에 `.trow` 내부 `<button class="info-btn" type="button" aria-label="상세" aria-expanded="false" aria-controls="trow-info-popover">ⓘ</button>` 가 Task 수만큼 포함된다.
- [ ] (정상) body 직계에 `<div id="trow-info-popover" role="dialog" hidden></div>` 가 **정확히 1회** 등장한다(두 번의 연속 GET 모두).
- [ ] (정상) `.info-btn` 클릭 시 `#trow-info-popover[hidden]` 속성이 제거되고, `getBoundingClientRect().bottom <= 클릭한 .trow.getBoundingClientRect().top + 4` 를 만족(꼬리 허용 오차 4px).
- [ ] (엣지) 첫 화면(`scrollY=0`) 상단 행에서 `.info-btn` 클릭 시 상단 여유가 팝오버 높이 미만 → 팝오버가 행 하단으로 이동(`popover.top > row.bottom`).
- [ ] (엣지) 동일 `.info-btn` 재클릭 시 팝오버가 닫히고 `aria-expanded="false"`로 복귀.
- [ ] (엣지) 다른 `.info-btn` 클릭 시 이전 버튼은 `aria-expanded="false"`, 새 버튼은 `"true"`, 팝오버는 새 행 기준으로 재배치.
- [ ] (에러) `data-state-summary` 속성이 없거나 JSON 파싱 실패 시 팝오버가 열리지 않고 콘솔 경고만 1회 출력(사용자 무반응은 허용).
- [ ] (통합) ESC 키 입력 시 팝오버 닫힘 + 포커스가 **직전에 클릭했던 `.info-btn`** 으로 복원(`document.activeElement === openedBtn`).
- [ ] (통합) 팝오버 외부(빈 공간, 다른 `.trow`, 사이드바 등) 클릭 시 닫힘. `.info-btn` 자체 클릭은 제외(토글 로직이 우선).
- [ ] (통합) 페이지 스크롤 또는 윈도우 리사이즈 이벤트 발생 시 팝오버 자동 닫힘.
- [ ] (접근성) `<button>` 기본 동작으로 Tab → 포커스 이동 + Enter/Space 입력 시 click 이벤트 디스패치되어 팝오버 열림. `aria-expanded` 속성이 열림/닫힘 상태를 정확히 반영.
- [ ] (회귀) HTML 응답에 `setupTaskTooltip`, `#trow-tooltip`, `mouseenter`(팝오버 관련), `mouseover`(팝오버 관련) 문자열이 **0회** 등장. `setupInfoPopover`, `renderInfoPopoverHtml`, `#trow-info-popover`, `.info-popover`는 각 1회 이상 등장.

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**
- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 (URL 직접 입력 금지)
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다
