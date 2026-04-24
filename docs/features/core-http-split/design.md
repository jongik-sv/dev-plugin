# core-http-split: HTTP 계층 분리 설계

## 요구사항 확인

- `scripts/monitor_server/core.py` (6,874 LOC) 에서 `MonitorHandler` 클래스(L6492–L6716, 225 lines)와 `_handle_*` 7개 함수(합계 484 lines)를 `handlers.py`로 이관하여 core.py를 ≥ 500 LOC 감소시킨다.
- `import monitor_server.core as core` → `core.MonitorHandler` 접근 경로를 포함한 기존 facade 계약을 유지한다.
- 이관 후 `handlers.py`는 NF-03(≤ 800 LOC)를 초과하므로, 같은 커밋 체인 내에서 `handlers_state.py` / `handlers_pane.py` / `handlers_graph.py` 3개로 2차 분할한다.

## 타겟 앱

- **경로**: N/A (단일 앱 — `scripts/monitor_server/` 패키지 직접 수정)
- **근거**: 내부 리팩토링. 사용자 UI·API URL 계약 변경 없음.

## 구현 방향

1. **baseline 기록** → `python3 -m pytest -q scripts/ --tb=no` 결과를 `docs/features/core-http-split/baseline.txt`에 저장 (2개 사전 실패 확인).
2. **C0-1 (prep)**: `handlers.py`에 이관 함수들이 의존하는 상수(`_GRAPH_PHASE_TAIL_LIMIT`, `_DEP_ANALYSIS_TIMEOUT`, `_RUNNING_STATUSES`, `_API_GRAPH_PATH`, `_MERGE_STATUS_FILENAME`, `_MERGE_STALE_SECONDS`, `_DEFAULT_MAX_PANE_LINES`, `_DEFAULT_REFRESH_SECONDS`, `_PHASE_TAIL_LIMIT`)와 helper 함수들(`_server_attr`, `_resolve_effective_docs_dir` 등)이 어디서 오는지 확인하고, 지연 import 계획을 확정한다.
3. **C1-N (이관 + 분할)**: `MonitorHandler` + `_handle_*` 7개를 handlers.py로 이동 → 1075 LOC 초과 확인 → spec.md 분할 전략대로 `handlers_state.py` / `handlers_pane.py` / `handlers_graph.py`로 즉시 분할.
4. **C2-1 (core.py facade)**: 이관된 심볼에 대해 `from .handlers import MonitorHandler` + 서브모듈 재-export를 core.py에 추가하고 원본 블록을 삭제.
5. **C3-1 (cleanup)**: 이관 후 handlers.py에서 중복된 상수/helper 정리, 미사용 import 제거.

핵심 패턴: `core-decomposition`의 try/except 지연 import 전략을 동일하게 적용한다. 순환 참조(`handlers → core → handlers`)를 방지하기 위해 `_handle_*` 내부에서 `from monitor_server import api as _api` / `from monitor_server import caches as _caches` 형태의 함수 내부 지연 import를 사용한다.

## 실측 재확인

grep으로 재측정한 라인 범위 (설계 시점 기준):

| 심볼 | 시작 | 종료 | LOC |
|------|------|------|-----|
| `_handle_static` | L4584 | L4640 | 57 |
| `_handle_pane_html` | L4802 | L4833 | 32 |
| `_handle_pane_api` | L4834 | L4882 | 49 |
| `_handle_graph_api` | L5023 | L5176 | 154 |
| `_handle_api_task_detail` | L5339 | L5373 | 35 |
| `_handle_api_merge_status` | L5492 | L5518 | 27 |
| `_handle_api_state` | L6362 | L6491 | 130 |
| `MonitorHandler` (클래스 전체) | L6492 | L6716 | 225 |
| **이관 합계** | | | **709** |

현재 `handlers.py` LOC: 366  
이관 후 예상 LOC: **1,075** → NF-03(≤ 800) 초과 → **2차 분할 필수**

## 파일 계획

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `docs/features/core-http-split/baseline.txt` | pytest 사전 baseline (2 failed 확인용) | 신규 |
| `scripts/monitor_server/handlers.py` | `MonitorHandler` 클래스 + `_handle_static` + `_handle_api_merge_status` 이관. 기존 `Handler` 클래스는 `MonitorHandler`로 교체/병합 또는 병렬 공존 유지 (아래 설계 결정 참조) | 수정 |
| `scripts/monitor_server/handlers_state.py` | `_handle_api_state` 이관 | 신규 |
| `scripts/monitor_server/handlers_pane.py` | `_handle_pane_html` + `_handle_pane_api` 이관 | 신규 |
| `scripts/monitor_server/handlers_graph.py` | `_handle_graph_api` + `_handle_api_task_detail` 이관 | 신규 |
| `scripts/monitor_server/core.py` | 이관된 심볼 제거 + facade 재-export (`from .handlers import MonitorHandler` 등) | 수정 |

