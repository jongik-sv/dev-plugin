# TSK-02-02: 필터 칩 + auto-refresh 토글 동작 - 설계

## 요구사항 확인
- 필터 칩(All/Running/Failed/Bypass) 클릭 시 클릭된 칩만 `aria-pressed=true`, 나머지는 `false`로 전환하고 `state.activeFilter`에 저장한다.
- `state.activeFilter`가 `'all'`이 아닌 경우 `.task-row:not(.{filter})` 형태로 대상 외 row를 `display: none` 처리한다. 서버 호출 없음.
- auto-refresh 토글 버튼 클릭 시 `state.autoRefresh`를 플립하고 버튼 라벨을 `'◐ auto'` ↔ `'○ paused'`로 교체한다.

## 타겟 앱
- **경로**: N/A (단일 앱)
- **근거**: 단일 Python HTTP 서버 구조. 모노레포 분기 없음. 모든 코드는 `scripts/monitor-server.py` 한 파일에 집중.

## 구현 방향
- `DASHBOARD_CSS`에 `.chip` 스타일(기본/pressed 상태)을 추가한다. 현재 CSS에 `.chip` 규칙이 없으므로 신규 추가. TRD §4.2.1 CSS 스니펫 참조.
- `_DASHBOARD_JS` 인라인 문자열에 (A) 필터 칩 이벤트 바인딩(이벤트 위임), (B) `applyFilter()`, (C) auto-refresh 토글 바인딩을 추가한다. TSK-02-01이 먼저 `state` 객체와 IIFE 뼈대를 구현하며, 이 Task는 그 안에 필터·토글 블록을 삽입하는 형태다.
- `_render_task_row`에 상태 CSS class(`running`/`failed`/`bypass`/`done`/`pending`)를 추가한다. 필터 JS가 `row.classList.contains(f)`로 판단하기 때문에 서버측에서 class를 주입해야 한다.
- DOM 교체(부분 fetch, TSK-02-01) 후 `applyFilter()` 재호출이 필요하므로, TSK-02-01의 `patchDashboard()` 훅에 `applyFilter()` 호출을 포함시켜야 한다(협의 필요).

## 파일 계획

**경로 기준:** 모든 파일 경로는 **프로젝트 루트 기준**으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `DASHBOARD_CSS`에 `.chip`/`.chip[aria-pressed="true"]` 규칙 추가; `_render_task_row`에 상태 CSS class 주입; `_DASHBOARD_JS`에 필터 칩 이벤트 위임 + `applyFilter()` + 토글 바인딩 블록 추가 | 수정 |

> 이 Task는 단일 파일 수정만으로 완결된다. Python 인라인-HTML 구조이므로 별도 라우터 파일·네비게이션 파일은 없음.

## 진입점 (Entry Points)

- **사용자 진입 경로**: 브라우저에서 대시보드 `/` 페이지 로드 → KPI 영역의 필터 칩(`[All]` / `[Running]` / `[Failed]` / `[Bypass]`) 클릭, 또는 헤더 영역 `[◐ auto]` 버튼(auto-refresh 토글) 클릭
- **URL / 라우트**: `http://localhost:{PORT}/` — 기존 루트 엔드포인트 그대로 사용. 신규 엔드포인트 없음.
- **수정할 라우터 파일**: `scripts/monitor-server.py`의 `render_dashboard()` 함수 — `<script>` 태그에 `_DASHBOARD_JS` 삽입. 라우팅 경로 변경 없음. (파일 계획 표에 포함)
- **수정할 메뉴·네비게이션 파일**: `scripts/monitor-server.py`의 `_section_kpi()` 또는 `_section_sticky_header()` 내 필터 칩 HTML 렌더 위치. 동일 파일. (파일 계획 표에 포함)
- **연결 확인 방법**: 브라우저에서 `/` 로드 → KPI 섹션의 `[Running]` 칩 클릭 → `.task-row.running` 이외의 row가 숨겨짐 → `[All]` 칩 클릭 → 전체 row 재표시. URL 직접 입력 금지.

## 주요 구조

### 1. `DASHBOARD_CSS` 추가 규칙
```css
/* Filter chips */
.chip {
  padding: 0.25rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 0.85rem;
  cursor: pointer;
  user-select: none;
  background: transparent;
  color: var(--fg);
}
.chip[aria-pressed="true"] {
  background: var(--accent);
  color: var(--bg);
  border-color: var(--accent);
}
```

### 2. `_render_task_row` 수정 — 상태 class 주입
기존 `<div class="task-row">` → `<div class="task-row {status_class}">`.

헬퍼 함수 `_task_row_status_class(status, bypassed, running, failed)` 추가:
- `bypassed=True` → `'bypass'`
- `failed=True` → `'failed'`
- `running=True` → `'running'`
- `status == '[xx]'` → `'done'`
- 그 외 → `'pending'`

우선순위는 기존 `_status_badge` 로직과 동일.

