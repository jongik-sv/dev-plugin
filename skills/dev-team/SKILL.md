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
- `--on-fail strict|bypass|fast`: 테스트 실패 시 동작 모드 (기본값: `bypass`)

예:
- `/dev-team WP-04` — 기본 `docs/` 사용, 권장 모델 적용
- `/dev-team p1 WP-01` — 서브프로젝트 `docs/p1/` 사용
- `/dev-team p1 WP-01 WP-02 --team-size 5`
- `/dev-team p1` — 서브프로젝트 `docs/p1/`에서 자동 선정
- `/dev-team p1 WP-01 --model opus` — 전 단계 Opus
- `/dev-team WP-04 --on-fail strict` — 테스트 실패 시 중단(강력 검증)
- `/dev-team WP-04 --on-fail fast` — 테스트 실패 시 즉시 다음 진행(속도 우선)

## 0. 인자 파싱 및 설정

### 0-1. 인자 파싱

Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/args-parse.py dev-team $ARGUMENTS
```
JSON 출력에서 추출:
- `docs_dir`, `subproject`, `wp_ids[]`, `options.team_size`, `options.model`, `options.on_fail`
- `WINDOW_SUFFIX`: 서브프로젝트 있으면 `-{subproject}`, 없으면 빈 문자열
- `SHARED_SIGNAL_DIR`: `{TEMP_DIR}/claude-signals/{PROJECT_NAME}{WINDOW_SUFFIX}`

### 0-2. 설정 변수

파싱 결과와 기본값으로부터 다음 변수를 확정한다:

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `TEAM_SIZE` | 3 | 개발팀원 수 (스폰·할당 상한) |
| `TEMP_DIR` | `/tmp` (Unix) / `$TEMP` (Windows) | 임시 파일 루트 디렉토리 |
| `DOCS_DIR` | `docs` 또는 `docs/{SUBPROJECT}` | wbs/PRD/TRD/tasks 경로 루트 |
| `WINDOW_SUFFIX` | `` 또는 `-{SUBPROJECT}` | tmux 창 이름·시그널 디렉토리 suffix |
| `SHARED_SIGNAL_DIR` | `{TEMP_DIR}/claude-signals/{PROJECT_NAME}{WINDOW_SUFFIX}` | 팀리더↔WP 리더↔팀원 간 공유 시그널 디렉토리 (절대 경로 필수 — `references/signal-protocol.md` 참조) |
| `SESSION` | 현재 tmux 세션 이름 | 모든 tmux 명령의 세션 prefix |
| `MAX_ESCALATION` | 2 | task 실패 시 에스컬레이션 재시도 횟수 (1차=동일모델, 2차=Opus). 소진 시 ON_FAIL 동작 |
| `ON_FAIL` | `bypass` | 테스트 실패 시 동작 모드. `strict`=WP 중단, `bypass`=에스컬레이션→임시완료, `fast`=즉시 임시완료(재시도 없음) |
| `MODEL_OVERRIDE` | (없음) | `--model opus` 지정 시 `"opus"`. 미지정 시 Phase별 권장 모델 자동 적용 |
| `WP_LEADER_MODEL` | `sonnet` | WP 리더 claude 프로세스의 모델. `--model opus` 시 `opus` |
| `WORKER_MODEL` | `sonnet` | Worker pane claude 프로세스의 모델. `--model opus` 시 `opus` |

### 0-3. 모델 전파 체계

| 계층 | 기본 (`--model` 미지정) | `--model opus` |
|------|-------------------------|----------------|
| 팀리더 (현재 세션) | 사용자 기본 모델 | Opus |
| WP 리더 / Worker | Sonnet (스케줄링·DDTR 오케스트레이션) | Opus |
| Phase 서브에이전트 | 설계=Opus, 개발=Sonnet, 테스트=Haiku, 리팩토링=Sonnet | 전 계층 Opus |

> 💡 오케스트레이션 계층은 Sonnet으로 비용 절감, 실제 설계 작업만 Opus로 품질 확보 — 의도된 비용 최적화. `--model opus` 지정 시 전 계층 Opus.

> 시그널 파일(`.running`/`.done`/`.failed`/`.shutdown`) 경로 규칙(절대 경로 + 로컬 디스크 필수)과 명령은 `${CLAUDE_PLUGIN_ROOT}/references/signal-protocol.md` 단일 소스 참조.

## 전제조건 확인

- **WBS 모드 전용** — `/dev-team`은 Feature 모드 병렬화를 지원하지 않는다. `args-parse.py`가 `source=feat`을 감지하면(예: `feat:NAME` 토큰) 즉시 중단하고 다음 메시지를 출력한다:
  > ❌ `/dev-team`은 WBS 모드 전용입니다. Feature 모드 병렬화는 지원하지 않습니다.
  > Feature 개발은 `/feat {NAME}`으로 순차 실행하세요.

  이 검증은 `args-parse.py`가 스킬 이름 `dev-team`과 함께 호출될 때 내부에서 수행한다. Feature는 독립 단위로 WBS Task 의존성 그래프를 공유하지 않으므로 병렬 워크트리 분배 의미가 없다.
- **tmux 필수** — `/dev-team`은 tmux 환경에서만 동작한다. 아래 조건이 모두 만족되어야 한다:
  ```bash
  [ -n "$TMUX" ] && command -v tmux > /dev/null
  ```
  미충족 시 **즉시 중단**하고 다음 메시지를 사용자에게 출력한 뒤 **더 이상 진행하지 않는다**:
  > ❌ `/dev-team`은 tmux 세션 내에서만 실행 가능합니다.
  > 현재 환경에 tmux가 없거나 tmux 세션 밖입니다.
  >
  > **tmux가 없는 환경에서는 `/dev {TSK-ID}`로 Task를 하나씩 순차 개발하세요.**
  > 병렬 개발이 필요하면 tmux 설치 후 세션을 시작하고 다시 `/dev-team`을 호출하세요 (`tmux new -s dev`).
  >
  > 비-tmux 폴백 모드는 머지/복구 절차가 정의되지 않아 지원하지 않습니다.

- **플랫폼 지원 및 시그널 경로** — 모든 WP 워크트리는 **동일 호스트·동일 사용자**로 실행되어야 한다. 시그널 디렉토리는 `scripts/_platform.py:TEMP_DIR`(Python `tempfile.gettempdir()`) 기반 절대 경로로 자동 결정된다.

  | 환경 | 상태 | 임시 디렉토리 | 비고 |
  |------|------|---------------|------|
  | macOS / Linux | ✅ 지원 | `$TMPDIR` 또는 `/tmp` | bash/zsh 기본 |
  | WSL2 | ✅ 지원 | WSL 내부 `/tmp` | bash 기본 |
  | 네이티브 Windows | ⚠️ 부분 지원 (psmux) | `%TEMP%` | psmux를 `tmux`로 별칭하여 게이트 통과. 단 psmux pane 기본 쉘이 **PowerShell**이라 POSIX bash 예시는 그대로 동작하지 않음. 완전 지원에는 쉘 예시 재작성 또는 Python 래퍼 전환 필요 (CLAUDE.md의 "CLI 작성 원칙" 참고). |

  **네트워크 파일시스템 금지**: `SHARED_SIGNAL_DIR`을 NFS/SMB/sshfs에 두면 시그널 파일의 rename 원자성이 깨질 수 있다. `$TMPDIR`을 네트워크 경로로 설정한 환경에서는 `/dev-team` 사용 금지. 기본값(`tempfile.gettempdir()`)은 세 플랫폼 모두 로컬 per-user 경로이므로 건드리지 않으면 안전.
- git repo 초기화 여부 확인 (`git status`). 안 되어 있으면 사용자에게 안내 후 중단.
- `tmux list-windows -F '#{window_name}'`로 기존 창 확인.
  - 동일 이름 창이 있으면: **tmux 창(window)만 종료**한다. 아래 항목은 **절대 삭제하지 않는다**:
    - 워크트리: `.claude/worktrees/{WT_NAME}/`
    - 브랜치: `dev/{WT_NAME}`
    - 프롬프트 파일: `{TEMP_DIR}/task-*.txt`, `.claude/worktrees/{WT_NAME}-*.txt`
    - 시그널 디렉토리: `{SHARED_SIGNAL_DIR}/`
  - 기존 워크트리가 존재하면 `wp-setup.py`가 자동으로 재개 모드(resume)로 동작한다. 재개 시 시그널 복원 프로토콜은 다음과 같다 (`references/signal-protocol.md` 참고):

    | 시그널 | 재개 시 동작 | 이유 |
    |--------|-------------|------|
    | `{TSK}.done` | **유지** | 완료 증거 — 리더가 해당 Task 스킵 |
    | `{TSK}.bypassed` | **유지** | bypass 증거 — `.done`과 동일하게 리더가 스킵 |
    | `{TSK}.failed` | **삭제** | 이전 실패 시그널이 남아있으면 재실행이 즉시 실패로 오인됨 → 재실행 허용 |
    | `{TSK}.running` | **stale 감지 후 삭제** | mtime ≥ 5분(heartbeat 2분 × 2.5 grace)이면 stale로 판정, 미만이면 살아있는 워커의 시그널로 간주하여 유지 |
    | `{TSK}-design.done` | wbs.md 상태가 `[dd]`/`[im]`/`[xx]`이면 **없을 경우만 생성** | design 단계 완료 복원 |
    | `{TSK}.done` (신규) | wbs.md 상태가 `[xx]`이면 **없을 경우만 생성** | 메인 WBS가 완료 상태인 경우 복원 |

    복원 결과는 `[{WP}] signals: restore complete (failed-removed=N, running-stale-removed=N, running-live-kept=N)` 로그로 출력된다.

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
 └─ [tmux window: WP-04]   ← WP마다 1개 window (WP-05도 동일 구조 반복)
     ├─ [pane 0] WP 리더    — Task 스케줄링, 시그널 감시, 팀원 관리
     └─ [pane 1~N] 개발팀원 — Task 수행 → 시그널 파일로 완료 보고 → /clear 재활용
```

