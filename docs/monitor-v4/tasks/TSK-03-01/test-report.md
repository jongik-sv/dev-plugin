# TSK-03-01: Dep-Graph 2초 hover 툴팁 - 테스트 결과

## 결과: PASS

## 실행 요약

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 | 16 | 0 | 16 |
| E2E 테스트 | 11 | 0 | 11 |

## 정적 검증 (Dev Config에 정의된 경우만)

| 구분 | 결과 | 비고 |
|------|------|------|
| lint | N/A | Dev Config에 lint 명령 미정의 |
| typecheck | pass | `py_compile scripts/monitor-server.py scripts/dep-analysis.py` 통과 |

## QA 체크리스트 판정

| # | 항목 | 결과 |
|---|------|------|
| 1 | 노드 위에 마우스를 2초간 유지하면 popover가 표시된다 (`data-source="hover"`) | pass |
| 2 | 1.5초 후 마우스를 이동하면 popover가 표시되지 않는다 (타이머 취소) | pass |
| 3 | 노드 클릭(tap) 시 기존대로 즉시 popover가 표시된다 (`data-source="tap"`) | pass |
| 4 | tap popover는 외부 클릭, ESC 키, 빈 영역 클릭 시에만 사라진다 | pass |
| 5 | hover popover는 mouseout 시 즉시 사라진다 | pass |
| 6 | pan/zoom 중 hover 타이머가 취소되어 popover가 표시되지 않는다 | pass |
| 7 | pan/zoom 중 이미 표시된 tap popover는 위치만 추종하고 유지된다 | pass |
| 8 | `HOVER_DWELL_MS` 상수가 2000으로 선언되어 있다 | pass |
| 9 | popover DOM은 1개뿐이며 hover/tap이 같은 DOM을 재사용한다 | pass |
| 10 | `graph-client.js`에 `"mouseover"` + `"mouseout"` 이벤트 바인딩이 존재한다 | pass |
| 11 | `renderPopover` 호출 시 `data-source` 속성이 "hover" 또는 "tap"으로 설정된다 | pass |

**fullstack/frontend 필수 항목:**

| # | 항목 | 결과 |
|---|------|------|
| 12 | (클릭 경로) 대시보드 메인 접속 → Dep-Graph 섹션에 노드가 렌더됨 | pass |
| 13 | (화면 렌더링) 노드 위 2초 hover 시 popover가 브라우저에서 실제 표시되고, 마우스 이동 시 즉시 사라짐 | pass |

## 재시도 이력
- 첫 실행에 통과

## 비고
- 전체 단위 테스트 스위트(1503 passed, 11 failed, 15 skipped) 중 11개 실패는 TSK-03-01과 무관한 기존 실패(test_monitor_e2e.py의 WP-Cards, Sticky Header, KPI Section 등)
- TSK-03-01 관련 테스트 파일: `scripts/test_monitor_graph_hover.py`(12 tests), `scripts/test_monitor_graph_hover_e2e.py`(4 tests), `scripts/test_monitor_dep_graph_html_e2e.py`(7 tests) — 모두 통과
