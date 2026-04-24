# TSK-04-01: FR-06 Phase 배지 색상 + 내부 스피너 + Dep-Graph 노드 `data-phase` 적용 - 설계

## 요구사항 확인

- `.badge[data-phase="dd|im|ts|xx|failed|bypass|pending"]` 7종 CSS 규칙을 `--phase-X` 토큰 기반으로 추가하고, 배지 내부에 `.spinner-inline` (8×8px) 을 삽입하여 running 시 노출한다.
- `_render_task_row_v2` 에서 배지 DOM 에 `data-phase` 속성 및 `<span class="spinner-inline">` 을 추가하고 기존 row 레벨 `.spinner` 요소를 제거한다.
- `_build_graph_payload` 노드 dict 에 `phase` 필드를 추가하고, `graph-client.js` 노드 HTML 에 `data-phase` 속성을 1줄 추가한다. `.dep-node[data-phase]` 6종 글자색 CSS 규칙을 추가한다.

## 타겟 앱

- **경로**: N/A (단일 앱 — `scripts/monitor-server.py` 인라인 모놀리스. 패키지 분리 진행 중이나 TSK-04-01 범위 내에서는 모두 `monitor-server.py` 내 함수를 편집)
- **근거**: 현재 `scripts/monitor_server/` 패키지가 아직 미생성(TSK-01-02, TSK-02-01이 선행 의존이나 이 WP에서 미완료 상태). 따라서 TSK-04-01은 `scripts/monitor-server.py` 내 CSS 문자열·Python 함수를 직접 편집한다. wbs.md note의 5파일(renderers/wp.py, renderers/depgraph.py, static/style.css, static/app.js, vendor/graph-client.js)은 패키지 분리 이후 경로이며, 현재는 `monitor-server.py` 내 해당 섹션을 편집하는 것으로 매핑한다.

## 구현 방향

1. **CSS (`DASHBOARD_CSS` 문자열 내)**: `.badge[data-phase="..."]` 7종 규칙 추가, `.badge .spinner-inline` 규칙 추가, `.trow[data-running="true"] .badge .spinner-inline { display: inline-block }` 추가. v4 row-level `.trow[data-running="true"] .spinner { display: inline-block }` display 규칙 제거(`@keyframes spin` 및 `.spinner`·`.node-spinner` 공통 규칙은 유지). `.dep-node[data-phase="..."] .dep-node-id { color: var(--phase-X) }` 6종 규칙 추가.
2. **Python (`_render_task_row_v2`)**: 배지 `<div>` 에 `data-phase="{data_phase}"` 추가, 내부에 `<span class="spinner-inline" aria-hidden="true"></span>` 삽입. 기존 row-level `<span class="spinner">` 요소 제거.
3. **Python (`_build_graph_payload`)**: 노드 dict에 `"phase": _phase_data_attr(task.status, failed=node_status=="failed", bypassed=task.bypassed)` 필드 추가.
4. **JS (`graph-client.js`)**: `nodeHtmlTemplate` 함수에서 `<div class="...">` 오프닝 태그에 `data-phase="${escapeHtml(nd.phase || 'pending')}"` 추가.
5. **테스트**: `scripts/test_monitor_phase_badge_colors.py` 신규 생성, `scripts/test_monitor_graph_api.py` 에 `test_graph_node_has_phase_field` 추가.

## 파일 계획

**경로 기준:** 프로젝트 루트 기준.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | CSS 규칙 추가/제거 (`.badge[data-phase]` 7종, `.badge .spinner-inline`, `.dep-node[data-phase]` 6종, row-level `.spinner` display 규칙 제거) | 수정 |
| `scripts/monitor-server.py` | `_render_task_row_v2`: 배지 `data-phase` 속성 추가, `.spinner-inline` span 삽입, `.spinner` span 제거 | 수정 |
| `scripts/monitor-server.py` | `_build_graph_payload`: 노드 dict에 `phase` 필드 추가 | 수정 |
| `skills/dev-monitor/vendor/graph-client.js` | `nodeHtmlTemplate`: div 오프닝 태그에 `data-phase` 속성 1줄 추가 | 수정 |
| `scripts/test_monitor_phase_badge_colors.py` | CSS 규칙 존재 검증 테스트 (7종 badge + spinner-inline + 6종 dep-node) | 신규 |
| `scripts/test_monitor_graph_api.py` | `test_graph_node_has_phase_field` 추가 | 수정 |

