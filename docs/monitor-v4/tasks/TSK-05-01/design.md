# TSK-05-01: 필터 바 UI + wp-cards 필터링 + URL sync - 설계

## 요구사항 확인

- 대시보드 상단에 sticky 필터 바(`[🔍 검색] [상태 ▼] [도메인 ▼] [모델 ▼] [✕ 초기화]`)를 신규 렌더하고, wp-cards의 비매칭 Task를 `display:none`으로 숨긴다 (PRD §2 P1-11, §4 S10, §5 AC-27, AC-28 부분).
- 필터 상태를 URL 쿼리 파라미터(`?q=...&status=...&domain=...&model=...`)에 양방향 동기화한다. 기존 `subproject`, `lang` 파라미터를 병합 보존한다.
- 5초 auto-refresh로 `patchSection('wp-cards', ...)` 이후에도 필터가 유지되도록 `patchSection` 함수를 monkey-patch한다. 구현은 완전 클라이언트 전용 — 서버/워커 토큰 영향 0.

## 타겟 앱

- **경로**: N/A (단일 앱 — dev-plugin 저장소는 `scripts/` 루트에 Python 모노리스 `monitor-server.py`를 배치한 구조. 별도 `apps/` 없음.)
- **근거**: Dev Config `design_guidance.frontend`가 "SSR HTML은 monitor-server.py 내부 문자열 템플릿"으로 명시. 필터 바 SSR 헬퍼와 인라인 JS 모두 해당 모노리스에 인라인으로 작성.

## 구현 방향

1. **SSR (Python)**: `monitor-server.py`에 `_section_filter_bar(lang, distinct_domains)` 헬퍼 신규 추가. `render_dashboard()`에서 `<header>` 아래 sticky 컨테이너로 삽입. `_render_task_row_v2()`에 `data-domain="{domain}"` 속성 추가(기존 `data-status`/`data-phase`/`data-running`과 병렬). `/api/state` 응답에 `distinct_domains: list[str]` 필드 추가(도메인 select option 채우기용, wbs.md task.domain dedup).
2. **클라이언트 JS**: TRD §3.13 5개 함수(`currentFilters`, `matchesRow`, `applyFilters`, `syncUrl`, `loadFiltersFromUrl`) + 이벤트 바인딩 + `patchSection` monkey-patch를 `monitor-server.py` 인라인 `<script>` 블록에 추가. 별도 벤더 JS 파일 불필요.
3. **CSS**: `.filter-bar` sticky 스타일을 인라인 `<style>` 블록에 추가. 기존 `:root` CSS 변수 재사용.
4. **Dep-Graph 연동**: `window.depGraph.applyFilter(predicate)` 훅 경유 — `graph-client.js`에 `applyFilter` export 추가(TRD §3.13 마지막). 비매칭 노드 `opacity:0.3`, 간선 회색.

## 파일 계획

**경로 기준:** 프로젝트 루트 기준.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | (1) `_section_filter_bar(lang, distinct_domains)` SSR 헬퍼 신규, (2) `render_dashboard()`에 필터 바 삽입 지점 추가, (3) `_render_task_row_v2()`에 `data-domain` 속성 추가, (4) `_handle_api_state()` 응답에 `distinct_domains` 필드 추가, (5) 인라인 `<style>` 블록에 `.filter-bar` CSS 추가, (6) 인라인 `<script>` 블록에 필터 로직 5함수 + 이벤트 바인딩 + `patchSection` wrapping + 초기 로드 시퀀스 추가 | 수정 |
| `skills/dev-monitor/vendor/graph-client.js` | `applyFilter(predicate)` 함수 export 추가 — `cy.nodes()`/`cy.edges()` opacity 조절. `window.depGraph.applyFilter` 로 노출 | 수정 |
| `scripts/test_monitor_filter_bar.py` | 단위 테스트 — 필터 바 DOM 렌더, `data-domain` 속성, URL 상태 왕복, `patchSection` wrapping 후 필터 재적용, 초기화 버튼 | 신규 |
| `scripts/test_monitor_filter_bar_e2e.py` | E2E 테스트 — 실 브라우저 `test_filter_interaction` 시나리오 (필터 입력 → Task 숨김/표시 → URL 동기화) | 신규 |

> 단일 파일(`monitor-server.py`)이 라우터·네비게이션·SSR·JS 모두를 겸하는 구조이므로, "라우터 파일"과 "메뉴/네비게이션 파일"이 동일 파일을 가리킨다. 이 점을 진입점 섹션에 명시.

## 진입점 (Entry Points)

**domain: frontend — 4필드 모두 작성.**

