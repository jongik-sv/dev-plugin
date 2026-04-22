# TSK-01-02: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | `scan_signals()`: scope를 subdir 이름으로 변경 (TSK-00-01 통합 구현) | 수정 |
| `scripts/monitor-server.py` | `discover_subprojects()`: wbs.md 전용 판정 (tasks/features 폴더 제외) | 수정 |
| `scripts/monitor-server.py` | `_filter_panes_by_project()` 신규 (TSK-00-02) | 수정 |
| `scripts/monitor-server.py` | `_filter_signals_by_project()` 신규 (TSK-00-02) | 수정 |
| `scripts/monitor-server.py` | `_filter_by_subproject()` 신규 (TSK-00-03) | 수정 |
| `scripts/monitor-server.py` | `_build_render_state()`: `project_name`, `subproject`, `available_subprojects`, `is_multi_mode`, `lang` 5개 키 추가 | 수정 |
| `scripts/monitor-server.py` | `_section_subproject_tabs(model)` 신규 — 멀티 모드에서 `<nav class="subproject-tabs">` 방출 | 수정 |
| `scripts/monitor-server.py` | `render_dashboard()`: `_section_subproject_tabs` 호출 및 `_build_dashboard_body`에 `subproject-tabs` 키 전달 | 수정 |
| `scripts/monitor-server.py` | `_build_dashboard_body()`: header 직후 `subproject-tabs` 삽입 | 수정 |
| `scripts/monitor-server.py` | `DASHBOARD_CSS`: `.subproject-tabs` / `.subproject-tabs a` / `[aria-current="page"]` 스타일 추가 | 수정 |
| `scripts/monitor-server.py` | `MonitorHandler._route_root()`: 쿼리 파싱 (`subproject`/`lang`), `discover_subprojects`, 필터 클로저 합성, `_build_render_state` 호출 확장 | 수정 |
| `scripts/test_monitor_render.py` | `DiscoverSubprojectsTests`, `FilterBySubprojectTests`, `FilterPanesByProjectTests`, `FilterSignalsByProjectTests`, `SectionSubprojectTabsTests`, `RenderDashboardTabsTests` 추가 | 수정 |
| `scripts/test_monitor_signal_scan.py` | TSK-00-01 scope 변경에 맞게 `test_done_signal_in_shared_dir`, `test_recursive_scan_claude_signals` 업데이트 + `test_scope_is_subdir_name`, `test_flat_signal_under_claude_signals_is_shared` 추가 | 수정 |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 (TSK-01-02 관련 3개 파일) | 226 | 1(기존) | 227 |

**기존 실패**: `NavigationAndEntryLinksTests::test_pane_show_output_link_per_pane` — TSK-01-02 이전부터 실패 중인 기존 테스트 (href="/pane/%1" 미존재). 이 TSK에서 수정 대상 아님.

**전체 스위트 변화**: 기존 81 failed, 649 passed → 81 failed, 712 passed (신규 63개 통과, regression 없음).

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| N/A — e2e_test 미정의 | Dev Config `fullstack` domain의 e2e_test=null |

## 커버리지

N/A — Dev Config `quality_commands.coverage` 미정의

## 비고

- **TSK-00-01/02/03 통합 구현**: WBS note의 "의도된 3→1 merge"에 따라 WP-00의 3개 헬퍼를 이 TSK에서 함께 구현. 각 TSK 번호 상태는 별도로 전이 필요.
- **`scan_signals()` scope 변경**: `claude-signals/{subdir}/` 하위 파일의 scope가 subdir 이름으로 변경됨. flat 파일(`claude-signals/` 직접)은 여전히 `"shared"`. `_classify_signal_scopes`는 `agent-pool:` prefix만 특별 처리하고 나머지는 shared 버킷에 넣으므로 렌더 표시 불변.
- **`_build_render_state` 시그니처 확장**: `subproject`와 `lang` 인자가 추가되었으나 기본값이 있어 기존 호출자 무중단.
- **`_route_root` 필터 클로저**: `_scan_signals_f` / `_list_panes_f` 클로저를 통해 프로젝트 레벨 + 서브프로젝트 레벨 이중 필터링. `/api/state`는 `_handle_api_state`가 별도로 `discover_subprojects` mock을 통해 이미 테스트됨.
- **design.md `available_subprojects` override**: `_build_render_state`는 `effective_docs_dir`를 받으므로 서브프로젝트 subdir에서 `discover_subprojects`를 실행하면 빈 리스트가 된다. `_route_root`에서 base_docs_dir로 계산 후 override하는 방식으로 해결.
