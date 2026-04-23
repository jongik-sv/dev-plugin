# TSK-00-02: `/api/graph` payload v4 필드 확장 - 설계

## 요구사항 확인
- `/api/graph` 응답의 `nodes[*]` 에 5개 신규 필드(`phase_history_tail`, `last_event`, `last_event_at`, `elapsed_seconds`, `is_running_signal`)를 추가한다. 값이 없으면 `null`/빈 배열.
- 기존 필드(`id`, `label`, `status`, `is_critical`, `is_bottleneck`, `fan_in`, `fan_out`, `bypassed`, `wp_id`, `depends`)와 `running_ids` 로직은 불변 — 계약 전용(contract-only) 확장. `.running` 시그널 존재 여부만 노드 수준에 노출한다.
- 기존 `scripts/test_monitor_graph_api.py` 는 회귀 없이 통과해야 하며, 새 테스트 3종(필드 존재, 시그널 토글, tail limit 3) 추가.

## 타겟 앱
- **경로**: N/A (단일 스크립트 프로젝트 — `scripts/monitor-server.py` 모놀리스)
- **근거**: dev-plugin 리포 루트에 `package.json`/`pnpm-workspace.yaml` 없음. 서버 로직은 `scripts/monitor-server.py` 한 파일에 집중.

## 구현 방향
- `_build_graph_payload(tasks, signals, graph_stats, ...)` 내부에서 노드 dict 를 조립할 때, 호출 직전에 `_signal_set(signals, "running")` 으로 running-id set 을 한 번 계산해 클로저로 재사용한다 (전체 signals 재순회 금지).
- 각 `task: WorkItem` 에 대해 dataclass 필드(`task.last_event`, `task.last_event_at`, `task.elapsed_seconds`, `task.phase_history_tail`) 를 그대로 읽어 페이로드 dict 에 투영한다 — state.json 재파싱 없음.
- `phase_history_tail` 은 서버 내부 캐시(최대 10개)에서 `[-3:]` 슬라이스 + `PhaseEntry` → 스펙 dict(`{event, from, to, at, elapsed_seconds}`) 변환을 수행하는 순수 함수 `_serialize_phase_history_tail_for_graph(entries, limit=3)` 로 분리한다. `from_status`/`to_status` → `from`/`to` 키 복원, `elapsed_seconds` 가 `None` 이면 `null` 유지.
- `is_running_signal = task.id in running_ids_set` (단순 set membership, O(1)).
- `last_event_at`, `elapsed_seconds` 는 WorkItem 원본이 `None` 이면 JSON 에서 `null` 로 직렬화 (json.dumps 기본 동작 — 추가 코드 불필요).

## 파일 계획

**경로 기준:** 프로젝트 루트 기준.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `_build_graph_payload` 에 5개 신규 필드 투영 로직 추가, 헬퍼 `_serialize_phase_history_tail_for_graph` 신규 추가 (파일 상단 `_PHASE_TAIL_LIMIT` 근처 또는 `/api/graph` 섹션 상단 `_GRAPH_PHASE_TAIL_LIMIT = 3` 상수와 함께) | 수정 |
| `scripts/test_monitor_graph_api.py` | 3종 신규 pytest 추가: `test_api_graph_payload_v4_fields_present`, `test_api_graph_is_running_signal_reflects_signal_file`, `test_api_graph_phase_history_tail_limit_3` | 수정 |

> 비-UI Task (`domain=backend`) — 라우터/메뉴 파일 불필요.

## 진입점 (Entry Points)
- N/A (backend 전용, UI 없음)

## 주요 구조
- **`_serialize_phase_history_tail_for_graph(entries: List[PhaseEntry], limit: int = 3) -> List[dict]`** (신규): `entries[-limit:]` 을 스펙 dict 리스트로 변환. `PhaseEntry.from_status` → `"from"`, `to_status` → `"to"`, 기타(`event`, `at`, `elapsed_seconds`)는 이름 그대로. 입력이 `None`/빈 리스트면 `[]` 반환. 순수 함수, 부작용 없음.
- **`_build_graph_payload`** (수정): 루프 진입 전 `running_ids_set = _signal_set(signals, "running")` 계산 (Set[str]). 노드 dict 조립 시 아래 5개 key/value append:
  - `"phase_history_tail": _serialize_phase_history_tail_for_graph(task.phase_history_tail)`
  - `"last_event": task.last_event`
  - `"last_event_at": task.last_event_at`
  - `"elapsed_seconds": task.elapsed_seconds`
  - `"is_running_signal": task.id in running_ids_set`
- **상수 `_GRAPH_PHASE_TAIL_LIMIT = 3`** (신규): `/api/graph` 섹션 상단(`_API_GRAPH_PATH` 근처)에 배치. 서버 내부 캐시 `_PHASE_TAIL_LIMIT=10` 과 구분 — 그래프 응답 전용 상한.

## 데이터 흐름
`scan_tasks(effective_docs_dir)` → `WorkItem.phase_history_tail`(≤10) + `.last_event*` + `.elapsed_seconds` 채워짐 → `scan_signals()` → `_signal_set(signals, "running")` = `Set[str]` → `_build_graph_payload` 루프에서 task 별 5개 필드 투영 → `_serialize_phase_history_tail_for_graph(tail)[-3:]` JSON 직렬화(`json.dumps(..., ensure_ascii=False)`) → HTTP 200 응답.