> 이 Task는 `fullstack` domain이지만 신규 라우트·메뉴 항목 없이 기존 `/` 루트의 기존 컴포넌트를 편집하는 Task다. 라우터 파일과 네비게이션 파일은 해당 없음 (기존 대시보드 루트에 이미 연결된 컴포넌트 내부 편집).

## 진입점 (Entry Points)

- **사용자 진입 경로**: 브라우저에서 대시보드 루트 `/` 접속 → WP 카드 내 Task 행 배지 확인 → 의존성 그래프(`/` 하단 dep-graph 섹션) 노드 확인
- **URL / 라우트**: `/` (기존 대시보드 루트, 신규 라우트 없음)
- **수정할 라우터 파일**: 없음 — 기존 `/` 핸들러의 HTML 렌더링 함수(`_render_task_row_v2`, `_build_graph_payload`) 내부만 편집
- **수정할 메뉴·네비게이션 파일**: 없음 — 기존 UI 내 컴포넌트 내부 편집
- **연결 확인 방법**: 브라우저에서 `/` 접속 → WP 카드 Task 행의 `.badge` div에 `data-phase` 속성이 렌더됨 확인 → running 상태 task의 배지 내부에 `.spinner-inline` 요소 확인 → `/api/graph` 응답 JSON의 각 노드에 `phase` 필드 존재 확인

> **비-페이지 UI**: 이 Task는 기존 대시보드 `/` 페이지 내 컴포넌트(배지, dep-graph 노드)를 수정한다. 상위 페이지는 `/`이며 `test_monitor_e2e.py` E2E 테스트에서 렌더링 검증한다.

## 주요 구조

- **`_phase_data_attr(status_code, *, failed, bypassed) -> str`** (기존 함수, `monitor-server.py` L1159): 이미 구현됨. `_build_graph_payload`에서 새로 호출하여 `phase` 필드 생성에 재사용.
- **`_render_task_row_v2(item, running_ids, failed_ids, lang) -> str`** (`monitor-server.py` L3008): 배지 div에 `data-phase` 속성 추가 + `.spinner-inline` span 삽입 + `.spinner` span 제거.
- **`_build_graph_payload(tasks, signals, graph_stats, docs_dir_str, subproject) -> dict`** (`monitor-server.py` L5222): 각 노드 dict에 `"phase"` 필드 추가.
- **`nodeHtmlTemplate(nd)`** (`skills/dev-monitor/vendor/graph-client.js` L66): div 오프닝 태그에 `data-phase="${escapeHtml(nd.phase || 'pending')}"` 삽입.
- **CSS 블록** (`DASHBOARD_CSS` 문자열, `monitor-server.py` L1184~): `.badge[data-phase]` 7종 + `.badge .spinner-inline` + `.dep-node[data-phase]` 6종 규칙 추가. `.trow[data-running="true"] .spinner { display: inline-block }` display 선언만 제거.

## 데이터 흐름

입력: `task.status` (state.json 읽은 결과) + `running_ids` / `failed_ids` 집합 → `_phase_data_attr()` 통해 `"dd"|"im"|"ts"|"xx"|"failed"|"bypass"|"pending"` 문자열 생성 → HTML `data-phase` 속성 및 JSON `phase` 필드로 주입 → CSS/JS에서 `data-phase` 값으로 색·스피너 표시.

## 설계 결정 (대안이 있는 경우만)

