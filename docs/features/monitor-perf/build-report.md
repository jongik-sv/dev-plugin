# Build Report — monitor-perf

**Phase:** Build (TDD) `[dd]` → `[im]`
**Date:** 2026-04-24
**Status:** PASS

## 산출물 목록

| 산출물 | 역할 |
|--------|------|
| `scripts/monitor_server/etag_cache.py` | weak ETag 헬퍼 (compute_etag, check_if_none_match) |
| `scripts/monitor_server/core.py` | _ensure_etag_cache() lazy-load + _json_response ETag/304 처리 |
| `scripts/monitor_server/static/app.js` | visibilitychange 폴링 guard + If-None-Match / 304 클라이언트 처리 |
| `scripts/monitor_server/static/style.css` | GPU audit baseline 주석 추가 |
| `scripts/test_monitor_etag.py` | ETag 단위 테스트 (24 cases) |
| `scripts/test_monitor_polling_visibility.py` | 가시성 폴링 정적 단언 (6 cases) |
| `scripts/test_monitor_perf_regression.py` | Playwright 기반 성능 회귀 테스트 (4 cases, CI skip) |
| `scripts/test_monitor_gpu_audit.py` | GPU 레이어 남용 감사 (9 cases) |

## 테스트 결과

```
39 passed, 4 skipped (Playwright — MONITOR_PERF_REGRESSION=1 필요)
```

- `test_monitor_etag.py`: 24/24 PASS
- `test_monitor_polling_visibility.py`: 6/6 PASS
- `test_monitor_perf_regression.py`: 4/4 SKIP (정상 — CI 환경변수 미설정)
- `test_monitor_gpu_audit.py`: 9/9 PASS

## 회귀 확인

기존 테스트 스위트 (`test_monitor_graph_api.py`, `test_monitor_api_state.py`) 결과:
- 124 PASS, 3 FAIL — 3개 실패는 모두 pre-existing (HEAD에서도 동일):
  - `test_api_graph_subprocess_error_returns_500` — `_load_dep_analysis_module` in-process 로딩이 subprocess mock 우회 (pre-existing)
  - `test_api_graph_subprocess_timeout_returns_500` — 동일 원인 (pre-existing)
  - `test_graph_node_has_phase_field` — pre-existing 버그

우리 변경으로 인한 신규 회귀 없음.

## 설계 결정 준수

- weak ETag (`W/"<SHA256[:14]>"`) — RFC 7232 §2.3 준수
- `_ensure_etag_cache()`: `_monitor_perf_etag_cache` 고유 키로 sys.modules 오염 방지
- GPU 레이어 프로퍼티(will-change/translateZ/translate3d) 0건 유지
- Playwright 회귀 테스트: `MONITOR_PERF_REGRESSION=1` 환경변수로 CI 격리