## 설계 결정 (대안이 있는 경우만)
- **결정**: `phase_history_tail` 의 3개 제한을 **응답 직렬화 시점**에 적용 (`_serialize_phase_history_tail_for_graph(limit=3)`).
- **대안**: `_PHASE_TAIL_LIMIT` 을 3으로 줄이거나, `WorkItem.phase_history_tail` 길이 자체를 3으로 축소.
- **근거**: 서버 내부 캐시(홈 대시보드 `history` 테이블, `_count_fail_events` 등)는 현재 10개 tail 을 사용 중이며 회귀 위험. `/api/graph` 응답만 3개로 제한하는 관점(view) 분리가 안전하다.

- **결정**: `is_running_signal` 산출을 위해 `_signal_set(signals, "running")` 결과를 **그래프 payload 빌더 내부에서 한 번만** 계산하여 재사용.
- **대안**: 각 노드마다 `any(sig.kind == "running" and sig.task_id == task.id for sig in signals)` linear scan.
- **근거**: 노드 수(N) × 시그널 수(M) = O(N·M) → set membership 으로 O(N+M). 50노드 × 수십 signals 규모에서도 체감 차이는 작지만 기존 `/api/state` 패턴과 일관되며 AC-16 no-cache 요구를 유지한다.

## 선행 조건
- 없음. `WorkItem.phase_history_tail`, `.last_event`, `.last_event_at`, `.elapsed_seconds` 는 기존 `scan_tasks` 가 이미 state.json 에서 채우고 있음 (line 440-677 참조). `_signal_set` 헬퍼 (line 2107) 도 기존 재사용.

## 리스크
- **MEDIUM**: `phase_history_tail` 원소에 포함된 `elapsed_seconds` 가 float 인 경우 JSON 에서 소수점으로 직렬화된다. 스펙은 `elapsed_seconds: int` 로 표기했으나 실제 state.json 에서 float 로 저장될 수 있음. 기존 `_normalize_elapsed` 가 bool 만 배제하고 int/float 모두 허용하는 규약을 유지하여 스펙 문구보다 **실제 저장값을 그대로 전달**한다. (구현 시 변환 금지 — 손실 위험).
- **LOW**: 응답 크기 증가. 50 노드 × (5 필드 × 평균 직렬화 바이트 ≈ 200B) ≈ +10KB 로 노드당 500B 상한·총 25KB 상한 모두 여유.
- **LOW**: dataclass `PhaseEntry.from_status`/`to_status` → 응답 키 `from`/`to` 매핑 누락 시 파이썬 예약어 문제로 드러나지 않고 침묵 회귀(테스트가 정확한 key 를 단언). `_serialize_phase_history_tail_for_graph` 를 순수 함수로 분리한 이유가 이 회귀를 단위 테스트로 고정하기 위함.
- **LOW**: 기존 `test_monitor_graph_api.py` 의 노드 dict 전체 비교(deep-equal) 테스트가 있을 경우 회귀. → dev-test 단계에서 스냅샷을 "필수 key 포함" 방식으로 느슨화하거나 기대값 업데이트 필요.

## QA 체크리스트
dev-test 단계에서 검증할 항목. 각 항목은 pass/fail 로 판정 가능하다.

- [ ] (정상) `GET /api/graph?subproject=monitor-v4` 응답의 모든 `nodes[*]` 가 정확히 5개 신규 key(`phase_history_tail`, `last_event`, `last_event_at`, `elapsed_seconds`, `is_running_signal`) 를 포함한다.
- [ ] (정상) 기존 key 10종(`id`, `label`, `status`, `is_critical`, `is_bottleneck`, `fan_in`, `fan_out`, `bypassed`, `wp_id`, `depends`) 는 값·타입이 변경 없이 유지된다.
- [ ] (엣지) `state.json` 이 없거나 `phase_history` 가 비어있는 task 의 `phase_history_tail` 은 `[]`, `last_event`/`last_event_at`/`elapsed_seconds` 는 `null`.
- [ ] (엣지) `phase_history` 원소가 4개 이상인 task 는 `phase_history_tail` 길이가 정확히 3 이며, **가장 최근** 3개(리스트 끝에서부터)가 포함된다. 순서는 시간 오름차순 유지.
- [ ] (엣지) `phase_history_tail` 각 원소가 정확히 5개 key(`event`, `from`, `to`, `at`, `elapsed_seconds`) 를 가지며 `from_status`/`to_status` 같은 내부 이름은 응답에 노출되지 않는다.
- [ ] (통합) `.running` signal 파일이 존재하는 task 의 `is_running_signal=true`, 삭제 후 재요청 시 `false` 로 토글된다 (AC-6).
- [ ] (통합) `running_ids` 계산이 기존 `/api/state` 와 동일한 set 을 재사용한다 — signal scan 이 per-node 반복되지 않는다 (호출 횟수 단언 또는 구현 리뷰).
- [ ] (에러) `state.json` 이 손상(JSON 파싱 실패)된 task 도 신규 필드는 `null`/`[]` 기본값으로 응답하며 500 에러를 유발하지 않는다.
- [ ] (회귀) 기존 `test_monitor_graph_api.py` 의 모든 테스트가 변경 없이 통과한다.
- [ ] (성능) 50노드 가상 픽스처로 응답 크기가 노드당 평균 +500B 이하, 총 +25KB 이하임을 단언.
- [ ] (타입체크) `python3 -m py_compile scripts/monitor-server.py scripts/dep-analysis.py` 통과.
