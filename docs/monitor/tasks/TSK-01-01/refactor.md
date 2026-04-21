# TSK-01-01: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor-server.py` | `MonitorHandler._route_root()`에서 인라인으로 중복 실행하던 scan/signal 집계 로직을 `_build_state_snapshot()` 재사용으로 교체. 약 15줄 → 5줄로 축소 | Remove Duplication, Extract Method (함수 재사용) |

**변경 상세**: `_route_root()`가 `scan_tasks`, `scan_features`, `scan_signals`, `_classify_signal_scopes`, `list_tmux_panes`를 직접 호출하고 `model` dict를 수동 조립하던 방식에서, `_handle_api_state`와 동일한 `_build_state_snapshot()` 헬퍼를 호출하는 방식으로 통일. `refresh_seconds` 키만 `{**snapshot, "refresh_seconds": ...}` spread로 추가. `_server_attr()` 헬퍼도 기존과 동일하게 재사용.

## 테스트 확인

- 결과: PASS
- 실행 명령: `python3 -m unittest discover -s scripts -p "test_monitor*.py" -v`
- 통과: 178 / 178 (skipped 9 — E2E, 서버 미기동)

## 비고

- 케이스 분류: A (리팩토링 성공 — 변경 적용 후 테스트 통과)
- `render_dashboard(model)`이 수신하는 model dict의 키 구조는 `_build_state_snapshot()` 반환값과 동일하므로 동작 보존이 보장됨. `refresh_seconds` 키는 snapshot에 없어 spread 추가로 보완.
