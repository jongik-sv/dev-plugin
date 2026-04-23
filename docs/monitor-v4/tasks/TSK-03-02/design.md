# TSK-03-02: Dep-Graph 실행 중 노드 스피너 - 설계

## 요구사항 확인
- Dep-Graph 노드 중 `.running` signal이 존재하는 Task(`is_running_signal=true`)의 HTML 레이블에 회전 스피너(`.node-spinner`)를 우상단에 표시한다.
- 스피너 표시/제거는 `/api/graph` 2초 폴링 주기에 따라 자동 갱신된다 — signal 해제 시 다음 폴링(최대 2초) 이내 스피너 제거.
- CSS `.node-spinner` 규칙(공용 `@keyframes spin`, `display:none` 기본, `data-running="true"` 조건부 `display:inline-block`)은 TSK-00-01에서 이미 구현됨. 이 Task는 graph-client.js의 템플릿과 데이터 흐름만 수정.

## 타겟 앱
- **경로**: N/A (단일 앱)
- **근거**: 모놀리식 dev-plugin 프로젝트 — graph-client.js와 monitor-server.py가 같은 저장소에 위치.

## 구현 방향
- `graph-client.js`의 `nodeHtmlTemplate` 함수에 `data-running` 속성과 조건부 `.node-spinner` `<span>`을 삽입한다.
- `_addNode`/`_updateNode`에서 노드 cytoscape data에 `is_running_signal`을 전달하여 nodeHtmlLabel 플러그인이 템플릿에서 참조할 수 있게 한다.
- CSS는 TSK-00-01에서 이미 구현된 `.dep-node[data-running="true"] .node-spinner { display:inline-block; position:absolute; top:4px; right:4px; }` 규칙을 재사용하므로 추가 CSS 불필요.
- `.dep-node`에 이미 `position: relative`가 설정되어 있어 spinner의 `position: absolute`가 정상 동작한다.

## 파일 계획

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `skills/dev-monitor/vendor/graph-client.js` | nodeHtmlTemplate에 `data-running` 속성 + 조건부 `.node-spinner` 삽입; `_addNode`/`_updateNode`에 `is_running_signal` 데이터 전달 | 수정 |
| `scripts/test_monitor_task_spinner.py` | `test_graph_node_has_spinner_when_running`, `test_graph_node_spinner_absent_when_not_running` 단위 테스트 | 신규 |

> 이 Task는 Dep-Graph 내부 컴포넌트의 HTML 템플릿 수정이며, 라우터 파일이나 메뉴/네비게이션 파일의 변경은 없다. Dep-Graph는 대시보드의 `data-section="dep-graph"` 섹션으로 SSR 렌더되며 별도 라우트가 아니다.

## 진입점 (Entry Points)

**대상**: `domain=frontend`이나 Dep-Graph는 대시보드 페이지 내 섹션이므로 별도 라우트/메뉴 없음.

- **사용자 진입 경로**: 대시보드 메인 페이지 로드 → "의존성 그래프" 섹션 자동 렌더 → 실행 중 Task 노드의 우상단 스피너 관찰
- **URL / 라우트**: `/` (대시보드 메인, `?subproject=monitor-v4&lang=ko`)
- **수정할 라우터 파일**: N/A — 대시보드 단일 페이지 내 섹션. 서버 라우팅은 `monitor-server.py`의 `do_GET`이 `/` 경로에서 `render_dashboard()` 호출.
- **수정할 메뉴/네비게이션 파일**: N/A — Dep-Graph는 대시보드의 `<section data-section="dep-graph">` 내부에 자동 렌더됨. 메뉴 탐색 불필요.
- **연결 확인 방법**: 대시보드 로드 → Dep-Graph 섹션에 노드 카드 렌더 확인 → Task 중 `is_running_signal=true`인 노드에 `.node-spinner` 요소 존재 확인 (브라우저 DevTools 또는 단위 테스트).

## 주요 구조
- **`nodeHtmlTemplate(nd)`** (graph-client.js L58): `nd.is_running_signal`을 확인하여 `<div>`에 `data-running` 속성을 추가하고, `true`일 때 `<span class="node-spinner"></span>`을 삽입. node-html-label 플러그인이 매 갱신 시 이 템플릿을 재호출.
- **`_addNode(nd, style)`** (graph-client.js L82): cytoscape node data에 `is_running_signal: nd.is_running_signal` 추가.
- **`_updateNode(nd, style)`** (graph-client.js L97): 기존 노드 갱신 시 `is_running_signal` 값을 cytoscape data에 동기화하여 nodeHtmlLabel이 재렌더 시 최신 running 상태를 반영.

