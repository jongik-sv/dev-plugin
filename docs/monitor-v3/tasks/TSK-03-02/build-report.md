# TSK-03-02: /api/graph 엔드포인트 - TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | `_is_api_graph_path`, `_derive_node_status`, `_build_graph_payload`, `_handle_graph_api` 추가; `MonitorHandler.do_GET`에 `/api/graph` 라우팅 추가 | 수정 |
| `scripts/dep-analysis.py` | `fan_out_map` 별칭 키 추가 (기존 `fan_out` dict의 alias — monitor-server.py 호환용) | 수정 |
| `scripts/test_monitor_graph_api.py` | `/api/graph` 응답 구조·상태 도출·필터·에러 처리·AC-16 캐시 없음 테스트 | 신규 |
| `scripts/test_dep_analysis_critical_path.py` | `fan_out_map`, `critical_path`, `bottleneck_ids` 신규 항목 테스트 | 신규 |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 | 68 | 0 | 68 |

### 테스트 목록

**test_monitor_graph_api.py** (44 tests):
- `TestIsApiGraphPath`: 라우팅 매칭/비매칭 8개
- `TestDeriveNodeStatus`: bypassed/failed/done/running/pending 5종 + edge case 16개
- `TestBuildGraphPayload`: 응답 구조, stats 항등식, 노드 필드, edges 6개
- `TestHandleGraphApi`: AC-10/11/15/16, 500 에러, 빈 응답 등 11개
- `TestMonitorHandlerGraphRoute`: do_GET 라우팅 검증 2개

**test_dep_analysis_critical_path.py** (24 tests):
- `TestFanOut`: fan_out_map 존재·카운트·대칭 4개
- `TestCriticalPath`: nodes/edges 구조, 단일/선형/분기/동점 9개
- `TestBottleneckIds`: fan_in/fan_out 임계값, 중복 없음 5개
- `TestGraphStatsEmptyInput`: 빈 입력 기본값 6개

## E2E 테스트 (작성만 — 실행은 dev-test)

N/A — backend domain

## 커버리지 (Dev Config에 coverage 정의 시)

N/A

## 비고

- 워크트리의 `dep-analysis.py`는 `fan_out` 키를 사용하고 있었으며, `fan_out_map` 별칭을 추가하여 `_build_graph_payload`에서 호환성 유지 (`graph_stats.get("fan_out_map", graph_stats.get("fan_out", {}))` 패턴).
- `_handle_graph_api`는 `from urllib.parse import parse_qs`를 함수 내부에서 import하여 모듈 레벨 import 의존성 없이 stdlib만 사용.
- design.md 비고: `_derive_node_status`의 `fail` event 감지는 `.fail` suffix 방식 외에 `== "fail"` exact match도 포함하여 legacy event 이름 방어.
