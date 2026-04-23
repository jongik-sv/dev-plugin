# TSK-04-02: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `skills/dev-monitor/vendor/graph-client.js` | `escapeHtml` 헬퍼 추가; `nodeHtmlTemplate` 함수 추가; `nodeStyle()` label/⚠ 제거; cytoscape node style 투명화(background-opacity:0, border-width:0, width:180, height:54); `cy.nodeHtmlLabel` 등록; layout nodeSep:60/rankSep:120; applyDelta label 갱신 정리 | 수정 |
| `scripts/monitor-server.py` | DASHBOARD_CSS에 `.dep-node*` CSS 인라인 추가 (2줄 카드, status strip, critical/bottleneck 클래스) | 수정 |
| `scripts/test_monitor_dep_graph_html.py` | `nodeHtmlTemplate` 구조, `escapeHtml`, bottleneck/critical 클래스, nodeSep/rankSep, nodeStyle label 제거, 팝오버/updateSummary 보존 단위 테스트 (24개) | 신규 |
| `scripts/test_monitor_dep_graph_html_e2e.py` | 대시보드 HTML dep-graph 섹션, dep-graph-canvas, graph-client.js 로드, cytoscape-node-html-label 로드, dep-node CSS, dep-graph-summary 존재 E2E 테스트 (7개) | 신규 (build 작성, 실행은 dev-test) |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (test_monitor_dep_graph_html.py) | 24 | 0 | 24 |
| 전체 스위트 회귀 확인 (scripts/) | 1116 | 0 (신규 없음) | - |

> 기존 `test_monitor_e2e.py`의 8개 E2E 실패는 본 Task 이전부터 pre-existing failures이며 본 변경으로 인해 새로 발생하지 않았다.

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| `scripts/test_monitor_dep_graph_html_e2e.py` | dep-graph 섹션 존재, graph-client.js 로드 확인, cytoscape-node-html-label.min.js 로드, dep-graph-canvas container 존재, dep-node CSS 포함, /static/graph-client.js 서빙 (nodeHtmlTemplate/escapeHtml/nodeHtmlLabel 함수 포함 확인), dep-graph-summary 존재 |

## 커버리지 (Dev Config에 coverage 정의 시)

- N/A (Dev Config에 coverage 명령 미정의)

## 비고

- LOC 제약(≤350): 최종 315 LOC — 여유 있음
- `applyDelta` 내 `ele.data("label", style.label)` 제거하고 `ele.data("label", nd.label)`로 대체 — HTML 플러그인이 `nd.label` 직접 사용하므로 `style.label`(구 ⚠ 포함) 갱신 불필요 (design.md 리스크 MEDIUM 해소)
- `.dep-node*` CSS는 design.md 파일 계획에 `scripts/monitor-server.py` 수정 항목으로 명시됨 — 동일 Task에서 함께 처리
- `cy.nodeHtmlLabel` 플러그인 가드(`typeof cy.nodeHtmlLabel === "function"`) 추가 — design.md 리스크 HIGH 해소
