# TSK-02-02: --stop / --status 서브커맨드 - 설계

## 요구사항 확인
- `skills/dev-monitor/SKILL.md`에 `--stop [--port PORT]`와 `--status [--port PORT]` 서브커맨드를 추가한다.
- `--stop`: PID 파일에서 PID를 읽어 프로세스에 SIGTERM을 전송하고 PID 파일을 삭제한다. 프로세스가 이미 없는 경우(좀비 PID)에도 PID 파일만 삭제 후 정상 종료한다.
- `--status`: PID 파일 존재 여부와 프로세스 생존 여부를 체크하여 기동 상태와 접속 URL을 출력한다. 미기동이면 "not running"을 출력한다.
- 서버 측(`scripts/monitor-server.py`)에서 SIGTERM 핸들러를 등록하여, 수신 시 `serve_forever()` 루프를 중단하고 `finally` 블록에서 PID 파일을 삭제한다.
- Windows psmux 환경에서는 `os.kill()`이 SIGTERM을 지원하지 않으므로 `taskkill /PID {pid} /F`로 대체한다.

## 타겟 앱
- **경로**: N/A (단일 앱)
- **근거**: dev-plugin은 단일 앱 플러그인 레포지토리다.

## 구현 방향
- `skills/dev-monitor/SKILL.md`에 `--stop`/`--status` 처리 로직을 추가한다. `$ARGUMENTS`에서 서브커맨드를 파싱하여 기존 기동 플로우와 분기한다.
- `--stop` 흐름: PID 파일 읽기 → `os.kill(pid, 0)` 생존 확인 → 살아있으면 플랫폼별 종료 신호 전송 → PID 파일 삭제.
- `--status` 흐름: PID 파일 읽기 → `os.kill(pid, 0)` 생존 확인 → 결과와 URL 출력.
- `scripts/monitor-server.py`에 SIGTERM 핸들러(`signal.signal(signal.SIGTERM, handler)`)를 추가하고, `finally` 블록에서 PID 파일을 삭제한다.
- 플랫폼 분기: `sys.platform == "win32"` 조건으로 `taskkill` vs `os.kill(pid, signal.SIGTERM)` 선택.

## 파일 계획

**경로 기준:** 모든 파일 경로는 **프로젝트 루트 기준**으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `skills/dev-monitor/SKILL.md` | `--stop`/`--status` 서브커맨드 파싱 및 처리 로직 추가 | 수정 |
| `scripts/monitor-server.py` | SIGTERM 핸들러 등록, `finally` 블록에서 PID 파일 삭제 | 수정 |

## 진입점 (Entry Points)

N/A — domain=infra, UI 없음.

## 주요 구조

### `skills/dev-monitor/SKILL.md` — 추가될 로직

1. **서브커맨드 파싱 섹션**
   - `$ARGUMENTS`에서 `--stop`, `--status`, `--port PORT` 토큰 추출
   - `--stop` 또는 `--status` 플래그 존재 시 각 처리 경로로 분기 (기존 기동 플로우와 상호 배타적)

2. **`--stop` 처리 (Python 인라인 스크립트)**
   - `_read_pid(pid_file) -> int | None`: PID 파일에서 정수 읽기. 파일 없으면 None 반환.
   - `_process_alive(pid) -> bool`: `os.kill(pid, 0)`으로 생존 확인. `OSError` → False.
   - `_terminate_process(pid)`: 플랫폼별 종료
     - `sys.platform != "win32"`: `os.kill(pid, signal.SIGTERM)`
     - `sys.platform == "win32"`: `subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False)`
   - 제어 흐름:
     - PID 파일 없음 → `"not running"` 출력, exit 0
     - PID 파일 있음 + 프로세스 없음(좀비) → PID 파일 삭제 + `"Process already stopped; PID file removed."` 출력, exit 0
     - PID 파일 있음 + 프로세스 살아있음 → `_terminate_process(pid)` 호출 + PID 파일 삭제 + `"Stopped."` 출력, exit 0

3. **`--status` 처리 (Python 인라인 스크립트)**
   - `_check_status(pid_file, port) -> None`: PID 파일 읽기 → `_process_alive(pid)` 확인
   - 출력:
     - 기동 중: `"running: PID {pid} — http://localhost:{port}"`
     - 미기동 (파일 없음 또는 좀비): `"not running"`
   - 주의: `--status`는 PID 파일을 수정하지 않는다(읽기 전용).

