# TSK-04-03: WP 카드 뱃지 렌더 + 슬라이드 패널 통합 - 설계

## 요구사항 확인

- `_section_wp_cards()` 내 각 WP 카드 헤더에 `_merge_badge(ws, lang)` 헬퍼를 호출하여 머지 준비도 뱃지를 삽입한다. 뱃지는 WP 제목 우측(fold 토글 옆) flex 컨테이너에 배치된다 (PRD §2 P1-10, §5 AC-24).
- TSK-02-04에서 구축한 `#task-panel` DOM을 재사용하여 머지 모드 패널을 추가한다. `data-panel-mode="task"|"merge"` attr로 모드를 구분하며, 클라이언트 JS `openMergePanel(wpId)` 가 `/api/merge-status?wp={wpId}` fetch 후 `§ 머지 프리뷰` 섹션으로 렌더한다 (PRD §5 AC-26, TRD §3.12 `openMergePanel()`).
- state 판정 소스는 `docs/wp-state/{WP-ID}/merge-status.json` (TSK-04-02가 `merge-preview-scanner.py` 로 생성). 필드 누락 시 `state="unknown"` graceful degradation. `AUTO_MERGE_FILES` 충돌 파일은 패널 상세에서 회색 disabled `<li>` 로 표시 (PRD §5 AC-24, §4 S9).

## 타겟 앱

- **경로**: N/A (단일 앱 — `scripts/monitor-server.py` SSR 모놀리스 + `skills/dev-monitor/vendor/` 클라이언트 JS)
- **근거**: dev-plugin 대시보드는 별도 프레임워크 없이 `monitor-server.py` 내부 문자열 템플릿으로 SSR하며, 클라이언트 JS는 `vendor/` 디렉토리에 벤더링된다. 별도 라우터 파일이나 네비게이션 설정 파일이 존재하지 않는다.

## 구현 방향

- **SSR (monitor-server.py)**: `_merge_badge(ws: dict, lang: str) -> str` 순수 함수를 추가하여 state별 emoji + label + stale 표식을 `<button class="merge-badge">` 로 반환한다. `_section_wp_cards()` 내 `wp_title_html` 구성 시 `row1` div 우측에 뱃지를 삽입한다. `/api/merge-status?wp={WP-ID}&subproject={sp}` 라우트는 TSK-04-02에서 구현되므로, 본 Task는 소비 측(SSR 뱃지 + 클라이언트 fetch)만 담당한다.
- **클라이언트 JS**: 기존 `_TASK_PANEL_JS` 에 `openMergePanel(wpId)`, `renderMergePreview(ms)`, `closeMergePanel()` 함수를 추가한다. `#task-panel` DOM에 `data-panel-mode` attr를 설정하여 task/merge 모드를 구분하고, document-level click delegation에 `.merge-badge` 분기를 추가한다.
- **패널 DOM 공유**: 기존 `#task-panel`, `#task-panel-overlay`, `#task-panel-title`, `#task-panel-body`를 그대로 재사용한다. 새 패널 DOM 생성 금지 제약(WBS constraints)을 준수한다.
- **CSS**: `.merge-badge` + `[data-state="*"]` 변형자 규칙을 `_task_panel_css()` 에 추가한다. 기존 `:root` 변수(`--done`, `--run`, `--fail`)를 재사용한다.

## 파일 계획

