# Feature: core-decomposition

## 요구사항

`scripts/monitor_server/core.py`는 현재 **7,940줄 / 177 top-level defs**의 모놀리스이다. monitor-v5 FR-07(S1~S6)이 entry를 얇게 만들었지만 로직 전체를 `core.py`로 이사시켰을 뿐이다. WBS `NF-03 ≤ 800줄` 제약을 10배 위반 중이며, 여러 WP가 동시에 수정할 때 **충돌 자석**으로 작동한다 (memory `project_monitor_server_inline_assets.md`, `feedback_wp_worktree_merge_contract_gap.md`).

세 단계로 점진 해결:

### Phase 0 — 중복·dead 코드 정리 (분할 전)
분할하기 전에 먼저 줄여서 이관 부담을 낮춘다.

- **중복 함수 8개 제거 (~188 LOC)** — `api.py`로 이관되었지만 `core.py` 사본이 남은 것:
  - `_build_task_detail_payload` (L6350–6394, 45줄)
  - `_build_graph_payload` (L5791–5898, 108줄)
  - `_derive_node_status` (L5754–5790, 37줄)
  - `_serialize_phase_history_tail_for_graph` (L5704–5737, 34줄)
  - `_signal_set` (L2625–2637, 13줄)
  - `_load_state_json` (L6338–6349, 12줄)
  - `_build_fan_in_map` (L5986–5999, 14줄)
  - `_now_iso_z` (L6999–7011, 13줄)
- **`renderers/_util.py` 재배선** — 위 중 4개 (`_now_iso_z`, `_signal_set`, `_serialize_phase_history_tail_for_graph`, `_derive_node_status`)가 `_util.py`에서 core 경유로 재노출 중. `_util.py`의 import를 `from monitor_server import api as _mod`로 교체.
- **TSK 마커 정리 (41건, ~50 LOC)** — 완료된 마이그레이션 참조 주석 (`# TSK-01-01`, `# TSK-02-05` 등). 코드 흐름과 무관해진 것만 제거, 현재 동작을 설명하는 주석은 유지.
- **수용 기준**: 전체 `pytest -q scripts/` 그린 유지, core.py LOC 최소 200줄 감소.

### Phase 1 — 주제별 모듈 1차 분할
facade 패턴으로 backward-compat 보장하며 `core.py`를 5개 모듈로 나눈다.

| 신규 모듈 | 예상 LOC | 이전 대상 심볼 |
|-----------|---------|---------------|
| `monitor_server/caches.py` | ~170 | `_TTLCache`, `_ensure_etag_cache`, `_SIGNALS_CACHE`, `_GRAPH_CACHE`, TTL 상수 |
| `monitor_server/signals.py` | ~210 | `SignalEntry`, `_signal_entry`, `_walk_signal_entries`, `scan_signals*`, `_wp_busy_set` |
| `monitor_server/panes.py` | ~130 | `PaneInfo`, `list_tmux_panes`, `capture_pane` |
| `monitor_server/workitems.py` | ~340 | `PhaseEntry`, `WorkItem`, `_read_state_json`, phase_history 헬퍼, WBS/feat title 로더, workitem 팩토리 |
| `core.py` (facade) | ~초기 2,500줄, 최종 ~50줄 | 남은 HTTP handler + 재export |

- **facade 원칙**: `core.py`는 각 신규 모듈에서 `from .{mod} import *`로 재노출 → 기존 `import monitor_server.core as core` 코드 무수정 통과.
- **모듈 이관 단위 = 커밋 1건**: 한 모듈씩 옮기고 `pytest -q scripts/` 통과 후 커밋. 4~5커밋 예상.
- **수용 기준**: 각 신규 모듈 ≤ 800줄 (NF-03), facade 통과 테스트 그린, `monitor-server.py --port XXXX` 실 기동 smoke OK.

### Phase 2 — HTTP handler 2차 분할 (별도 후속)
Phase 1 완료 후 `core.py`에 남은 HTTP handler (~7,000줄)를 재평가. 필요 시 `monitor_server/http/` 서브패키지로:
- `http/routes_dashboard.py` — `/` 루트 + SSR 조립
- `http/routes_pane.py` — `/pane/{id}`, `/api/pane/{id}`
- `http/routes_graph.py` — dep-graph SSR + `/api/graph*`
- `http/routes_static.py` — `/static/*` (handlers.py와 통합 검토)
- `http/server.py` — `run_server`, threading, argparse

**본 feature 범위는 Phase 0 + Phase 1까지.** Phase 2는 별도 feature(`core-http-split`)로 분리하여 Phase 1 결과를 보고 결정한다.

## 배경 / 맥락

- monitor-v5(FR-07)가 **파일 이동 ≠ 분해**를 보여준 사례. 빌드 게이트가 LOC 제약(NF-03 ≤ 800줄)을 각 모듈별로 강제하지 못해 `core.py`가 통과해버림.
- 현재 진행 중인 monitor-v5 WP들이 여전히 `core.py`를 수정 중(git status `M scripts/monitor_server/core.py`)이라, **본 feature는 monitor-v5 WP-05까지 완료된 후 main에서 단독 실행한다**.
- 테스트 대부분이 `import monitor_server.core as core` 또는 lazy-load 경유로 core의 심볼에 의존. facade 유지가 필수.

## 도메인

backend

## 진입점 (Entry Points)

N/A (내부 리팩토링 — 사용자 UI 변경 없음)

## 비고

- **시작 조건**: main 브랜치가 monitor-v5 전체 머지 완료 상태여야 함. 미완료 시 이 feature를 시작하지 않는다.
- **병렬 금지**: Phase 0, 1 모두 `core.py` 단독 수정을 전제. 다른 WP/feature와 동시 진행 금지 (lock 역할).
- **rerere 활성 권장**: `git config --global rerere.enabled true` — 커밋 단위가 작아도 conflict 누적을 줄인다.
- **마이그레이션 안전장치**:
  1. Phase 0 시작 전 전체 `pytest -q scripts/` 그린 baseline 기록 → `docs/features/core-decomposition/baseline-test-report.txt` 저장.
  2. 각 커밋마다 동일 테스트 재실행, diff 0 확인.
  3. `scripts/monitor-server.py --port 7321 --docs docs/monitor-v5` smoke 기동 후 `/`, `/api/state`, `/pane/{id}` 200 OK 확인.
- **스코프 밖** (본 feature에서 다루지 않음):
  - HTML/CSS/JS 리팩토링 (이미 static/으로 분리됨)
  - `api.py`, `handlers.py`, `renderers/*` 내부 정리 — 필요 시 각각 별도 feature
  - Phase 2 (HTTP handler 서브분할)
