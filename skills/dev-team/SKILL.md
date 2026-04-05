---
name: dev-team
description: "WP(Work Package) 단위로 하위 Task들을 병렬 분배하여 개발. 사용법: /dev-team WP-04 또는 /dev-team WP-04 WP-05 또는 /dev-team (자동 선정) 또는 /dev-team WP-04 --team-size 5"
---

# /dev-team - WP 단위 팀 병렬 개발

인자: `$ARGUMENTS` (WP-ID + 옵션)
- WP-ID: 1개 이상 (공백 구분). 생략 시 자동 선정
- `--team-size N`: 개발팀원 수 (기본값: 3)

## 0. 설정 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `TEAM_SIZE` | 3 | 개발팀원 수 (스폰·할당 상한) |
| `SHARED_SIGNAL_DIR` | `/tmp/claude-signals/{PROJECT_NAME}` | 팀리더↔WP 리더↔팀원 간 공유 시그널 디렉토리 (**절대 경로**) |
| `MAX_RETRIES` | 1 | task 실패 시 재시도 횟수 |

> `--team-size N` 옵션으로 변경 가능. 아래 문서에서 `{TEAM_SIZE}`로 참조.
> ⚠️ **시그널 경로는 반드시 절대 경로**를 사용한다. 상대 경로(`../.signals/`)는 worktree 내부에서 의도한 위치로 해석되지 않아 시그널 감지가 실패할 수 있다.

### 시그널 프로토콜

| 상태 | 파일 | 생성 시점 |
|------|------|-----------|
| 실행 중 | `{TSK-ID}.running` | 팀원이 task 시작 직후 |
| 완료 | `{TSK-ID}.done` | 팀원이 DDTR 4단계 + 커밋 완료 시 |
| 실패 | `{TSK-ID}.failed` | 팀원이 task 실패 시 |

모든 시그널 파일은 `tmp + mv` 패턴으로 원자적으로 생성한다.

## 전제조건 확인
- git repo 초기화 여부 확인 (`git status`). 안 되어 있으면 사용자에게 안내 후 중단.
- `tmux list-windows -F '#{window_name}'`로 기존 창 확인. 동일 이름 창이 있으면 사용자에게 확인 후 정리.

## 실행 절차

### 1. WP 선정 및 Task 수집

#### 인자 파싱
- `$ARGUMENTS`에서 WP-ID 목록과 `--team-size N` 옵션을 추출한다
- WP-ID가 없으면 자동 선정 로직 실행

#### 인자가 있는 경우
- 각 WP-ID에 대해 `docs/wbs.md`에서 `## {WP-ID}:` 섹션을 찾는다

#### 인자가 없는 경우 (자동 선정)
1. `docs/wbs.md`에서 `progress: 100%`가 아닌 모든 WP를 수집
2. 각 WP의 하위 Task 중 status가 `[ ]`이고, depends가 모두 충족된(`[xx]` 또는 해당 WP 외부에서 이미 완료) Task가 1개 이상 있는 WP를 **실행 가능 WP**로 판정
3. 실행 가능 WP를 **모두 선택**하여 병렬 실행
4. 선택된 WP 목록을 사용자에게 보여주고 확인 후 진행

#### Task 수집
- 선택된 각 WP 하위의 모든 `### TSK-XX-XX:` Task 블록을 수집한다
- 각 Task에서 추출: TSK-ID, domain, status, depends

### 2. 의존성 분석 및 실행 계획

각 WP 내부에서 Task의 **실행 레벨**을 산출한다:

```
Level 0: depends가 모두 완료이거나, 선택된 WP 외부 Task에만 의존 (즉시 시작 가능)
Level 1: WP 내 Level 0 Task에 의존
Level 2: WP 내 Level 1 Task에 의존
...
```

**같은 Level의 Task는 domain에 관계없이 병렬 실행한다.**
다른 WP의 Task에 의존하는 경우, 시그널 파일로 완료를 감지한다 (cross-WP 동기화 참조).

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

#### DDTR 할당 프롬프트 템플릿

각 Task에 대해 `/tmp/task-{TSK-ID}.txt`를 생성한다.
**템플릿**: `references/ddtr-prompt-template.md` 파일을 Read하여 `{TSK-ID}`, `{SHARED_SIGNAL_DIR}` 등 변수를 치환한다.

#### (A) tmux 환경 — team-mode 패턴 적용 ← 권장

