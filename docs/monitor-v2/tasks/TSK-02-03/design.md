# TSK-02-03: 드로어 열기/닫기 + `/api/pane/{id}` 2초 폴링 - 설계

## 요구사항 확인

- `[data-pane-expand]` 버튼 클릭으로 사이드 드로어를 열고 `/api/pane/{pane_id}` 2초 폴링을 시작한다.
- `[✕]` / backdrop 클릭 / `ESC` 키로 드로어를 닫고 폴링을 중지한다.
- 단일 드로어 인스턴스 — 다른 pane 클릭 시 `pane_id` 교체, 드로어 DOM은 재사용.
- 드로어 본문 `<pre>` 영역에 `textContent`만 사용해 XSS를 차단한다.

## 타겟 앱

- **경로**: N/A (단일 앱) — `scripts/monitor-server.py` 단일 파일 프로젝트
- **근거**: PRD/TRD가 `scripts/monitor-server.py`의 인라인 CSS/JS 교체로 범위를 명확히 한정함

## 구현 방향

TSK-02-03은 두 가지 독립 구현 단위로 분리된다.

1. **드로어 HTML 골격 (`_drawer_skeleton`)**: `render_dashboard()` 호출 시 `<body>` 하단에 주입하는 정적 HTML. backdrop + aside.drawer 구조. 처음엔 `display:none` 상태.
2. **`_DASHBOARD_JS` 드로어 제어 블록**: `openDrawer(paneId)`, `closeDrawer()`, `startDrawerPoll()`, `stopDrawerPoll()`, `tickDrawer()` 5개 함수 + 이벤트 위임 2건(click, keydown) + auto-refresh 토글 — 모두 단일 IIFE 안에 캡슐화.

`_render_pane_row()` 함수는 기존 `[show output]` 링크를 `<button data-pane-expand="{id}">` 버튼으로 교체하여 이벤트 위임의 앵커를 만든다.

대시보드 부분 fetch(`GET /api/state` → `innerHTML` 섹션 교체)가 pane row를 재생성해도 이벤트 위임은 `document.addEventListener`에 바인딩돼 있으므로 드로어 폴링이 중단되지 않는다.

## 파일 계획

**경로 기준:** 프로젝트 루트 기준 (단일 앱)

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `_drawer_skeleton()` 신규 함수, `_DASHBOARD_JS` 문자열 상수 추가, `render_dashboard()` 조립부 수정, `_render_pane_row()` expand 버튼 추가, `DASHBOARD_CSS` 드로어·backdrop CSS 추가 | 수정 |
| `scripts/test_monitor_drawer.py` | 드로어 관련 단위 테스트 (`_drawer_skeleton` 마크업 검증, `_render_pane_row` expand 버튼 검증, JS 이벤트 위임 구조 확인) | 신규 |

> **라우터·메뉴 연결 해당 없음**: 단일 파일 Python HTTP 서버. `render_dashboard()` 함수가 라우터 역할을 하며 TSK-01-04에서 이미 배선 완료. 드로어는 기존 대시보드 `/` 페이지 내부 오버레이이므로 라우트 추가 없음.

## 진입점 (Entry Points)

- **사용자 진입 경로**: 브라우저에서 `http://localhost:7321/` 접속 → Team Agents 섹션 pane row → `[expand ↗]` 버튼 클릭 → 드로어 오픈
- **URL / 라우트**: `GET /` (대시보드 메인, 기존 라우트 — 신규 없음)
- **수정할 라우터 파일**: `scripts/monitor-server.py`의 `render_dashboard()` 함수 (약 1080-1127번 라인) — `_drawer_skeleton()` 호출 결과를 `<body>` 하단에 삽입 + `<script>` 태그에 `_DASHBOARD_JS` 주입
- **수정할 메뉴·네비게이션 파일**: `scripts/monitor-server.py`의 `_render_pane_row()` 함수 (약 950-962번 라인) — 기존 `<a class="pane-link" href="/pane/{id}">[show output]</a>`를 `<button class="pane-expand-btn" data-pane-expand="{id}">[expand ↗]</button>`으로 교체. (사이드 메뉴 없음 — pane row의 CTA 버튼이 진입점 역할)
- **연결 확인 방법**: 브라우저에서 `/` 접속 → Team Agents 섹션의 `[expand ↗]` 버튼 클릭 → `aside.drawer.open`이 표시되고 드로어 타이틀이 클릭한 pane_id를 포함하는지 확인

## 주요 구조

### Python (server-side)

