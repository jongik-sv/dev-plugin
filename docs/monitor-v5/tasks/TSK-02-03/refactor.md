# TSK-02-03: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| `scripts/monitor_server/handlers.py` | `_get_core_handler_fn` + `_get_core_fn` 두 함수의 중복 flat-module fallback 로직을 `_load_core()` + `_get_core_attr()` 단일 경로로 통합; `_route_api_*` 4개 메서드의 반복 `from monitor_server import api` 임포트를 `_get_api_module()` 헬퍼로 추출; `_route_api_state`의 tmux_fn 조회 인라인 로직을 `_resolve_tmux_fn()` 헬퍼로 분리; 불필요한 `from typing import List, Optional` + `parse_qs` 임포트 제거 | Extract Method, Remove Duplication, Remove Unused Import |
| `scripts/monitor-server.py` | `main()`에서 `MonitorHandler`(core.py)를 사용하던 것을 `handlers.Handler`(AC-FR07-b 요구사항)로 교체; core에서 `_resolve_plugin_root`를 가져오던 복잡한 로직을 `handlers`에서 직접 임포트하도록 단순화; core 로드 실패 시 sys.exit 경로 제거(Handler 임포트 실패 시 ImportError로 자연 처리) | Simplify Conditional, Remove Duplication |

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m pytest scripts/test_monitor_module_split.py scripts/test_monitor_static.py -v`
- 결과: 76 passed (test_monitor_module_split.py 28개 + test_monitor_static.py 48개)
- 전체 suite: `python3 -m pytest scripts/ --tb=no -q` → 기존 pre-existing 실패(test_monitor_e2e.py, test_monitor_render.py, test_monitor_dep_graph_html.py 일부)와 동일 수준 유지, TSK-02-03 범위 테스트 회귀 0

## 비고
- 케이스 분류: A (리팩토링 성공, 변경 적용 후 테스트 통과)
- `monitor-server.py`의 `main()`이 `MonitorHandler`(core)가 아닌 `Handler`(handlers.py)를 사용하도록 수정한 것이 핵심 기능 수정이기도 함 — AC-FR07-b("Handler 기반 서버 기동") 요구사항을 완전히 충족시키는 변경
- `handlers.py` 줄 수: 346 → 351줄 (코드 추출로 소폭 증가, ≤ 800 AC 유지)
- `monitor-server.py` 줄 수: 239 → 228줄 (< 500 AC 유지)