**경로 기준:** 프로젝트 루트 기준. 단일 앱이므로 접두어 없음.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `_merge_badge(ws, lang)` 헬퍼 추가, `_section_wp_cards()` 의 `wp_title_html` row1 우측에 뱃지 삽입, `_task_panel_css()` 에 `.merge-badge` CSS 추가, `_TASK_PANEL_JS` 에 `openMergePanel`/`renderMergePreview`/`closeMergePanel` + `.merge-badge` click delegation 추가 | 수정 |
| `skills/dev-monitor/vendor/graph-client.js` | 현재 이 파일은 그래프 전용 IIFE — merge-badge delegation은 `_TASK_PANEL_JS`(monitor-server.py 인라인)에 추가하므로 **이 파일은 본 Task에서 수정 없음**. 단, TSK-04-02 에서 `applyFilter` 훅이 추가되면 이 파일도 수정될 수 있으나 그것은 해당 Task 범위. | 무변경(본 Task 범위) |
| `scripts/test_monitor_merge_badge.py` | `_merge_badge` 4개 state HTML 렌더 단위 테스트, `.merge-badge` 클릭 delegation JS 통합 확인, `data-panel-mode` 전환 단위 테스트, `AUTO_MERGE_FILES` 회색 disabled 렌더 확인 | 신규 |
| `scripts/test_monitor_merge_badge_e2e.py` | E2E `test_merge_badge_e2e` — 실 브라우저에서 뱃지 클릭 → 패널 열림 → `§ 머지 프리뷰` 섹션 표시 확인 | 신규 |
| `docs/monitor-v4/tasks/TSK-04-03/test-report.md` | dev-test 산출물 (설계 단계에서는 생성하지 않음) | 신규(후속) |
| `docs/monitor-v4/tasks/TSK-04-03/refactor.md` | dev-refactor 산출물 (설계 단계에서는 생성하지 않음) | 신규(후속) |

> **플러그인 캐시 동기화 리스크**: `scripts/monitor-server.py`와 관련 테스트 파일 수정 후 `~/.claude/plugins/cache/dev-tools/dev/1.5.2/` 에 반드시 동기화해야 한다 (CLAUDE.md 규약). 캐시 동기화 누락 시 다른 세션에서 구버전이 적용되는 무성 회귀가 발생한다. 동기화는 dev-build 단계 완료 후 별도 단계로 수행한다.

## 진입점 (Entry Points)

- **사용자 진입 경로**: 브라우저에서 대시보드 루트(`http://localhost:7321/?lang=ko&subproject=monitor-v4`) 접속 → "작업 패키지" 섹션(`data-section="wp-cards"`) 에서 임의 WP 카드 헤더 확인 → WP 제목 우측에 표시된 머지 준비도 뱃지(`.merge-badge`, 예: `🟢 머지 가능` / `🟡 N Task 대기`) 클릭 → 우측에서 `#task-panel` 이 `data-panel-mode="merge"` 로 전환되며 슬라이드 인 → `§ 머지 프리뷰` 섹션(state별 본문) 표시 → `×` 버튼 / overlay 클릭 / `Esc` 로 닫기.
- **URL / 라우트**: 페이지는 `/?subproject=monitor-v4&lang=ko` (기존 루트 재사용, 신규 페이지 없음). 데이터 API는 `/api/merge-status?wp={WP-ID}&subproject={sp}` (TSK-04-02 구현, 본 Task는 소비만).
- **수정할 라우터 파일**: `scripts/monitor-server.py` — 별도 라우터 파일 없음. `_section_wp_cards()` 함수(현재 L3041)의 `wp_title_html` 구성 블록 내 `row1` div 에 `_merge_badge(ws, lang)` 출력을 우측 flex 아이템으로 삽입하는 것이 유일한 SSR 진입점 수정이다. `/api/merge-status` 라우트 자체는 TSK-04-02 범위이므로 본 Task의 `do_GET` 수정은 없다.
- **수정할 메뉴·네비게이션 파일**: `scripts/monitor-server.py` 의 `_section_wp_cards()` 함수 — WP 카드 헤더(`wp_title_html` 내 `row1` div)에 뱃지 버튼을 삽입한다. WP 카드 헤더 자체가 유일한 네비게이션 진입점이며, 별도 사이드바/탑바 파일은 없다. 클라이언트 JS delegation은 `_TASK_PANEL_JS` 문자열(monitor-server.py L5337 `_TASK_PANEL_JS = r"""...`)에 `.merge-badge` 분기를 추가한다.
- **연결 확인 방법**: E2E에서 `page.goto('/?subproject=monitor-v4&lang=ko')` (URL 직접 이동은 루트 페이지이므로 허용, 단 뱃지 자체는 클릭으로 접근) → `page.click('.merge-badge[data-wp="WP-02"]')` → `expect(page.locator('#task-panel')).toHaveClass(/open/)` + `expect(page.locator('#task-panel')).toHaveAttribute('data-panel-mode', 'merge')` → 패널 본문에 `§ 머지 프리뷰` 텍스트 존재 확인 → `page.waitForTimeout(5500)` (5초 auto-refresh 경과) 후에도 패널 `.open` 클래스 유지 확인 → `page.keyboard.press('Escape')` 로 닫힘 확인.

