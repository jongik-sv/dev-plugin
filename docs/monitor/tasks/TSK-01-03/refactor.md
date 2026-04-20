# TSK-01-03: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| scripts/monitor-server.py | `scan_signals` 내부의 두 벌로 반복되던 `os.walk` + `_signal_entry` 루프를 `_walk_signal_entries(root, scope)` 헬퍼로 추출하고, `isdir` 사전체크를 헬퍼로 흡수 (shared·agent-pool 두 경로가 동일한 2줄 호출로 수렴) | Extract Method, Remove Duplication |
| scripts/monitor-server.py | `list_tmux_panes`의 `except TimeoutExpired` / `except (OSError, SubprocessError)` 두 블록을 하나의 튜플 except로 통합 (동일 반환 `[]`) | Consolidate Conditional / Simplify Error Handling |
| scripts/monitor-server.py | `capture_pane`의 returncode≠0 에러 메시지 포맷 두 갈래(stderr 有/無)를 `detail = stderr if stderr else "exited with code N"` 단일 템플릿(`{detail} (pane {id})`)으로 통합 | Simplify Conditional |
| scripts/monitor-server.py | magic value(`"-500"`, `2`, `3`)를 `_CAPTURE_PANE_SCROLLBACK` / `_LIST_PANES_TIMEOUT` / `_CAPTURE_PANE_TIMEOUT` 상수로 승격하고 subprocess.run/타임아웃 메시지에서 단일 출처 참조 | Replace Magic Number, Introduce Named Constant |

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m unittest discover -s scripts -p "test_monitor*.py" -v`
- 44 tests, 0 failures, 0 errors (0.029s). 린트 `python3 -m py_compile scripts/monitor-server.py` exit 0.

## 비고
- 케이스 분류: **A (리팩토링 성공)** — 품질 개선 반영 후 기존 44건 유닛 테스트가 그대로 통과. 동작 보존 확인.
- 타임아웃 상수화는 테스트가 `kwargs.get("timeout") == 2 / 3` 로 정수 동등성을 검증하므로(`_LIST_PANES_TIMEOUT=2`, `_CAPTURE_PANE_TIMEOUT=3`) 기존 테스트 수정 없이 호환. `-500` 상수도 `assertIn("-500", args_list)` 를 그대로 만족.
- `capture_pane` 에러 메시지 포맷 통합은 외부 계약상 "stderr 문자열 그대로 반환"이라는 TSK acceptance만 만족하면 되며, 테스트(`test_returns_stderr_string_for_nonexistent_pane`)는 `"%9999"` / `"can't find pane"` 의 substring 포함만 검증하므로 안전.
- `list_tmux_panes` except 통합은 `shell=False` + 리스트 인자 + 고정 timeout 전제에서 세 예외 분기가 모두 동일 반환(`[]`)이라 조건 갈래 제거가 무해.
