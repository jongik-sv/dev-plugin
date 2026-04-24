# Build Report — core-http-split

**Feature:** core-http-split  
**Phase:** build (`[dd]` → `[im]`)  
**Date:** 2026-04-24  
**Test gate:** only 2 pre-existing failures allowed

---

## Deliverables

| Commit | Description |
|--------|-------------|
| C1-1 `handlers_pane.py` | `_handle_pane_html`, `_handle_pane_api` 이관 |
| C1-2 `handlers_graph.py` | `_handle_graph_api`, `_handle_api_task_detail` 이관 |
| C1-3 `handlers_state.py` | `_handle_api_state` 이관, 모듈 레벨 workitem 심볼 노출 |
| C1-4 `handlers.py` | `MonitorHandler` + `_resolve_plugin_root` 이관 |
| C2-1 (이번 커밋) | `_resolve_core()` 우선순위 수정 + facade stable key 등록 |

---

## 핵심 구조 결정

### `_resolve_core()` 우선순위: `monitor_server_core_impl` → `monitor_server.core`

- `test_monitor_graph_api.py`가 `core_mod = sys.modules["monitor_server_core_impl"]`로 패치
- handler 함수가 같은 객체를 써야 패치가 유효함 → impl 먼저

### `_resolve_graph_cache()` 우선순위: `monitor_server.core` → `monitor_server_core_impl` (역순)

- `test_monitor_server_perf.py`가 `self.core._GRAPH_CACHE = fresh_cache` 교체 (self.core = monitor_server.core 패키지)
- cache 객체 교체를 반영하려면 패키지 core 먼저 확인

### stable module key (`monitor_server_handlers_impl`)

- `test_monitor_module_split.py`가 `monitor_server.*` 전부 삭제하고 패키지 재로드
- `do_GET.__globals__["__name__"]` = `"monitor_server_handlers_impl"` → stable key는 삭제되지 않음
- `_get_do_get_module()`가 stable key로 sys.modules 조회 → 동일 객체 반환 보장

### sync 전략 기각

- `monitor_server_core_impl` → `monitor_server.core` 동기화 시도
- `_iter_flat_entry_modules()`의 함수 identity 검사가 깨짐 (다른 module의 `capture_pane`을 mock으로 오인)
- revert 후 두-우선순위 시스템으로 해결

---

## 테스트 결과

```
2 failed (pre-existing), 1997 passed, 176 skipped
```

**Pre-existing failures (허용):**
1. `test_monitor_task_expand_ui.py::TestTaskPanelCss::test_initial_right_negative` — slide-panel CSS 560px 단언
2. `test_platform_smoke.py::SmokeTestBase::test_pane_polling_interval` — 폴링 메커니즘 단언

---

## 파일 목록

- `scripts/monitor_server/handlers_pane.py` (신규)
- `scripts/monitor_server/handlers_graph.py` (신규)
- `scripts/monitor_server/handlers_state.py` (신규)
- `scripts/monitor_server/handlers.py` (대폭 확장 — MonitorHandler 이관)
- `scripts/monitor_server/core.py` (facade 단순화 — 약 310줄 net 감소)
