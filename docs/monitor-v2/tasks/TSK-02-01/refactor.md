# TSK-02-01: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor-server.py` (`render_dashboard`) | `refresh = _refresh_seconds(model)` dead code 제거 — TSK-01-06에서 `<meta http-equiv="refresh">`를 JS 폴링으로 교체하면서 `render_dashboard` 내 `refresh` 변수가 계산되지만 사용되지 않는 상태였음 | Remove Dead Code |

## 테스트 확인

- 결과: PASS
- 실행 명령: `python3 scripts/test_monitor_e2e.py`
- 단위 테스트: frontend 도메인이므로 N/A
- E2E: 12/12 통과

## 비고

- 케이스 분류: A (성공)
- `_DASHBOARD_JS` JS 코드는 이미 정돈된 상태였음 (`_setDrawerOpen`/`_hasAttr` 헬퍼가 이미 적용됨).
  Python 레이어에서 `render_dashboard`의 `refresh` dead code만 제거.
- `_refresh_seconds` 함수 자체는 `_route_root`에서 `server.refresh_seconds`를 model에 주입하고
  `MonitorHandler` 서버 설정에 사용되므로 삭제하지 않음 (render_dashboard 내 호출만 제거).
