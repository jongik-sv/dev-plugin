# TSK-04-01: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| `scripts/test_monitor_api_state.py` | `_build_state_snapshot` 반복 호출 패턴을 모듈 레벨 `_snapshot()` 헬퍼로 추출. `BuildStateSnapshotTests._snapshot`은 `staticmethod(_snapshot)` 바인딩으로 단순화 | Extract Method, Remove Duplication |
| `scripts/test_monitor_api_state.py` | `BuildStateSnapshotTests` 내 8개 테스트 메서드에서 `monitor_server._build_state_snapshot(..., scan_tasks=lambda _d: ..., ...)` 6~7줄 반복 블록을 `self._snapshot(tasks=...)` 단일 호출로 대체 | Remove Duplication, Simplify Conditional |
| `scripts/test_monitor_render.py` | `SectionTeamV2Tests`의 `@skipUnless` 조건에서 `_HAS_SECTION_TEAM_V2 and hasattr(monitor_server, "_section_kpi")` 중 `_HAS_SECTION_TEAM_V2` 정의에 이미 `_HAS_SECTION_KPI`가 포함되므로 중복 조건 제거 | Remove Duplication |

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m unittest discover scripts/ -v`
- `test_monitor_render.py`: 47건 (30 OK, 17 SKIP)
- `test_monitor_api_state.py`: 36건 (36 OK)
- 전체 discover: 298 OK, 22 SKIP, 1 pre-existing FAIL (test_monitor_server_bootstrap.TestMainFunctionality.test_server_attributes_injected — TSK-04-01 파일 범위 외, 기존 동일)

## 비고
- 케이스 분류: A (리팩토링 성공 — 변경 적용 후 테스트 통과)
- `_snapshot` 헬퍼는 `None` vs `[]` 구분을 위해 `panes=None` 전달 시 `lambda: None`이 아닌 `lambda: []`를 기본값으로 사용한다. `test_tmux_panes_none_is_preserved`는 직접 `monitor_server._build_state_snapshot(..., list_tmux_panes=lambda: None)`을 호출하여 명시적으로 None 반환을 검증 — 이 케이스는 헬퍼 기본값 동작과 구분되어 그대로 유지했다.
