# TSK-01-04: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| scripts/monitor-server.py | 순서-유지 그룹핑 중복(`_section_wbs`/`_section_team`/`_section_subagents`)을 공용 헬퍼 `_group_preserving_order(items, key)`로 추출 | Extract Method, Remove Duplication |
| scripts/monitor-server.py | 6개 섹션이 반복하던 `<section id="..."><h2>...</h2>...</section>` 뼈대를 `_section_wrap(anchor, heading, body)` + `_empty_section(anchor, heading, message, css)` 헬퍼로 정리 | Extract Method, Remove Duplication |
| scripts/monitor-server.py | `_status_badge`의 status→(emoji,label,css) 매핑을 모듈 상수 `_STATUS_BADGE_MAP` + 기본값 `_STATUS_BADGE_DEFAULT`로 승격 | Replace Conditional with Lookup Table |
| scripts/monitor-server.py | `_section_subagents` 루프 내부에서 매번 재정의되던 `css_map`을 모듈 상수 `_SUBAGENT_BADGE_CSS`로 이동, pane/subagent 행 렌더를 `_render_pane_row` / `_render_subagent_row`로 분리 | Extract Method, Extract Constant |
| scripts/monitor-server.py | `_render_task_row`의 정상/raw_error 두 분기 — 중간 status 셀만 다르고 5개 셀은 동일하던 구조를 단일 반환문으로 통합 | Simplify Conditional, Remove Duplication |
| scripts/monitor-server.py | `_section_phase_history`의 중첩 `_sort_key` 내부 함수를 lambda로 단순화 | Inline |
| scripts/monitor-server.py | `chr(10).join(...)` 가독성 저하 → `"\n".join(...)` 및 `_section_wrap` 경유로 치환 | Rename / Use Readable Literal |
| scripts/monitor-server.py | `from typing import` 에 `Dict` 추가(그룹핑 헬퍼 타입 힌트용) | Type Annotation Completeness |

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m unittest discover -s scripts -p "test_monitor*.py"`
  - 결과: `Ran 106 tests in 0.033s  OK (skipped=6)` — skip 6건은 TSK-01-01 HTTP 부트스트랩 미구현에 의한 E2E 파일 레벨 `skipUnless` (test-report.md에 명시된 기존 상태와 동일).
- lint: `python3 -m py_compile scripts/monitor-server.py` → exit 0.
- 되돌린 범위 없음 (전 구간 PASS).

## 비고
- 케이스 분류: **A (성공)** — 리팩토링 변경이 모두 적용된 상태에서 단위 테스트 106/106 통과.
- 라인 수: 1289 → 1286 LOC. 본질 감소폭은 작으나 6개 섹션이 공유하던 뼈대 중복이 `_section_wrap`/`_empty_section`으로 응축되어 **향후 TSK-01-05(pane capture 엔드포인트)에서 동일 뼈대를 재사용할 때 추가 중복 없이 확장 가능**.
- 배지 매핑표(`_STATUS_BADGE_MAP`)를 상수화하여 design.md의 상태 배지 테이블과 1:1 매핑되는 선언적 구조가 됨 — 향후 새 상태 코드 추가 시 매핑 상수만 갱신하면 되고 `_status_badge` 본체 수정 불요.
- 동작 보존 기준선(단위 테스트 68건 → 전체 106건 중 해당 파트)이 유지되었고 외부 도메인 0건 조건(`NoExternalDomainTests`)도 여전히 통과.
