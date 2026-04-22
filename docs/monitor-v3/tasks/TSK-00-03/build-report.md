# TSK-00-03: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | `discover_subprojects()` + `_filter_by_subproject()` 함수 추가 (`--- end scan functions ---` 섹션 바로 위) | 수정 |
| `scripts/test_monitor_subproject.py` | TSK-00-03 전용 단위 테스트 (18개 케이스) | 신규 |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 | 18 | 0 | 18 |

필수 5개 케이스 전부 통과:
- `test_discover_subprojects_multi` ✅
- `test_discover_subprojects_legacy` ✅
- `test_discover_subprojects_ignores_dirs_without_wbs` ✅
- `test_filter_by_subproject_signals` ✅
- `test_filter_by_subproject_panes_by_window` ✅

## E2E 테스트 (작성만 — 실행은 dev-test)

N/A — backend domain

## 커버리지 (Dev Config에 coverage 정의 시)

N/A

## 비고

- design.md QA 체크리스트의 모든 항목을 포함하는 18개 단위 테스트 작성. 필수 5개 케이스 외 추가 케이스:
  - `test_discover_subprojects_multi_sorted` — 정렬 보장 검증
  - `test_is_multi_mode_true` / `test_is_multi_mode_false` — `len(...) > 0` 패턴 직접 검증
  - `test_discover_subprojects_empty_docs` / `test_discover_subprojects_nonexistent_docs_dir` / `test_discover_subprojects_file_not_dir_child` — 엣지 케이스 커버
  - `test_filter_by_subproject_signals_exact_match` / `test_filter_by_subproject_signals_prefix_match` / `test_filter_by_subproject_no_matching_signals` — signal 필터 세분화
  - `test_filter_by_subproject_panes_contains_sp_infix` / `test_filter_by_subproject_panes_by_cwd` / `test_filter_by_subproject_panes_none_preserved` / `test_filter_by_subproject_panes_empty_list` — pane 필터 세분화
- 기존 테스트 (`test_monitor_scan.py` 21개, `test_monitor_signal_scan.py` 15개) regression 없음 확인.
- `_filter_by_subproject` 구현: `state["tmux_panes"]` 가 `None` 이면 `None` 보존 (tmux 미설치 환경 대응).
