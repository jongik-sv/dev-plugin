# monitor-server-perf: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor_server/core.py` | `hashlib` import 추가; `_TTLCache` 클래스 신규 (threading.Lock + monotonic TTL); `_SIGNALS_CACHE`/`_GRAPH_CACHE` 모듈 레벨 인스턴스; `scan_signals_cached()` 신규 (1초 TTL 래퍼); `_call_dep_analysis_graph_stats()` subprocess→importlib 인프로세스 전환 + 올바른 scripts/ 경로 fallback; `_load_dep_analysis_module()` 신규 (sys.modules 캐시); `_graph_etag()` / `_get_if_none_match()` 신규; `_handle_graph_api()` 캐시+ETag+304 지원으로 재작성 | 수정 |
| `scripts/leader-watchdog.py` | `check_window_and_pane()` 신규 (list-windows -F 1회 호출로 window_exists+pane_dead 통합) | 수정 |
| `scripts/test_monitor_server_perf.py` | 신규 회귀 테스트 37개 (TTLCache, scan_signals_cached, ETag/304, compute_graph_stats in-process, check_window_and_pane, p95 응답시간, subprocess fork count) | 신규 |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (test_monitor_server_perf.py) | 37 | 0 | 37 |
| 회귀 테스트 (test_monitor_server.py) | 22 | 0 | 22 |
| 회귀 테스트 (test_monitor_server_bootstrap.py) | pass | 0 | - |
| 회귀 테스트 (test_dep_analysis_graph_stats.py) | 15 | 0 | 15 |
| 회귀 테스트 (test_dep_analysis_critical_path.py) | 25 | 0 | 25 |
| 회귀 테스트 (test_monitor_dep_graph_html.py) | 38 | 0 | 38 |
| 회귀 테스트 (test_monitor_dep_graph_summary.py) | 5 | 0 | 5 |

## E2E 테스트 (작성만 — 실행은 dev-test)

N/A — backend/default domain

## 커버리지 (Dev Config에 coverage 정의 시)

N/A — Dev Config 미정의

## 비고

- `dep-analysis.py`의 `compute_graph_stats()` 함수는 WP-02 이전에 이미 추출되어 있었음. 설계 항목6은 신규가 아닌 현황 확인.
- `_call_dep_analysis_graph_stats()`의 기존 subprocess 경로가 `scripts/monitor_server/dep-analysis.py`(존재하지 않음)를 참조하는 버그를 발견, fallback subprocess 경로를 올바른 `scripts/dep-analysis.py`로 수정.
- `_DASHBOARD_JS`의 `fetchAndPatch` 폴링을 `fetch('/')` → `/api/state` JSON 패치로 전환하는 설계 항목4는 대시보드 JS 내 DOM 매핑 복잡도로 인해 이번 Build 범위에서 제외. dev-test 단계에서 통합 테스트 실행 후 별도 작업으로 진행 권장.
- `_import_core()` 헬퍼에 `importlib.reload(core)` 적용: 테스트 프로세스 내 모듈 캐시와 디스크 파일 불일치 방지.
- p95 응답시간 테스트: 캐시 히트 경로에서 50회 측정, p95 < 100ms 달성 (실측 p95 ~0.3ms).
- subprocess fork 0회 확인: dep-analysis를 importlib 인프로세스 호출로 전환 완료.
