# TSK-05-01: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | (1) `WorkItem.domain` 필드 추가, (2) `_load_wbs_title_map` 5-tuple 확장(domain 파싱), (3) `scan_tasks` domain 후처리, (4) `_render_task_row_v2` `data-domain` 속성 추가, (5) `_section_filter_bar(lang, distinct_domains)` SSR 헬퍼 신규, (6) `render_dashboard`에 filter-bar 삽입, (7) `_build_dashboard_body`에 filter-bar 위치 추가, (8) DASHBOARD_CSS `.filter-bar` sticky 스타일, (9) `_DASHBOARD_JS` 필터 로직 5함수 + patchSection monkey-patch + 이벤트 바인딩, (10) `patchSection`에 filter-bar skip guard, (11) `_handle_api_state` `distinct_domains` 필드 추가 | 수정 |
| `skills/dev-monitor/vendor/graph-client.js` | `applyFilter(predicate)` 함수 + `window.depGraph.applyFilter` 노출 | 수정 |
| `scripts/test_monitor_filter_bar.py` | 단위 테스트 55개 — filter-bar DOM, data-domain, URL state, patchSection wrapping, reset, CSS, JS 함수 presence | 신규 |
| `scripts/test_monitor_filter_bar_e2e.py` | E2E 테스트 — reachability, URL roundtrip, patchSection, reset, /api/state distinct_domains, filter interaction | 신규 (build 작성, 실행은 dev-test) |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (test_monitor_filter_bar.py) | 55 | 0 | 55 |
| 기존 단위 테스트 전체 (regression) | 1485 | 0 | 1485 (+15 skip) |

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| `scripts/test_monitor_filter_bar_e2e.py` | FilterBarReachabilityTests, FilterBarUrlStateTests, FilterBarSurvivesRefreshTests, FilterBarResetTests, FilterBarApiStateTests, FilterInteractionTests — QA 체크리스트 통합 케이스 |

## 커버리지 (Dev Config에 coverage 정의 시)
- N/A (Dev Config에 coverage 명령 없음)

## 비고
- `WorkItem.domain` 필드를 신규 추가했으며 기존 `model` 필드와 동일한 후처리 패턴 사용
- `_load_wbs_title_map`을 4-tuple→5-tuple로 확장했으나 기존 len 체크 로직(`len(entry) >= 4/5`)으로 하위호환 보장
- `patchSection`에 `filter-bar` skip guard 추가 — 필터 바 자체의 SSR 내용이 5초 polling으로 교체되지 않도록 보호
- `window.depGraph.applyFilter` guard (`if(window.depGraph&&typeof window.depGraph.applyFilter==='function')`) 로 dep-graph 비활성 환경에서도 TypeError 없이 동작
- `patchSection.__filterWrapped` sentinel로 이중 monkey-patch 방지
