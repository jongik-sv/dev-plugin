# TSK-06-03: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/merge-state-json.py` | `_atomic_write_json`의 `str(dirp) if str(dirp) else None` 패턴 제거 — `pathlib.Path.parent`는 절대 빈 문자열이 아니므로 `str(dirp)` 단순화 | Simplify Conditional |
| `scripts/merge-wbs-status.py` | `_atomic_write_text`의 동일 패턴 제거 (`str(dirp)` 단순화) | Simplify Conditional |
| `scripts/merge-wbs-status.py` | `_split_lines_keepends` 단순 래퍼 함수 제거 — 호출 사이트 5곳을 `str.splitlines(keepends=True)` 직접 호출로 대체 | Inline |
| `scripts/merge-wbs-status.py` | `_reapply_statuses`의 `line.lstrip().startswith("### ")` → `line.startswith("### ")` — `parse_status_lines`와 동일 패턴으로 통일, 들여쓰기된 `### ` 오감지 제거 | Simplify Conditional, Remove Duplication |
| `scripts/merge-wbs-status.py` | `_diff3_hunks` 내 inserts 누적 루프(30줄 중복) → 로컬 헬퍼 `_collect_inserts` 로 추출 | Extract Method, Remove Duplication |

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m pytest scripts/test_merge_state_json.py scripts/test_merge_wbs_status.py -v`
- 19/19 통과

## 비고
- 케이스 분류: A (성공)
- 동작 변경 없음. 모든 변경은 불필요한 조건, 래퍼 함수 제거, 중복 루프 추출에 한정.