## 데이터 흐름
- **입력**: `/api/graph` 2초 폴링 응답의 노드 `is_running_signal` 필드 (TSK-00-02에서 이미 제공)
- **처리**: `applyDelta()` → `_addNode`/`_updateNode` → cytoscape node data에 `is_running_signal` 저장 → nodeHtmlLabel 플러그인이 `nodeHtmlTemplate(data)` 호출
- **출력**: `.dep-node` div에 `data-running="true|false"` 속성 + 조건부 `<span class="node-spinner"></span>`. CSS가 `data-running="true"`일 때만 스피너를 `display:inline-block`으로 활성화.

## 설계 결정 (대안이 있는 경우만)
- **결정**: `_addNode`/`_updateNode`에서 cytoscape data에 `is_running_signal`을 저장하고 nodeHtmlTemplate에서 직접 참조.
- **대안**: `_raw` 객체(node data에 이미 저장됨)에서만 참조하고 별도 필드를 추가하지 않음.
- **근거**: `nodeHtmlTemplate(data)`의 `data` 매개변수는 cytoscape node의 `data` 객체이며, `_raw`도 그 안에 있지만 `_raw.is_running_signal`로 접근하는 것보다 `data.is_running_signal`로 일관성 있게 접근하는 것이 명확. 기존 코드에서도 `data.id`, `data.label` 등 최상위 필드를 직접 참조하는 패턴을 따름.

## 선행 조건
- **TSK-00-01** (완료): 공용 `@keyframes spin` CSS + `.node-spinner` 기본 규칙 + `.dep-node[data-running="true"] .node-spinner` 위치 규칙이 monitor-server.py에 이미 구현됨.
- **TSK-00-02** (완료): `/api/graph` 노드 payload에 `is_running_signal` 필드가 이미 포함됨 (monitor-server.py L4925).
- **node-html-label 플러그인**: cytoscape 확장으로 이미 연동됨 (graph-client.js L330-335). 템플릿 변경 시 플러그인이 자동으로 HTML을 재렌더함.

## 리스크
- **LOW**: node-html-label 플러그인이 템플릿 재호출 시 이전 HTML을 완전히 교체하지 않고 incremental update를 할 가능성. — `_updateNode`에서 `_raw`를 갱신하면 nodeHtmlLabel이 템플릿을 재평가하므로, 기존 패턴(다른 필드 갱신 시 HTML이 올바르게 재생성됨)에서 문제 없음이 확인됨.
- **LOW**: 스피너 `<span>`이 노드 카드의 ID/title 텍스트를 가릴 가능성. — `.dep-node`에 `position: relative`가 이미 설정되어 있고, 스피너는 `position: absolute; top:4px; right:4px`로 우상단에 배치되어 텍스트와 겹치지 않음.
- **LOW**: `_updateNode`에서 `is_running_signal` 갱신을 누락하면 스피너가 해제되지 않음. — 설계에서 명시적으로 `_updateNode`에 `is_running_signal` 갱신 라인을 포함하므로 dev-build에서 누락 시 테스트가 실패함.

## QA 체크리스트
dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

- [ ] `is_running_signal=true`인 노드 데이터로 `nodeHtmlTemplate` 호출 시 반환 HTML에 `<span class="node-spinner"></span>`이 포함된다
- [ ] `is_running_signal=false`인 노드 데이터로 `nodeHtmlTemplate` 호출 시 반환 HTML에 `.node-spinner` 요소가 존재하지 않는다
- [ ] `is_running_signal=true`인 노드의 HTML에 `data-running="true"` 속성이 존재한다
- [ ] `is_running_signal=false`인 노드의 HTML에 `data-running="false"` 속성이 존재한다
- [ ] `_addNode` 호출 시 cytoscape node data에 `is_running_signal` 필드가 저장된다
- [ ] `_updateNode` 호출 시 기존 노드의 `is_running_signal` 값이 갱신된다
- [ ] signal이 해제되어 다음 폴링에서 `is_running_signal=false`가 전달되면, nodeHtmlTemplate 재렌더 후 `.node-spinner` 요소가 DOM에서 제거된다 (2초 이내)
- [ ] 스피너가 노드 카드의 ID/title 텍스트를 가리지 않는다 — 우상단 4px offset 위치 확인
- [ ] 기존 노드 속성(ID, title, 상태 색상, critical/bottleneck 클래스)에 회귀가 없다

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**
- [ ] (클릭 경로) 대시보드 메인 페이지 로드 후 Dep-Graph 섹션이 자동 렌더된다 (별도 클릭 불필요, 섹션이 대시보드의 일부로 항상 표시됨)
- [ ] (화면 렌더링) 실행 중 Task의 Dep-Graph 노드 카드 우상단에 회전 스피너 애니메이션이 표시되고, 실행 중이 아닌 노드에는 스피너가 표시되지 않는다