- **사용자 진입 경로**: `대시보드 메인(/) 접속 → 상단 sticky 필터 바 노출 확인 → 검색 input 클릭 후 키워드 입력(예: "auth") → wp-cards Task 행 즉시 필터링 → 상태/도메인/모델 select 변경 → URL 쿼리 자동 업데이트 확인 → ✕ 초기화 버튼 클릭 → 전체 Task 복원`
- **URL / 라우트**: `/` (기존 루트 재사용). 필터 파라미터: `?q=...&status=...&domain=...&model=...` — 기존 `?subproject=...&lang=...`과 병합 보존. 예: `/?subproject=monitor-v4&lang=ko&q=auth&status=running&domain=backend&model=sonnet`
- **수정할 라우터 파일**: `scripts/monitor-server.py` — `render_dashboard()` 함수 (약 L4276) 내부의 섹션 조립 순서에 `_section_filter_bar()` 호출 삽입 (`<header>` 아래, `kpi` 섹션 위). 별도 라우터 파일 없음 (단일 파일 모놀리스).
- **수정할 메뉴·네비게이션 파일**: `scripts/monitor-server.py` — `_section_filter_bar(lang, distinct_domains)` 헬퍼 신규 추가. 이 함수 자체가 상단 sticky 네비게이션 역할을 수행. 기존 `_section_header()` / `_section_subproject_tabs()` 구조는 변경하지 않음.
- **연결 확인 방법**: E2E(`scripts/test_monitor_filter_bar_e2e.py`)에서: (1) 브라우저가 `/`를 로드 → (2) `#fb-q` input에 키워드 입력 → (3) 해당 키워드를 포함하지 않는 `.trow` 요소의 `display`가 `none`임을 확인 → (4) URL에 `?q=키워드`가 포함됨을 확인. URL 직접 입력(`page.goto('/?q=auth')`)은 초기 로드 테스트(`test_filter_bar_url_state_roundtrip`)에서만 허용하고, `test_filter_interaction` E2E는 반드시 클릭/입력 시퀀스로 진입.

## 주요 구조

- **`_section_filter_bar(lang: str, distinct_domains: list[str]) -> str`** (신규 SSR 헬퍼): `<div class="filter-bar" data-section="filter-bar" role="search">` 컨테이너에 4개 컨트롤(`#fb-q`, `#fb-status`, `#fb-domain`, `#fb-model`) + `#fb-reset` 버튼을 렌더. `distinct_domains`로 `#fb-domain` select option을 동적 구성. i18n: `lang` 파라미터 기반 label 텍스트 분기(`"검색"` vs `"Search"`, `"상태"` vs `"Status"` 등).
- **`currentFilters() -> {q, status, domain, model}`** (클라이언트 JS): DOM에서 4개 값 수집. `q`는 `.trim().toLowerCase()` 적용.
- **`matchesRow(trow, f) -> bool`** (클라이언트 JS): 4개 필터를 AND 평가. `q`는 `(data-task-id + .ttitle 텍스트).toLowerCase().indexOf(f.q)` substring 매칭. `status`는 `trow.dataset.status` 또는 `trow.dataset.phase` exact 매칭. `domain`은 `trow.dataset.domain` exact. `model`은 `.model-chip`의 `data-model` exact. 빈 값은 무조건 match.
- **`applyFilters()`** (클라이언트 JS): `document.querySelectorAll('.trow')` 순회하여 `matchesRow` 결과로 `display:none` 토글. `window.depGraph.applyFilter(predicate)` 훅으로 Dep-Graph 노드 opacity 조절.
- **`syncUrl(f)`** + **`loadFiltersFromUrl()`** (클라이언트 JS): `URL` + `URLSearchParams`로 기존 파라미터 보존하며 필터 4개 파라미터만 set/delete. `history.replaceState` 사용.
- **`applyFilter(predicate)` export** (`graph-client.js`): `_filterPredicate` 클로저 저장 후 `cy.nodes()`/`cy.edges()` 순회하여 opacity/line-color 조절. `window.depGraph.applyFilter`로 노출.

## 데이터 흐름

SSR: `wbs.md task.domain` dedup → `distinct_domains` → `_section_filter_bar()` SSR 렌더 + `/api/state` 응답 필드 추가.

클라이언트: `loadFiltersFromUrl()` (초기) → `applyFilters()` → 이벤트 발생(`input`/`change`) → `applyFilters()` + `syncUrl()`. 5초 auto-refresh: `patchSection('wp-cards', newHtml)` monkey-patch 경유 → 원본 patch 실행 후 `applyFilters()` 재호출 → 필터 상태 복원.

