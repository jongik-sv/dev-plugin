# TSK-03-02: /api/graph 엔드포인트 - 설계

## 요구사항 확인

- `GET /api/graph?subproject=<sp|all>` 핸들러를 `monitor-server.py`에 추가한다. 매 호출마다 `scan_tasks(effective_docs_dir)`로 fresh 스캔하고, `dep-analysis.py`의 `compute_graph_stats`을 호출하여 `nodes[]`, `edges[]`, `stats`, `critical_path`를 조립해 반환한다.
- 노드 상태는 `_derive_node_status(task, signals)` 헬퍼로 격리하며 `done`/`running`/`pending`/`failed`/`bypassed` 5종을 도출한다. 상태 판정 우선순위: `bypassed` → `failed` → `done` → `running` → `pending`.
- `dep-analysis.py`는 `fan_out` per-task, `critical_path`(longest-path DP), `bottleneck_ids` 세 항목을 `--graph-stats` 모드에 추가한다. `_handle_graph_api`는 두 스크립트 간 인터페이스를 JSON pipe(subprocess stdin)로 구성한다.

## 타겟 앱

- **경로**: N/A (단일 앱 — 모든 코드가 `scripts/` 루트에 위치)
- **근거**: 이 프로젝트는 모노레포 구조 없음. `scripts/monitor-server.py`와 `scripts/dep-analysis.py`가 수정 대상.

## 구현 방향

1. `dep-analysis.py`의 `compute_graph_stats`에 `fan_out`, `critical_path`, `bottleneck_ids`를 추가한다 (TRD §3.9.3).
2. `monitor-server.py`에 `_derive_node_status(task: WorkItem, signals: List[SignalEntry]) -> str` pure 헬퍼를 추가한다.
3. `monitor-server.py`에 `_handle_graph_api(handler, scan_tasks_fn, scan_signals_fn)` 핸들러를 추가한다. `dep-analysis.py`는 **subprocess**로 호출하며 `tasks` 목록을 JSON stdin으로 파이핑하고 stdout에서 graph-stats JSON을 읽는다(기존 `monitor-server.py` 관행 확인: subprocess 호출 패턴이 없으므로 이 Task에서 처음 도입).
4. `MonitorHandler.do_GET`에 `/api/graph` 경로를 추가하고 `_is_api_graph_path` 함수로 라우팅한다.
5. `subproject` 쿼리 파라미터에 따라 `effective_docs_dir`을 결정한다(`all` → `server.docs_dir`, `<sp>` → `server.docs_dir/<sp>`).

## 파일 계획

**경로 기준:** 모든 파일 경로는 프로젝트 루트 기준으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `_derive_node_status`, `_handle_graph_api`, `_is_api_graph_path` 추가; `MonitorHandler.do_GET` 라우팅 확장 | 수정 |
| `scripts/dep-analysis.py` | `compute_graph_stats`에 `fan_out`, `critical_path`, `bottleneck_ids` 추가 | 수정 |
| `scripts/test_monitor_graph_api.py` | `/api/graph` 응답 구조·필터·상태 도출 테스트 (`test_api_graph_returns_nodes_and_edges`, `test_api_graph_derives_status_done_running_pending_failed_bypassed`, `test_api_graph_respects_subproject_filter`) | 신규 |
| `scripts/test_dep_analysis_critical_path.py` | `--graph-stats`의 `critical_path`, `fan_out`, `bottleneck_ids` 테스트 | 신규 |

## 진입점 (Entry Points)

N/A — domain=backend. UI 없음.

## 주요 구조

- **`_derive_node_status(task: WorkItem, signals: List[SignalEntry]) -> str`**  
  pure 함수. 우선순위(bypassed > failed > done > running > pending)로 상태 문자열 반환. `signals`에서 해당 task.id에 대응하는 `.running`/`.failed` 파일 존재 여부를 체크. `state.json.last.event == "fail"` 판정은 `task.last_event` 필드로 확인.

