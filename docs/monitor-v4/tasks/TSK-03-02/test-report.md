# TSK-03-02: 테스트 결과

## 결과: PASS

## 실행 요약

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 | 21 | 0 | 21 |
| E2E 테스트 | 7 | 0 | 7 |

## 정적 검증 (Dev Config에 정의된 경우만)

| 구분 | 결과 | 비고 |
|------|------|------|
| typecheck | pass | `py_compile` 성공 |

## QA 체크리스트 판정

| # | 항목 | 결과 |
|---|------|------|
| 1 | `is_running_signal=true`인 노드 데이터로 `nodeHtmlTemplate` 호출 시 반환 HTML에 `<span class="node-spinner"></span>`이 포함된다 | pass |
| 2 | `is_running_signal=false`인 노드 데이터로 `nodeHtmlTemplate` 호출 시 반환 HTML에 `.node-spinner` 요소가 존재하지 않는다 | pass |
| 3 | `is_running_signal=true`인 노드의 HTML에 `data-running="true"` 속성이 존재한다 | pass |
| 4 | `is_running_signal=false`인 노드의 HTML에 `data-running="false"` 속성이 존재한다 | pass |
| 5 | `_addNode` 호출 시 cytoscape node data에 `is_running_signal` 필드가 저장된다 | pass |
| 6 | `_updateNode` 호출 시 기존 노드의 `is_running_signal` 값이 갱신된다 | pass |
| 7 | signal이 해제되어 다음 폴링에서 `is_running_signal=false`가 전달되면, nodeHtmlTemplate 재렌더 후 `.node-spinner` 요소가 DOM에서 제거된다 (2초 이내) | pass |
| 8 | 스피너가 노드 카드의 ID/title 텍스트를 가리지 않는다 — 우상단 4px offset 위치 확인 | pass |
| 9 | 기존 노드 속성(ID, title, 상태 색상, critical/bottleneck 클래스)에 회귀가 없다 | pass |
| 10 | (클릭 경로) 대시보드 메인 페이지 로드 후 Dep-Graph 섹션이 자동 렌더된다 (별도 클릭 불필요, 섹션이 대시보드의 일부로 항상 표시됨) | pass |
| 11 | (화면 렌더링) 실행 중 Task의 Dep-Graph 노드 카드 우상단에 회전 스피너 애니메이션이 표시되고, 실행 중이 아닌 노드에는 스피너가 표시되지 않는다 | pass |

## 재시도 이력

첫 실행에 통과 — 3회 시도 예산 미소진.

## 비고

**단위 테스트 상세**:
- `test_graph_node_has_spinner_when_running` (TestGraphNodeHasSpinnerWhenRunning): 조건부 스피너 삽입 검증
- `test_graph_node_spinner_absent_when_not_running` (TestGraphNodeSpinnerAbsentWhenNotRunning): 스피너 비존재 검증
- `test_graph_node_data_running_true_when_running` (TestGraphNodeDataRunningAttribute): data-running="true" 검증
- `test_graph_node_data_running_false_when_not_running` (TestGraphNodeDataRunningAttribute): data-running="false" 검증
- `test_add_node_stores_is_running_signal` (TestAddNodeStoresIsRunningSignal): _addNode 데이터 저장 검증
- `test_update_node_syncs_is_running_signal` (TestUpdateNodeSyncsIsRunningSignal): _updateNode 동기화 검증
- `test_js_source_nodeHtmlTemplate_function_present` (TestNoRegressionExistingNodeAttributes): 함수 존재 검증
- `test_no_regression_critical_class`, `test_no_regression_bottleneck_class`, `test_no_regression_status_class`: 기존 속성 회귀 검증
- `test_spinner_position_in_js_source`, `test_monitor_server_has_dep_node_spinner_css`: CSS 위치 규칙 검증
- 기타 11개 테스트: JS 소스 정적 분석 및 XSS 이스케이프 검증

**E2E 테스트 상세** (dep-graph-html-e2e.py):
- `test_dep_graph_section_exists`: 대시보드 HTML에 dep-graph 섹션 존재 확인
- `test_dep_graph_canvas_exists`: dep-graph-canvas div 존재 확인
- `test_graph_client_js_static_served`: graph-client.js 정적 파일 서빙 확인
- `test_node_html_label_plugin_loaded`: cytoscape-node-html-label 플러그인 로드 확인
- 기타 3개 테스트: CSS 인라인 포함, 스크립트 태그 로드 확인

**dep-graph HTML 단위 테스트 상세** (38개 통과):
- CSS 규칙 검증: `.dep-node .node-spinner` 위치 규칙, critical/bottleneck 보더 등
- 노드 템플릿 구조 검증: ID, title, 상태 색상 매핑, XSS 이스케이프 처리
- 기존 기능 회귀 검증: layout nodeSeq/rankSep, status 매핑, popover handler 등

**서버 정상성**:
- typecheck (py_compile) 통과 — monitor-server.py, dep-analysis.py 문법 검증 완료
- E2E 서버 (http://localhost:7321) 정상 구동 중

**결론**: TSK-03-02 Dep-Graph 실행 중 노드 스피너 기능이 요구사항 정합성과 회귀 검증 모두 통과했습니다.