### `scripts/monitor-server.py` — 추가될 로직

4. **SIGTERM 핸들러 (`_setup_signal_handler(server, pid_file)`)**
   - macOS/Linux에만 등록: `if sys.platform != "win32": signal.signal(signal.SIGTERM, handler)`
   - 핸들러 내부: `threading.Thread(target=server.shutdown, daemon=True).start()`
     (핸들러는 임의 스레드에서 호출될 수 있으므로, `server.shutdown()`을 별도 스레드로 호출하여 데드락 방지)

5. **PID 파일 정리 (`finally` 블록)**
   - `serve_forever()` 완료 후 `finally:` 블록에서 `pid_file.unlink(missing_ok=True)`
   - `pid_file`은 `argparse`에서 계산된 절대 경로 `Path` 객체

## 데이터 흐름

```
# --stop
$ARGUMENTS 파싱 → --stop 감지 → PID 파일 경로 계산
  → PID 파일 없음 → "not running" 출력 → exit 0
  → PID 파일 있음 → pid = int(파일 읽기)
      → os.kill(pid, 0) 실패(좀비) → PID 파일 삭제 → "already stopped" 출력 → exit 0
      → os.kill(pid, 0) 성공        → _terminate_process(pid) → PID 파일 삭제 → "Stopped." → exit 0

# --status
$ARGUMENTS 파싱 → --status 감지 → PID 파일 경로 계산
  → PID 파일 없음 → "not running" 출력
  → PID 파일 있음 → pid = int(파일 읽기)
      → os.kill(pid, 0) 실패 → "not running" 출력
      → os.kill(pid, 0) 성공 → "running: PID {pid} — http://localhost:{port}" 출력

# 서버 측 SIGTERM (macOS/Linux)
SIGTERM 수신 → handler() 호출
  → threading.Thread(target=server.shutdown).start()
  → serve_forever() 반환
  → finally 블록 → pid_file.unlink(missing_ok=True)
  → 프로세스 정상 종료
```

## 설계 결정 (대안이 있는 경우만)

**결정 1 — SKILL.md 내 Python 인라인으로 `--stop`/`--status` 처리**
- **결정**: SKILL.md 내에서 Python 인라인 코드 블록(`python3 -c "..."` 또는 heredoc)으로 처리
- **대안**: 별도 `scripts/monitor-ctl.py` 파일 신규 작성
- **근거**: 로직이 50줄 미만의 단순 처리이므로 별도 파일 없이 SKILL.md에서 직접 처리하여 관리 포인트를 최소화한다. 인라인 코드가 50줄 초과 시 `scripts/monitor-ctl.py` 분리를 재검토한다.

**결정 2 — Windows 종료: `taskkill /F` 사용**
- **결정**: `sys.platform == "win32"` 분기에서 `subprocess.run(["taskkill", "/PID", str(pid), "/F"])` 사용
- **대안**: `os.kill(pid, signal.CTRL_C_EVENT)` 또는 `os.kill(pid, signal.CTRL_BREAK_EVENT)`
- **근거**: TRD §3.2에 명시된 방식이며, `taskkill /F`는 psmux 환경에서도 일관되게 동작한다. `CTRL_C_EVENT`는 콘솔 프로세스에만 유효하여 detach된 프로세스에서 실패할 수 있다.

**결정 3 — SIGTERM 핸들러에서 `server.shutdown()` 별도 스레드 호출**
- **결정**: `threading.Thread(target=server.shutdown, daemon=True).start()`
- **대안**: 핸들러에서 직접(동기) `server.shutdown()` 호출
- **근거**: `ThreadingHTTPServer`의 request 처리 스레드 컨텍스트에서 `serve_forever()` 루프를 직접 중단하면 데드락 가능성이 있다. 별도 스레드로 비동기 호출하여 안전하게 처리한다.