## 주요 구조

- **`_merge_badge(ws: dict, lang: str) -> str`** (monitor-server.py 신규): 입력은 WP merge-status dict(`{state, stale, pending_count, conflict_count, wp_id, conflicts}`), 출력은 `<button class="merge-badge" data-state="{state}" data-wp="{wp_id}" aria-label="...">` HTML 문자열. `state` 키 누락 시 `"unknown"` fallback 으로 `🔘 확인 필요` 렌더.
- **`_section_wp_cards()` 수정**: `wp_title_html` 내 `row1` div를 flex 컨테이너로 만들고(`display:flex; align-items:center; gap:8px`), WP-ID `<span>` + `<h3>` 우측에 `_merge_badge(wp_merge_state.get(wp, {}), lang)` 삽입. `wp_merge_state: dict`는 `/api/merge-status` on-demand 대신 `render_dashboard` 호출 시 미리 스캔한 WP 요약 dict (기존 `_load_wp_merge_states(docs_dir)` 패턴 — TSK-04-02 설계 계약에 따라 `docs/wp-state/{WP-ID}/merge-status.json` 을 mtime 기반 캐시로 읽는다).
- **`openMergePanel(wpId)`** (클라이언트 JS 추가): `fetch('/api/merge-status?wp='+wpId+'&subproject='+sp)` → 응답 JSON → `#task-panel-title` 에 `{WP-ID} — 머지 프리뷰` 설정 → `#task-panel-body.innerHTML = renderMergePreview(ms)` → `#task-panel.dataset.panelMode = 'merge'` → `classList.add('open')` + overlay 표시.
- **`renderMergePreview(ms)`** (클라이언트 JS 추가): state 별 본문 분기. `is_stale=true` 시 상단 warn 배너 선행 삽입. `state='ready'` → "모든 Task 완료 · 충돌 없음" 배너. `state='waiting'` → pending Task `<ul>` 목록(TSK-ID + phase). `state='conflict'` → 충돌 파일 `<ul>` + hunk preview `<pre>` 최대 5개. `AUTO_MERGE_FILES`에 해당하는 항목은 `<li class="disabled">` + 라벨 "auto-merge 드라이버 적용 예정".
- **`.merge-badge` click delegation**: 기존 `_TASK_PANEL_JS` 의 `document.addEventListener('click', ...)` 핸들러에 분기 추가 — `e.target.closest('.merge-badge')` 매치 시 `openMergePanel(btn.dataset.wp)` 호출. `closeTaskPanel()` → `closePanel()` 로 범용화(task/merge 공통 닫기).

## 데이터 흐름

```
SSR (render_dashboard 호출 시)
  _load_wp_merge_states(docs_dir)
    └─ docs/wp-state/{WP-ID}/merge-status.json 읽기 (mtime 캐시, TSK-04-02 산출물)
  _section_wp_cards(tasks, ..., wp_merge_state=wp_merge_state, lang=lang)
    └─ per WP: _merge_badge(wp_merge_state.get(wp, {}), lang) → <button class="merge-badge"> 삽입

클라이언트 (뱃지 클릭 시)
  click .merge-badge
    └─ openMergePanel(dataset.wp)
         └─ fetch /api/merge-status?wp={WP-ID}&subproject={sp}   (TSK-04-02 라우트)
              └─ JSON 응답 (state, stale, conflicts, pending_tasks, ...)
                   └─ renderMergePreview(ms) → #task-panel-body.innerHTML
                   └─ #task-panel.dataset.panelMode = 'merge'
                   └─ #task-panel.classList.add('open')

5초 auto-refresh 발생 시
  patchSection('wp-cards', newHtml) → 뱃지 innerHTML 교체
  #task-panel 은 body 직계 → 영향 없음
  document-level delegation → 재바인딩 불필요
```

## 설계 결정

