# TSK-03-01: dep-analysis.py --graph-stats 확장 (critical_path, fan_out, bottleneck_ids) - 설계

## 요구사항 확인
- 기존 `scripts/dep-analysis.py --graph-stats` JSON 출력에 3개 필드 추가: 태스크별 `fan_out`, 루트→리프 longest-path인 `critical_path` (`{nodes, edges}`), 그리고 `fan_in>=3 또는 fan_out>=3`인 `bottleneck_ids` 목록.
- 알고리즘은 topological-sort 기반 longest-path DP로 구현하며 동점 시 task_id alphabetical 작은 쪽 우선(결정론적). 사이클 감지 시 명시적 에러(기존 동작 유지).
- 기존 필드(`max_chain_depth`, `fan_in_top`, `fan_in_ge_3_count`, `diamond_patterns`, `diamond_count`, `review_candidates`, `total`)와 기본 모드(topological level sort) 동작은 그대로 유지 — backward compatible.

## 타겟 앱
- **경로**: N/A (단일 플러그인 프로젝트, 스크립트 디렉토리 `scripts/`)
- **근거**: 본 Task는 plugin 자체의 Python stdlib 스크립트 확장이다. 모노레포 workspaces 없음.

## 구현 방향
- `compute_graph_stats()` 내부를 확장해 `fan_out`, `critical_path`, `bottleneck_ids` 3개 필드를 반환 JSON에 추가한다.
- **fan_out**: 기존 fan_in 계산의 쌍대. `dep_map[t]`를 순회하며 각 dep의 역방향(= `t`의 자식)이 아니라 `t`가 몇 개의 선행(depends) 노드를 가리키는지 아닌, **"t로부터 출발하는 간선 수"**, 즉 **t를 depends로 갖는 자식의 수 = fan_out[t]**로 정의한다. (주의: 본 스크립트에서 `dep_map[t]`는 t의 "의존 대상들"이므로 정방향 그래프 A→B는 A가 B에 의존한다는 의미 → 소스가 A, 타깃이 B. fan_out(A)는 A가 의존하는 대상 수.) 그래프 방향 규약을 아래 "데이터 흐름" 섹션에서 명시한다.
- **critical_path (longest-path DP)**: Kahn 방식으로 topological 순서를 만든 뒤, 각 노드 v에 대해 `dist[v] = 1 + max(dist[p] for p in predecessors(v))` DP. 동점 처리를 위해 `parent[v]`에는 `(dist, parent_id)` 비교에서 더 큰 dist를, 동률이면 **parent_id alphabetical 작은 쪽**을 저장한다. 전체 노드 중 `dist` 최대값을 가진 리프를 선택할 때도 동률이면 id alphabetical 작은 것 우선. 선택된 리프에서 `parent[]`로 역추적해 경로를 복원한 뒤 reverse하여 `nodes` 배열을 만들고, 인접 쌍으로 `edges`(`{"source","target"}`) 배열을 만든다.
- **bottleneck_ids**: 기존 fan_in 계산 결과와 신규 fan_out 계산 결과를 합집합 필터. `fan_in[t] >= 3 or fan_out[t] >= 3`이면 포함. 결정론을 위해 task_id alphabetical 정렬.
- **사이클 처리**: topological sort에서 모든 노드를 처리하지 못하면 기존 동작(`default` 모드)과 동일 규약으로 **명시적 에러**를 stderr에 출력하고 exit 1. 기존 `--graph-stats`는 사이클을 그대로 통과시켰지만, 본 Task 요구사항에서 "사이클 감지 시 명시적 에러(기존 동작 유지)"는 longest-path DP 입장에서의 기존 동작을 의미한다 — DP는 사이클에서 무한 루프하므로 반드시 사이클 발견 시 에러로 종료해야 한다. (본 변경은 `--graph-stats` 모드에 한함, 기본 topological level 모드의 기존 `circular` 배열 동작은 건드리지 않는다.)
- **외부 의존 Task**: `dep_map[t]`의 원소가 `task_ids`에 없으면(외부 의존) 기존 로직처럼 건너뛴다. fan_out 카운트도 본 Task 그래프 내 간선만 센다.

## 파일 계획