| 계층 | 단위 | 실행 방식 |
|------|------|-----------|
| Window | WP (리더 + 팀원 N명) | tmux window per WP |
| Pane | 팀원 (고정 {TEAM_SIZE}명, claude 프로세스 재활용) | tmux pane |
| Agent | Phase (DDTR 단계) | 팀원 내부 서브에이전트 |

### 4. DDTR 프롬프트 파일 생성 및 팀 spawn

> tmux 전제조건은 "전제조건 확인" 섹션에서 이미 검증됨. tmux가 없으면 이 단계에 도달하지 않는다.

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

   1. `tmux kill-window -t "${SESSION}:{WT_NAME}"`로 해당 WP 창 종료
   2. `.claude/worktrees/{WT_NAME}`에 미커밋 변경이 있으면 `git add -A && git commit -m "chore: {WT_NAME} leader-crash recovery"`
   3. wbs.md에서 해당 WP의 Task status를 읽어 `[xx]` 완료/그 외 미완료로 분류
   4. `.done` 복구 시그널 생성 — 본문 포맷과 `tmp`→`mv` 원자 전환 절차는 `${CLAUDE_PLUGIN_ROOT}/references/signal-protocol.md`의 "Leader Death Recovery `.done` 포맷" 섹션 단일 소스 참조. `{WT_NAME}`/완료·미완료 목록/최신 커밋 해시를 치환한다.
   5. 정상 머지 플로우로 진행 (`merge-procedure.md` 참조)

