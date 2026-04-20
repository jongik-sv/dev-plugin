# TSK-01-02: 테스트 결과

## 결과: PASS

## 실행 요약

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 단위 테스트 | 44 | 0 | 44 |
| E2E 테스트 | N/A — backend domain | - | - |

> 본 Task는 domain=backend이며 Dev Config의 `domains.backend.e2e_test`가 null이다. 따라서 `references/test-commands.md`의 정책에 따라 E2E는 실행 대상 아님. 단계 1-5 UI 게이트 역시 design.md 본문에 UI 키워드가 없어 effective_domain=backend로 확정되었다.
>
> `test_monitor_scan.py` (18건) 외에 동시 discovery된 `test_monitor_signal_scan.py`(9건), `test_monitor_tmux.py`(17건)는 이 Task 직접 범위가 아니지만 unittest discover 한 번으로 함께 실행되어 모두 통과했다.

## 정적 검증 (Dev Config에 정의된 경우만)

| 구분 | 결과 | 비고 |
|------|------|------|
| lint | pass | `python3 -m py_compile scripts/monitor-server.py` → 바이트컴파일 성공 (에러 0) |
| typecheck | N/A | Dev Config에 typecheck 미정의 |

## QA 체크리스트 판정

design.md "QA 체크리스트" 14개 항목을 대응 단위 테스트로 검증.

| # | 항목 | 결과 | 대응 테스트 |
|---|------|------|-------------|
| 1 | 정상 — WBS (status `[dd]`, phase_history 12건 → tail 길이 10, raw_error=None) | pass | `ScanTasksNormalTests.test_scan_tasks_returns_single_workitem` |
| 2 | 정상 — Feature (spec.md 첫 non-empty 라인이 title) | pass | `ScanFeaturesNormalTests.test_scan_features_uses_spec_first_nonempty_line_as_title` |
| 3 | 정상 + 손상 혼재 (acceptance 1) | pass | `ScanMixedValidCorruptTests.test_valid_and_corrupt_are_both_returned` |
| 4 | 빈 디렉터리 (acceptance 2) — `tasks/`, `features/` 부재 → `[]` | pass | `ScanEmptyDirectoryTests.test_scan_tasks_returns_empty_when_tasks_dir_missing`, `test_scan_features_returns_empty_when_features_dir_missing`, `test_scan_tasks_returns_empty_when_tasks_dir_empty` |
| 5 | 1MB 초과 (acceptance 3) — `"file too large"` | pass | `ScanOversizeTests.test_file_larger_than_1mb_is_rejected`, `test_file_exactly_1mb_is_allowed_by_size_guard` |
| 6 | 읽기 권한 0o444 (constraint) | pass | `ScanReadOnlyTests.test_scan_tasks_works_on_0o444_state_json` |
| 7 | wbs.md 부재 — title/wp_id=None, depends=[] | pass | `WbsTitleMapTests.test_wbs_md_missing_yields_none_title` |
| 8 | phase_history 슬라이스 경계 (0/5/10/11/100 → tail 길이 0/5/10/10/10, 마지막 10개 유지) | pass | `PhaseHistorySliceTests.test_history_length_boundaries`, `test_last_ten_preserved_not_first_ten` |
| 9 | bypassed 플래그 전파 | pass | `BypassAndLastBlockTests.test_bypassed_flag_roundtrips` |
| 10 | last 블록 (누락 시 None) | pass | `BypassAndLastBlockTests.test_last_block_missing_yields_none` |
| 11 | depends 파싱 (wbs.md `- depends:` 라인) | pass | `WbsTitleMapTests.test_title_wp_depends_are_populated_from_wbs_md` |
| 12 | raw_error 500B 상한 | pass | `RawErrorCapTests.test_raw_error_max_length_500` |
| 13 | `open()` mode=read-only 검증 (constraint: 쓰기 모드 없음) | pass | `OpenModeReadOnlyTests.test_no_write_mode_open_calls` |
| 14 | 통합 (WBS 정상 2 + Feature 1 + WBS 손상 1 = 4, kind별 필터) | pass | `IntegrationTests.test_mixed_wbs_feat_corrupt` |

## 재시도 이력
- 첫 실행에 통과 (unit 44/44 pass, lint pass). 수정-재실행 사이클 미소진.

## 비고
- 실행 명령: `python3 -m unittest discover -s scripts -p "test_monitor*.py" -v` (Dev Config `domains.backend.unit_test`와 일치)
- lint: `python3 -m py_compile scripts/monitor-server.py`
- TSK-01-02 state: [im] (build.ok 후 test 대기) → 본 검증 통과로 test.ok 전이
- effective_domain 판정: design.md 본문에 UI 키워드 없음 → `domain` 라벨 `backend` 그대로 사용. 1-5/1-6/1-7 게이트 모두 해당 없음으로 스킵