### 1. `#task-panel` DOM 공유 — 새 패널 DOM 생성 금지

- **결정**: TSK-02-04가 구현한 `#task-panel`, `#task-panel-overlay`, `#task-panel-title`, `#task-panel-body` DOM을 그대로 재사용한다. 모드 구분은 `#task-panel.dataset.panelMode` (`"task"` | `"merge"`) attr 으로 한다.
- **대안**: 머지 전용 `#merge-panel` DOM을 별도 생성하는 안.
- **근거**: WBS constraints가 "새 패널 DOM 생성 금지"를 명시적으로 요구한다. 또한 동시에 두 패널이 열리는 시나리오는 없으므로 단일 DOM 재사용이 코드 중복 없이 더 간결하다.

### 2. SSR 뱃지 state 소스 — `_load_wp_merge_states()` 미리 로드

- **결정**: `render_dashboard` 호출 시 `_load_wp_merge_states(docs_dir)` 로 WP별 merge-status.json을 일괄 읽어 `_section_wp_cards()` 에 `wp_merge_state` 인자로 전달한다.
- **대안**: `_section_wp_cards()` 내부에서 WP별로 파일을 직접 읽는 안, 또는 클라이언트가 `/api/merge-status` 로 뱃지 state를 fetch하는 SPA 방식.
- **근거**: SSR에서 뱃지를 포함하면 첫 렌더에서 JS 없이도 상태가 표시되어 robustness가 높다. `docs/wp-state/` 파일 수는 WP 수(통상 3~10개)이므로 초기 로드 비용 무시할 수준.

### 3. `openMergePanel` vs. `openTaskPanel` 공통화

- **결정**: `openTaskPanel`과 `openMergePanel`을 별도 함수로 유지한다. 공통 닫기는 `closePanel()` (또는 기존 `closeTaskPanel()` 그대로 재사용)로 통일한다.
- **대안**: `openPanel(mode, id)` 단일 함수로 통합하는 안.
- **근거**: fetch 엔드포인트(task-detail vs. merge-status), 헤더 텍스트 포맷, 본문 렌더 함수가 완전히 다르다. 통합하면 분기가 복잡해지고 개별 테스트가 어려워진다. WBS note에도 "`openMergePanel(wpId)` 만 추가"라고 명시되어 있다.

### 4. `_load_wp_merge_states()` 파일 읽기 실패 시 graceful degradation

- **결정**: `docs/wp-state/{WP-ID}/merge-status.json` 파일이 없거나 파싱 실패 시 `{}` 빈 dict로 폴백한다. `_merge_badge({}, lang)` 는 `state="unknown"` 뱃지를 렌더한다.
- **근거**: TSK-04-02 스캐너가 아직 실행되지 않은 초기 상태(파일 미존재)에서도 대시보드가 크래시 없이 렌더되어야 한다.

## 선행 조건

- **TSK-02-04 (슬라이드 패널 인프라)**: 이미 구현 완료. `#task-panel` DOM, `.slide-panel` CSS, `openTaskPanel`/`closeTaskPanel` JS, document-level click/keydown delegation이 `monitor-server.py`에 존재한다 (L5300 `_task_panel_css()`, L5337 `_TASK_PANEL_JS`, L5423 `_task_panel_dom()`).
- **TSK-04-02 (`/api/merge-status` + `merge-preview-scanner.py`)**: 런타임에 `/api/merge-status` 가 응답해야 클라이언트 JS가 머지 프리뷰를 렌더할 수 있다. 단, 미구현 상태에서도 SSR 뱃지는 `docs/wp-state/` 파일 기반으로 독립 렌더 가능(파일 없으면 unknown 뱃지). 본 Task 설계·구현은 TSK-04-02와 병렬 진행 가능하나 통합 E2E는 TSK-04-02 완료 후 실행해야 한다.
- 외부 라이브러리 추가 없음 (Python stdlib + 바닐라 JS 제약 유지).

## 리스크

