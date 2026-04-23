# TSK-05-02: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `skills/dev-monitor/vendor/graph-client.js` | `FILTER_OPACITY_DIM`/`FILTER_OPACITY_ON` 상수 추가, `_filterPredicate` 모듈 스코프 변수 추가, `applyFilter(predicate)` 함수 정의(노드/엣지 opacity 제어), `applyDelta` topoChanged/동기 양 경로에 필터 재적용 훅 삽입, `window.depGraph.applyFilter` 전역 노출 | 수정 |
| `scripts/monitor-server.py` | `_build_graph_payload` 노드 dict에 `"domain"`, `"model"` 필드 추가 (`task.domain`/`task.model` 그대로, None → `"-"` fallback) | 수정 |
| `scripts/test_monitor_graph_filter.py` | 단위 테스트 20개: applyFilter 함수 정의, 상수, _filterPredicate, reload hook, /api/graph domain/model payload, domain fallback, JS 코드 텍스트 분석, _load_wbs_title_map domain 파싱 | 신규 |
| `scripts/test_monitor_graph_filter_e2e.py` | E2E 테스트: 정적 JS 검증 4개, /api/graph 응답 필드 3개, Playwright 필터 상호작용 4개 (build 작성, 실행은 dev-test) | 신규 (build 작성, 실행은 dev-test) |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (test_monitor_graph_filter.py) | 20 | 0 | 20 |
| 회귀 테스트 (test_monitor_graph_api.py + test_monitor_graph_hover.py) | 67 | 0 | 67 |

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| `scripts/test_monitor_graph_filter_e2e.py` | /static/graph-client.js applyFilter/상수/window.depGraph 노출, /api/graph domain/model 필드, 필터 바 조작 → Cytoscape opacity, applyFilter(null) 복원, 2초 폴링 후 필터 유지, 비매칭 엣지 dim |

## 커버리지 (Dev Config에 coverage 정의 시)
- N/A (Dev Config에 coverage 명령 없음)

## 비고

- `_load_wbs_title_map`과 `WorkItem.domain` 필드는 monitor-server.py에 TSK-05-01 과정에서 이미 추가되어 있었음. `_build_graph_payload` payload 필드 추가만 필요했음.
- `applyDelta`의 두 경로(topoChanged=true의 layoutstop 비동기 콜백, topoChanged=false 동기 경로) 모두에 재적용 훅 삽입하여 2초 폴링 후 필터 생존 보장.
- 엣지 복원 시 `edge.data("color")`로 원본 색상을 읽어 복원 (design.md 결정 준수).
- `test_monitor_render.py::KpiCountsTests::test_done_excludes_bypass_failed_running` 실패는 TSK-05-02 이전부터 존재하는 pre-existing 문제 (`_kpi_counts` 로직 변경이 uncommitted 상태였음) — 본 Task 범위 밖.
- 플러그인 캐시 동기화: `~/.claude/plugins/cache/dev-tools/dev/1.6.1/skills/dev-monitor/vendor/graph-client.js` 완료.
