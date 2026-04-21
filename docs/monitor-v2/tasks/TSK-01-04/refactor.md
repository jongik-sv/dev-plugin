# TSK-01-04: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor-server.py` | `_section_live_activity` 내 중복 변수 `event_data` 제거 — `event_esc`를 `data-event` 속성과 텍스트 노드 양쪽에 재사용 | Remove Duplication |
| `scripts/monitor-server.py` | `_x_of` 함수 내 로컬 `from datetime import timedelta as _td` 제거 — 파일 상단에 이미 임포트된 `timedelta`를 직접 사용 | Remove Duplication, Inline |
| `scripts/monitor-server.py` | `_timeline_svg` X축 tick 라벨 결정 조건을 `minutes_ago == 0` (float 비교) → `i == 12` (정수 인덱스 비교)로 교체 | Simplify Conditional |

## 테스트 확인

- 결과: PASS
- 실행 명령: `python3 -m unittest discover scripts/ -v`
- 558 tests, 0 failures, 6 skipped

## 비고

- 케이스 분류: **A (성공)** — 리팩토링 적용 후 전체 단위 테스트 통과
- 동작 보존 확인: `event_data`와 `event_esc`는 동일한 `_esc(event or "")` 값이었으므로 HTML 출력 동일
- float `== 0` 비교는 `span_minutes / 12` 나눗셈에서 정수 배수일 때만 안전했으나, 인덱스 기반으로 변경하여 float 정밀도 의존성 제거