- **HIGH: TSK-02-04 슬라이드 패널 DOM 경합** — `task` 모드와 `merge` 모드가 동일 `#task-panel-body`를 공유하므로 task expand → merge 뱃지 클릭(또는 역방향) 시 `data-panel-mode` attr 전환 누수 가능성. 특히 `openTaskPanel`이 mode를 `"task"`로 재설정하지 않으면 닫은 후 재열기 시 이전 `"merge"` 모드 레이블이 헤더에 남을 수 있다. **완화**: `openTaskPanel` / `openMergePanel` 각각 호출 시 `data-panel-mode`를 명시 설정. 단위 테스트 `test_slide_panel_mode_switch`로 task → merge → task 전환을 검증.
- **MEDIUM: 5초 auto-refresh 중 뱃지 이벤트 생존** — `patchSection('wp-cards', newHtml)` 호출 시 `wp-cards` 섹션의 innerHTML이 교체되어 `.merge-badge` 요소가 새로 생성된다. `onclick` 직접 바인딩 방식이면 이벤트가 소멸한다. **완화**: document-level delegation(`document.addEventListener('click', ...)`) 으로 구현하므로 섹션 재렌더 후에도 자동 생존. 단위 테스트에서 patchSection 후 `.merge-badge` 클릭이 `openMergePanel`을 호출하는지 검증.
- **MEDIUM: TSK-04-02 `/api/merge-status` 스키마와 프런트 계약 드리프트** — TRD §3.12 명세 기준으로 `renderMergePreview(ms)` 를 구현하지만, TSK-04-02 빌드 결과에서 필드명 변경이 발생하면 패널이 빈 화면으로 렌더된다. **완화**: `renderMergePreview`는 모든 필드 접근에 `||` 폴백 디폴트 적용 (`ms.state || 'unknown'`, `ms.conflicts || []`). 통합 E2E `test_merge_badge_e2e`에서 실제 API 응답으로 검증.
- **LOW: WP 카드 헤더 레이아웃 깨짐** — `row1` div에 뱃지를 추가할 때 WP-ID `<span>` + `<h3>` 와 flex 정렬 불일치 시 줄 바꿈 발생 가능. **완화**: `row1`을 `display:flex; align-items:center; gap:8px; flex-wrap:nowrap` 으로 설정, `.merge-badge`에 `flex-shrink:0` 추가. 필터 바(TSK-05-01) 도입 시에도 flexbox 정렬이 깨지지 않도록 명세한다.
- **LOW: `state="unknown"` 뱃지 표시 혼란** — TSK-04-02 스캐너가 실행되지 않은 초기 상태에서 모든 WP가 `🔘 확인 필요` 뱃지를 표시. **완화**: unknown 뱃지는 회색으로 구분, 클릭 시 패널에 "스캔 데이터 없음 — merge-preview-scanner.py 를 실행하세요" 안내 메시지 표시.

## QA 체크리스트

dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

**단위 테스트 (4개)**

- [ ] (정상) `test_wp_merge_badge_states` — `_merge_badge` 함수에 4개 state dict 입력 시 각각 올바른 HTML 출력: `state='ready'` → `class="merge-badge" data-state="ready"` + 🟢 이모지, `state='waiting'` → 🟡 + pending_count 포함 라벨, `state='conflict'` → 🔴 + conflict_count 포함 라벨, `state='stale'`(`is_stale=True`) → `<span class="stale">⚠ stale</span>` 포함 (AC-24).
- [ ] (정상) `test_merge_badge_click_opens_preview_panel` — `_section_wp_cards()` 반환 HTML에 `<button class="merge-badge" data-wp="WP-02">` 가 포함되며, `openMergePanel` JS delegation 분기가 `.merge-badge` 클릭 이벤트를 처리하는 코드 경로가 `_TASK_PANEL_JS`에 존재한다 (AC-26).
- [ ] (정상) `test_slide_panel_mode_switch` — `openTaskPanel` 호출 후 `#task-panel.dataset.panelMode === 'task'`, 이어서 `openMergePanel` 호출 후 `'merge'` 로 전환되고 이전 task 모드 제목이 헤더에 남지 않음. `closePanel()` 후 재열기 시에도 올바른 모드 설정 확인.
- [ ] (정상) `test_auto_merge_files_greyed_in_panel` — `renderMergePreview({state:'conflict', conflicts:[{file:'state.json', ...}, {file:'main.py', ...}]})` 호출 시 `state.json` entry 가 `<li class="disabled">` + "auto-merge 드라이버 적용 예정" 라벨로 렌더, `main.py` entry는 일반 `<li>` 로 렌더 (AC-24, PRD §4 S9).