## 설계 결정

- **결정**: `patchSection`을 **monkey-patch(런타임 함수 교체)** 방식으로 wrapping한다.
- **대안**: `patchSection` 본문 내부에 직접 `applyFilters()` 호출 삽입.
- **근거**: TSK-05-01의 JS 코드가 `patchSection` 정의 이후에 삽입되는 별도 `<script>` 블록이므로, 기존 정의 파일을 건드리지 않고 확장할 수 있는 monkey-patch가 더 안전. 단, `patchSection.__filterWrapped` 센티널 attribute로 중복 wrapping 방지.

- **결정**: `#fb-domain` select의 option은 **SSR에서 `distinct_domains`로 정적 렌더**하고 클라이언트에서 `/api/state`로 동적 갱신하지 않는다.
- **대안**: 페이지 로드 후 JS가 `/api/state.distinct_domains`를 fetch하여 select 재구성.
- **근거**: SSR 렌더 시 이미 wbs.md 파싱 결과가 있으므로 추가 fetch 불필요. 도메인 목록은 wbs.md 변경 전까지 정적이므로 5초 polling에서 갱신할 필요 없음.

- **결정**: `data-domain` 속성을 `_render_task_row_v2()`의 **기존 `<div class="trow">` 태그에 추가** (별도 하위 요소 없음).
- **대안**: `.trow` 내부에 `data-domain`을 담는 숨겨진 span 추가.
- **근거**: 기존 `data-status`, `data-phase`, `data-running`이 모두 `.trow` 레벨 속성이며, `matchesRow()`가 `trow.dataset.domain`으로 단일 접근하는 것이 일관적이고 테스트도 단순.

## 선행 조건

- **TSK-02-01** (`_render_task_row_v2`): 본 Task가 수정하는 함수의 v4 기반 구조 완성. 현재 저장소에 구현 완료 확인(`scripts/monitor-server.py` L2967).
- **TSK-02-05** (모델 칩 DOM): `<span class="model-chip" data-model="{model}">` 렌더 완료 — `matchesRow()`의 model 필터 매칭 앵커. 현재 저장소에 구현 완료 확인(`scripts/monitor-server.py` L3014).
- 기존 `patchSection` 함수 확인 완료: `monitor-server.py` L3890, 이미 `wp-cards`/`live-activity` fold-state 복원 로직 포함.

## 리스크

- **HIGH: `patchSection` monkey-patch 중복 wrapping 충돌** — 다른 Task(TSK-02-02 fold 헬퍼, 미래 Task)가 동일하게 `patchSection`을 wrapping할 경우 `applyFilters` 이중 호출 또는 누락 발생. 완화: `window.patchSection.__filterWrapped` 센티널 boolean attribute로 중복 wrapping 방지. wrapping 코드 최초 1회만 실행되도록 `if (!window.patchSection.__filterWrapped)` guard 추가.
- **MEDIUM: 5초 auto-refresh 타이밍 — `loadFiltersFromUrl` 재실행 불필요** — URL에 필터 파라미터가 있고 DOM이 재렌더될 때 `applyFilters()` 재호출로 충분하다. `loadFiltersFromUrl()`은 초기 로드 1회만 실행. patchSection wrapping이 `applyFilters()`만 재호출하므로 DOM의 `#fb-q` 등 컨트롤 값은 유지됨.
- **MEDIUM: `distinct_domains` 필드 캐시 없음** — `/api/state` 매 요청마다 wbs.md를 파싱하므로 wbs.md 변경 시 즉시 반영. 단 현재 서버는 mtime 기반 재로드(기존 패턴)를 사용하므로 wbs.md 변경 → 캐시 무효화는 자동.
- **LOW: 라이브 활동 섹션 필터 비대상** — `.trow` 선택자가 wp-cards 밖의 `.trow` 요소까지 포함할 경우 의도치 않은 필터 적용. `applyFilters()`에서 `document.querySelectorAll('.trow[data-task-id]')` (task-id 속성이 있는 것만)로 범위 제한. 라이브 활동 섹션 행에는 `data-task-id` 없음을 코드 주석으로 명시.
- **LOW: Dep-Graph `applyFilter` 미지원 환경** — `window.depGraph` 또는 `window.depGraph.applyFilter`가 없을 때(`dep-graph` 비활성 등) `applyFilters()`가 TypeError. `if (window.depGraph && typeof window.depGraph.applyFilter === 'function')` guard 필수.

## QA 체크리스트

dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

