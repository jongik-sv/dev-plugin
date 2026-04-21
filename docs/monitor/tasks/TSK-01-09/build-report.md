# TSK-01-09: HTML 렌더 경로 dataclass 보존 (DEFECT-3 후속) - 빌드 보고서

## 변경 사항

| 파일 | 변경 내용 | 라인 증감 |
|------|-----------|-----------|
| `scripts/monitor-server.py` | `_build_render_state()` 신규 함수 추가 (원시 dataclass 리스트 반환, 8-key dict) | +38 |
| `scripts/monitor-server.py` | `_build_state_snapshot()` 본문을 `_build_render_state()` 호출 + 각 리스트 `_asdict_or_none()` 적용 래퍼로 리팩토링 | 0 순증 (본문 교체) |
| `scripts/monitor-server.py` | `_route_root()` → `_build_state_snapshot(...)` 호출을 `_build_render_state(...)` 호출로 교체. docstring 추가 | ~+6 |

## 주요 결정

1. **외부 계약 불변 유지**: `_build_state_snapshot()`의 시그니처·반환 dict key 구성·원소 dict 형태를 모두 보존했다. `scripts/test_monitor_api_state.py`의 17개 호출 지점이 수정 없이 통과되어야 한다는 제약을 우선했다.

2. **핸들러별 호출 분리**: `_route_root`(HTML)만 raw 경로로 전환하고 `_handle_api_state`(JSON)는 변경하지 않는다. 두 핸들러가 동일한 snapshot을 공유할 때 생기는 타입 불일치를 **핸들러 경계에서** 흡수한다.

3. **`_asdict_or_none` 제거 아님**: `_asdict_or_none`은 JSON 직렬화 용도로 여전히 필요하다. 단지 HTML 경로에는 호출되지 않도록 배치만 옮겼다.

4. **테스트 코드 무수정**: 기존 `test_monitor_*.py` 240건은 이미 `render_dashboard`에 직접 dataclass를 주입하거나 `_build_state_snapshot` 반환을 JSON 계약 관점에서 검증하는 방식이라 리팩토링 영향을 받지 않는다. 신규 E2E 회귀 테스트(snapshot→HTTP→HTML 전 경로) 추가는 후속 보강 여지로 남겼다.

## 회피한 대안

| 대안 | 폐기 이유 |
|------|-----------|
| A. `_render_task_row` 내부에서 dict/dataclass 양쪽 대응 | `_section_wbs`, `_section_features`, `_section_team`, `_render_pane_row`, `_render_subagent_row`, `_section_phase_history` 등 **13개 이상의 `getattr` 지점을 모두** dict-safe 접근자로 바꿔야 한다. 변경 면적이 크고 렌더러가 자료 표현에 의존하게 됨. |
| B. `_asdict_or_none`을 HTML 경로에서 bypass (inline toggle) | snapshot 함수에 "어느 경로에서 쓰일지"를 매개변수로 흘리게 되어 결합도 증가. |
| C. `_build_state_snapshot`을 공통 raw 함수로 전면 변경 | 외부 계약(JSON key 원소 dict 형태) 파괴. 17개 기존 테스트가 깨진다. |

선택: "raw 수집 + dict 래퍼" 분리 (본 Task 채택 방향). 한 지점(`_route_root`)만 바꾸고 모든 외부 계약을 보존한다.

## 구현 완료 확인
- [x] `_build_render_state()`가 `_build_state_snapshot()`과 동일한 8개 key (`generated_at`, `project_root`, `docs_dir`, `wbs_tasks`, `features`, `shared_signals`, `agent_pool_signals`, `tmux_panes`) 반환
- [x] `_build_render_state()` 반환의 `wbs_tasks`/`features` 원소는 `WorkItem` dataclass 인스턴스 (런타임 확인)
- [x] `_build_state_snapshot()` 시그니처 불변 — 기존 17개 호출 지점 수정 없음
- [x] `_route_root()`가 `_build_render_state()`를 호출하도록 전환됨
- [x] `_handle_api_state()` 는 변경 없음