**E2E 테스트 (1개)**

- [ ] (통합 E2E) `test_merge_badge_e2e` — 실 브라우저에서: (1) 대시보드 루트 접속 → WP 카드 헤더의 `.merge-badge` 존재 확인 → 클릭 → `#task-panel` `.open` 클래스 획득 + `data-panel-mode="merge"` 확인 + `§ 머지 프리뷰` 텍스트 표시 확인, (2) 5초 auto-refresh 경과 후에도 패널 유지 확인, (3) `Esc` 키로 패널 닫힘 확인, (4) 이후 `.expand-btn` 클릭 → task 모드로 전환되고 `data-panel-mode="task"` 확인 (AC-26).

**fullstack 필수 항목**

- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 (URL 직접 입력 금지) — 대시보드 WP 카드 헤더의 `.merge-badge` 버튼을 클릭하여 `#task-panel`(머지 프리뷰 모드)에 도달한다 (E2E `test_merge_badge_e2e`).
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다 — WP별 머지 뱃지가 브라우저에서 state에 따른 올바른 emoji + label 로 표시되고, 클릭 시 슬라이드 패널이 열리며 `§ 머지 프리뷰` 본문이 렌더된다. state=`conflict` 시 충돌 파일 목록과 `AUTO_MERGE_FILES` 회색 항목이 표시된다 (E2E `test_merge_badge_e2e` + browser inspect).

---

## 부록: SSR 뱃지 렌더 상세 명세

### `_merge_badge(ws: dict, lang: str) -> str` 로직

| `ws.get('state')` | emoji | ko label | en label |
|-------------------|-------|----------|----------|
| `'ready'` | 🟢 | `머지 가능` | `Ready` |
| `'waiting'` | 🟡 | `{pending_count} Task 대기` | `{pending_count} pending` |
| `'conflict'` | 🔴 | `{conflict_count} 파일 충돌 예상` | `{conflict_count} conflicts` |
| `'unknown'` / fallback | 🔘 | `확인 필요` | `Unknown` |

`ws.get('stale', False)` 가 `True` 이면 label 뒤에 `<span class="stale">⚠ stale</span>` 추가.

출력 형태:
```
<button class="merge-badge" data-state="{state}" data-wp="{wp_id}" aria-label="merge {state}">
  {emoji} {label}{stale_mark}
</button>
```

### `_section_wp_cards()` 수정 지점

현재 `row1` div (L3117):
```
'  <div class="row1">\n'
f'    <span class="id">{_esc(wp)}</span>\n'
f'    <h3 class="wp-card-title">{_esc(wp_label)}</h3>\n'
'  </div>\n'
```

수정 후:
```
'  <div class="row1" style="display:flex;align-items:center;gap:8px;">\n'
f'    <span class="id">{_esc(wp)}</span>\n'
f'    <h3 class="wp-card-title">{_esc(wp_label)}</h3>\n'
f'    {_merge_badge(wp_merge_state.get(wp, {}), lang)}\n'
'  </div>\n'
```

`wp_merge_state`는 `_section_wp_cards()` 의 새 선택 인자 `wp_merge_state: dict = None` 으로 추가하며, 없으면 `{}` 폴백.

### CSS 추가 규칙 (`_task_panel_css()` append)

