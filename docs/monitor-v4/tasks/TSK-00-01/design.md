# TSK-00-01: 공용 spinner CSS + 범용 fold 헬퍼 - 설계

## 요구사항 확인
- v4 전반에서 공유할 `@keyframes spin` 공용 키프레임과 `.spinner`/`.node-spinner` 클래스를 인라인 CSS에 1회 추가 (PRD §2 P0-2, AC-5/AC-6).
- 현재 wp-cards 전용(`details[data-wp]`)으로 하드코딩된 fold 영속성 로직을 `data-fold-key` + `data-fold-default-open` 속성 기반 범용 헬퍼 4종으로 일반화하되 wp-cards 기본 열림과 기존 localStorage prefix(`dev-monitor:fold:`)는 무회귀 유지 (PRD §2 P0-4, AC-7/AC-8/AC-9).
- 이 Task는 계약 전용(contract-only) — 소비자(TSK-01-02/02-02/03-02)가 이 계약에 의존하므로 API 표면만 노출하고 기존 동작은 그대로.

## 타겟 앱
- **경로**: N/A (단일 앱 — dev-plugin 저장소 자신이 monitor-server.py 단일 스크립트 구조)
- **근거**: `scripts/monitor-server.py`가 HTTP 서버 + SSR + 인라인 CSS/JS를 모두 품은 모놀리식 스크립트이며, monorepo `apps/*` 구조가 없음.

## 구현 방향
1. `_DASHBOARD_CSS` 인라인 스타일 블록 상단(기존 `@keyframes pulse` 근처, L1254 부근) 바로 위에 `@keyframes spin` + `.spinner`/`.node-spinner` 기본 스타일 + `.trow[data-running="true"] .spinner`/`.dep-node[data-running="true"] .node-spinner` 노출 규칙을 단일 블록으로 추가.
2. `_DASHBOARD_JS` 내 `readFold`/`writeFold`/`applyFoldStates`/`bindFoldListeners` 4 함수를 `data-fold-key` + `data-fold-default-open` 기반으로 재작성. 기존 시그니처(`readFold(wpId)`, `writeFold(wpId, open)`)를 `readFold(key, defaultOpen)`, `writeFold(key, open)`로 확장하되 기존 wp-cards 호출부가 깨지지 않도록 호출측(`_section_wp_cards`의 `<details data-wp="X" open>`)을 `<details data-fold-key="X" data-fold-default-open>` 로 마이그레이션.
3. `patchSection`의 `wp-cards` 특례에서 `applyFoldStates(current)`/`bindFoldListeners(current)` 호출은 그대로 유지 — 헬퍼 내부만 `[data-fold-key]` 셀렉터로 바뀜.
4. 기존 `test_monitor_fold.py`(v3 WP-05) 전체 통과를 회귀 기준선으로 삼는다. 셀렉터 `details[data-wp]` → `details[data-fold-key]` 전이를 수용할 수 있도록 test fixture html도 필요 시 양쪽 속성을 모두 포함(실제 런타임 DOM은 `data-fold-key`로 통일).

## 파일 계획

**경로 기준:** 모든 파일 경로는 프로젝트 루트(`/Users/jji/project/dev-plugin/`) 기준. 단일 앱이므로 접두어 없음.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | ① `_DASHBOARD_CSS`에 `@keyframes spin` + `.spinner`/`.node-spinner` 블록 추가 (L1253 근처). ② `_DASHBOARD_JS`의 `readFold`/`writeFold`/`applyFoldStates`/`bindFoldListeners` 4함수 시그니처·셀렉터 변경 (L3755~3778). ③ `_section_wp_cards`에서 `<details class="wp wp-tasks" data-wp="..." open>` → `<details class="wp wp-tasks" data-fold-key="..." data-fold-default-open open>` 치환 (L2875, L2879). | 수정 |
| `scripts/test_monitor_shared_css.py` | 신규 단위 테스트. `@keyframes spin` 정확히 1회 포함 검증 + `.spinner`/`.node-spinner` 클래스 선언 + `.trow[data-running="true"] .spinner`/`.dep-node[data-running="true"] .node-spinner` 노출 규칙 검증. | 신규 |
| `scripts/test_monitor_fold_helper_generic.py` | 신규 단위 테스트. JS 소스 grep 방식으로 `readFold(key, defaultOpen)` 시그니처 + `querySelectorAll('[data-fold-key]')` + `data-fold-default-open` 처리 + `_foldBound` 플래그 존재 검증. | 신규 |
| `scripts/test_monitor_fold.py` | (회귀 기준선) 기존 v3 테스트. **수정 최소화** — 셀렉터/시그니처 변경으로 깨지는 케이스만 새 속성명(`data-fold-key`)을 수용하도록 최소 패치. | 수정 (회귀 흡수) |

