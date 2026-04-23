# TSK-00-02: `/api/graph` payload v4 필드 확장 - TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | `_GRAPH_PHASE_TAIL_LIMIT = 3` 상수 추가; `_serialize_phase_history_tail_for_graph()` 순수 함수 추가; `_build_graph_payload()` 에 5개 신규 필드(`phase_history_tail`, `last_event`, `last_event_at`, `elapsed_seconds`, `is_running_signal`) 및 `running_ids_set` O(N+M) 계산 추가 | 수정 |
| `scripts/test_monitor_graph_api.py` | `TestSerializePhaseHistoryTailForGraph` 클래스(7종) + `TestApiGraphPayloadV4Fields` 클래스(5종) 신규 추가 | 수정 |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (test_monitor_graph_api.py) | 55 | 0 | 55 |
| 전체 단위 테스트 (scripts/, E2E 제외) | 1189 | 0 | 1189 |

### 신규 테스트 목록 (TSK-00-02 추가분)

**TestSerializePhaseHistoryTailForGraph** (7개):
- `test_empty_input_returns_empty_list` — None/빈 리스트 → []
- `test_single_entry_converted_correctly` — 키 매핑 정확성 (event/from/to/at/elapsed_seconds)
- `test_internal_keys_not_exposed` — from_status/to_status 내부 이름 노출 금지
- `test_limit_3_applied` — 기본 limit=3, 마지막 3개 반환
- `test_limit_param_respected` — limit 파라미터 커스텀 지정
- `test_elapsed_seconds_none_preserved` — None → null 보존
- `test_order_preserved_ascending` — 시간 오름차순 유지

**TestApiGraphPayloadV4Fields** (5개):
- `test_api_graph_payload_v4_fields_present` — 모든 노드에 5개 신규 필드 존재
- `test_api_graph_payload_v4_fields_defaults_when_no_state` — 기본값([], null, false)
- `test_api_graph_is_running_signal_reflects_signal_file` — signal 생성/삭제 시 토글
- `test_api_graph_phase_history_tail_limit_3` — 4개 이상 엔트리 → 최근 3개만
- `test_existing_fields_not_modified` — 기존 10개 필드 값/타입 불변

### 회귀 확인

기존 `test_monitor_graph_api.py` 테스트 전부 (48개) 회귀 없이 통과.

E2E 테스트(`test_monitor_e2e.py`) 8개 실패는 라이브 서버 미기동으로 인한 pre-existing failures — TSK-00-02 변경과 무관.

## E2E 테스트 (작성만 — 실행은 dev-test)

N/A — backend domain

## 커버리지

N/A — Dev Config에 `coverage` 명령 미정의 (`quality_commands.typecheck`만 정의됨)

Typecheck: `python3 -m py_compile scripts/monitor-server.py scripts/dep-analysis.py` → PASS

## 비고

- `running_ids_set`을 루프 진입 전 한 번만 계산하여 `_signal_set()` per-node 반복 금지 (설계 결정 준수).
- `_serialize_phase_history_tail_for_graph` 는 순수 함수로 분리, `from_status`/`to_status` → `from`/`to` 키 복원 검증을 단위 테스트로 고정.
- `elapsed_seconds` 는 float/int/None 그대로 통과 (`_normalize_elapsed` 규약 준수, 손실 없음).
