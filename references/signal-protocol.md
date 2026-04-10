# 시그널 프로토콜

Task 상태를 파일 기반 시그널로 추적한다. 원자적 전환을 위해 `tmp` → `mv` 패턴을 사용한다.

## 시그널 파일

| 상태 | 파일 | 생성 시점 |
|------|------|-----------|
| 실행 중 | `{id}.running` | task 시작 직후 |
| 완료 | `{id}.done` | task 성공 완료 시 |
| 실패 | `{id}.failed` | task 실패 시 |

## signal-helper.py 명령

모든 명령: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/signal-helper.py <command> <id> <signal-dir> [arg]`

### Worker용 (시그널 생성)

```bash
# 시작
python3 signal-helper.py start {id} {SIGNAL_DIR}

# 완료
python3 signal-helper.py done {id} {SIGNAL_DIR} "메시지"

# 실패
python3 signal-helper.py fail {id} {SIGNAL_DIR} "에러 내용"

# 하트비트 (2분 간격)
python3 signal-helper.py heartbeat {id} {SIGNAL_DIR}
```

### 리더용 (시그널 대기/확인)

```bash
# 대기 (timeout 초, 0=무제한)
python3 signal-helper.py wait {id} {SIGNAL_DIR} {timeout}
# 출력: DONE:{id} 또는 FAILED:{id}

# 시작 대기 (.running/.done/.failed 중 하나가 나타날 때까지, 기본 120초)
python3 signal-helper.py wait-running {id} {SIGNAL_DIR} {timeout}
# 출력: RUNNING:{id} 또는 DONE:{id} 또는 FAILED:{id}

# 상태 확인 (비차단)
python3 signal-helper.py check {id} {SIGNAL_DIR}
# 출력: running | done | failed | none
```

## 규칙

- 시그널 파일 내용은 자동으로 **50줄까지 절삭**됨. 대량 출력은 별도 파일에 기록
- worktree 환경에서는 반드시 **절대 경로** 사용 (상대 경로는 의도한 위치로 해석되지 않음)
- `.done` 또는 `.failed` 시그널을 반드시 생성해야 리더가 완료를 감지함
