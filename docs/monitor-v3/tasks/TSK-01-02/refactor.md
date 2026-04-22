# TSK-01-02: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor-server.py` | `_filter_panes_by_project` 내부 `import re as _re` 제거 — 모듈 최상단 `import re` 재사용 | Remove Duplication |
| `scripts/monitor-server.py` | `_route_root`의 `is_multi_mode = len(...) > 0` → `bool(...)` 로 통일 (동일 패턴이 `_build_render_state`에도 존재했음) | Simplify Conditional |
| `scripts/monitor-server.py` | `_build_render_state`의 `is_multi_mode = len(...) > 0` → `bool(...)` 로 통일 | Simplify Conditional |

### 상세 설명

**변경 1 — `_filter_panes_by_project` 내부 중복 임포트 제거**

`_passes` 내부 클로저에 `import re as _re`가 있었으나, 이 모듈은 최상단(라인 31)에서 이미 `import re`로 임포트되어 있다. Python 모듈 임포트는 `sys.modules` 캐시를 통해 중복 임포트를 방지하므로 런타임 비용은 미미하나, 로컬 바인딩 생성과 최상단 `re` 가 이미 있다는 사실을 은닉하는 코드 냄새다. 함수 내부에서 `re.match`/`re.escape`를 직접 사용하는 것이 명확하다.

**변경 2, 3 — `is_multi_mode` 계산 통일**

`_route_root`와 `_build_render_state` 양쪽에서 `is_multi_mode`를 각각 `len(available_subprojects) > 0`으로 계산하고 있었다. Python에서 빈 리스트의 참/거짓 판별은 `bool(list)` 관용구가 더 간결하고 의도를 명확히 한다. 두 위치 모두 `bool(available_subprojects)`로 통일했다.

## 테스트 확인

- 결과: PASS
- 실행 명령: `/usr/bin/python3 -m pytest scripts/test_monitor_render.py scripts/test_monitor_api_state.py --tb=no -q`
- 결과 요약: 216개 중 215개 통과, 1개 실패 (`test_pane_show_output_link_per_pane`) — 리팩토링 전후 동일하게 존재하는 기존 실패, TSK-01-02 범위 외
- TSK-01-02 직접 관련 테스트 (`SectionSubprojectTabsTests`, `RenderDashboardTabsTests`) 12개 전원 통과

## 비고

- 케이스 분류: A (리팩토링 성공 — 변경 적용 후 테스트 통과)
- `test_pane_show_output_link_per_pane` 실패는 리팩토링 전부터 존재하며 TSK-01-02 범위(탭 바 / 루트 라우트 / 서브프로젝트 필터)와 무관 — pane URL 인코딩 관련 별도 Task 범위
- `test_platform_smoke.py::SmokeTestBase::test_dashboard_loads`는 전체 suite 실행 시 포트 충돌 상황에 따라 flaky하게 fail/skip 됨 — 리팩토링과 무관 (개별 실행 시 SKIP)