**tmux 환경 감지**:
```bash
[ -n "$TMUX" ] && command -v tmux > /dev/null
```

현재 세션이 **팀리더** 역할을 한다. 각 WP마다:

1. **환경 준비** (worktree + 시그널 디렉토리):
   ```bash
   # 프로젝트 이름 및 시그널 디렉토리 확정
   PROJECT_NAME="$(basename "$(pwd)")"
   SHARED_SIGNAL_DIR="/tmp/claude-signals/${PROJECT_NAME}"

   # worktree 생성
   git worktree add .claude/worktrees/{WP-ID} -b dev/{WP-ID}

   # 시그널 디렉토리 생성
   mkdir -p "${SHARED_SIGNAL_DIR}"
   ```

2. **Task manifest 생성**: `/tmp/team-manifest-{WP-ID}.md`를 team-mode 형식으로 작성한다:
   ```markdown
   # Configuration
   - team_size: {TEAM_SIZE}
   - window_name: {WP-ID}
   - signal_dir: {SHARED_SIGNAL_DIR}

   ## Tasks

   ### {TSK-ID}
   - depends: {의존 TSK-ID 목록 또는 (none)}
   - prompt_file: /tmp/task-{TSK-ID}.txt
   ```
   > ⚠️ `signal_dir`은 반드시 **절대 경로**로 지정한다 (`{SHARED_SIGNAL_DIR}` = `/tmp/claude-signals/{PROJECT_NAME}`)

3. **WP 리더 프롬프트 생성**: `.claude/worktrees/{WP-ID}-prompt.txt`를 아래 "WP 리더 프롬프트" 섹션 내용으로 작성한다

4. **WP 리더 spawn**:
   ```bash
   # 래퍼 스크립트 생성
   cat > .claude/worktrees/{WP-ID}-run.sh << 'SCRIPT_EOF'
   #!/bin/bash
   cd "$(dirname "$0")/{WP-ID}"
   exec claude --dangerously-skip-permissions "$(<../"{WP-ID}-prompt.txt")"
   SCRIPT_EOF
   chmod +x .claude/worktrees/{WP-ID}-run.sh

   # tmux 창으로 실행 (--workdir로 worktree 경로 지정)
   tmux new-window -n "{WP-ID}" .claude/worktrees/{WP-ID}-run.sh
   tmux set-option -w -t {WP-ID} pane-border-status top
   tmux set-option -w -t {WP-ID} pane-border-format " #{pane_index}: #{@label} "
   ```

5. **WP별 완료 감지 및 조기 머지**:
   팀리더는 각 WP의 시그널 파일을 Bash `run_in_background`로 감시한다:
   ```bash
   SIGNAL_DIR="/tmp/claude-signals/{PROJECT_NAME}"
   WP_ID="{WP-ID}"
   while [ ! -f "${SIGNAL_DIR}/${WP_ID}.done" ]; do sleep 15; done
   echo "WP_DONE:${WP_ID}"
   cat "${SIGNAL_DIR}/${WP_ID}.done"
   ```
   시그널 감지 시: 해당 WP의 tmux 창 정리 → 즉시 5단계(A) 조기 머지 실행

   **백업 — 창 닫힘 감지**:
   ```bash
   TEAM_WINDOWS=({spawn한 WP 창 이름들})
   while true; do
     ALL_DONE=true
     for w in "${TEAM_WINDOWS[@]}"; do
       if tmux list-windows -F '#{window_name}' | grep -q "^${w}$"; then
         ALL_DONE=false; break
       fi
     done
     if $ALL_DONE; then echo "ALL_TEAM_MEMBERS_DONE"; break; fi
     sleep 30
   done
   ```

#### (B) tmux 외 환경 — agent-pool 패턴 적용

각 WP마다 Agent 도구로 서브에이전트를 **병렬** 실행한다:

- **isolation**: "worktree"
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
| WP 리더 → 팀리더 (보고) | **시그널 파일** | `{SHARED_SIGNAL_DIR}/{WP-ID}.done` 생성 (**절대 경로**) |

### cross-WP 동기화

다른 WP의 Task에 의존하는 경우, 시그널 파일로 동기화한다.

**팀원이 Task 완료 시** (절대 경로 사용):
```bash
touch {SHARED_SIGNAL_DIR}/{TSK-ID}.done
```

