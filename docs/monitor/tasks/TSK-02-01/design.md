# TSK-02-01: SKILL.md 작성 및 기동 + PID 관리 - 설계

## 요구사항 확인

- `skills/dev-monitor/SKILL.md` 파일을 완성하여, 사용자가 `/dev-monitor [--port N] [--docs DIR]` 명령으로 `scripts/monitor-server.py`를 백그라운드로 기동하고 URL을 출력받을 수 있어야 한다.
- PID 파일(`${TMPDIR}/dev-monitor-{port}.pid`)을 통해 중복 기동을 방지(idempotent)하고, 좀비 프로세스 감지 후 재기동을 지원해야 한다.
- `sys.executable`을 사용하여 Python 실행파일을 참조하며, macOS/Linux와 Windows(psmux) 두 경로를 분기하여 프로세스를 detach한다.

## 타겟 앱

- **경로**: N/A (단일 앱 — 플러그인 루트 자체)
- **근거**: 이 Task는 Claude Code 플러그인의 스킬 파일(SKILL.md)을 작성하는 infra Task로, 별도 앱 구조가 없다.

## 구현 방향

- 기존 placeholder `skills/dev-monitor/SKILL.md`를 완전한 스킬 본문으로 교체한다.
- SKILL.md 실행 절차는 Claude가 Bash 도구로 Python 인라인 스크립트를 실행하는 지시문 형식으로 작성한다.
- 기동 로직(PID 체크, 소켓 바인딩 테스트, Popen detach, PID 기록)은 `scripts/monitor-launcher.py`라는 별도 Python 헬퍼 스크립트로 분리하여, SKILL.md가 이를 호출하는 구조로 구현한다.
- 플랫폼 감지는 `sys.platform == "win32"` 분기로, Windows는 `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP` 플래그를, 그 외는 `start_new_session=True`를 사용한다.
- `sys.executable`을 사용, `python3` 하드코딩 금지.

## 파일 계획

**경로 기준:** 모든 파일 경로는 프로젝트 루트 기준으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `skills/dev-monitor/SKILL.md` | /dev-monitor 스킬 본문 — YAML frontmatter + `$ARGUMENTS` 파싱 + 기동 플로우 지시 | 수정 (placeholder → 완성본) |
| `scripts/monitor-launcher.py` | PID 체크·소켓 바인딩 테스트·Popen detach·PID 기록·`--stop`/`--status` 처리를 담당하는 Python 헬퍼 스크립트 | 신규 |

## 진입점 (Entry Points)

N/A — `domain=infra`, UI가 없는 Task.

## 주요 구조

### `skills/dev-monitor/SKILL.md`

YAML frontmatter (`name: dev-monitor`, `description`에 자연어 트리거 포함)와 다음 실행 절차로 구성된다:

1. **0. 인자 파싱**: `$ARGUMENTS`에서 `--port`(기본 7321), `--docs`(기본 `docs`), `--stop`, `--status` 추출
2. **1. 기동 플로우**: Bash 도구로 `scripts/monitor-launcher.py` 호출

### `scripts/monitor-launcher.py`

| 함수/상수 | 책임 |
|-----------|------|
| `parse_args()` | `argparse`로 `--port`, `--docs`, `--project-root`, `--stop`, `--status` 파싱 |
| `pid_file_path(port)` | `TEMP_DIR / f"dev-monitor-{port}.pid"` 경로 반환 |
| `log_file_path(port)` | `TEMP_DIR / f"dev-monitor-{port}.log"` 경로 반환 |
| `is_alive(pid)` | `os.kill(pid, 0)` 으로 생존 확인, `OSError` → False |
| `read_pid(pid_path)` | PID 파일 읽기, 없거나 파싱 불가 → None |
| `test_port(port)` | `socket.socket().bind(('127.0.0.1', port))` 바인딩 테스트, 성공 시 True |
| `start_server(port, docs, project_root)` | `subprocess.Popen` detach (플랫폼 분기) + PID 파일 기록 |
| `stop_server(port)` | PID 파일 읽기 → `os.kill(pid, signal.SIGTERM)` → PID 파일 삭제 |
| `main()` | 서브커맨드 분기: `--stop` → `stop_server`, `--status` → alive 출력, default → 기동 플로우 |

## 데이터 흐름

```
$ARGUMENTS
  → SKILL.md 절차 → Bash 도구: "python {monitor-launcher.py} --port N --docs D --project-root $PWD"
    → parse_args()
    → [--stop] stop_server(port) → kill + PID 파일 삭제
    → [--status] read_pid → is_alive → 출력
    → [default]
        read_pid → is_alive? → YES: URL 재출력 종료
                             → NO (좀비 또는 없음):
                   test_port → 실패: 안내 메시지 종료
                   start_server(port, docs, project_root)
                     → subprocess.Popen(monitor-server.py, detach flags)
                     → PID 파일 기록
                     → "http://localhost:{port}" 출력
```

## 설계 결정 (대안이 있는 경우만)

