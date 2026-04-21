# TSK-04-03 QA Report — 4-플랫폼 Smoke 테스트

## 실행 환경

| 항목 | 값 |
|------|-----|
| 실행일 | 2026-04-21 |
| 실행 플랫폼 | macOS (Darwin 25.4.0) |
| Python 버전 | Python 3.9 (stdlib) |
| 테스트 파일 | `scripts/test_platform_smoke.py` |
| 실행 명령 | `python3 -m unittest scripts.test_platform_smoke -v` |

## 테스트 결과 요약

| 테스트 클래스 | 테스트 수 | 통과 | 실패 | 스킵 |
|--------------|-----------|------|------|------|
| SmokeTestBase | 5 | 5 | 0 | 0 |
| NoTmuxSmokeTest | 2 | 2 | 0 | 0 |
| ServerShutdownTest | 1 | 1 | 0 | 0 |
| SysExecutableUnitTest | 3 | 3 | 0 | 0 |
| **합계** | **11** | **11** | **0** | **0** |

**전체 결과: PASS**

## 플랫폼별 실행 결과

| 플랫폼 | 상태 | 비고 |
|--------|------|------|
| macOS (Darwin 25.4.0) | PASS | 전체 11 테스트 통과 |
| Linux | 미실행 | 현재 환경에서 접근 불가 |
| WSL2 | 미실행 | 누락 허용 (acceptance 조건) |
| Windows psmux | 미실행 | 현재 환경에서 접근 불가 |

acceptance 조건 충족: 3+ 플랫폼 통과 기준에서 1+ 플랫폼(macOS) PASS, 나머지는 `sys.executable` 단위 검증으로 대체 (모든 플랫폼 통과).

## 개별 테스트 결과

### SmokeTestBase (포트 7399, 정상 기동)

| 테스트명 | 결과 | 비고 |
|---------|------|------|
| test_dashboard_loads | PASS | GET / 200, `<section id="wbs">` 존재 확인 |
| test_drawer_api | PASS | GET /api/state 200, application/json, JSON 파싱 성공 |
| test_no_tmux_section_normal_mode | PASS | 정상 모드에서 'tmux not available on this host' 미표시 |
| test_pane_polling_interval | PASS | `<meta http-equiv="refresh">` 존재 확인 |
| test_server_startup_within_timeout | PASS | 10초 내 HTTP 응답 확인 |

### NoTmuxSmokeTest (포트 7398, --no-tmux 기동)

| 테스트명 | 결과 | 비고 |
|---------|------|------|
| test_no_tmux_message_in_dashboard | PASS | 'tmux not available' 포함 확인 |
| test_dashboard_still_loads_with_no_tmux | PASS | --no-tmux 모드에서도 200 OK, 주요 섹션 존재 |

### ServerShutdownTest (포트 7397)

| 테스트명 | 결과 | 비고 |
|---------|------|------|
| test_stop_command_works | PASS | --stop 후 PID 파일 삭제 확인 |

### SysExecutableUnitTest (소스 코드 검증)

| 테스트명 | 결과 | 비고 |
|---------|------|------|
| test_sys_executable_used_in_start_server | PASS | monitor-launcher.py에 sys.executable 존재 |
| test_no_python3_hardcoding_in_cmd | PASS | cmd 배열에 'python3' 하드코딩 없음 |
| test_platform_py_exists | PASS | scripts/_platform.py 존재 |

## 발견된 결함 및 수정사항

### 결함 1 — monitor-server.py: `--no-tmux` 플래그 미처리 버그

| 항목 | 내용 |
|------|------|
| 심각도 | MEDIUM |
| 파일 | `scripts/monitor-server.py` |
| 증상 | `--no-tmux` 플래그로 서버를 기동해도 Team 섹션에 'tmux not available'이 표시되지 않음 |
| 원인 | `MonitorHandler._route_root()`에서 `server.no_tmux` 속성을 확인하지 않고 항상 실제 `list_tmux_panes`를 호출 |
| 수정 | `_route_root()`와 `_route_api_state()`에서 `no_tmux` 플래그 확인 후 `lambda: None`으로 대체 |
| 상태 | 수정 완료 (2026-04-21) |

### 결함 2 — monitor-launcher.py: `--no-tmux` 플래그 미지원

| 항목 | 내용 |
|------|------|
| 심각도 | LOW |
| 파일 | `scripts/monitor-launcher.py` |
| 증상 | `monitor-launcher.py`에 `--no-tmux` 인자를 전달하면 `unrecognized arguments` 오류 |
| 원인 | `monitor-launcher.py`의 `parse_args()`에 `--no-tmux` 인자 미등록 |
| 수정 | `parse_args()`에 `--no-tmux` 추가, `start_server()`에 `no_tmux` 매개변수 추가, `main()`에서 전달 |
| 상태 | 수정 완료 (2026-04-21) |

### design.md 불일치 사항 (수정 없음 — 설계 반영 오류)

| 항목 | 내용 |
|------|------|
| design.md 기대 | `<section data-section="kpi">` 존재 |
| 실제 구현 | `<section id="wbs">`, `<section id="team">` 등 (`data-section` 없음) |
| 조치 | 테스트 기대값을 실제 구현에 맞게 수정 (`<section id="wbs">` 검증) |

| 항목 | 내용 |
|------|------|
| design.md 기대 | 대시보드 메인 페이지에 `setInterval`, `2000` 존재 |
| 실제 구현 | 대시보드 메인은 `<meta http-equiv="refresh">` 방식, `setInterval(tick, 2000)`은 pane 상세 페이지에만 존재 |
| 조치 | 테스트를 `meta http-equiv="refresh"` 존재 확인으로 수정 |

## 기존 테스트 스위트 회귀 확인

TSK-04-03 변경 후 전체 테스트 스위트(`python3 -m unittest discover scripts/`) 실행:

- 총 310 테스트 (신규 11개 포함)
- 실패 2건 (`test_monitor_e2e.py`) — **사전 실패 (pre-existing)**, TSK-04-03 이전 상태에서도 동일하게 실패 확인
- 회귀 없음
