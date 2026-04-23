# TSK-04-03: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| `scripts/test_monitor_dep_graph_html.py` | `_py_node_html_template` status 정규화 분기에서 도달 불가 `elif` 브랜치 3개 제거 (`elif raw == "done"`, `elif raw == "running"`, `elif raw == "failed"`) — 상위 `in` 연산자 분기에서 이미 처리되는 dead code | Remove Dead Code, Simplify Conditional |
| `scripts/test_monitor_dep_graph_html.py` | 미사용 함수 `_read_section_dep_graph_html` 제거 — 정의만 있고 호출되지 않으며, canvas height 검증은 `TestDepGraphCanvasHeight640.setUp`에서 소스 파싱으로 직접 처리됨 | Remove Dead Code |
| `scripts/test_monitor_dep_graph_html.py` | 미사용 `import sys` 제거 — `_read_section_dep_graph_html` 제거로 더 이상 참조되지 않음 | Remove Unused Import |

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m pytest scripts/test_monitor_dep_graph_html.py -q`
- 38/38 통과. 전체 suite (`python3 -m pytest scripts/ -q`) 에서도 기존 통과 항목 전부 유지.

## 비고
- 케이스 분류: A (성공 — 리팩토링 적용 후 테스트 통과)
- `monitor-server.py`의 dep-node CSS 블록(lines 1961-2026)은 구조가 명확하고 CSS 커스텀 프로퍼티 패턴이 일관되어 CSS 측 변경 불필요로 판단. `pointer-events: none` + `.dep-node:hover` 공존은 cytoscape canvas overlay 구조상 의도적이므로 동작 변경 없이 유지.
- 리팩토링 대상은 테스트 헬퍼 함수(`_py_node_html_template`) 내 dead code에 한정.