| 함수 | 책임 |
|------|------|
| `_drawer_skeleton()` | 드로어 HTML 골격 반환. `<div class="drawer-backdrop">` + `<aside class="drawer" role="dialog" aria-modal="true">` 구조. 초기 상태 닫힘. |
| `_render_pane_row(pane)` | (수정) 기존 anchor 제거, `<button data-pane-expand="{id}">` 추가. pane_id는 `_esc()`로 escape. |
| `render_dashboard(model)` | (수정) `body` 하단에 `_drawer_skeleton()` 삽입 + `<script>_DASHBOARD_JS</script>` 추가. |
| `_DASHBOARD_JS` | 모듈 레벨 문자열 상수. 드로어 제어 IIFE 전체를 담음. `render_dashboard()`에서 `<script>` 태그에 주입. |

### JavaScript (client-side, `_DASHBOARD_JS` IIFE 내부)

| 함수 | 책임 |
|------|------|
| `openDrawer(paneId)` | `state.drawerPaneId = paneId`, 드로어 타이틀 교체, `.drawer`·`.drawer-backdrop`에 `open` 클래스 추가, `startDrawerPoll()` 호출. |
| `closeDrawer()` | `state.drawerPaneId = null`, `stopDrawerPoll()`, `open` 클래스 제거. |
| `startDrawerPoll()` | `stopDrawerPoll()` 먼저 호출(중복 방지), `tickDrawer()` 즉시 1회, `setInterval(tickDrawer, 2000)` 시작. |
| `stopDrawerPoll()` | `clearInterval(state.drawerPollId)`, `state.drawerPollId = null`. |
| `tickDrawer()` | `state.drawerPaneId` 없으면 즉시 리턴. `fetch('/api/pane/'+encodeURIComponent(id))` → `.then(updateDrawerBody)` → `.catch(function(){})` (silent). |
| `updateDrawerBody(j)` | `document.querySelector('.drawer-body pre').textContent = (j.lines \|\| []).join('\n')`. `innerHTML` 사용 금지. |

### 이벤트 위임 구조

```javascript
// click 위임 — document 레벨, DOM 재생성 불감
document.addEventListener('click', function(e) {
  var exp = e.target.closest('[data-pane-expand]');
  if (exp) { openDrawer(exp.dataset.paneExpand); return; }
  if (e.target.matches('.drawer-close, .drawer-backdrop')) closeDrawer();
});
// ESC 키 위임
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape' && state.drawerPaneId) closeDrawer();
});
```

## 데이터 흐름

```
[data-pane-expand] 버튼 클릭
  → openDrawer(paneId)
    → startDrawerPoll()
      → tickDrawer() [즉시 + 2초마다]
        → fetch('/api/pane/{pane_id}')  ← 기존 TSK-01-06 엔드포인트 재사용
          → 서버: _pane_capture_payload() → capture_pane(tmux)
          → 응답: {pane_id, lines: string[], captured_at: iso8601}
        → updateDrawerBody(j): pre.textContent = lines.join('\n')

[✕] 버튼 / backdrop 클릭 / ESC 키
  → closeDrawer()
    → stopDrawerPoll() → clearInterval(state.drawerPollId)
    → DOM .open 클래스 제거 (드로어 숨김)
```

## 설계 결정 (대안이 있는 경우만)

### 1. 이벤트 위임 방식
- **결정**: `document.addEventListener('click', ...)` 단일 위임 (document 레벨)
- **대안**: pane row 생성 시 각 `[expand ↗]` 버튼에 직접 `.addEventListener` 추가
- **근거**: 대시보드 부분 fetch가 pane row DOM을 innerHTML 교체하면 직접 바인딩 리스너가 소실됨. 이벤트 위임은 DOM 교체에 무관하며, 이벤트 리스너 중복 등록 메모리 누수를 구조적으로 차단.

### 2. 드로어 pane_id 교체 방식
- **결정**: 단일 드로어 DOM 재사용, `state.drawerPaneId` 값만 교체
- **대안**: 드로어 여러 개 동시 열기
- **근거**: PRD §4.5.8 "다중 동시 열기 불가(단일 드로어)" 명시. 구현 단순화 및 메모리 누수 방지.

### 3. `pre.textContent` 사용
- **결정**: `textContent`만 사용
- **대안**: DOMPurify 등으로 sanitize 후 `innerHTML`
- **근거**: PRD §4.9 보안 요구사항 명시 + 외부 CDN 금지 원칙(DOMPurify 도입 불가).

## 선행 조건