```css
/* merge-badge (TSK-04-03) */
.merge-badge {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; border-radius: 12px; cursor: pointer;
  font-size: 11px; font-weight: 600; border: 1px solid transparent;
  flex-shrink: 0; white-space: nowrap;
  background: none; /* state별로 덮어씀 */
}
.merge-badge[data-state="ready"]    { background: var(--done, #22c55e20); color: var(--done, #22c55e); border-color: var(--done, #22c55e); }
.merge-badge[data-state="waiting"]  { background: var(--run,  #eab30820); color: var(--run,  #eab308); border-color: var(--run,  #eab308); }
.merge-badge[data-state="conflict"] { background: var(--fail, #ef444420); color: var(--fail, #ef4444); border-color: var(--fail, #ef4444); }
.merge-badge[data-state="stale"]    { background: transparent; color: var(--ink-3, #cdd6f4); border: 1px dashed var(--ink-3, #cdd6f4); }
.merge-badge[data-state="unknown"]  { background: transparent; color: var(--ink-3, #585b70); border-color: var(--ink-3, #585b70); }
.merge-badge .stale                 { font-size: 10px; opacity: .8; }

/* merge preview panel body */
.merge-stale-banner { padding: 6px 10px; background: var(--run, #eab30820); border: 1px solid var(--run, #eab308); border-radius: 4px; font-size: 12px; margin-bottom: 12px; }
.merge-ready-banner { padding: 6px 10px; background: var(--done, #22c55e20); border: 1px solid var(--done, #22c55e); border-radius: 4px; font-size: 12px; margin-bottom: 12px; }
.merge-conflict-file li.disabled { color: var(--ink-3, #585b70); }
.merge-conflict-file li.disabled code { opacity: .6; }
.merge-hunk-preview { max-height: 120px; overflow: auto; font-size: 11px; font-family: var(--font-mono, monospace); background: var(--bg-1, #181825); border-radius: 4px; padding: 6px; white-space: pre-wrap; word-break: break-all; margin-top: 4px; }
```

### `renderMergePreview(ms)` JS 분기 로직

```
is_stale 배너 (선행)
  └─ ms.stale === true → '<div class="merge-stale-banner">⚠ 스캔 결과가 30분 이상 경과 — 재스캔 필요</div>'

state 분기:
  'ready'    → '<div class="merge-ready-banner">✅ 모든 Task 완료 · 충돌 없음</div>'
  'waiting'  → '<h4>§ 대기 중인 Task</h4><ul>' + ms.pending_tasks.map(t => '<li>'+t.id+' ('+t.phase+')</li>') + '</ul>'
  'conflict' → '<h4>§ 충돌 파일</h4><ul class="merge-conflict-file">' + per_file 분기:
                  AUTO_MERGE_FILES 해당 → '<li class="disabled"><code>'+file+'</code> <span>auto-merge 드라이버 적용 예정</span></li>'
                  일반 충돌 파일       → '<li><code>'+file+'</code>'
                                           + hunk preview (최대 5개, <pre class="merge-hunk-preview">)
               + '</ul>'
  unknown/기타 → '<p>스캔 데이터 없음 — <code>scripts/merge-preview-scanner.py</code> 를 실행하세요.</p>'
```

### `openMergePanel(wpId)` JS 구조

```
function openMergePanel(wpId) {
  var sp = [subproject query from location.search];
  fetch('/api/merge-status?wp=' + encodeURIComponent(wpId) + '&subproject=' + encodeURIComponent(sp))
    .then(r => r.json())
    .then(ms => {
      var panel = document.getElementById('task-panel');
      var title = document.getElementById('task-panel-title');
      var body  = document.getElementById('task-panel-body');
      title.textContent = wpId + ' — 머지 프리뷰';
      body.innerHTML = renderMergePreview(ms);
      panel.dataset.panelMode = 'merge';
      panel.classList.add('open');
      document.getElementById('task-panel-overlay').removeAttribute('hidden');
    })
    .catch(err => {
      // graceful degradation: 패널에 에러 메시지 표시
    });
}
```

### click delegation 추가 (`_TASK_PANEL_JS` 수정)

기존 `document.addEventListener('click', function(e){...})` 에 분기 추가:
```
var badge = e.target.closest ? e.target.closest('.merge-badge') : null;
if (!badge && e.target.classList && e.target.classList.contains('merge-badge')) badge = e.target;
if (badge) { openMergePanel(badge.getAttribute('data-wp') || ''); return; }
```
(`.expand-btn` 분기 앞에 추가하거나, 순서 독립적으로 각 분기를 early-return)

`openTaskPanel()` 내부에 `panel.dataset.panelMode = 'task'` 명시 추가 (모드 전환 누수 방지).
