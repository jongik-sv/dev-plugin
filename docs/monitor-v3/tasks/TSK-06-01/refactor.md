# TSK-06-01: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| `scripts/merge-preview.py` | `from typing import Dict, List, Tuple` 제거 → `from __future__ import annotations` 유지로 충분 (런타임 평가 없음) | Remove Unused Import |
| `scripts/merge-preview.py` | `_run_git` 기본값 `check=True` → `check=False`로 변경 — 모든 호출부가 `check=False`를 명시하고 있었으며, 기본값과 실제 사용이 불일치하여 혼란 유발 | Rename (Parameter Default Alignment) |
| `scripts/merge-preview.py` | `_is_up_to_date()` 헬퍼 함수 추출 — `simulate_merge` 내 stdout 체크 로직이 stderr를 누락하던 버그 수정 겸 가독성 개선 (`stdout + stderr` combined 체크) | Extract Method, Bug Fix |
| `scripts/merge-preview.py` | `parse_conflicts()` 리팩토링 — 단일 `git diff --diff-filter=U` 호출로 단순화를 시도했으나 combined diff(`diff --cc`) 헤더 형식 차이로 regression 발생 → 두-단계 방식 유지하되 코드 구조 개선 (`hunk_map` dict + list comprehension) | Extract Variable, Simplify Loop |
| `scripts/merge-preview.py` | `simulate_merge` `finally` 블록 간소화 — MERGE_HEAD 존재 여부로 abort vs reset 분기는 동일하게 유지하되 불필요한 주석 제거 | Simplify Conditional |
| `scripts/test_merge_preview.py` | 미사용 import 제거 (`os`, `textwrap`, `typing.List`, `typing.Optional`) | Remove Unused Import |
| `scripts/test_merge_preview.py` | `_make_clean_repo()` 미사용 헬퍼 제거 — 4개 테스트 중 어느 것도 호출하지 않아 데드코드 제거 | Remove Dead Code |
| `scripts/test_merge_preview.py` | `Optional[List[str]]` → `list[str] | None` + `from __future__ import annotations` 추가 (Python 3.9 호환) | Modernize Type Hints |

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m unittest scripts.test_merge_preview -v`
- 4/4 테스트 통과 (1.156s)

## 비고
- 케이스 분류: A (리팩토링 성공 — 변경 적용 후 테스트 통과)
- `parse_conflicts()` 단순화 시도 중 combined diff(`diff --cc`) 헤더 형식이 일반 diff(`diff --git`)와 다름을 확인, 즉시 수정. `--name-only --diff-filter=U` 두-단계 방식이 필요함을 docstring에 명시.
- `_is_up_to_date()` 헬퍼 추출로 `stdout`만 체크하던 기존 로직에서 `stderr`까지 포함한 robust 체크로 개선 (silent failure 방지).