## 진입점 (Entry Points)

N/A (내부 리팩토링 — 사용자 UI·URL 변경 없음)

## 주요 구조

### 심볼 의존 그래프 (이관 대상 → 의존 모듈)

```
handlers_pane.py
  _handle_pane_html, _handle_pane_api
    → core (facade via try/except): capture_pane, _pane_capture_payload, _render_pane_html, _render_pane_json
    → core (facade): _send_html_response, _json_error
    → core (constants): _DEFAULT_MAX_PANE_LINES, _PHASE_TAIL_LIMIT, _GRAPH_PHASE_TAIL_LIMIT, _RUNNING_STATUSES
    → api (via inline import): _serialize_phase_history_tail_for_graph

handlers_graph.py
  _handle_graph_api
    → caches (direct import): _GRAPH_CACHE
    → api (direct import): _build_graph_payload, _build_fan_in_map
    → core (facade): _aggregated_scan, _call_dep_analysis_graph_stats, _server_attr
    → core (constants): _API_GRAPH_PATH, _DEP_ANALYSIS_TIMEOUT, _GRAPH_PHASE_TAIL_LIMIT
    → core (facade): _json_response, _json_error, _graph_etag, _get_if_none_match
  _handle_api_task_detail
    → api (direct import): _build_task_detail_payload
    → workitems (direct import): discover_subprojects
    → core (facade): _server_attr, _resolve_effective_docs_dir, _json_response, _json_error
    → core (constants): _API_MERGE_STATUS_PATH, _MERGE_STALE_SECONDS, _MERGE_STATUS_FILENAME

handlers_state.py
  _handle_api_state
    → workitems (direct import): scan_tasks, scan_features, discover_subprojects, _dedup_workitems_by_id, _aggregated_scan
    → signals (direct import): scan_signals, SignalEntry
    → panes (direct import): PaneInfo, list_tmux_panes
    → core (facade): _build_state_snapshot, _apply_subproject_filter, _apply_include_pool
    → core (facade): _server_attr, _resolve_effective_docs_dir, _parse_state_query_params
    → core (facade): _json_response, _json_error

handlers.py (MonitorHandler)
  → handlers_state.py: _handle_api_state
  → handlers_graph.py: _handle_graph_api, _handle_api_task_detail
  → handlers_pane.py: _handle_pane_html, _handle_pane_api
  → handlers.py internal: _handle_static, _handle_api_merge_status
```

### 순환 참조 회피 전략

`handlers_*.py` → `core.py` → `handlers.py` (facade re-export) 경로에서 순환이 발생할 수 있다.

**회피 방식**: 신규 `handlers_*.py`는 `core.py`를 직접 import하지 않는다. 대신:
1. **api.py 직접 참조**: `_build_graph_payload`, `_build_fan_in_map`, `_build_task_detail_payload`, `handle_state` 등은 `from monitor_server import api as _api` (함수 내부 지연 import).
2. **workitems.py 직접 참조**: `scan_tasks`, `scan_features`, `discover_subprojects` 등은 `from monitor_server.workitems import ...` (모듈 레벨 import — workitems→handlers 순환 없음).
3. **signals.py / caches.py 직접 참조**: `scan_signals`, `_GRAPH_CACHE` 등 동일하게 직접 import.
4. **panes.py 직접 참조**: `list_tmux_panes`, `capture_pane` 등.
5. **core.py 경유가 불가피한 심볼** (`_server_attr`, `_resolve_effective_docs_dir`, `_build_state_snapshot`, `_call_dep_analysis_graph_stats`, `render_dashboard` 등): 함수 내부에서 `from monitor_server import core as _core` 지연 import.

이 패턴은 `core-decomposition`에서 이미 검증된 방식과 동일하다 (`_c1_bootstrap_submodules` + try/except 참조).

### Handler 클래스 통합 방침

`handlers.py`에는 현재 `Handler(BaseHTTPRequestHandler)` 클래스가 366 LOC로 존재한다. `MonitorHandler(BaseHTTPRequestHandler)`와 기능이 중복된다.

