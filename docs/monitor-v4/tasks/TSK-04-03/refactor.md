# TSK-04-03: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor-server.py` | `_merge_badge()`: `state="stale"` 명시 입력 처리 분기 추가 — CSS `.merge-badge[data-state="stale"]` 규칙과 정합, 이전에는 unknown fallback으로 떨어짐 | Introduce Guard Clause |
| `scripts/monitor-server.py` | `_section_wp_cards()`: `_wp_ms` 변수 2단계 조건 재할당 패턴 → `_raw_ms`/`_wp_ms` 단일 삼항 표현식으로 정리, 주석 간소화 | Simplify Conditional, Rename |
| `scripts/monitor-server.py` | `openMergePanel()` JS: `.then`/`.catch` 양쪽에서 중복으로 4번 호출하던 `getElementById`를 함수 상단에서 1회 조회 + `_showPanel(contentHtml)` 내부 함수로 패널 열기 로직 DRY화 | Extract Method, Remove Duplication |

## 테스트 확인
- 결과: PASS
- 실행 명령: `/Users/jji/Library/Python/3.9/bin/pytest -q scripts/test_monitor_merge_badge.py`
- 47 passed (TSK-04-03 단위 테스트 전체)
- 전체 suite 45 failed는 test-report.md 기재 pre-existing 실패 + filter_bar/dep_graph/graph_hover 테스트(TSK-05-01 범위, 리팩토링 전 동일 실패 확인됨)

## 비고
- 케이스 분류: A (리팩토링 성공 — 변경 적용 후 단위 테스트 통과)
- `_showPanel` 추출로 `openMergePanel` catch 핸들러 코드 3줄 → 1줄 축소, 에러 메시지 표시 경로와 정상 경로의 패널 열기 동작 일관성 보장
- `state="stale"` 분기 추가는 신규 동작이 아닌 CSS 의도(`[data-state="stale"]` 규칙 존재)와의 정합 복원 — 기존에는 stale state 입력 시 `data-state="unknown"`으로 렌더되어 스타일이 적용되지 않았음
