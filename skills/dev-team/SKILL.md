---
name: dev-team
description: "WP(Work Package) 단위로 하위 Task들을 병렬 분배하여 개발. 사용법: /dev-team [SUBPROJECT] WP-04 또는 /dev-team p1 WP-01 또는 /dev-team p1 (자동 선정) 또는 /dev-team WP-04 --team-size 5"
---

# /dev-team - WP 단위 팀 병렬 개발

인자: `$ARGUMENTS` ([SUBPROJECT] + WP-ID + 옵션)
- SUBPROJECT: (옵션) 하위 프로젝트 폴더 이름. 예: `p1` → `docs/p1/` 하위에서 동작
- WP-ID: 1개 이상 (공백 구분). 생략 시 자동 선정
- `--team-size N`: 개발팀원 수 (기본값: 3)
- `--model opus`: 전 단계 Opus 모델 사용 (미지정 시 Phase별 권장 모델 자동 적용)

예:
- `/dev-team WP-04` — 기본 `docs/` 사용, 권장 모델 적용
- `/dev-team p1 WP-01` — 서브프로젝트 `docs/p1/` 사용
- `/dev-team p1 WP-01 WP-02 --team-size 5`
- `/dev-team p1` — 서브프로젝트 `docs/p1/`에서 자동 선정
- `/dev-team p1 WP-01 --model opus` — 전 단계 Opus

## 0. 인자 파싱

Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/args-parse.py dev-team $ARGUMENTS
```
JSON 출력에서 추출:
- `docs_dir`, `subproject`, `wp_ids[]`, `options.team_size`, `options.model`
- `WINDOW_SUFFIX`: 서브프로젝트 있으면 `-{subproject}`, 없으면 빈 문자열
- `SHARED_SIGNAL_DIR`: `{TEMP_DIR}/claude-signals/{PROJECT_NAME}{WINDOW_SUFFIX}`

## 0. 설정 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `TEAM_SIZE` | 3 | 개발팀원 수 (스폰·할당 상한) |
| `TEMP_DIR` | `/tmp` (Unix) / `$TEMP` (Windows) | 임시 파일 루트 디렉토리 |
| `DOCS_DIR` | `docs` 또는 `docs/{SUBPROJECT}` | wbs/PRD/TRD/tasks 경로 루트 |
| `WINDOW_SUFFIX` | `` 또는 `-{SUBPROJECT}` | tmux 창 이름·시그널 디렉토리 suffix |
| `SHARED_SIGNAL_DIR` | `{TEMP_DIR}/claude-signals/{PROJECT_NAME}{WINDOW_SUFFIX}` | 팀리더↔WP 리더↔팀원 간 공유 시그널 디렉토리 (**절대 경로**) |
| `SESSION` | 현재 tmux 세션 이름 | 모든 tmux 명령의 세션 prefix |
| `MAX_RETRIES` | 1 | task 실패 시 재시도 횟수 |
| `MODEL_OVERRIDE` | (없음) | `--model opus` 지정 시 `"opus"`. 미지정 시 Phase별 권장 모델 자동 적용 |
| `WP_LEADER_MODEL` | `sonnet` | WP 리더 claude 프로세스의 모델. `--model opus` 시 `opus` |
| `WORKER_MODEL` | `sonnet` | Worker pane claude 프로세스의 모델. `--model opus` 시 `opus` |

### 모델 전파 체계

```
--model opus 미지정 (기본):
  팀리더 (현재 세션)     → 사용자 기본 모델
  WP 리더 (tmux window) → Sonnet  (스케줄링/시그널 감시 + 오케스트레이션)
  Worker (tmux pane)    → Sonnet  (DDTR 오케스트레이션)
  Phase 서브에이전트      → 설계=Opus, 개발=Sonnet, 테스트=Haiku, 리팩토링=Sonnet

--model opus 지정:
  전 계층 Opus