- **`_is_api_graph_path(path: str) -> bool`**  
  `urlsplit(path).path == "/api/graph"`이면 True. 기존 `_is_api_state_path`와 동일 패턴.

- **`_handle_graph_api(handler, *, scan_tasks_fn, scan_signals_fn) -> None`**  
  1. `handler.server.docs_dir` + `subproject` 쿼리 파라미터로 `effective_docs_dir` 결정  
  2. `scan_tasks_fn(effective_docs_dir)` 호출 → `List[WorkItem]`  
  3. `scan_signals_fn()` 호출 → `List[SignalEntry]`  
  4. tasks를 `[{"tsk_id": t.id, "depends": ",".join(t.depends), "status": t.status or "[ ]", "bypassed": t.bypassed, "title": t.title, "wp_id": t.wp_id}]` 형태로 직렬화  
  5. `dep-analysis.py --graph-stats`를 subprocess stdin으로 호출하여 graph_stats JSON 수신  
  6. `_build_graph_payload(tasks, signals, graph_stats, effective_docs_dir, subproject)` 호출  
  7. `_json_response(handler, 200, payload)`

- **`_build_graph_payload(tasks, signals, graph_stats, docs_dir_str, subproject) -> dict`**  
  nodes, edges, stats, critical_path 조립. 각 노드의 fan_in/fan_out은 graph_stats에서, is_critical/is_bottleneck은 graph_stats의 `bottleneck_ids`/`critical_path.nodes`로 판정.

- **`compute_graph_stats` 확장 (dep-analysis.py)**  
  - `fan_out`: children 맵에서 각 노드의 직접 의존 역방향 수 (`fan_in`과 대칭, 기존 `children` 딕셔너리 재활용)  
  - `critical_path`: 위상 정렬 후 DP로 longest path 계산 → `{"nodes": [...], "edges": [...]}`  
  - `bottleneck_ids`: `fan_in[t] >= 3 or fan_out[t] >= 3`인 task ID 목록

## 데이터 흐름

`GET /api/graph?subproject=X` → `_handle_graph_api` → `scan_tasks(effective_docs_dir)` + `scan_signals()` → `dep-analysis.py --graph-stats`(subprocess stdin JSON) → `_build_graph_payload` → JSON 응답 200

## 설계 결정 (대안이 있는 경우만)

- **결정**: `dep-analysis.py`를 subprocess로 호출 (JSON stdin/stdout 파이핑)
- **대안**: `dep-analysis.py`를 Python 모듈로 import하여 직접 `compute_graph_stats()` 호출
- **근거**: 기존 `monitor-server.py`의 단일-파일 stdlib 원칙을 유지하고, `dep-analysis.py` 코드 변경 시 `monitor-server.py`를 재로드할 필요가 없으며, 테스트에서 `dep-analysis.py` 응답을 mock으로 대체하기 용이하다. 단, subprocess 오버헤드(~10-20ms)가 있어 <50ms 목표 달성에 영향을 줄 수 있으므로, `sys.executable`로 현재 파이썬 인터프리터를 명시하고 timeout을 3초로 설정한다.

- **결정**: 상태 판정 우선순위 `bypassed > failed > done > running > pending`
- **대안**: TRD 열거 순서(done→running→pending→failed→bypassed) 그대로
- **근거**: `bypassed`와 `failed`는 이미 최종 상태이므로 signal 존재보다 우선해야 한다. `failed`는 running 신호가 남아있어도 실패 상태가 덮어야 맞다.

## 선행 조건

- `TSK-03-01`: `_handle_graph_api`가 필요로 하는 `scan_tasks`, `scan_signals` 등 helper 계약 확립 (WP-03 첫 Task)
- `TSK-00-03`: `discover_subprojects` 헬퍼. `effective_docs_dir` 결정 시 `?subproject=<sp>` 경로를 `docs_dir/<sp>`로 변환할 때 사용. (직접 경로 조합으로도 가능하나 일관성을 위해 참조)
- Python 3 stdlib `subprocess`, `json`, `sys` — 추가 pip 의존성 없음