**결정 4 — Windows 서버 측 SIGTERM 핸들러 미등록**
- **결정**: `sys.platform != "win32"` 조건부 등록으로 Windows에서는 SIGTERM 핸들러를 등록하지 않는다
- **대안**: `signal.SIGBREAK` 등록
- **근거**: Windows에서는 `taskkill /F`로 강제 종료되어 핸들러가 실행될 보장이 없다. PID 파일 정리는 `finally` 블록에 위임하되, `taskkill /F` 강제 종료 시 `finally`도 실행되지 않으므로 PID 파일 잔류 허용(기동 시 좀비 감지로 처리).

## 선행 조건
- TSK-02-01: `skills/dev-monitor/SKILL.md` 기본 기동 로직과 `scripts/monitor-server.py`의 PID 파일 기록 구조가 구현되어 있어야 한다. 설계는 TSK-02-01 미완료 상태에서도 진행 가능하나, dev-build는 TSK-02-01 완료 후 진행한다.

## 리스크

- **MEDIUM**: TSK-02-01이 아직 구현되지 않았다. `scripts/monitor-server.py`의 구체적인 코드 구조(PID 파일 경로 변수명, `serve_forever()` 호출 위치, `argparse` 구조)가 확정되어 있어야 SIGTERM 핸들러와 `finally` 블록 삽입 위치를 정확히 결정할 수 있다. 설계는 TRD §8 구조(`if __name__ == "__main__": argparse + serve_forever`)를 따른다고 가정한다.
- **MEDIUM**: Windows psmux 환경에서 `taskkill /F`는 강제 종료라 `finally` 블록이 실행되지 않아 PID 파일이 잔류할 수 있다. 기동 시 좀비 감지 로직(TSK-02-01에서 구현)이 이를 처리하므로 운영 영향은 낮다.
- **LOW**: `threading.Thread(target=server.shutdown, daemon=True).start()` 후 main thread가 `finally` 블록에 즉시 진입하는 타이밍 이슈. `server.shutdown()`은 내부 `_BaseServer.__shutdown_request` 플래그를 세우고 select loop 종료까지 블로킹하므로 정상적으로는 문제 없다.

## QA 체크리스트

dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

### --stop 커맨드
- [ ] 정상: 서버가 기동 중일 때 `--stop` 실행 → 프로세스가 종료되고 PID 파일이 삭제된다.
- [ ] 정상: `--stop` 실행 후 `--status` 실행 → "not running" 출력.
- [ ] 엣지: 서버 미기동(PID 파일 없음) 상태에서 `--stop` 실행 → "not running" 출력 + exit code 0.
- [ ] 엣지: 좀비 PID(PID 파일 존재, 프로세스 없음) 상태에서 `--stop` 실행 → PID 파일 삭제 + 정상 종료 메시지 출력 + exit code 0.
- [ ] 엣지: `--stop --port 8080`처럼 커스텀 포트 지정 시 해당 포트의 PID 파일(`dev-monitor-8080.pid`)만 대상으로 처리한다.

### --status 커맨드
- [ ] 정상: 서버 기동 중 `--status` 실행 → "running: PID {pid} — http://localhost:{port}" 형식 출력.
- [ ] 정상: 서버 미기동 시 `--status` 실행 → "not running" 출력.
- [ ] 엣지: 좀비 PID 상태에서 `--status` 실행 → "not running" 출력 (PID 파일을 수정하지 않는다).
- [ ] 엣지: `--status --port 8080`처럼 커스텀 포트 지정 시 해당 포트의 상태를 출력한다.

### 서버 측 SIGTERM 처리 (macOS/Linux)
- [ ] 정상: 서버 프로세스에 SIGTERM을 전송하면 서버가 정상 종료되고 PID 파일이 삭제된다.
- [ ] 정상: `--stop` 실행 후 서버 프로세스가 3초 이내에 종료된다.
- [ ] 엣지: 비정상 종료(SIGKILL 등)로 PID 파일이 잔류한 상태에서 동일 포트로 재기동 시, 기동 로직(TSK-02-01)의 좀비 감지가 작동하여 정상 기동된다.

### 통합
- [ ] 통합: `--stop` 후 `--status`의 전체 흐름이 일관되게 "not running"을 출력한다.
- [ ] 통합: 기본 포트(7321)와 커스텀 포트(8080) 두 서버가 동시 기동 중일 때, `--stop --port 7321`이 포트 7321 서버만 종료하고 8080은 영향받지 않는다.