```
> ⚠️ **시그널 경로는 반드시 절대 경로**를 사용한다.

### 시그널 프로토콜

시그널 파일(`.running`/`.done`/`.failed`)로 Task 상태를 추적한다. 전체 프로토콜: `${CLAUDE_PLUGIN_ROOT}/references/signal-protocol.md` 참조.

## 전제조건 확인
- git repo 초기화 여부 확인 (`git status`). 안 되어 있으면 사용자에게 안내 후 중단.
- `tmux list-windows -F '#{window_name}'`로 기존 창 확인.
  - 동일 이름 창이 있으면: **tmux 창(window)만 종료**한다. 아래 항목은 **절대 삭제하지 않는다**:
    - 워크트리: `.claude/worktrees/{WT_NAME}/`
    - 브랜치: `dev/{WT_NAME}`
    - 프롬프트 파일: `{TEMP_DIR}/task-*.txt`, `.claude/worktrees/{WT_NAME}-*.txt`
    - 시그널 디렉토리: `{SHARED_SIGNAL_DIR}/`
  - 기존 워크트리가 존재하면 `wp-setup.py`가 자동으로 재개 모드(resume)로 동작하여 시그널을 복원하고 완료된 Task를 건너뛴다.

### 플랫폼 감지 및 변수 초기화

```bash
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$(uname -r)" == *Microsoft* || "$(uname -r)" == *microsoft* ]]; then
  PLATFORM="windows"; TEMP_DIR="${TEMP:-${TMP:-/tmp}}"
else
  PLATFORM="unix"; TEMP_DIR="/tmp"
fi
SESSION=$(tmux display-message -p '#{session_name}')
```

## 실행 절차

### 1. WP 선정 및 Task 수집

#### WP-ID가 없는 경우 (자동 선정)

Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md - --resumable-wps
```
JSON 출력에서 실행 가능 WP 목록을 확인한다. 사용자에게 보여주고 확인 후 진행.

#### WP-ID가 있는 경우

각 WP에 대해 Task 수집:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {WP-ID} --tasks-pending
```
JSON 출력에서 미완료 Task 목록을 확인한다.

### 2. 의존성 분석 및 실행 계획

wbs-parse.py의 출력을 dep-analysis.py로 파이프:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {WP-ID} --tasks-pending | \
  python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dep-analysis.py
```
JSON 출력에서 레벨별 실행 계획과 순환 의존 여부를 확인한다.

### 3. 아키텍처

```
팀리더 (현재 세션)
 ├─ [tmux window: WP-04]
 │   ├─ [pane 0] WP 리더 (claude) ──→ 시그널 파일로 팀리더에게 보고
 │   ├─ [pane 1] 개발팀원1 (claude) ──→ 시그널 파일로 완료 보고 ──→ /clear 후 재활용
 │   ├─ [pane 2] 개발팀원2 (claude) ──→ 시그널 파일로 완료 보고 ──→ /clear 후 재활용
 │   └─ [pane 3] 개발팀원3 (claude) ──→ 시그널 파일로 완료 보고 ──→ /clear 후 재활용
 │
 └─ [tmux window: WP-05]
     ├─ [pane 0] WP 리더 (claude)
     ├─ [pane 1] 개발팀원1 (claude)
     ├─ [pane 2] 개발팀원2 (claude)
     └─ [pane 3] 개발팀원3 (claude)
```

| 계층 | 단위 | 역할 | 실행 방식 |
|------|------|------|-----------|
| Window | WP | WP 리더 (pane 0): Task 스케줄링, 팀원 관리 | tmux window |
| Pane | 팀원 | 고정 {TEAM_SIZE}명, Task를 순차 수행 | tmux pane (claude 프로세스, 재활용) |
| Agent | Phase | 개발 단계 실행 | 팀원 내부 서브에이전트 |

### 4. DDTR 프롬프트 파일 생성 및 팀 spawn

#### (A) tmux 환경 — 셋업 스크립트 사용 ← 권장

**tmux 환경 감지**:
```bash
[ -n "$TMUX" ] && command -v tmux > /dev/null
```

현재 세션이 **팀리더** 역할을 한다. 셋업 스크립트(`scripts/wp-setup.py`)로 worktree 생성, 프롬프트/manifest 생성, tmux spawn을 **일괄 처리**한다.

> ⚠️ 스크립트가 생성하는 모든 시그널 경로는 `SHARED_SIGNAL_DIR` (프로젝트 레벨) 하나만 사용한다.

1. **config JSON 생성** — `${CLAUDE_PLUGIN_ROOT}/skills/dev-team/references/config-schema.md`를 Read하여 스키마를 확인하고, `{TEMP_DIR}/wp-setup-config.json`을 Write 도구로 작성한다.