> 라우터·메뉴 파일 항목은 본 Task 범위 밖(계약 전용) — 진입점 섹션 "N/A" 참조.

## 진입점 (Entry Points)

본 Task는 wbs.md `entry-point: library` — 라이브러리성 공용 유틸(CSS keyframe 1종 + JS 헬퍼 4종) 계약 전용이지만, 해당 유틸이 즉시 바인딩되는 상위 페이지(대시보드 루트)와 수정할 라우터/네비게이션 파일을 명시하여 변경 범위를 특정한다.

- **사용자 진입 경로**: 브라우저에서 대시보드 루트 URL 진입 → 상단 서브프로젝트 탭에서 `monitor-v4` 클릭 → 작업 패키지(WP-00) 카드 `<summary>` 클릭으로 접힘/펼침 토글 (토글 시 `<details data-fold-key>`에 바인딩된 `toggle` 이벤트가 localStorage 동기화를 수행). 스피너 가시화 클릭 경로는 소비자 Task(TSK-02-02/TSK-03-02) 범위이며, 본 Task는 CSS 규칙 주입만 담당.
- **URL / 라우트**: `/?subproject=monitor-v4&lang=ko` (monitor-server.py `do_GET` 루트 핸들러 — `render_dashboard(model, lang, sps, sp)`)
- **수정할 라우터 파일**: `scripts/monitor-server.py`의 `render_dashboard` 함수 (인라인 HTML/CSS/JS 템플릿 — 별도 라우터 엔진 없이 `do_GET` 분기가 라우터 역할). 수정 지점은 `_DASHBOARD_CSS` 문자열 상수(L1254 근처 `@keyframes pulse` 위) + `_DASHBOARD_JS` 문자열 상수 내 `readFold`/`writeFold`/`applyFoldStates`/`bindFoldListeners` 4함수 정의부(L3755~3778) + `_section_wp_cards` 함수(L2875/L2879)의 `<details>` 속성 치환.
- **수정할 메뉴·네비게이션 파일**: `scripts/monitor-server.py`의 `_section_wp_cards` 함수 내 `<details class="wp wp-tasks" data-wp="..." open>` 블록 — 본 프로젝트에서 WP 카드가 네비게이션 역할(Task 그룹 접힘/펼침 메뉴)을 겸한다. `data-wp` 속성을 `data-fold-key` + `data-fold-default-open`로 치환. 별도의 사이드바/nav 컴포넌트 파일은 존재하지 않음(단일 SSR 스크립트 구조).
- **연결 확인 방법**: `monitor-server.py`를 포트 7321로 기동 후 브라우저에서 `/?subproject=monitor-v4` 진입 → WP-00 카드 `<summary>` 클릭으로 접음 → 하드 리로드(F5) → 카드가 접힌 상태로 복원됨. DevTools Console에서 `document.querySelectorAll('[data-fold-key]').length > 0` 확인. `@keyframes spin`은 Computed Style에서 `.spinner` 규칙으로 확인.

**비-페이지 UI 소비 맵**: 공용 CSS/JS 헬퍼가 실제로 소비되는 상위 렌더 컨텍스트는 (a) wp-cards `<details data-fold-key="{WP-ID}">` (본 Task 범위), (b) live-activity `<details data-fold-key="live-activity">` (TSK-01-02), (c) Task 행 `.trow[data-running]` 내부 `.spinner` (TSK-02-02), (d) Dep-Graph `.dep-node[data-running]` 내부 `.node-spinner` (TSK-03-02). 본 Task E2E는 (a)의 기존 `test_monitor_fold.py` 회귀로 커버.

## 주요 구조