- [ ] `test_filter_bar_dom_renders` — 대시보드 HTML에 `<div class="filter-bar">` 컨테이너가 존재하고, `#fb-q`(input), `#fb-status`(select), `#fb-domain`(select), `#fb-model`(select), `#fb-reset`(button) 5개 요소가 모두 존재한다.
- [ ] `test_filter_bar_data_domain_on_trow` — `_render_task_row_v2()`가 렌더하는 `<div class="trow">` 요소에 `data-domain="{task.domain}"` 속성이 존재하고, 값이 wbs.md `- domain:` 필드와 일치한다.
- [ ] `test_filter_bar_url_state_roundtrip` — URL `/?q=auth&status=running&domain=backend&model=sonnet`로 접속 시 `loadFiltersFromUrl()`이 4개 컨트롤 DOM 값을 올바르게 세팅하고, 이후 `syncUrl(currentFilters())`가 동일 파라미터를 URL에 다시 기록한다. `subproject`/`lang` 파라미터는 유지된다.
- [ ] `test_filter_survives_refresh` — `patchSection('wp-cards', newHtml)` 호출 후 `.trow[data-task-id]`에 대해 `display:none` 필터가 재적용된다. monkey-patch 없이 patchSection만 호출 시에는 필터가 사라짐을 대비 케이스로 검증.
- [ ] `test_filter_reset_clears_url_params` — `#fb-reset` 버튼 클릭 후 4개 컨트롤이 빈 값으로 리셋되고, URL에서 `q`/`status`/`domain`/`model` 파라미터가 제거된다. 모든 `.trow`가 `display:none`이 아닌 상태로 복원된다.
- [ ] (정상 케이스) `matchesRow()` — `f.q=""`, `f.status=""`, `f.domain=""`, `f.model=""` 전부 빈 값이면 모든 `.trow`가 match(true).
- [ ] (정상 케이스) `matchesRow()` — `f.q="auth"` 입력 시 `data-task-id` 또는 `.ttitle` 텍스트에 `auth`(대소문자 무시)를 포함하는 행만 true.
- [ ] (엣지 케이스) `matchesRow()` — `f.status="running"` 입력 시 `trow.dataset.status === "running"` 또는 `trow.dataset.phase === "running"` 행만 match.
- [ ] (엣지 케이스) `f.domain` 필터 — `data-domain` 속성이 없는 `.trow`는 domain 필터가 활성일 때 match=false (숨겨짐).
- [ ] (에러 케이스) `_section_filter_bar(lang, [])` — `distinct_domains` 빈 리스트 시 `#fb-domain`에 `<option value="">도메인</option>` 헤더 옵션만 렌더, 에러 없음.
- [ ] (통합 케이스) `/api/state` 응답에 `distinct_domains: list[str]` 필드가 존재하고, wbs.md의 `- domain:` 값 중 중복 제거된 유일값 목록이다.
- [ ] (통합 케이스) `patchSection.__filterWrapped` 센티널로 중복 monkey-patch가 차단되어 `applyFilters()`가 단 1회만 호출된다.
- [ ] (통합 케이스) `window.depGraph.applyFilter`가 없는 환경에서 `applyFilters()` 호출 시 TypeError 없이 정상 종료.
- [ ] `test_filter_interaction` (E2E 실 브라우저) — 브라우저가 `/`를 로드한 뒤 `#fb-q`에 `"auth"` 입력 → `auth` 미포함 `.trow`가 화면에서 사라짐(display:none) → URL에 `?q=auth` 반영 → `#fb-reset` 클릭 → 전체 Task 복원.
- [ ] (acceptance) `?q=auth` 접속 → 검색 input 값 `auth` + wp-cards에서 "auth" 포함 Task만 표시.
- [ ] (acceptance) 5초 auto-refresh로 `/api/state` 응답이 wp-cards를 재렌더해도 필터 결과 유지(`display:none` 재적용).
- [ ] (acceptance) 모바일/1280px 뷰포트에서 필터 바가 줄바꿈(`flex-wrap`) 상태로 컨트롤이 두 줄 이상으로 배치된다.

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**
- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 (URL 직접 입력 금지)
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다

## 필터 데이터 모델

```
{
  q:      string,   // 검색 키워드 (대소문자 무시 적용됨, 빈 문자열 = 필터 없음)
  status: string,   // 상태값 ("running"|"done"|"failed"|"bypass"|"pending"|"")
  domain: string,   // 도메인 exact 매칭 (wbs.md domain 필드 값, 빈 문자열 = 필터 없음)
  model:  string,   // 모델 exact 매칭 ("opus"|"sonnet"|"haiku"|"")
}
```