**경로 기준:** 모든 파일 경로는 프로젝트 루트 기준.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/dep-analysis.py` | `compute_graph_stats()` 확장(fan_out/critical_path/bottleneck_ids 계산) + 모듈 docstring의 `--graph-stats` 출력 예시 갱신 | 수정 |
| `scripts/test_dep_analysis_graph_stats.py` | pytest 모듈 — `test_dep_analysis_critical_path_linear`, `test_dep_analysis_critical_path_diamond`, `test_dep_analysis_fan_out`, `test_dep_analysis_bottleneck_ids` 포함. stdlib만 사용, `subprocess`로 `dep-analysis.py --graph-stats`를 호출하고 JSON을 검증 + `compute_graph_stats()`를 직접 import(동적 로드, `importlib.util`)하여 순수 함수 단위 테스트 | 신규 |

## 진입점 (Entry Points)
N/A (backend CLI 확장, UI 없음)

## 주요 구조
- `compute_graph_stats(items, fan_in_threshold=3, depends_threshold=4, top_n=5) -> dict`: 기존 시그니처 유지. 본체 내부에 `_compute_fan_out(dep_map, task_ids)`, `_compute_critical_path(dep_map, task_ids)` 헬퍼를 모듈 레벨 함수로 추출 후 호출하여 테스트 용이성을 확보한다.
- `_compute_fan_out(dep_map, task_ids) -> dict[str, int]`: `dep_map`을 순회하며 각 depends 타깃의 카운터를 증가. 반환은 task_id→정수.
- `_compute_critical_path(dep_map, task_ids) -> dict`: 정방향 그래프(A가 B에 depends → edge A→B가 아니라 **B→A**의 실행 순서 에지)를 만든 뒤(즉 dep가 먼저 실행되어야 함), Kahn 위상정렬 + longest-path DP로 `{"nodes": [...], "edges": [{"source","target"}, ...]}`을 반환. 동률은 task_id alphabetical 작은 쪽 우선. 사이클 발견 시 `ValueError("cycle detected in dependency graph")` raise.
- `main()`: 기존 흐름 유지. `--graph-stats` 분기에서 `compute_graph_stats()` 호출 시 `ValueError`를 catch하여 `print("ERROR: cycle detected in dependency graph", file=sys.stderr); sys.exit(1)`로 변환.
- `test_dep_analysis_graph_stats.py` 테스트들: 순수 함수 호출 + CLI 서브프로세스 호출 두 루트로 검증. AC-10~AC-14 관련 acceptance와 일치.

## 데이터 흐름
입력 JSON array (각 item `{tsk_id, depends, status}`) → `compute_graph_stats`에서 `dep_map`(의존 방향: "t는 [d1, d2…]에 의존")과 `task_ids` 구성 → fan_in/fan_out/diamond/max_chain_depth/review_candidates/critical_path 각각 계산 → merge하여 JSON dict 반환 → `main()`이 `json.dumps(indent=2)`로 stdout 출력.

**그래프 방향 규약**: "A → B" 화살표는 **A가 먼저 실행되어 B가 뒤를 잇는다**는 실행 방향(= B depends on A)이다. `critical_path.edges[i] = {source: nodes[i], target: nodes[i+1]}`이며 source→target 순서가 실행 순서(= depends 역방향)다. 즉 TRD 예시의 `{source: "TSK-00-01", target: "TSK-01-02"}`는 TSK-01-02가 TSK-00-01에 depends한다는 의미.

## 설계 결정 (대안이 있는 경우만)

### 결정 1 — longest-path 알고리즘: Kahn 기반 topological DP vs 메모이즈 DFS
- **결정**: Kahn(진입차수 BFS) + DP
- **대안**: 기존 `max_chain_depth` 계산에 쓰인 메모이즈 DFS를 재사용하여 거리/부모까지 함께 기록
- **근거**: Kahn은 사이클 감지가 자연스럽고(큐가 소진되기 전에 처리된 노드 수 < 전체 → 사이클), 결정론적 동률 처리를 진입차수 0 노드 추출 시 alphabetical sort로 명시할 수 있다. DFS는 재귀 스택 깊이 이슈(큰 WBS 1000+ Task 가정 시)와 결정론 처리가 까다롭다.

### 결정 2 — fan_out의 출력 형태: 전체 dict vs top-N 리스트
- **결정**: 전체 dict `{task_id: count}` 반환 (fan_in_top과는 다른 구조)
- **대안**: fan_in_top과 대칭으로 `fan_out_top` top-5만
- **근거**: TRD §3.9.2 예시 응답에서 노드별 `fan_out` 수치가 모든 노드에 담겨 있다(`nodes[].fan_out = 4`). monitor-server.py가 `/api/graph`에서 노드별 배지를 판정하려면 **전체 매핑**이 필요하다. 기존 `fan_in_top`은 "상위 병목 요약"용이고 신규 `fan_out`은 "노드별 병목 판정"용으로 목적이 다르다. 스크립트는 `fan_out: {tsk_id: count}` dict로 반환하여 호출자가 각 노드 조회.

### 결정 3 — critical_path 소스/리프 기준
- **결정**: 루트(진입차수 0, 즉 depends 없음)에서 리프까지 longest path. 경로 끝의 리프는 fan_out==0인 노드(자신을 depend하는 노드가 없음) 뿐 아니라 **최장 거리에 도달한 어떤 노드든** 허용하되, 동률이면 alphabetical.
- **대안**: 리프를 엄격히 fan_out==0으로 제한
- **근거**: 외부 의존 Task 존재 시 리프가 없을 수 있고(모두 상위 Task로 연결), DP의 최장 거리 노드가 리프 역할을 한다. TRD §3.9.3 "루트(fan_in==0)부터 리프까지의 longest path" 정의를 완화 해석(`dist[] argmax` = longest path의 끝).

## 선행 조건
- Python 3 stdlib만 사용 (`collections.defaultdict`, `json`, `importlib.util` 테스트 시). 없음 그 외.

## 리스크
- **MEDIUM**: 기존 `--graph-stats` 소비자(monitor-server.py `/api/graph`)가 기대치 못한 신규 필드로 파싱 에러를 낼 가능성. 완화: 신규 필드는 **추가만**(기존 필드명/타입 불변), JSON은 unknown key에 관용적이므로 regression 위험 낮음. 그래도 `test_platform_smoke.py` 기존 테스트를 한 번 돌려 회귀 없음을 확인한다.
- **MEDIUM**: 빈 그래프(태스크 0개), 단일 노드, 완전 고립 노드(엣지 없음)의 엣지 케이스. critical_path가 빈 배열일 때 반환 형식을 `{"nodes": [], "edges": []}`로 고정해 호출자 NPE 방지.
- **LOW**: 동률 결정론 보장 — 여러 테스트 노드가 alphabetical 순으로 같은 distance를 가질 때 parent 업데이트 순서가 결과를 바꾸지 않는지 주의. Kahn 큐에서 pop 시 정렬 리스트 + dist 업데이트 시 `(new_dist, new_parent) > (cur_dist, cur_parent)` 비교에서 parent는 alphabetical 작은 쪽 우선하도록 tuple 비교 방향을 뒤집는다(`parent` 비교 시 `<`).
- **LOW**: 사이클 시 `default` 모드는 circular 배열에 기록하고 종료 코드 0인 반면, `--graph-stats`는 exit 1. 비대칭 동작이지만 본 Task가 명시적으로 요구("사이클 감지 시 명시적 에러").

## QA 체크리스트
dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

- [ ] (정상 - 선형) TSK-A→B→C→D (B depends A, C depends B, D depends C) → `critical_path.nodes == ["TSK-A","TSK-B","TSK-C","TSK-D"]`, `edges` 길이 3 — `test_dep_analysis_critical_path_linear`
- [ ] (정상 - 다이아몬드) Apex X, 중간 Y1/Y2, merge Z (X→Y1→Z, X→Y2→Z)에 Y1이 추가 Y0→Y1로 1단계 더 길 때 longest path는 X→Y0→Y1→Z → `nodes == ["X","Y0","Y1","Z"]`; 동률이면 alphabetical 작은 쪽 — `test_dep_analysis_critical_path_diamond`
- [ ] (정상 - fan_out) TSK-A가 B/C/D에 선행(= B/C/D가 A에 depends)일 때 `fan_out["TSK-A"] == 3`, `fan_out["TSK-B/C/D"] == 0` — `test_dep_analysis_fan_out`
- [ ] (정상 - bottleneck) fan_in==3인 노드, fan_out==3인 노드가 각각 존재 → 두 id 모두 `bottleneck_ids`에 포함; fan_in==2, fan_out==2는 포함되지 않음; 반환은 alphabetical sort — `test_dep_analysis_bottleneck_ids`
- [ ] (엣지 - 빈 그래프) 입력 `[]` → `critical_path == {"nodes": [], "edges": []}`, `fan_out == {}`, `bottleneck_ids == []`
- [ ] (엣지 - 단일 노드) 1개 태스크 → `critical_path.nodes == [해당 id]`, `edges == []`
- [ ] (에러 - 사이클) A depends B, B depends A → stderr에 "cycle detected" 메시지 + exit code 1
- [ ] (통합 - 기존 필드 유지) `max_chain_depth`, `fan_in_top`, `fan_in_ge_3_count`, `diamond_patterns`, `diamond_count`, `review_candidates`, `total` 모두 기존과 동일 계산/타입
- [ ] (통합 - 회귀) `pytest -q scripts/` 전체 통과 (기존 `test_monitor_*.py`/`test_platform_smoke.py` 등 regression 없음)
- [ ] (결정론) 동일 입력을 두 번 실행했을 때 `critical_path.nodes`와 `bottleneck_ids` 순서가 정확히 동일