**결정**: `MonitorHandler`를 `handlers.py`로 이관하되, 기존 `Handler` 클래스는 **그대로 유지**한다. 이유:
- `handlers.py`의 `Handler`는 `api.handle_*` 직접 위임 방식(api.py SSOT), `MonitorHandler`는 `_handle_*` 함수 직접 포함 방식 — 두 구현이 병존한다.
- `monitor-server.py` 엔트리포인트가 현재 어느 핸들러를 사용하는지 C0-1(baseline) 단계에서 확인 후 결정.
- 병합 여부는 C2-1(facade) 커밋에서 재판단 (테스트 그린 후).

## 데이터 흐름

HTTP 요청 → `MonitorHandler.do_GET` → path 분기 → `_handle_*` / api.handle_* → 스캔/캐시 → JSON/HTML 응답

## 설계 결정 (대안이 있는 경우만)

### handlers.py 분할 여부

- **결정**: 이관 후 1,075 LOC로 NF-03 초과 → **분할 실행**. `handlers_state.py` / `handlers_pane.py` / `handlers_graph.py` 3개 신규 파일.
- **대안**: 단일 handlers.py에 모두 수용 (≤ 800 이면 분할 보류).
- **근거**: 실측 결과 이관 합계 709 LOC + 기존 366 LOC = 1,075 LOC > 800. 분할이 필수. spec.md의 "NF-03 위반 가능성" 예고대로 판정.

### 분할 경계 설계

- **결정**: spec.md 제안 경계를 채택:
  - `handlers.py`: `MonitorHandler` 기본 routing + `_handle_static` + `_handle_api_merge_status` (예상 ~675 LOC)
  - `handlers_state.py`: `_handle_api_state` (~130 LOC)
  - `handlers_pane.py`: `_handle_pane_html` + `_handle_pane_api` (~81 LOC)
  - `handlers_graph.py`: `_handle_graph_api` + `_handle_api_task_detail` (~189 LOC)
- **근거**: 의존성 결합도 기준 — state는 단독 복잡도가 높고(ETag, subproject, include_pool), pane/graph는 각각 내부 결합이 강하며, merge_status는 간단하여 handlers.py에 인접.

### 순환 참조 회피

- **결정**: `handlers_*.py` → `core.py` 직접 import 금지. 대신 `api.py`, `workitems.py`, `caches.py`, `signals.py`, `panes.py` 직접 참조 + core 심볼은 함수 내 지연 import.
- **대안**: `core.py`를 직접 import (간단하지만 순환 발생).
- **근거**: `core.py`가 `from .handlers import MonitorHandler`를 facade 재-export 하는 순간 `core → handlers → core` 순환이 성립한다. 지연 import만이 이를 회피한다.

### 커밋 단위

- **결정**: C0-1(baseline), C1-1(pane 이관), C1-2(graph+task_detail 이관), C1-3(state 이관), C1-4(MonitorHandler+static+merge 이관+분할), C2-1(core.py facade 재배선), C3-1(cleanup). 각 커밋 직후 pytest + smoke 통과 확인.
- **대안**: 전체를 한 번에 (롤백 난이도 높음).
- **근거**: `core-decomposition` 설계 원칙(1 커밋 = 1 논리적 변경) 계승. 중간 롤백 시 `git revert <SHA>` 단건으로 가능.

## 선행 조건

- `core-decomposition` feature 완료 상태 (commit `caed787`) — 확인 완료.
- `handlers.py`의 기존 `Handler` 클래스가 `MonitorHandler`와 다른 역할인지 엔트리포인트 확인 필요 (C0-1 단계).
- `_DEFAULT_MAX_PANE_LINES`, `_DEFAULT_REFRESH_SECONDS`, `_PHASE_TAIL_LIMIT` 등 상수가 core.py에 남아있는지 확인 필요.

## 리스크