**WP 리더가 cross-WP 의존 Task를 할당하기 전** (절대 경로 사용):
```bash
while [ ! -f {SHARED_SIGNAL_DIR}/{의존-TSK-ID}.done ]; do sleep 10; done
```

예: TSK-04-05가 TSK-05-02에 의존 → WP-04 리더가 `{SHARED_SIGNAL_DIR}/TSK-05-02.done` 파일을 확인 후 TSK-04-05 할당.

> ⚠️ 상대 경로(`../.signals/`) 사용 금지 — worktree 내부에서 상대 경로는 `/tmp/claude-signals/{PROJECT_NAME}/`가 아닌 worktree 내부의 다른 위치로 해석될 수 있다.

---

### WP 리더 프롬프트

`.claude/worktrees/{WP-ID}-prompt.txt`를 생성한다.
**템플릿**: `references/wp-leader-prompt.md` 파일을 Read하여 `{WP-ID}`, `{TEAM_SIZE}`, `{SHARED_SIGNAL_DIR}` 등 변수를 치환한다.

### 5. 결과 통합 (팀리더)

#### (A) 개별 WP 조기 머지 — WP 완료 즉시 실행

다른 WP가 아직 실행 중이더라도, 완료된 WP는 즉시 머지할 수 있다.
`{SHARED_SIGNAL_DIR}/{WP-ID}.done` 시그널 파일이 생성되면 해당 WP를 머지한다:

0. **산출물 검증** (머지 전 필수):
   WP 내 모든 Task에 대해 아래 파일이 존재하는지 확인한다:
   - `docs/tasks/{TSK-ID}/design.md` — 설계 산출물
   - `docs/tasks/{TSK-ID}/test-report.md` — 테스트 결과
   - `docs/tasks/{TSK-ID}/refactor.md` — 리팩토링 내역
   - `docs/wbs.md` 해당 Task의 status가 `[xx]`인지 확인

   누락된 산출물이 있으면 시그널 내용과 대조하여 판단:
   - 시그널에 실패 내용이 있으면 → 해당 Task를 부분 완료로 기록
   - 파일은 없지만 시그널은 성공이면 → WP 리더에게 재확인 요청 후 진행

1. 해당 WP의 tmux 창(window) 종료:
```bash
for i in $(tmux list-panes -t {WP-ID} -F '#{pane_index}'); do
  tmux send-keys -t {WP-ID}.$i Escape 2>/dev/null
  sleep 1
  tmux send-keys -t {WP-ID}.$i '/exit' Enter 2>/dev/null
done
sleep 3
tmux kill-window -t {WP-ID} 2>/dev/null
```

2. main에 미커밋 변경이 있으면 먼저 커밋
3. 머지 실행:
```bash
git merge --no-ff dev/{WP-ID} -m "Merge dev/{WP-ID}: {WP 제목} ({TSK-ID 목록})"
```
4. 충돌 발생 시: 수동 해결 후 `git add` + `git commit --no-edit`
5. worktree + 브랜치 정리:
```bash
git worktree remove --force .claude/worktrees/{WP-ID}
git branch -d dev/{WP-ID}
```
6. `docs/wbs.md`에서 해당 WP의 `- progress:` 값 업데이트

#### (B) 전체 완료 머지 — 모든 WP 완료 후 실행

모니터링에서 `ALL_TEAM_MEMBERS_DONE`을 수신하면 팀리더가 아직 머지되지 않은 WP들을 순차 머지한다:

1. 각 worktree 브랜치의 변경사항을 확인 (`git log main..dev/{WP-ID} --oneline`)
2. main 브랜치에 순차적으로 머지 (`git merge --no-ff dev/{WP-ID}`)
   - 머지 순서: 의존성 하위 WP부터
3. 머지 후 충돌 여부 확인
   - 충돌 발생 시: 사용자에게 보고하고 수동 해결 요청 후 대기
   - 충돌 없으면: 다음 브랜치 머지 진행
4. 모든 머지 완료 후 정리:
   - 시그널 디렉토리 정리: `rm -rf /tmp/claude-signals/{PROJECT_NAME}`
   - 남은 worktree 정리: `git worktree remove --force .claude/worktrees/{WP-ID} && git branch -d dev/{WP-ID}`
5. `docs/wbs.md`에서 각 WP의 `- progress:` 값을 업데이트
6. 전체 결과 요약 보고:
   - WP별 완료 Task 수
   - 성공/실패 현황
   - 머지 결과