- **TSK-01-06 완료 확인**: `/api/pane/{pane_id}` JSON 엔드포인트 (`_handle_pane_api`, `_pane_capture_payload`, `_render_pane_json`) — `docs/monitor/tasks/TSK-01-06/state.json` status `[xx]` 확인됨.
- `_render_pane_row()`, `_section_team()`, `render_dashboard()` 함수가 `scripts/monitor-server.py`에 이미 존재 (수정 대상).
- Python 3.8+ stdlib (외부 의존 없음).

## 리스크

- **LOW**: CSS `transform: translateX(100%)` + `.drawer { display:none }` 조합에서 `.open` 클래스 추가 직후 슬라이드 애니메이션이 씹히는 현상. `requestAnimationFrame` 또는 `setTimeout(0)` 트릭으로 해결 가능. 닫힘 애니메이션 없이 즉시 사라지는 것은 MVP 수용.
- **LOW**: 드로어가 열린 상태에서 TSK-02-02의 대시보드 부분 fetch가 섹션 innerHTML을 교체해도 `aside.drawer` DOM은 범위 밖이므로 영향 없음. `state.drawerPaneId`도 JS 메모리에 있어 안전.
- **LOW**: `fetch` 타임아웃 미설정 — 드로어 폴링은 2초 간격·경량 JSON 응답이므로 MVP에서 AbortController 생략 허용. 필요 시 후속 Task에서 추가.

## QA 체크리스트

### 정상 케이스
- [ ] `[expand ↗]` 버튼 클릭 시 `aside.drawer`에 `open` 클래스가 추가되고 드로어가 화면에 표시된다
- [ ] 드로어 타이틀 영역이 클릭한 pane_id를 포함한 텍스트로 갱신된다
- [ ] 드로어 오픈 직후 (2초 이내) `/api/pane/{pane_id}` 최초 요청이 발생하고 `<pre>` 내용이 채워진다
- [ ] 이후 2초마다 폴링이 반복되고 `<pre>` 내용이 갱신된다
- [ ] `[✕]` 버튼 클릭 시 드로어가 닫히고 폴링이 중단된다
- [ ] backdrop 영역 클릭 시 드로어가 닫히고 폴링이 중단된다
- [ ] `ESC` 키 입력 시 드로어가 닫히고 폴링이 중단된다
- [ ] 드로어가 닫힌 상태에서 `ESC` 키를 눌러도 에러 없음

### 엣지 케이스
- [ ] pane A로 드로어를 연 상태에서 pane B의 `[expand ↗]` 버튼 클릭 시 `<pre>` 내용이 pane B로 교체되고 폴링 대상이 B로 교체된다 (이전 인터벌 잔존 없음)
- [ ] 드로어 열림 ↔ 닫힘 3회 연속 반복 후 이벤트 리스너 중복 등록 없음 (이벤트 위임 구조상 구조적 불가 — 코드 리뷰로 확인)
- [ ] 대시보드 부분 fetch로 pane row가 DOM 재생성된 후에도 `[expand ↗]` 버튼이 동작한다 (이벤트 위임 검증)
- [ ] tmux가 없어 pane row가 렌더되지 않는 경우 드로어 관련 JS 코드가 에러 없이 idle 상태를 유지한다

### 에러 케이스
- [ ] `/api/pane/{id}` 응답이 4xx/5xx일 때 드로어 `<pre>` 내용이 변경되지 않고 다음 tick에 재시도한다 (silent catch 확인)
- [ ] 네트워크 단절 시 `fetch` 예외가 발생해도 드로어가 닫히지 않으며 다음 tick에 재시도한다
- [ ] 잘못된 pane_id로 서버가 400을 반환해도 JS 예외 없이 조용히 실패한다

### 통합 케이스
- [ ] 드로어가 열린 상태에서 대시보드 부분 fetch(`/api/state` 폴링)가 계속 동작하고 pane row가 갱신된다 (두 폴링 독립성 확인)
- [ ] 드로어 `<pre>` 내용에 `<script>` 등 HTML 문자열이 포함돼도 그대로 텍스트로 표시되어 XSS가 발생하지 않는다 (`textContent` 확인)

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**
- [ ] (클릭 경로) Team Agents 섹션의 `[expand ↗]` 버튼을 클릭하여 드로어가 열린다 (URL 직접 입력 금지)
- [ ] (화면 렌더링) 드로어의 핵심 UI 요소(타이틀, `<pre>`, `[✕]` 버튼)가 브라우저에서 실제 표시되고 기본 상호작용(닫기, ESC)이 동작한다
