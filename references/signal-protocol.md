# 시그널 프로토콜

Task 상태를 파일 기반 시그널로 추적한다. 원자적 전환을 위해 `tmp` → `mv` 패턴을 사용한다.

## ⚠️ 경로 규칙 (단일 소스)

**모든 시그널 파일 경로는 반드시 절대 경로를 사용한다.** 이 규칙은 플러그인 전체(dev-team, team-mode, agent-pool, DDTR 워커, WP 리더 프롬프트 등)에서 예외 없이 적용된다. 상대 경로(`./signals/`, `../.signals/`)는 worktree·서브쉘·서브에이전트 등 다양한 실행 컨텍스트에서 해석 실패하므로 금지한다.

- 기본 경로 결정: `scripts/_platform.py:TEMP_DIR`(`tempfile.gettempdir()`) 기반으로 자동 생성 → macOS/Linux/WSL/네이티브 Windows 모두 per-user 로컬 절대 경로
- **로컬 디스크 전용**: `$TMPDIR`을 NFS/SMB/sshfs 경로로 설정한 환경에서는 rename 원자성이 깨져 시그널 유실. 네트워크 파일시스템 위에서 `/dev-team`, `/team-mode`, `/agent-pool` 사용 금지
- **상위 스킬/참조 문서는 이 블록을 인용하라** — 각자 독립적으로 절대 경로 경고를 재작성하지 말 것

## 시그널 파일

| 상태 | 파일 | 생성 시점 | Resume 동작 |
|------|------|-----------|-------------|
| 실행 중 | `{id}.running` | task 시작 직후 | stale 감지 (mtime > 300s) 후 제거 |
| 완료 | `{id}.done` | task 성공 완료 시 (또는 Leader Death 부분 머지) | 유지 (스킵 대상) |
| 실패 | `{id}.failed` | task 실패 시 | 제거 (재실행 허용) |
| 바이패스 | `{id}.bypassed` | 에스컬레이션 재시도 소진 후 WP 리더가 bypass 확정 시 | 유지 (`.done`과 동일하게 스킵 대상) |
| 중단 | `{id}.shutdown` | 사용자 graceful shutdown 시 | 제거 (state.json 기반 정상 재개) |

## signal-helper.py 명령

모든 명령: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/signal-helper.py <command> <id> <signal-dir> [arg]`

스크립트 경로와 `signal-dir` 모두 절대 경로 (위 "경로 규칙" 단일 소스 참조).

### Worker용 (시그널 생성)

```bash
# 시작
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/signal-helper.py start {id} {SIGNAL_DIR}

# 완료
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/signal-helper.py done {id} {SIGNAL_DIR} "메시지"

# 실패
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/signal-helper.py fail {id} {SIGNAL_DIR} "에러 내용"

# 바이패스 (에스컬레이션 재시도 소진 후 WP 리더가 실행)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/signal-helper.py bypass {id} {SIGNAL_DIR} "사유"

# 하트비트 (2분 간격)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/signal-helper.py heartbeat {id} {SIGNAL_DIR}

# 사용자 graceful shutdown 마커 (WP 단위)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/signal-helper.py shutdown {WT_NAME} {SIGNAL_DIR} "user-shutdown"
```

### 리더용 (시그널 대기/확인)

```bash
# 대기 (timeout 초, 0=무제한)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/signal-helper.py wait {id} {SIGNAL_DIR} {timeout}
# 출력: DONE:{id} 또는 FAILED:{id} 또는 BYPASSED:{id}

# 시작 대기 (.running/.done/.failed/.bypassed 중 하나가 나타날 때까지, 기본 120초)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/signal-helper.py wait-running {id} {SIGNAL_DIR} {timeout}
# 출력: RUNNING:{id} 또는 DONE:{id} 또는 FAILED:{id} 또는 BYPASSED:{id}

# 상태 확인 (비차단)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/signal-helper.py check {id} {SIGNAL_DIR}
# 출력: running | done | failed | bypassed | none
```

## 규칙

- 시그널 파일 내용은 자동으로 **50줄까지 절삭**됨. 대량 출력은 별도 파일에 기록
- 경로는 반드시 절대 경로 (위 "경로 규칙" 단일 소스 참조)
- `.done` 또는 `.failed` 시그널을 반드시 생성해야 리더가 완료를 감지함
- `.shutdown`은 사용자 graceful shutdown 시에만 생성. 리더 비정상 종료는 `.done`(부분 머지 포함) 경로를 사용 (`skills/dev-team/SKILL.md` Leader Death 섹션 참조)

## Leader Death Recovery `.done` 포맷 (단일 소스)

WP 리더가 비정상 종료된 상태에서 팀리더가 부분 머지를 위해 생성하는 `.done` 시그널의 본문 템플릿. `skills/dev-team/SKILL.md`의 Leader Death 복구 절차는 이 포맷을 그대로 인용한다.

```
[{WT_NAME} 리더 비정상 종료 — 자동 복구]
- 완료 Task: {[xx] 상태 TSK-ID 목록}
- 미완료 Task: {그 외 TSK-ID 목록}
- 리뷰: 스킵
- 커밋: {최신 커밋 해시}
- 특이사항: WP 리더 비정상 종료. 자동 복구로 시그널 생성.
```

**치환 값 추출 규칙** (state.json은 워크트리 기준):

| 플레이스홀더 | 추출 방법 |
|--------------|-----------|
| `{WT_NAME}` | 팀리더가 알고 있는 WP 워크트리 이름 (`{WP-ID}{WINDOW_SUFFIX}`) |
| `{[xx] 상태 TSK-ID 목록}` | 워크트리 `.claude/worktrees/{WT_NAME}/{DOCS_DIR}/wbs.md`에서 해당 WP Task의 `- status: [xx]`인 TSK-ID 전부 (state.json이 있으면 우선). 쉼표 구분. |
| `{그 외 TSK-ID 목록}` | 같은 WP에서 위 목록에 포함되지 않은 나머지 TSK-ID 전부. 쉼표 구분. 없으면 `-`. |
| `{최신 커밋 해시}` | 워크트리 기준: `cd .claude/worktrees/{WT_NAME} && git rev-parse --short HEAD`. 미커밋 변경이 있어 자동 복구 commit을 만든 경우 그 해시. |

작성 원칙: `tmp` → `mv` 원자 전환 패턴을 사용한다(상단 "시그널 파일" 표의 rename 규칙과 동일).
```bash
cat > {SIGNAL_DIR}/{WT_NAME}.done.tmp <<'EOF'
...위 템플릿 (치환 완료본)...
EOF
mv {SIGNAL_DIR}/{WT_NAME}.done.tmp {SIGNAL_DIR}/{WT_NAME}.done
```