## 리스크

- **HIGH**: `dep-analysis.py --graph-stats` 응답에 `fan_out`, `critical_path`, `bottleneck_ids`가 없는 경우 (아직 확장 전). `_build_graph_payload`는 `graph_stats.get("fan_out_map", {})` 방어 코드 필수. 테스트에서는 mock subprocess로 검증.
- **HIGH**: `dep-analysis.py` subprocess 실패(timeout, OSError) 시 500 반환. `_handle_graph_api`는 try/except로 감싸고 `_json_error(handler, 500, ...)` 처리.
- **MEDIUM**: `effective_docs_dir`이 존재하지 않는 subproject 이름이면 `scan_tasks` → `[]` 반환. 이 경우 nodes=[], edges=[], stats 모두 0인 빈 응답을 200으로 반환 (에러가 아닌 empty state).
- **MEDIUM**: `WorkItem.depends`가 `List[str]`이나 wbs.md에서 파싱 실패 시 빈 리스트. `dep-analysis.py` 입력의 `depends` 필드는 쉼표 구분 문자열 또는 `"-"`로 변환한다.
- **LOW**: `<50ms` 성능 목표. 수백 Task의 경우 `scan_tasks` + subprocess 합산이 50ms를 초과할 수 있다. 현재 스펙에서 in-memory 캐시를 금지하므로 허용 범위로 간주 (WBS 주석: "2초 폴링이므로 지연 허용").

## QA 체크리스트

- [ ] `test_api_graph_returns_nodes_and_edges`: `GET /api/graph` 응답에 `nodes`, `edges`, `stats`, `critical_path`, `subproject`, `docs_dir`, `generated_at` 필드가 모두 존재하고, nodes 수가 wbs.md Task 수와 일치한다.
- [ ] `test_api_graph_derives_status_done_running_pending_failed_bypassed`: 5종 상태를 각각 트리거하는 WorkItem을 mock하고 `_derive_node_status`가 올바른 문자열을 반환한다.
  - `state.json.status == "[xx]"` → `"done"`
  - `.running` 신호 존재 → `"running"`
  - `status in {"[dd]","[im]","[ts]"}` (신호 없음) → `"running"`
  - `.failed` 신호 존재 → `"failed"`
  - `state.json.last.event == "fail"` → `"failed"`
  - `state.json.bypassed == true` → `"bypassed"`
  - 나머지 → `"pending"`
- [ ] `test_api_graph_respects_subproject_filter`: `?subproject=p1` 파라미터 시 `docs/p1/`의 Task만 nodes에 포함되고, `docs/` 루트 Task는 포함되지 않는다.
- [ ] `_build_graph_payload`가 조립한 `stats.total`이 `len(nodes)`와 일치한다.
- [ ] `stats.done + stats.running + stats.pending + stats.failed + stats.bypassed == stats.total` 항등식 성립.
- [ ] `?subproject=all` (기본값) 시 docs_dir 루트의 모든 Task가 반환된다.
- [ ] `dep-analysis.py` subprocess timeout/에러 시 500 JSON 응답 (`{"error": ..., "code": 500}`)이 반환된다.
- [ ] `dep-analysis.py compute_graph_stats`에서 `fan_out[t]`가 `fan_in[t]`의 반대 방향으로 올바르게 계산된다.
- [ ] `critical_path.nodes`가 longest path를 따르며, 동점 시 task_id alphabetical 작은 것이 우선 선택된다.
- [ ] `bottleneck_ids`에 `fan_in >= 3` 또는 `fan_out >= 3`인 Task만 포함된다.
- [ ] `AC-16`: state.json 변경 후 다음 `/api/graph` 호출에서 변경된 상태가 즉시 반영된다 (in-memory 캐시 없음 검증 — 두 연속 호출 사이에 mock state.json을 수정하고 두 번째 응답이 달라짐을 확인).