- 빈 문자열 = "필터 없음" 의미 (해당 조건은 모든 행에 match)
- model 필터는 TSK-02-05가 심은 `<span class="model-chip" data-model="{model}">` 요소의 `data-model` 속성으로 매칭
- 4필드 AND 조건: 하나라도 불일치하면 해당 `.trow` 숨김

## SSR 변경 상세

### `_section_filter_bar(lang, distinct_domains)` 신규 헬퍼

- i18n label 분기:

  | 요소 | ko | en |
  |------|----|----|
  | `#fb-q` placeholder | `🔍 검색 (ID / 제목)` | `🔍 Search (ID / title)` |
  | `#fb-status` 헤더 option | `상태` | `Status` |
  | `#fb-domain` 헤더 option | `도메인` | `Domain` |
  | `#fb-model` 헤더 option | `모델` | `Model` |
  | `#fb-reset` aria-label | `초기화` | `Reset` |

- `#fb-status` 고정 option 값: `running`, `done`, `failed`, `bypass`, `pending` (TRD §3.13 DOM 계약 준수)
- `#fb-domain` option: `distinct_domains` 순회하여 `<option value="{d}">{d}</option>` 생성
- `data-section="filter-bar"` 속성 부여 → `patchSection` 대상에서 **제외** (필터 바 자체는 재렌더 불필요, 주석으로 명시)

### `_render_task_row_v2()` 수정 지점

현재 `<div class="trow" data-status="..." data-phase="..." data-running="..." data-state-summary='...'>` 태그에 `data-domain="{domain}"` 속성 추가:

- `domain_val = _esc(getattr(item, "domain", None) or "")`
- 삽입 위치: `data-running` 바로 뒤

### `render_dashboard()` 삽입 지점

현재 `sections` dict 조립 후 레이아웃 HTML 생성 구간 (L4347 주변)에서 `filter_bar_html = _section_filter_bar(lang, distinct_domains)` 호출 후 `<header>` 렌더 직후, `sticky-header` 섹션 이전에 삽입. `distinct_domains`는 `tasks` 리스트에서 `task.domain` 수집 후 dedup한 sorted list.

### `/api/state` 응답 확장

`_handle_api_state()` (L5860) 내 `payload` dict에 `distinct_domains: list[str]` 필드 추가:
- `effective_docs_dir` 기준 `wbs.md` 파싱 결과에서 task domain 값 dedup → `sorted(list({t.get("domain","") for t in tasks} - {""}))` 방식
- 기존 payload merge 패턴(`{**payload, ...}`) 재사용

## 클라이언트 JS 상세

### `patchSection` monkey-patch

```
기존 정의 (L3890):
  function patchSection(name, newHtml) { ... }

monkey-patch (TSK-05-01 <script> 블록):
  if (!window.patchSection.__filterWrapped) {
    var _origPatch = window.patchSection;
    window.patchSection = function(name, html) {
      _origPatch.call(this, name, html);
      if (name === 'wp-cards' || name === 'live-activity') applyFilters();
    };
    window.patchSection.__filterWrapped = true;
  }
```

라이브 활동 섹션(`live-activity`)은 필터 대상 비포함이지만 `.trow[data-task-id]` 선택자로 범위가 제한되므로 wrapping에서 제외하지 않아도 무해. 단, 코드 주석으로 "라이브 활동 섹션 행은 data-task-id 없으므로 필터 대상 아님" 명시.

### 초기 로드 시퀀스

```
DOMContentLoaded 이벤트:
  1. loadFiltersFromUrl()   — URL 파라미터 → DOM 컨트롤 값 세팅
  2. applyFilters()         — 초기 필터 적용
  3. patchSection monkey-patch 등록 (sentinel guard)
```

## CSS 상세

```css
.filter-bar {
  position: sticky;
  top: 0;
  z-index: 70;
  display: flex;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-1);
  border-bottom: 1px solid var(--border);
  flex-wrap: wrap;          /* 1280px 이하 모바일 대응 */
}
.filter-bar input,
.filter-bar select,
.filter-bar button {
  font: 12px var(--font-body);
  padding: 4px 8px;
  background: var(--bg-2);
  color: var(--ink-1);
  border: 1px solid var(--border);
  border-radius: 3px;
}
.filter-bar input { min-width: 140px; }
```

- `flex-wrap: wrap` — 1280px 이하 뷰포트에서 컨트롤 줄바꿈 허용 (별도 미디어 쿼리 불필요)
- `z-index: 70` — 기존 `.slide-panel`(z-index:90), `#trow-tooltip`(z-index:100) 아래, 일반 콘텐츠 위
- 배경색 `var(--bg-1)` — `:root` 기본 배경색 재사용 (기존 CSS 변수 체계 준수)
