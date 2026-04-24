# TSK-04-01: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| `scripts/monitor-server.py` | `_PHASE_LABELS` / `_PHASE_CODE_TO_ATTR` 두 사전의 역할·관계 명시. 두 사전이 같은 `[dd/im/ts/xx]` key space를 공유하나 독립적 목적(label vs attr 값)임을 주석으로 명확화. 가상 phase(failed/bypass/pending)가 flag 기반으로 인라인 처리됨을 표기. | Clarify Comment |
| `scripts/monitor-server.py` | `_render_task_row_v2` docstring 업데이트: TSK-02-02 시대의 stale 문구("The .spinner span is always emitted as a badge sibling") 제거, TSK-04-01에서 spinner를 `.badge` 내부 `.spinner-inline`으로 이동한 사실을 반영. children 목록도 현재 DOM 구조(info-btn/expand-btn 포함)에 맞게 갱신. | Update Documentation |
| `scripts/monitor-server.py` | `_build_graph_payload` 내 `phase` 필드 코멘트를 인접 필드 그룹 코멘트 스타일과 일치하도록 정렬. `data-phase attribute in JS template` 부연 추가로 JS 연결 지점 명시. | Clarify Comment |
| `skills/dev-monitor/vendor/graph-client.js` | `getStatusKey` 헬퍼 주석 업데이트: signal-based CSS 키(status-* 클래스·border/색상 전용)임을 명시. `data-phase`는 별도 `nd.phase` API 필드에서 읽으며 `getStatusKey()`와 무관함을 표기하여 두 축(signal status vs DDTR phase)의 관계를 명확화. | Clarify Comment |

## 테스트 확인
- 결과: PASS
- 실행 명령: `/usr/bin/python3 -m pytest scripts/test_monitor_phase_badge_colors.py scripts/test_monitor_graph_api.py::TestApiGraphPayloadV4Fields::test_graph_node_has_phase_field -v --tb=short`
- 결과: 30/30 통과

## 비고
- 케이스 분류: A (리팩토링 성공 — 변경 적용 후 테스트 통과)
- 리팩토링 범위: 동작 변경 없는 주석·docstring 정리에 집중. 코드 로직(함수·CSS·JS 동작)은 일체 변경하지 않음.
- `_PHASE_LABELS`와 `_PHASE_CODE_TO_ATTR` 두 사전을 단일 구조체로 통합하는 방안을 검토했으나, 두 사전의 value 타입이 다르고(`dict[str, str]` vs `str`) 통합 시 `_phase_label` / `_phase_data_attr` 두 함수의 조회 패턴이 달라져 가독성 대비 변경 비용이 크다고 판단하여 미수행. 현재 주석으로 관계 명시하는 것으로 충분.