---

### 보고 체계

```
팀원 ──시그널 파일──→ WP 리더 ──시그널 파일──→ 팀리더
```

| 방향 | 방법 | 용도 |
|------|------|------|
| WP 리더 → 팀원 (할당) | **tmux send-keys** | Task 프롬프트를 pane에 전송 |
| 팀원 → WP 리더 (보고) | **시그널 파일** | `{SHARED_SIGNAL_DIR}/{TSK-ID}.done` 생성 |
| WP 리더 → 팀원 (초기화) | **tmux send-keys** | `/clear` 전송 (컨텍스트 리셋) |
| WP 리더 → 팀리더 (보고) | **시그널 파일** | `{SHARED_SIGNAL_DIR}/{WT_NAME}.done` 생성 |

> 모든 시그널 경로는 절대 경로 필수 — `references/signal-protocol.md` 경로 규칙 참조.

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

1. **`.shutdown` 마커 생성** (각 WP에 대해, 창 종료 **전**):
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/signal-helper.py shutdown {WT_NAME} {SHARED_SIGNAL_DIR} "user-shutdown"
   ```
   이 마커는 다음 resume 시 `wp-setup.py`가 "사용자가 의도적으로 중단한 WP" 임을 식별하여 **`.done`과 구분**되게 한다. Leader Death 경로(`.done` + 부분 머지)와 달리 `.shutdown`은 **머지 트리거가 아니며**, 다음 resume 시 자동 제거 + state.json 기반 정상 재개된다.

2. **WP 리더 tmux 창 종료** (각 WP 창에 대해):
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

3. **보존 대상** (절대 삭제하지 않는다):
   - 워크트리: `.claude/worktrees/{WT_NAME}/`
   - 브랜치: `dev/{WT_NAME}`
   - 프롬프트 파일: `{TEMP_DIR}/task-*.txt`, `.claude/worktrees/{WT_NAME}-prompt.txt`
   - 시그널 디렉토리: `{SHARED_SIGNAL_DIR}/`

4. **종료 보고**: 현재 진행 상황을 사용자에게 요약 보고 (WP별 완료/진행중/미시작 Task 수).

**Leader Death vs Graceful Shutdown vs Bypass 시그널 대비**:

| 경로 | 생성 시그널 | 머지 트리거 | Resume 동작 |
|------|------------|-------------|-------------|
| Leader Death (비정상 종료) | `.done` (메타 포함) | ✅ 자동 조기 머지 | 완료 WP로 스킵 (미완료 Task는 수동 `/dev` 재실행 필요) |
| Graceful Shutdown (사용자 중단) | `.shutdown` | ❌ 머지 안 함 | wp-setup.py가 `.shutdown` 제거 후 state.json 기반 정상 재개 |
| Task Bypass (에스컬레��션 소진) | `.bypassed` (task 레벨) | ❌ (WP `.done`에 포함) | 유지 — 의존 task 차단 해제, state.json `bypassed: true` |

> 워크트리와 프롬프트를 보존하면 이후 `/dev-team`을 다시 실행할 때 `wp-setup.py`가 기존 워크트리를 감지하여 재활용한다.

### 5. 결과 통합 (팀리더)

`${CLAUDE_PLUGIN_ROOT}/skills/dev-team/references/merge-procedure.md`를 Read하여 머지 절차를 따른다.

WP 완료 시그널(`{SHARED_SIGNAL_DIR}/{WT_NAME}.done`) 감지 시 → **(A) 조기 머지** 실행.
모든 WP 완료 후 → **(B) 전체 완료 머지**로 미처리 WP 순차 머지.