**결정 1: 기동 로직을 별도 `scripts/monitor-launcher.py`로 분리**
- **결정**: `monitor-launcher.py` 헬퍼 스크립트를 신규 작성하고 SKILL.md에서 이를 호출
- **대안**: SKILL.md 내 Bash 도구 코드 블록에서 Python 원라이너/heredoc으로 모든 로직 인라인 처리
- **근거**: 기동 로직이 50줄 이상(PID 체크 + 소켓 테스트 + 플랫폼 분기 + stop/status 서브커맨드)이므로 인라인 heredoc으로 넣으면 SKILL.md가 읽기 어렵고 유지보수가 힘들다. 기존 스크립트 관례(`scripts/_platform.py` 등)와 일관성도 유지된다.

**결정 2: `--stop` / `--status` 서브커맨드 monitor-launcher.py에서 처리**
- **결정**: TRD §9.2 명세에 따라 `--stop`, `--status` 플래그를 포함
- **대안**: 기동(launch)만 구현하고 stop/status는 사용자가 직접 kill 명령 사용
- **근거**: 수용 기준에 "동일 포트 재기동 → 기존 PID 재사용 안내"가 있어 상태 조회가 필수이며, `--stop`은 사용자 DX에 필수다.

**결정 3: `DETACHED_PROCESS` 플래그 안전 참조**
- **결정**: `getattr(subprocess, 'DETACHED_PROCESS', 0x00000008)` 패턴 사용
- **대안**: `subprocess.DETACHED_PROCESS` 직접 참조
- **근거**: Python 3.8 이하에서 `subprocess.DETACHED_PROCESS` 상수가 없을 수 있어 `getattr` 패턴으로 방어

## 선행 조건

- `skills/dev-monitor/` 디렉터리가 TSK-00-01에서 이미 생성되어 있음 (확인 완료).
- `scripts/_platform.py`가 존재하여 `TEMP_DIR` 상수를 import할 수 있음 (확인 완료).
- `scripts/monitor-server.py`는 TSK-02-02에서 구현될 예정. monitor-launcher.py는 서버 스크립트를 `Popen`으로 실행만 하므로, 파일이 없으면 Popen이 실패하나 launcher 자체의 PID/소켓 로직은 독립적으로 테스트 가능.

## 리스크

- **MEDIUM**: SKILL.md 내 코드 블록에서 `$PWD` 환경변수가 Claude Code의 Bash 도구 실행 컨텍스트와 다를 수 있다. `os.getcwd()`를 Python 코드 내에서 사용하거나 `--project-root`를 SKILL.md에서 명시적으로 전달하도록 설계한다.
- **MEDIUM**: Windows(psmux) 환경에서 `DETACHED_PROCESS` flag가 없는 Python 버전 대응. `getattr(subprocess, 'DETACHED_PROCESS', 0x00000008)` 패턴으로 완화.
- **LOW**: PID 파일 경로에 공백이 포함된 TMPDIR에서 발생할 수 있는 쉘 분리 문제. Python `pathlib.Path`로 처리하면 무관.
- **LOW**: `socket.bind` 테스트 후 Popen 사이의 TOCTOU 경쟁. 로컬 개발 환경에서 무시 가능.

## QA 체크리스트

- [ ] **정상 케이스 — 최초 기동**: SKILL.md 실행 시 `http://localhost:7321` URL이 출력되고, `${TMPDIR}/dev-monitor-7321.pid`가 생성되며, 내용이 유효한 PID 숫자이다.
- [ ] **정상 케이스 — 커스텀 포트**: `--port 8080`으로 실행 시 `http://localhost:8080`이 출력되고 PID 파일은 `dev-monitor-8080.pid`이다.
- [ ] **idempotent 재기동**: 동일 포트로 두 번 실행했을 때 두 번째 실행에서 기존 PID 재사용 메시지가 출력되고 새 프로세스가 생성되지 않는다.
- [ ] **좀비 PID 재기동**: PID 파일은 있으나 해당 프로세스가 죽은 상태에서 실행하면 재기동에 성공하고 PID 파일이 새 PID로 갱신된다.
- [ ] **포트 충돌**: 7321 포트가 이미 다른 프로세스에 의해 점유된 상태에서 실행하면 "포트 충돌" 메시지와 `--port` 옵션 힌트가 출력되고 새 프로세스가 생성되지 않는다.
- [ ] **`--stop` 플래그**: 기동 중인 서버에 `--stop`으로 실행하면 프로세스가 종료되고 PID 파일이 삭제된다.
- [ ] **`--status` 플래그**: 기동 중이면 "running at http://localhost:{port}" 출력, 미기동 상태이면 "not running" 메시지가 출력된다.
- [ ] **`sys.executable` 사용 확인**: `monitor-launcher.py` 코드에 `python3` 하드코딩이 없고 `sys.executable`을 사용한다.
- [ ] **로그 파일 생성**: 기동 후 `${TMPDIR}/dev-monitor-{port}.log`가 존재한다.
- [ ] **플랫폼 분기 코드 확인**: `monitor-launcher.py`에 `sys.platform == "win32"` 분기가 존재하고, Windows 경로는 `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP` 플래그를, 그 외는 `start_new_session=True`를 사용한다.
- [ ] **YAML frontmatter 확인**: `skills/dev-monitor/SKILL.md`의 `name`이 `dev-monitor`이고 `description`에 "모니터링", "대시보드", "monitor", "dashboard" 키워드가 포함된다.
