# monitor-port-per-project: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor-launcher.py` | `stop_server_by_project()`와 `stop_server()` 양쪽에 중복된 SIGTERM/taskkill 플랫폼 분기 로직을 `_send_sigterm(pid, port_label)` 헬퍼로 추출 | Extract Method, Remove Duplication |
| `scripts/monitor-launcher.py` | `stop_server()` 내 early-return 순서를 정리하여 중첩 if 깊이 감소 (PID 파일 없음 → 파싱 실패 → is_alive 분기 순) | Simplify Conditional |

## 테스트 확인

- 결과: PASS
- 실행 명령: `python3 scripts/test_monitor_launcher.py -v`
- 74/74 테스트 통과

## 비고

- 케이스 분류: A (성공 — 변경 적용 후 테스트 통과)
- `_send_sigterm()` 헬퍼는 모듈 내부 전용(언더스코어 prefix)으로 공개 API 변경 없음
- `stop_server()` 의 중첩 if → early-return 리팩토링 후 `stop_server_by_project()`와 제어 흐름 패턴이 통일됨
- 플러그인 캐시(`~/.claude/plugins/cache/dev-tools/dev/1.5.0/scripts/`) 동기화 완료