2. **셋업 스크립트 실행**:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/wp-setup.py" "${TEMP_DIR}/wp-setup-config.json"
   ```

   스크립트가 **자동** 수행하는 작업:
   | 작업 | 생성 파일 |
   |------|-----------|
   | worktree 생성 (또는 재개 감지 + 시그널 복원) | `.claude/worktrees/{WT_NAME}/` |
   | wbs.md에서 task 블록 추출 + DDTR 프롬프트 치환 | `{TEMP_DIR}/task-{TSK-ID}.txt` |
   | 미설계 task용 설계 전용 프롬프트 생성 | `{TEMP_DIR}/task-{TSK-ID}-design.txt` |
   | WP 리더 프롬프트 치환 | `.claude/worktrees/{WT_NAME}-prompt.txt` |
   | team manifest 생성 | `{TEMP_DIR}/team-manifest-{WT_NAME}.md` |
   | runner script + tmux window spawn | `.claude/worktrees/{WT_NAME}-run.sh` |

   > `[xx]` 상태 Task는 자동 제외. 모든 Task가 `[xx]`인 WP는 즉시 `.done` 시그널 생성 후 스킵.

3. **WP별 완료 감지 및 조기 머지**:
   팀리더는 각 WP의 시그널 파일을 Bash `run_in_background`로 감시한다:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/signal-helper.py wait {WT_NAME} {SHARED_SIGNAL_DIR} 14400
   ```
   시그널 감지 시: 해당 WP의 tmux 창 정리 → 즉시 5단계(A) 조기 머지 실행

   **백업 — 창 닫힘 + 리더 사망 감지**:
   ```bash
   TEAM_WINDOWS=({spawn한 WP 창 이름들})
   while true; do
     ALL_DONE=true
     for w in "${TEAM_WINDOWS[@]}"; do
       if tmux list-windows -F '#{window_name}' | grep -q "^${w}$"; then
         ALL_DONE=false
         # 리더 pane(index 0) 사망 감지
         LEADER_DEAD=$(tmux display-message -t "${SESSION}:${w}.0" -p '#{pane_dead}' 2>/dev/null)
         SIGNAL_EXISTS=$(ls ${SHARED_SIGNAL_DIR}/${w}.done 2>/dev/null)
         if [ "$LEADER_DEAD" = "1" ] && [ -z "$SIGNAL_EXISTS" ]; then
           echo "WP_LEADER_DEAD:${w}"
         fi
       fi
     done
     if $ALL_DONE; then echo "ALL_TEAM_MEMBERS_DONE"; break; fi
     sleep 30
   done
   ```

   **`WP_LEADER_DEAD:{WT_NAME}` 감지 시 복구 절차**:

   1. 해당 WP의 tmux 창 전체 종료:
      ```bash
      tmux kill-window -t "${SESSION}:{WT_NAME}" 2>/dev/null
      ```
   2. worktree의 미커밋 변경 커밋:
      ```bash
      UNCOMMITTED=$(git -C .claude/worktrees/{WT_NAME} status --short 2>/dev/null)
      if [ -n "$UNCOMMITTED" ]; then
        git -C .claude/worktrees/{WT_NAME} add -A
        git -C .claude/worktrees/{WT_NAME} commit -m "chore: {WT_NAME} leader-crash recovery"
      fi
      ```
   3. Task 완료 현황 확인 — wbs.md에서 해당 WP의 Task status를 읽어 완료/미완료를 파악
   4. 복구 시그널 생성:
      ```bash
      cat > {SHARED_SIGNAL_DIR}/{WT_NAME}.done.tmp << 'EOF'
      [{WT_NAME} 리더 비정상 종료 — 자동 복구]
      - 완료 Task: {[xx] 상태 TSK-ID 목록}
      - 미완료 Task: {그 외 TSK-ID 목록}
      - 리뷰: 스킵
      - 커밋: {최신 커밋 해시}
      - 특이사항: WP 리더 비정상 종료. 자동 복구로 시그널 생성.
      EOF
      mv {SHARED_SIGNAL_DIR}/{WT_NAME}.done.tmp {SHARED_SIGNAL_DIR}/{WT_NAME}.done
      ```
   5. 정상 머지 플로우로 진행 (merge-procedure 참조)