- **결정**: `.badge` div 자체에 `data-phase` 속성을 추가하고, `.badge[data-phase="dd"]` CSS 셀렉터로 배지 색을 지정한다.
- **대안**: 기존처럼 `.trow[data-status]` 상위 셀렉터에서 `.badge` 색을 제어하는 방식 유지.
- **근거**: `data-phase`는 7종 DDTR 상태를 세분화하는 반면 `data-status`는 5종(done/running/failed/bypass/pending) 신호 기반이어서 두 체계가 다르다. 배지는 DDTR phase 색이 목적이므로 배지 자체에 `data-phase`를 두는 것이 CSS property scope를 명확히 분리한다(TSK 제약사항 준수).

- **결정**: `.trow[data-running="true"] .spinner { display: inline-block }` 규칙의 `display` 선언만 제거하고, `.spinner` 요소의 size/border/animation 공통 규칙은 유지한다.
- **대안**: `.spinner` 클래스 규칙 전체 제거.
- **근거**: `.spinner`는 `@keyframes spin`과 함께 `scripts/monitor-server.py` L1373에서 `.node-spinner`와 공통 규칙으로 선언되어 있어 완전 제거 시 `.node-spinner` dep-graph 스피너가 깨진다. TSK 제약("display 규칙만 제거, 키프레임·공용 스피너 CSS 유지")과 일치.

- **결정**: `.dep-node[data-phase]` CSS 규칙은 `.dep-node-id { color: var(--phase-X) }` 로 글자색만 담당하고, `border-left-color`는 기존 `.dep-node.status-*` 규칙이 계속 담당한다.
- **대안**: `.dep-node[data-phase]`로 border-left-color까지 통합 제어.
- **근거**: TSK 제약("`.dep-node.status-failed` 빨강 경로(TSK-03-03) 훼손 금지 — property scope 분리"). 두 속성을 다른 셀렉터 축으로 제어하여 공존.

## 선행 조건

- **TSK-03-01**: `--phase-dd/im/ts/xx/failed/bypass/pending` CSS 변수 8종이 `:root`에 선언되어야 한다. 현재 `monitor-server.py`에는 해당 변수가 없으므로, TSK-03-01이 완료되거나, TSK-04-01 구현 시 해당 변수가 `:root`에 없으면 CSS 규칙이 silent fallback된다. **AC-FR06-e 조건**: `var(--phase-bypass)` = `#f59e0b`이 `:root`에 있어야 한다.
  - 현재 worktree 상태에서 TSK-03-01도 `[ ]`이므로, TSK-04-01 빌드 시 `--phase-*` 변수를 `monitor-server.py`의 `:root` 블록(L1189)에 함께 추가한다 (TSK-03-01 선행 작업을 포함하여 이 Task에서 자립적으로 완성 — WBS depends는 논리적 순서이며 동일 파일 편집이므로 병합 가능).
- **TSK-01-03 / TSK-02-01**: 패키지 분리가 완료되지 않은 상태이므로 `renderers/wp.py`, `renderers/depgraph.py`, `static/style.css` 등은 아직 존재하지 않는다. TSK-04-01은 `monitor-server.py` 내 해당 Python 함수와 CSS 문자열을 직접 편집한다.
- **`_phase_data_attr`**: 이미 `monitor-server.py` L1159에 구현되어 있어 그대로 재사용.

## 리스크

- **MEDIUM**: `@keyframes spin` 중복 선언 금지 — 이미 L1372에 `@keyframes spin{ to{ transform: rotate(360deg); } }` 가 있으므로 `.badge .spinner-inline` 규칙 추가 시 키프레임을 재선언하지 않도록 주의.
- **MEDIUM**: `.dep-node.status-failed` CSS 우선순위 충돌 — `.dep-node[data-phase="failed"] .dep-node-id { color }` 와 `.dep-node.status-failed .dep-node-id { color }` 가 공존할 수 있다. 두 규칙이 동일 property(`color`)를 지정하는 경우 셀렉터 명시도(specificity)가 같으면 마지막 선언이 우선이다. 새 `data-phase` 규칙을 기존 `.status-*` 규칙 이후에 배치하여 `data-phase` 색이 우선 적용되도록 한다.
- **LOW**: `_build_graph_payload`에서 `_phase_data_attr` 호출 시 `failed`/`bypassed` 플래그를 올바르게 전달해야 한다. `node_status=="failed"`를 기준으로 `failed` 플래그를, `task.bypassed`를 `bypassed` 플래그로 전달하면 기존 `_render_task_row_v2`와 동일한 로직이 된다.
- **LOW**: `graph-client.js` `nd.phase`가 `undefined`일 경우(구형 API 응답) — `nd.phase || 'pending'` 방어 코드로 fallback.