- **CSS 블록**: `_DASHBOARD_CSS`의 `@keyframes pulse` 바로 위 또는 `:root` 변수 블록 직후에 삽입. `.spinner`/`.node-spinner` 공통 선언 + `.trow[data-running="true"] .spinner`/`.dep-node[data-running="true"] .node-spinner` 노출 규칙 한 덩어리.
- **`readFold(key, defaultOpen)`**: `localStorage.getItem('dev-monitor:fold:' + key)`를 읽어 `'open'` → `true`, `'closed'` → `false`, 그 외 → `defaultOpen` 반환. localStorage 접근 예외는 삼켜서 `defaultOpen` fallback.
- **`writeFold(key, open)`**: `localStorage.setItem('dev-monitor:fold:' + key, open ? 'open' : 'closed')`. 예외 삼킴.
- **`applyFoldStates(container)`**: `container.querySelectorAll('[data-fold-key]')` 순회. 각 요소에 대해 `data-fold-default-open` 속성 존재 여부로 기본값 결정 → `readFold(key, default)` 결과로 `open` 속성 on/off.
- **`bindFoldListeners(container)`**: 동일 셀렉터 순회. `el._foldBound` 플래그로 중복 바인딩 방지 후 `toggle` 이벤트에서 `writeFold(key, el.open)`.
- **호출측 마이그레이션**: `_section_wp_cards`의 `<details>` 두 지점(L2875/L2879)에서 `data-wp="{WP-ID}" open` → `data-fold-key="{WP-ID}" data-fold-default-open open` 로 치환. `data-wp` 속성은 후속 섹션 질의에 쓰이는지 확인 후, 쓰이면 **함께 유지**(backward-compat), 쓰이지 않으면 제거. (현재 grep 결과로는 readFold/writeFold 컨텍스트 외에서 `data-wp` 사용 없음 → 제거해도 안전하나 리스크 최소화 목적으로 유지 권장.)

## 데이터 흐름

```
사용자 <details> toggle
   │
   ▼
bindFoldListeners가 등록한 'toggle' 이벤트 핸들러
   │
   ▼
writeFold(key, el.open) → localStorage['dev-monitor:fold:' + key] = 'open'|'closed'
   │
   ▼ (5초 auto-refresh / 하드 리로드)
patchSection('wp-cards' or 'live-activity') → innerHTML 교체
   │
   ▼
applyFoldStates(container) → readFold(key, default) → 각 <details>에 open 속성 반영
```

스피너 경로: 서버 SSR이 `data-running="true"` 속성을 `trow`/`dep-node`에 붙이면 CSS 규칙 `.trow[data-running="true"] .spinner { display:inline-block }` 만으로 스피너 가시화. JS 개입 없음 — 5초 polling 중 DOM innerHTML 교체가 일어나도 CSS 규칙은 문서 전역에 남아있어 자동 생존.

## 설계 결정

- **결정**: `data-wp` → `data-fold-key`로 속성명 변경 + `data-fold-default-open` 별도 속성 도입.
- **대안 1**: 기존 `data-wp` 유지하고 셀렉터만 `[data-wp], [data-activity-fold]` 식으로 OR 확장.
- **대안 2**: 헬퍼 함수를 두 벌로 유지(`readWpFold`/`readActivityFold`).
- **근거**: (a) PRD가 `data-fold-key`/`data-fold-default-open` 속성명을 명시적으로 요구, (b) 3개 이상의 소비자(wp-cards, live-activity, 향후 추가 가능)에 대해 OR 셀렉터 확장은 유지보수 부담, (c) 두 벌 유지는 DRY 위반. 대안은 backward-compat 장점이 있으나 localStorage 키 prefix(`dev-monitor:fold:`)가 그대로이므로 사용자 fold 상태는 속성명 변경과 무관하게 보존된다 → 마이그레이션 리스크는 런타임 DOM 셀렉터 전환 1회로 국한.

- **결정**: CSS는 `display:none` 기본 + `[data-running="true"]` 컨텍스트 오픈 방식.
- **대안**: JS에서 동적으로 class toggle.
- **근거**: PRD §AC-5/AC-6가 CSS 선택자 기반 검증(`display:inline-block`)을 명시. JS 의존 최소화로 토큰·성능·테스트 복잡도 모두 절감.

## 선행 조건

- **없음**. 이 Task 자체가 v4 전체의 선행 계약(fan-in 3: TSK-01-02/02-02/03-02이 `depends: TSK-00-01`).
- 외부 라이브러리 금지, Python 3 stdlib + vanilla JS only (wbs constraints). 기존 CSS 변수 `--run`/`--ink-3`/`--bg-2` 재사용.

