# TSK-01-05: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor-server.py` | `_pane_last_n_lines`: `while` loop → `raw.rstrip().splitlines()` 패턴으로 교체 | Simplify Conditional, Replace Algorithm |
| `scripts/monitor-server.py` | `_section_team` inner loop: `if/else` 4줄 블록 → 리스트 컴프리헨션 + 삼항 표현식으로 압축 | Extract Method (inline), Simplify Conditional |

### 상세 설명

**`_pane_last_n_lines` (`while` loop 제거)**

기존 코드는 `raw.splitlines()`로 분리한 뒤 `while lines and not lines[-1].strip(): lines.pop()` 루프로 trailing blank 줄을 순차 제거했다. `str.rstrip()`은 문자열 레벨에서 동일한 작업을 단일 연산으로 수행하고, `splitlines()`는 trailing 줄 구분자가 없으면 빈 요소를 생성하지 않으므로 동작이 동일하면서 더 Pythonic하다.

**`_section_team` inner loop (리스트 컴프리헨션)**

`row_parts: List[str] = []` + `for pane in ...: if too_many: ... else: ... row_parts.append(...)` 패턴을 리스트 컴프리헨션으로 교체했다. `too_many`가 loop 밖에서 계산되므로 삼항식 평가 비용은 동일하고, 코드 라인 수가 10줄 → 7줄로 감소했다.

## 테스트 확인

- 결과: PASS
- 실행 명령: `python3 -m unittest discover -s scripts -p "test_monitor*.py"`
- 총 495 테스트 통과 (skipped=1), 0 failure

## 비고

- 케이스 분류: A (성공) — 리팩토링 적용 후 테스트 통과
- `_render_pane_row`의 `pane_id_raw` 중간 변수, `_section_team`의 `_group_preserving_order` 호출 등은 이미 충분히 정돈되어 있어 추가 변경 없음