- **HIGH**: `MonitorHandler`가 `_route_root`에서 `render_dashboard`를 직접 호출하고 내부에 134줄의 복잡한 subproject/filter 로직을 포함 — `handlers_*.py`로 분리 후 `core.py` 지연 import 시 순환 참조 발생 가능성. 반드시 함수 내부 지연 import로 처리.
- **HIGH**: `_handle_graph_api`가 `_GRAPH_CACHE`(caches 모듈)를 직접 참조 — handlers_graph.py에서 `from monitor_server.caches import _GRAPH_CACHE`로 직접 import 시 flat-load 환경에서 실패 가능. try/except + `_c1_bootstrap_submodules` 패턴 재사용 필요.
- **MEDIUM**: `handlers.py`의 기존 `Handler` 클래스와 신규 `MonitorHandler` 클래스가 같은 파일에 공존하면 `monitor-server.py` 엔트리포인트가 어느 것을 사용하는지 혼란 발생. C0-1에서 `monitor-server.py`의 import 경로 확인 필수.
- **MEDIUM**: `_handle_api_state`의 `_build_state_snapshot` 호출은 `core.py` facade를 통해야 하는데, handlers_state.py → core.py → handlers.py 순환. 반드시 지연 import로 처리.
- **MEDIUM**: `MonitorHandler._route_root`(134줄)는 spec 범위 밖(`_render_dashboard` 의존). 이관 시 `render_dashboard` 호출을 유지하면서 core 지연 import 경로를 정확히 구성해야 함.
- **LOW**: `handlers.py`의 `_route_pane_html`, `_route_pane_api`가 현재 `_delegate_core(handler, "_handle_pane_html", ...)` 방식으로 core를 경유 — 이관 후에는 `handlers_pane._handle_pane_html`를 직접 호출로 교체 가능. 하지만 기존 `Handler` 클래스 유지 시 중복이 남는다.
- **LOW**: `_GRAPH_PHASE_TAIL_LIMIT`, `_DEP_ANALYSIS_TIMEOUT`, `_RUNNING_STATUSES`, `_PHASE_TAIL_LIMIT` 등 상수가 core.py에 있고 handlers_*.py에서 필요 — 각 서브모듈에 재정의하거나 직접 값을 하드코딩하거나 handlers.py에 한곳에 모아 서브모듈이 import하는 방식 중 선택.

## QA 체크리스트

- [ ] C0-1 baseline: `python3 -m pytest -q scripts/ --tb=no` 실행 후 `baseline.txt` 저장 — 2 failed, 나머지 passed, exit 0 확인.
- [ ] C1-1 (handlers_pane.py): `_handle_pane_html`/`_handle_pane_api` 이관 후 pytest 그린 (2 failed 유지). `core._handle_pane_html` + `core._handle_pane_api` `hasattr` 확인.
- [ ] C1-2 (handlers_graph.py): `_handle_graph_api`/`_handle_api_task_detail` 이관 후 pytest 그린. smoke: `GET /api/graph` 200, `GET /api/task-detail?task=TSK-00-01` 200.
- [ ] C1-3 (handlers_state.py): `_handle_api_state` 이관 후 pytest 그린. smoke: `GET /api/state` 200 + ETag 헤더 존재.
- [ ] C1-4 (handlers.py): `MonitorHandler` + `_handle_static` + `_handle_api_merge_status` 이관 후 pytest 그린. smoke: `GET /` 200, `GET /api/merge-status` 200, `GET /pane/{id}` 200.
- [ ] C2-1 (core.py facade): `from .handlers import MonitorHandler` + 서브모듈 재-export 추가, 원본 블록 삭제. `assert hasattr(core, 'MonitorHandler')` 통과.
- [ ] C3-1 (cleanup): 중복 상수/helper 정리. `wc -l scripts/monitor_server/handlers*.py` 모두 ≤ 800.
- [ ] 전체 완료 후 core.py LOC ≤ 6,300 (≥ 574 감소 확인: 709 이관 + 상수·helper 약 50 = ~760 예상 감소).
- [ ] 전체 완료 후 `python3 -m pytest -q scripts/ --tb=no` 결과와 baseline.txt Δ = 0.
- [ ] smoke 5개 경로 전체 200 확인: `GET /`, `GET /api/state` (ETag 포함), `GET /pane/{id}`, `GET /api/graph`, `GET /api/merge-status`.
- [ ] facade 무결성: `assert hasattr(core, 'MonitorHandler')`, `assert hasattr(core, '_handle_api_state')`, `assert hasattr(core, '_handle_graph_api')`.
- [ ] `handlers.py` ≤ 800 LOC, `handlers_state.py` ≤ 800 LOC, `handlers_pane.py` ≤ 800 LOC, `handlers_graph.py` ≤ 800 LOC.
- [ ] 새로운 순환 import 없음: `python3 -c "import monitor_server.handlers; import monitor_server.handlers_state; import monitor_server.handlers_pane; import monitor_server.handlers_graph"` 에러 없음.