## 리스크

- **MEDIUM**: `data-wp` → `data-fold-key` 속성명 전환 시 기존 `test_monitor_fold.py`가 `data-wp` 문자열을 grep하면 회귀. → 테스트 파일 내 `data-wp` 언급은 셀렉터 개념 검증이 목적이므로 `data-fold-key`로 갱신하거나 `data-wp` 호환층을 남겨 흡수. dev-build 단계에서 테스트 파일 diff를 최소 1줄씩 검토.
- **MEDIUM**: `@keyframes spin` 중복 방지 (AC-5 "정확히 1회"). monitor-server.py 내 기존 `@keyframes pulse/led-blink/breathe/fade-in`과는 이름 충돌 없음을 grep으로 확인 완료. 향후 v4 소비자 Task가 실수로 재삽입하지 않도록 주석 `/* shared — do not duplicate */` 부착.
- **LOW**: `localStorage` 접근 예외(프라이빗 모드 등) — 기존 `try/catch`를 그대로 유지하므로 회귀 없음.
- **LOW**: 인라인 CSS 삽입 위치 선택 — `:root` 변수 정의 뒤로 배치하여 변수 미정의로 인한 렌더 오류 가능성 차단.

## QA 체크리스트
dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

- [ ] (정상) 렌더된 대시보드 HTML에 `@keyframes spin` 문자열이 **정확히 1회** 포함된다 (AC-5 `test_monitor_shared_css_has_spin_keyframe`).
- [ ] (정상) `.spinner` 와 `.node-spinner` 클래스 CSS 선언이 각각 최소 1회 존재하고 `animation: spin` 토큰을 포함한다.
- [ ] (정상) `.trow[data-running="true"] .spinner { display:inline-block }` 와 `.dep-node[data-running="true"] .node-spinner { display:inline-block; position:absolute; top:4px; right:4px }` 규칙이 존재한다 (AC-5/AC-6 기반선).
- [ ] (정상) `readFold('X', true)` 호출 시 localStorage 미지정이면 `true`, `readFold('X', false)`는 `false` 반환 (AC-9 기반 단위 테스트 `test_monitor_fold_helper_generic_data_key`).
- [ ] (정상) `writeFold('X', true)` 후 `localStorage.getItem('dev-monitor:fold:X') === 'open'`, `writeFold('X', false)` 후 `'closed'`.
- [ ] (정상) `<details data-fold-key="X" data-fold-default-open>` + localStorage 값 `'closed'` → `applyFoldStates(document)` 호출 후 `open` 속성이 제거된다. 역으로 `data-fold-default-open` 없고 localStorage 값 `'open'` → `open` 속성이 추가된다.
- [ ] (엣지) `data-fold-key` 없는 `<details>`는 `applyFoldStates` 순회 대상에서 제외되어 `open` 속성이 변경되지 않는다.
- [ ] (엣지) `bindFoldListeners`를 동일 컨테이너에 2회 호출해도 `toggle` 이벤트 핸들러가 1회만 실행된다(`_foldBound` 플래그).
- [ ] (에러) `localStorage` 접근이 예외를 던져도 `readFold` 는 `defaultOpen` 반환, `writeFold` 는 조용히 실패한다.
- [ ] (통합) 기존 `scripts/test_monitor_fold.py` 전체 통과 — wp-cards fold 영속성에 회귀 없음 (AC-7/AC-8/AC-9 회귀 기준선).
- [ ] (통합) 5초 auto-refresh로 wp-cards innerHTML이 교체된 후에도 사용자가 접어놓은 WP 카드의 접힘 상태가 복원된다.

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**
- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 (URL 직접 입력 금지) — 본 Task는 library 성격의 공용 계약이므로 클릭 경로 E2E는 소비자 Task(TSK-01-02)에서 검증한다. 본 Task는 대시보드 루트(`/?subproject=monitor-v4`) 진입 후 기존 WP 카드를 접었다가 펼치는 상호작용으로 기반선 검증만 수행.
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다 — 대시보드 루트 진입 시 `@keyframes spin` 주입이 브라우저 DevTools Computed Style에서 확인되고, `<details data-fold-key>` 클릭 시 localStorage 값이 동기적으로 갱신된다.
