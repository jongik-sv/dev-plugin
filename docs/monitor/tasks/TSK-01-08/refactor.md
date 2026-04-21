# TSK-01-08: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| `scripts/monitor-server.py` | `_RAW_ERROR_CAP` → `_ERROR_CAP` rename — `raw_error` 시절 네이밍 잔재 제거 | Rename |
| `scripts/monitor-server.py` | `_RAW_ERROR_TITLE_CAP` → `_ERROR_TITLE_CAP` rename — 동일 이유 | Rename |
| `scripts/monitor-server.py` | `_cap_error(text: str)` 타입 어노테이션을 `Optional[str]`로 수정 — 실제 None 입력 경로와 어노테이션 일치 | Type Safety |

나머지 TSK-01-08 핵심 구현 (`WorkItem.error`, `badge-warn` CSS, `_render_task_row`, `_make_workitem_from_error`, `_make_workitem_from_state`) 은 이미 dev-build 단계에서 정돈된 상태이며 추가 변경 없음.

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m pytest scripts/test_monitor_scan.py scripts/test_monitor_render.py scripts/test_monitor_api_state.py scripts/test_monitor_pane.py scripts/test_monitor_server.py scripts/test_monitor_server_bootstrap.py scripts/test_monitor_signal_scan.py scripts/test_monitor_tmux.py -v`
- 결과 요약: 198 passed, 4 skipped (E2E 서버 의존 skip — 단위 테스트 전용 실행에서 정상)

## 비고
- 케이스 분류: A (리팩토링 성공 — 변경 적용 후 테스트 통과)
- 상수명 rename은 내부 전용 식별자(`_` prefix) 범위에 한정되어 breaking change 없음.
- `_cap_error`의 None 입력 방어 로직(`if text is None: return ""`)이 이미 존재하므로 어노테이션 수정은 문서화 수준의 정합성 개선이며 동작 변경 없음.
