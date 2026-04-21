# TSK-02-02: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| `scripts/monitor-launcher.py` | `pid_file_path` / `log_file_path`의 중복 문자열 패턴을 내부 헬퍼 `_temp_path(port, ext)`로 추출 | Extract Method, Remove Duplication |
| `scripts/monitor-launcher.py` | `stop_server()`에 Windows 플랫폼 분기 추가 — `sys.platform == "win32"` 시 `taskkill /PID {pid} /F` 호출 (설계 결정 2 구현 완료) | Introduce Guard Clause (platform branch) |
| `scripts/monitor-launcher.py` | `main()`의 좀비 PID 파일 정리 조건 `if existing_pid is not None and pid_path.exists():` → `if existing_pid is not None:` 로 단순화 (`unlink(missing_ok=True)` 위임) | Simplify Conditional |
| `scripts/monitor-server.py` | `cleanup_pid_file()`의 `except Exception` → `except OSError`로 예외 범위 축소 | Narrow Exception |

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m unittest discover -s scripts -p "test_monitor*.py" -v`
- 64 테스트 모두 통과 (0.327초)

## 비고
- 케이스 분류: **A (성공)** — 리팩토링 변경 적용 후 테스트 전부 통과
- `stop_server()`의 Windows 분기는 설계 문서(design.md 결정 2)에 명시된 사항이었으나 dev-build에서 구현 누락된 항목으로, 이번 리팩토링에서 보완됨
- 공개 인터페이스(`pid_file_path`, `log_file_path`, `stop_server`, `cleanup_pid_file`)의 시그니처·반환값·동작은 모두 유지됨
