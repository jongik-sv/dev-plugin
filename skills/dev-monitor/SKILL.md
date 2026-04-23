---
name: dev-monitor
description: "개발 활동 모니터링 대시보드 서버를 기동한다. 키워드: 모니터링, 대시보드, monitor, dashboard, WBS 진행 현황, 태스크 상태, dev-monitor 시작. 사용법: /dev-monitor [--port N] [--docs DIR] [--stop] [--status]"
---

# /dev-monitor — 개발 활동 모니터링 대시보드

WBS 태스크 진행 현황 · tmux pane 상태 · 시그널 파일을 실시간으로 보여주는 대시보드 서버를 기동한다.

인자: `$ARGUMENTS` (`[--port N] [--docs DIR] [--stop] [--status]`)

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--port N` | 자동 탐색 (7321~7399) | 서버 바인딩 포트 (명시 시 고정, 생략 시 프로젝트별 자동 할당) |
| `--docs DIR` | `docs` | 스캔할 docs 디렉터리 |
| `--stop` | — | 현재 프로젝트의 서버 종료 (`--port N` 명시 시 포트 기준) |
| `--status` | — | 현재 프로젝트의 서버 실행 상태 확인 (`--port N` 명시 시 포트 기준) |

## 0. 인자 파싱

`$ARGUMENTS`에서 다음을 추출한다 (없으면 기본값 사용):

- `PORT`: `--port` 값 (기본 `7321`)
- `DOCS`: `--docs` 값 (기본 `docs`)
- `ACTION`: `--stop` → `stop`, `--status` → `status`, 그 외 → `start`

## 1. 기동 플로우

Bash 도구로 실행:

```bash
"$(python3 -c 'import sys; print(sys.executable)')" "${CLAUDE_PLUGIN_ROOT}/scripts/monitor-launcher.py" \
  --port {PORT} \
  --docs {DOCS} \
  --project-root "$PWD" \
  {ACTION_FLAG}
```

> **참고**: `sys.executable`을 사용하는 이유는 `python3` 하드코딩 금지 원칙 때문이다 (CLAUDE.md). Windows(psmux)에서 MS Store App Execution Alias가 `python3`을 가로채 rc=9009를 반환할 수 있다.

여기서 `{ACTION_FLAG}`는:
- `ACTION=stop` → `--stop`
- `ACTION=status` → `--status`
- `ACTION=start` → (플래그 없음)

`{CLAUDE_PLUGIN_ROOT}`는 플러그인 루트 경로로 치환한다.

### 플로우 상세 (ACTION=start)

launcher가 내부적으로 다음 순서로 실행한다:

1. **프로젝트 PID 파일 존재 + 프로세스 생존** → URL 재출력 후 종료 (중복 기동 방지, idempotent). PID 파일 키는 `sha256(realpath(project_root))[:12]` 해시 기반
2. **포트 결정**: `--port N` 명시 시 해당 포트 사용; 미지정 시 7321~7399 범위에서 자동 탐색
3. **socket bind 테스트** → 포트 점유 시 안내 메시지 + `--port` 옵션 힌트 출력
4. **`subprocess.Popen` detach 기동**
   - macOS/Linux: `start_new_session=True`
   - Windows psmux: `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`
5. **JSON PID 파일 기록**: `${TMPDIR}/dev-monitor-{project_hash}.pid` → `{"pid": N, "port": N}`
6. **URL 출력**: `http://localhost:{port}`

로그는 `${TMPDIR}/dev-monitor-{project_hash}.log`에 append된다.

#### 프로젝트별 독립 실행

같은 포트 범위(7321~7399)를 여러 프로젝트가 공유한다. 각 프로젝트는 고유한 해시 기반 PID 파일(`dev-monitor-{hash}.pid`)을 가지므로 서로 다른 프로젝트의 서버가 동시에 실행될 수 있다. `--stop` / `--status`를 포트 없이 실행하면 현재 프로젝트(`$PWD`)의 서버만 조작한다.

## 2. 완료 보고

launcher 출력을 그대로 사용자에게 전달한다.

- **기동 성공**: `http://localhost:{port}` URL을 출력하고 브라우저에서 열도록 안내
- **이미 실행 중**: 기존 PID 재사용 안내
- **포트 충돌**: 오류 메시지 + `--port` 힌트 안내
- **--stop**: 종료 결과 안내
- **--status**: 실행 여부 안내

### 서버 응답 확인 (선택)

기동 성공 후 서버가 실제로 응답하는지 확인할 때는 `http-probe.py`를 사용한다.
> curl은 일부 CLI 프록시가 출력을 요약해 파이프 파서가 오작동할 수 있어 http-probe.py 사용 권장.

```bash
"$(python3 -c 'import sys; print(sys.executable)')" "${CLAUDE_PLUGIN_ROOT}/scripts/http-probe.py" \
  http://localhost:{PORT}/ --status
# 200 이면 정상 기동
```
