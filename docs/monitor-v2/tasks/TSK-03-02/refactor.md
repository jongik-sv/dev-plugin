# TSK-03-02: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|----------------------|
| `scripts/monitor-server.py` | `_timeline_svg` 내 반복되는 `isinstance(row, dict)` 삼항식 3개를 `_row_attr()` 헬퍼 호출로 교체 | Extract Method, Remove Duplication |
| `scripts/monitor-server.py` | `_row_attr()` 헬퍼 함수 신규 추가 — `_pane_attr`와 동일한 dict/dataclass 이중 접근 패턴을 추상화 | Extract Method |
| `scripts/monitor-server.py` | `_section_kpi` 내 `filters_def` 인라인 리스트를 모듈 상수 `_FILTER_CHIPS`로 추출 | Replace Magic Number (상수 추출), 모듈 레벨 상수 일관성 |
| `scripts/monitor-server.py` | `cards = "".join([...])` 리스트 래퍼를 제거, generator 표현식으로 통일 (파일 내 다른 `"".join(gen)` 패턴과 일치) | Remove Duplication, Simplify |

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m unittest discover scripts/ -v`
- 결과 요약: Ran 339 tests — OK (skipped=17). 접근성 전용 `test_monitor_a11y.py` 33 tests 모두 통과. 리팩토링 전후 동일한 결과.

## 비고
- 케이스 분류: A (성공) — 변경 적용 후 테스트 통과
- `_row_attr`는 기존 `_pane_attr`와 동일한 인터페이스(`obj, key, default`)로 설계하여 코드베이스 내 패턴 일관성 유지
- `_FILTER_CHIPS` 위치는 `_STATUS_BADGE_MAP`, `_SUBAGENT_BADGE_CSS` 등 기존 모듈 상수 블록 바로 아래에 배치
- 동작 변경 없음 — `_timeline_svg`, `_section_kpi` 렌더 출력이 리팩토링 전후 동일