### 3. `_DASHBOARD_JS` 추가 블록
```javascript
// --- Filter chips (event delegation — survives DOM replacement) ---
document.addEventListener('click', function(e){
  var chip = e.target.closest('.chip');
  if (!chip) return;
  state.activeFilter = chip.dataset.filter || 'all';
  document.querySelectorAll('.chip').forEach(function(c){
    c.setAttribute('aria-pressed', c === chip ? 'true' : 'false');
  });
  applyFilter();
});
function applyFilter(){
  var f = state.activeFilter;
  document.querySelectorAll('.task-row').forEach(function(row){
    var hide = f !== 'all' && !row.classList.contains(f);
    row.style.display = hide ? 'none' : '';
  });
}

// --- Auto-refresh toggle ---
var tog = document.querySelector('.refresh-toggle');
if (tog) tog.addEventListener('click', function(){
  state.autoRefresh = !state.autoRefresh;
  this.setAttribute('aria-pressed', String(state.autoRefresh));
  this.textContent = state.autoRefresh ? '◐ auto' : '○ paused';
  if (!state.autoRefresh) stopMainPoll();
  else startMainPoll();
});
```

### 4. 필터 칩 HTML (서버측 렌더, `_section_kpi` 또는 `_section_sticky_header` 내)
```html
<div class="chip-row" role="group" aria-label="filter">
  <button class="chip" data-filter="all"     aria-pressed="true"  tabindex="0">All</button>
  <button class="chip" data-filter="running" aria-pressed="false" tabindex="0">Running</button>
  <button class="chip" data-filter="failed"  aria-pressed="false" tabindex="0">Failed</button>
  <button class="chip" data-filter="bypass"  aria-pressed="false" tabindex="0">Bypass</button>
</div>
```

### 5. auto-refresh 토글 HTML (서버측 렌더, `_section_sticky_header` 내)
```html
<button class="refresh-toggle" aria-pressed="true" tabindex="0">◐ auto</button>
```

## 데이터 흐름
칩 클릭 → JS `state.activeFilter` 갱신 + `aria-pressed` 속성 토글 → `applyFilter()` 호출 → `.task-row` 순회하며 `display:none` / `''` 설정 (서버 호출 없음).
토글 클릭 → `state.autoRefresh` 플립 → 라벨 텍스트 교체 → `startMainPoll()` / `stopMainPoll()` 호출.

## 설계 결정 (대안이 있는 경우만)

- **결정**: 이벤트 위임(`document.addEventListener('click', ...)`)으로 칩 클릭 감지
- **대안**: 초기 로드 시 `querySelectorAll('.chip').forEach(addEventListener)` 직접 바인딩
- **근거**: DOM 교체(부분 fetch, TSK-02-01) 후 직접 바인딩 리스너는 소멸되므로 위임 방식이 필수.

- **결정**: 상태 CSS class를 서버측 `_render_task_row`에서 주입
- **대안**: JS가 `data-status` attribute를 파싱해 클라이언트에서 class 계산
- **근거**: 서버가 이미 상태 우선순위 로직(`_status_badge`)을 보유. 클라이언트 중복 시 동기화 문제 발생 위험.

## 선행 조건
- **TSK-02-01**: `_DASHBOARD_JS` IIFE 뼈대(`state` 객체, `startMainPoll`, `stopMainPoll`)가 먼저 구현되어야 함. 이 Task의 JS 블록은 그 IIFE 내에 삽입됨.
- `_section_kpi` 또는 `_section_sticky_header`에 필터 칩 HTML과 auto-refresh 토글 HTML이 실제 렌더되어야 기능 동작 (TSK-02-03 협의 필요).

## 리스크
- **MEDIUM**: TSK-02-01과 동일 함수(`_DASHBOARD_JS`, `render_dashboard`, `_render_task_row`) 수정 — 병렬 작업 시 머지 충돌 가능. TSK-02-01 완료 후 구현 권장.
- **MEDIUM**: `_render_task_row`에 status class 추가 시, TRD §4.2.1의 `.task-row::before` pseudo-element(좌측 컬러 바)가 `position: relative` 부재로 absolute 배치 실패할 수 있음. `.task-row { position: relative; }` CSS 추가 필요.
- **LOW**: DOM 교체(부분 fetch) 후 `applyFilter()` 재호출 누락 시 새 row에 필터 미적용. TSK-02-01의 `patchDashboard()` 내 `applyFilter()` 호출 훅 등록 필요.

## QA 체크리스트
dev-test 단계에서 검증할 항목:

- [ ] `[Running]` 칩 클릭 시 해당 칩만 `aria-pressed="true"`, 나머지 3개 칩은 `aria-pressed="false"` (DOM 속성 검사)
- [ ] `[Running]` 필터 활성 시 `.task-row.running` row만 표시되고, `.task-row.failed` / `.task-row.bypass` / `.task-row.done` / `.task-row.pending` row는 `display: none`
- [ ] `[All]` 칩 클릭 시 모든 `.task-row`가 `display: ''` (표시됨)
- [ ] `[Failed]` 필터 활성 시 `.task-row.failed` row만 표시
- [ ] `[Bypass]` 필터 활성 시 `.task-row.bypass` row만 표시
- [ ] auto-refresh 토글 1회 클릭 후 텍스트 `'○ paused'`, `aria-pressed="false"`
- [ ] 다시 클릭 시 텍스트 `'◐ auto'`, `aria-pressed="true"`
- [ ] 부분 fetch DOM 교체 후(TSK-02-01 연계) 기존 필터 상태 유지 — 새로 렌더된 row에도 동일 필터 적용됨
- [ ] `_render_task_row`가 생성한 HTML에서 `.task-row` div에 상태 class 중 정확히 1개가 존재
- [ ] (클릭 경로) 브라우저에서 `/` 로드 → KPI 영역 `[Running]` 칩 클릭 → Running row만 표시되는 화면 전환 확인 (URL 직접 입력 금지)
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**
- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 (URL 직접 입력 금지)
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다
