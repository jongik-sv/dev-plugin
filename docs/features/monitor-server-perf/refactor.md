# monitor-server-perf: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| `scripts/leader-watchdog.py` | `main()` 내 `window_exists()` + `pane_dead()` 2회 호출을 `check_window_and_pane()` 1회 호출로 통합. `check_window_and_pane()`은 이미 build 단계에서 구현되어 있었으나 `main()` 폴링 루프에 미반영된 상태였음. | Replace Function with Already-Extracted Abstraction, Remove Duplication |
| `scripts/monitor_server/core.py` | `_handle_graph_api` 기본 인자 `scan_signals_fn` 값을 `scan_signals` → `scan_signals_cached`로 수정. 설계 의도(캐시 사용)대로 기본 경로에서 TTL 캐시가 동작하도록 정렬. | Fix Default Parameter |
| `scripts/monitor_server/core.py` | `sys.pycache_prefix` 초기화 블록을 `_ensure_etag_cache()` 함수 정의 이후에서 import 블록 직후로 이동. 모듈 초기화 순서 명확화. etag_cache lazy-load 블록의 역할(일반 API weak ETag)과 `/api/graph` 전용 ETag(`_graph_etag` / `_get_if_none_match`)의 구분을 주석으로 명시. | Clarify Order, Explain Responsibilities |

## 테스트 확인
- 결과: PASS
- 실행 명령: `/usr/bin/python3 -m pytest scripts/test_monitor_server_perf.py scripts/test_merge_wbs_status.py scripts/test_feat_category.py scripts/test_log_mistake.py -q`
- 96 passed in 1.15s — 리팩토링 전후 동일

## 비고
- 케이스 분류: A (성공 — 변경 적용 후 테스트 통과)
- `leader-watchdog.py`의 `window_exists()`, `pane_dead()` 두 함수는 기존 하위 호환 공개 API로 유지 (다른 스크립트에서 직접 호출할 가능성 대비). `main()` 내부만 통합 함수로 전환.
- core.py는 대형 모놀리스(7205줄)이므로 전면 리팩토링 대신 이번 변경 범위 내 3곳만 수정.
