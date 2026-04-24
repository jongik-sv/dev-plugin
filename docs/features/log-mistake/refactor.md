# log-mistake: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/log-mistake.py` | `check_duplicate`의 title 포함 여부 검사를 `title in content`에서 `f"### {title}" in content`로 좁혀 description 필드에서 오탐 방지 | Simplify Conditional |
| `scripts/log-mistake.py` | `install_pointer`에서 `MARKER_CLOSE`가 없는 불완전 마커 블록에 대한 방어 처리 추가 (IndexError 방지) | Error Handling |
| `skills/log-mistake/SKILL.md` | step 3 코드 예시에서 `--mistakes-dir` 옵션을 positional 인자 뒤로 이동하여 argparse 관행 일치 | Rename (스타일 정합) |

## 테스트 확인

- 결과: PASS
- 실행 명령: `python3 -m unittest scripts/test_log_mistake.py -v`
- 18/18 통과, 회귀 없음

## 비고

- 케이스 분류: A (성공)
- `check_duplicate`의 `title in content` → `f"### {title}" in content` 변경은 동작 보존: 테스트의 기존 어서션은 `### {title}` 형식으로 저장된 항목을 대상으로 하므로 결과가 동일. description 안에 title과 동일한 문자열이 포함된 엣지 케이스에서는 오히려 정확도가 향상됨.
- `install_pointer` 방어 코드: 기존 테스트에서 불완전 마커 블록(MARKER_OPEN만 있고 MARKER_CLOSE 없는 경우) 커버리지가 없었으므로 동작 보존은 기존 케이스 기준으로 검증됨.
