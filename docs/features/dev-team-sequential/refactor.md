# dev-team-sequential: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/wp-setup.py` | `mode_notice` 빌드 로직에서 `if/elif/else` 3분기를 `branch_part` 중간 변수 1개 + 3항 표현식으로 단순화. 두 경우의 텍스트 중복 제거 | Remove Duplication, Simplify Conditional |
| `skills/dev-team/SKILL.md` | `--sequential` 모드 설명 항목(전제조건 섹션)이 단일 긴 문장으로 나열되어 있던 것을 개조식 하위 목록으로 분리. 내용 변경 없음 | Formatting (구조 개선) |

## 테스트 확인

- 결과: PASS (20/20)
- 실행 명령: `/Users/jji/Library/Python/3.9/bin/pytest scripts/test_args_parse_sequential.py scripts/test_wp_setup_sequential.py -v`

```
20 passed in 2.88s
```

## 비고

- 케이스 분류: A (성공 — 변경 적용 후 테스트 통과)
- `args-parse.py`의 `--sequential` 플래그 처리 코드는 이미 깔끔하게 작성되어 있어 별도 변경 없음
- `wp-setup.py`의 `is_windows` 변수(미사용)는 이번 feature 도입 이전부터 존재하는 기존 코드이므로 보수적 원칙에 따라 범위 외로 제외
