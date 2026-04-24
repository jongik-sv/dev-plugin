# TSK-04-02: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor-server.py` | `renderInfoPopoverHtml`의 `row` helper: `(value===null\|\|value===undefined)` → `value==null` | Simplify Conditional |
| `scripts/monitor-server.py` | `positionPopover` 단문자 변수 `r`, `pw`, `ph` → `btnRect`, `popW`, `popH` | Rename |
| `scripts/monitor-server.py` | `close()` 내부에 detached DOM 가드 주석 통합 + click handler의 중복 `openBtn=null` 가드 제거 | Remove Duplication |

## 테스트 확인
- 결과: PASS
- 실행 명령:
  - `python3 scripts/test_monitor_info_popover.py` → 25/25 OK
  - `python3 scripts/test_monitor_e2e.py TskTooltipE2ETests` → 7/7 OK

## 비고
- 케이스 분류: A (성공)
- `value==null` 은 ES5에서 `value === null || value === undefined` 와 동일하게 동작하는 관용 패턴 (loose equality null check). 동작 변경 없음.
- detached DOM 가드(5s 폴링 이후 `openBtn` 참조 stale)는 `close()` 내 주석으로 이동하고, click handler 내 별도 `if(!document.contains(openBtn)){...}` 블록(열기 직후 즉시 확인하는 불필요한 체크)을 제거하여 책임을 `close()` 한 곳에서 관리하도록 정리.
