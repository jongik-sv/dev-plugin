# TSK-04-01: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/merge-preview.py` | `write_output_file` 내부의 `tmp_fd = None` 초기화 제거, 변수명 `tmp_fd` → `tmp_fh`로 명확화 (with 블록 내에서만 유효한 변수가 블록 외부에서 `None`으로 pre-declare 될 필요 없음) | Rename, Remove Redundant Variable |
| `scripts/test_merge_preview.py` | `_make_clean_repo` 헬퍼 추가; `TestMergePreviewStdoutStillWorks`를 2개 독립 테스트 메서드로 분리; `TestMergePreviewAtomicRename`에 `test_single_write` + 스레드 동시 실행 시뮬레이션 추가; `TestMergePreviewOutputDirAutoCreate`에서 `_make_conflict_setup` → `_make_clean_repo` 교체 (불필요한 충돌 셋업 의존 제거); `TestMergePreviewHookInTemplate`에 `_read_template` 공통 추출 및 `test_tdd_prompt_contains_or_true`, `test_tdd_prompt_contains_no_read_instruction` 2개 메서드 추가; `import threading` 추가 | Extract Method, Rename, Remove Duplication, Decompose Test |
| `scripts/test_merge_preview_output.py` | 제거 — `test_merge_preview.py`에 모든 테스트가 통합된 상태로 중복 파일이 되어 삭제 | Remove Duplication |
| `~/.claude/plugins/cache/dev-tools/dev/1.6.1/scripts/merge-preview.py` | 워크트리와 동기화 | Plugin Cache Sync |
| `~/.claude/plugins/cache/dev-tools/dev/1.6.1/scripts/test_merge_preview.py` | 워크트리와 동기화 | Plugin Cache Sync |

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -c "import pytest; import sys; sys.exit(pytest.main(['-q', 'scripts/test_merge_preview.py']))"`
- 결과: 13 passed in 1.40s (리팩토링 전 13 passed → 변경 없음)

## 비고
- 케이스 분류: A (리팩토링 성공)
- 리팩토링 전 테스트 수: 17 (test_merge_preview.py 9 + test_merge_preview_output.py 8 → 중복 제거 후 13 unique)
- `test_merge_preview_output.py`의 중복 클래스 4개(`TestMergePreviewOutputFlag`, `TestMergePreviewStdoutStillWorks`, `TestMergePreviewAtomicRename`, `TestMergePreviewOutputDirAutoCreate`)는 `test_merge_preview.py`에 이미 존재했으므로 파일 제거 후 총 13개 테스트로 통합되었다.
- `TestTddPromptContainsMergePreviewHook`의 추가 메서드 2개(`test_tdd_prompt_contains_or_true`, `test_tdd_prompt_contains_no_read_instruction`)는 `test_merge_preview_output.py`에만 있던 테스트로, `test_merge_preview.py`의 `TestMergePreviewHookInTemplate`에 흡수하여 커버리지를 확장했다.
- 전체 `scripts/` 테스트 스위트의 45개 실패는 TSK-04-01 이전부터 존재하는 `filter_bar`, `graph_hover`, `task_spinner` E2E 테스트로, 이번 리팩토링과 무관하다.