#### (B) tmux 외 환경 — agent-pool 패턴 적용

각 WP마다 Agent 도구로 서브에이전트를 **병렬** 실행한다:

- **isolation**: "worktree"
- **model**: `--model opus`이면 `"opus"`, 미지정 시 `"sonnet"` (DDTR 오케스트레이션)
- **mode**: "auto"
- **run_in_background**: true

에이전트 프롬프트에 해당 WP의 Task 목록과 DDTR 프롬프트를 포함한다.
/agent-pool 스킬의 풀 관리 패턴(슬롯 유지, 개별 보충)을 따른다.

모든 에이전트 완료 통보 후 5단계로 진행한다.

---

### 보고 체계

```
팀원 ──시그널 파일──→ WP 리더 ──시그널 파일──→ 팀리더
```

| 방향 | 방법 | 용도 |
|------|------|------|
| WP 리더 → 팀원 (할당) | **tmux send-keys** | Task 프롬프트를 pane에 전송 |
| 팀원 → WP 리더 (보고) | **시그널 파일** | `{SHARED_SIGNAL_DIR}/{TSK-ID}.done` 생성 (**절대 경로**) |
| WP 리더 → 팀원 (초기화) | **tmux send-keys** | `/clear` 전송 (컨텍스트 리셋) |
| WP 리더 → 팀리더 (보고) | **시그널 파일** | `{SHARED_SIGNAL_DIR}/{WT_NAME}.done` 생성 (**절대 경로**) |

### cross-WP 동기화

다른 WP의 Task에 의존하는 경우, 시그널 파일로 동기화한다:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/signal-helper.py wait {의존-TSK-ID} {SHARED_SIGNAL_DIR}
```

### WP 리더 프롬프트

`.claude/worktrees/{WT_NAME}-prompt.txt`를 생성한다 (`{WT_NAME}` = `{WP-ID}{WINDOW_SUFFIX}`).
**템플릿**: `references/wp-leader-prompt.md` 파일을 Read하여 `{WP-ID}`, `{WT_NAME}`, `{TEAM_SIZE}`, `{SHARED_SIGNAL_DIR}` 등 변수를 치환한다.

### 사용자 종료 요청 시 (Graceful Shutdown)

사용자가 "종료", "중단", "stop" 등을 요청하면 **워크트리와 프롬프트를 보존**한 채 tmux 창만 정리한다.

1. **WP 리더 tmux 창 종료** (각 WP 창에 대해):
   ```bash
   for PANE_ID in $(tmux list-panes -t "${SESSION}:${WT_NAME}" -F '#{pane_id}'); do
     tmux send-keys -t "${PANE_ID}" Escape 2>/dev/null
   done
   ```
   ```bash
   for PANE_ID in $(tmux list-panes -t "${SESSION}:${WT_NAME}" -F '#{pane_id}'); do
     tmux send-keys -t "${PANE_ID}" '/exit' Enter 2>/dev/null
   done
   ```
   ```bash
   sleep 3
   tmux kill-window -t "${SESSION}:${WT_NAME}" 2>/dev/null
   ```

2. **보존 대상** (절대 삭제하지 않는다):
   - 워크트리: `.claude/worktrees/{WT_NAME}/`
   - 브랜치: `dev/{WT_NAME}`
   - 프롬프트 파일: `{TEMP_DIR}/task-*.txt`, `.claude/worktrees/{WT_NAME}-prompt.txt`
   - 시그널 디렉토리: `{SHARED_SIGNAL_DIR}/`

3. **종료 보고**: 현재 진행 상황을 사용자에게 요약 보고 (WP별 완료/진행중/미시작 Task 수)

> 워크트리와 프롬프트를 보존하면 이후 `/dev-team`을 다시 실행할 때 `wp-setup.py`가 기존 워크트리를 감지하여 재활용한다.

### 5. 결과 통합 (팀리더)

`${CLAUDE_PLUGIN_ROOT}/skills/dev-team/references/merge-procedure.md`를 Read하여 머지 절차를 따른다.

WP 완료 시그널(`{SHARED_SIGNAL_DIR}/{WT_NAME}.done`) 감지 시 → **(A) 조기 머지** 실행.
모든 WP 완료 후 → **(B) 전체 완료 머지**로 미처리 WP 순차 머지.