## QA 체크리스트

- [ ] (정상 케이스) `.badge[data-phase="dd"]` CSS 규칙이 `style.css`(또는 `DASHBOARD_CSS` 인라인) 에 존재한다 — `color-mix(in srgb, var(--phase-dd) 15%, transparent)` 배경 + `var(--phase-dd)` 테두리·텍스트.
- [ ] (정상 케이스) 7종 phase(`dd/im/ts/xx/failed/bypass/pending`) 각각에 `.badge[data-phase]` 규칙이 존재한다.
- [ ] (정상 케이스) `.badge .spinner-inline` 규칙이 존재한다 — `display:none`, `width:8px`, `height:8px`, `border-radius:50%`, `animation: spin 1s linear infinite`.
- [ ] (정상 케이스) `.trow[data-running="true"] .badge .spinner-inline { display: inline-block }` 규칙이 존재한다.
- [ ] (정상 케이스) `_render_task_row_v2` 출력 HTML에서 `.badge` div에 `data-phase` 속성이 있다.
- [ ] (정상 케이스) `_render_task_row_v2` 출력 HTML에서 `.badge` 내부에 `<span class="spinner-inline">` 요소가 있다.
- [ ] (정상 케이스) `_render_task_row_v2` 출력 HTML에 row-level `<span class="spinner">` 요소가 없다(제거 확인).
- [ ] (정상 케이스) `/api/graph` 응답 JSON의 각 노드 dict에 `phase` 필드가 존재하고 값이 `"dd"|"im"|"ts"|"xx"|"failed"|"bypass"|"pending"` 중 하나다.
- [ ] (정상 케이스) `nodeHtmlTemplate` 출력 HTML의 `.dep-node` div에 `data-phase` 속성이 있다.
- [ ] (정상 케이스) `.dep-node[data-phase="dd"] .dep-node-id { color: var(--phase-dd) }` 등 6종 규칙이 존재한다(`pending` 제외 — `pending`은 기본 `.dep-node-id` 색 사용).
- [ ] (엣지 케이스) `bypassed=True` task의 배지 `data-phase`가 `"bypass"`, `/api/graph` 노드 `phase`가 `"bypass"`.
- [ ] (엣지 케이스) `failed` task의 배지 `data-phase`가 `"failed"`, 노드 `phase`가 `"failed"`.
- [ ] (엣지 케이스) `status=None` task의 배지 `data-phase`가 `"pending"`, 노드 `phase`가 `"pending"`.
- [ ] (에러 케이스) `@keyframes spin` 중복 선언 없음 — CSS 파일에 `@keyframes spin` 이 1회만 존재한다.
- [ ] (에러 케이스) `.dep-node.status-failed .dep-node-id` 기존 규칙이 제거되지 않고 공존한다(TSK-03-03 regression 방지).
- [ ] (통합 케이스) `test_monitor_phase_badge_colors.py::test_badge_rule_for_each_phase` 통과.
- [ ] (통합 케이스) `test_monitor_phase_badge_colors.py::test_badge_spinner_inline_rule` 통과.
- [ ] (통합 케이스) `test_monitor_phase_badge_colors.py::test_running_row_shows_inline_spinner` 통과.
- [ ] (통합 케이스) `test_monitor_phase_badge_colors.py::test_dep_node_data_phase_rule` 통과.
- [ ] (통합 케이스) `test_monitor_graph_api.py::test_graph_node_has_phase_field` 통과.

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**
- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지에 도달한다 — 대시보드 루트 `/` 에서 WP 카드를 확인한다 (URL 직접 입력 금지)
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시되고 기본 상호작용이 동작한다 — `.trow .badge[data-phase]` 가 렌더되고 dep-graph 섹션 노드에 `data-phase` 속성이 존재한다
