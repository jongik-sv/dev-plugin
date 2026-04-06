---
name: team-mode
description: "팀(team) 병렬 개발 — 팀모드, team mode, 팀 에이전트, 팀으로 작업, team으로 돌려 등 '팀' 또는 'team'이 포함된 요청 시 이 스킬을 사용한다. N개의 독립 claude 세션을 tmux pane으로 병렬 실행. 사용법: /team-mode [manifest-path] [--team-size N] [--workdir PATH]"
---

# /team-mode - tmux 기반 병렬 세션 실행

N개의 독립 claude 프로세스를 tmux pane에서 실행하고, 시그널 파일 기반으로 task를 할당·감지·재활용하는 범용 병렬 실행 스킬이다. 개발, 분석, 문서 생성 등 다양한 작업을 병렬로 처리할 수 있다.

인자: `$ARGUMENTS` (옵션)
- 첫 번째 인자: manifest 파일 경로 (선택)
- `--team-size N`: worker 수 (기본값: 3, manifest의 team_size보다 우선)
- `--workdir PATH`: 작업 디렉토리 (기본: 현재 디렉토리. 호출자가 worktree 등을 지정할 때 사용)
- `--leader`: 리더 pane 유지 (pane 0을 빈 셸로 남김). 생략 시 모든 pane이 worker
- `--claim`: Worker pull 모드 활성화. 리더가 push하는 대신 worker가 큐에서 self-claim (→ "3-B. Claim 기반 할당" 참조)

**manifest 파일이 없으면** 대화에서 작업 리스트를 수집하여 자동 생성한다 (→ "1-A. 대화형 Task 수집" 참조).

## 0. 설정 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `TEAM_SIZE` | 3 | worker pane 수 |
| `TEMP_DIR` | `/tmp` (Unix) / `$TEMP` (Windows) | 임시 파일 루트 디렉토리 |
| `SIGNAL_DIR` | `{TEMP_DIR}/claude-signals/{window_name}` | 시그널 파일 디렉토리 |
| `SESSION` | 현재 tmux 세션 이름 | 모든 tmux 명령의 세션 prefix |
| `LEADER_MODE` | false | `--leader` 지정 시 true |
| `WORKER_OFFSET` | 0 | worker pane 시작 인덱스. 리더 있으면 1, 없으면 0 |
| `MAX_RETRIES` | 1 | task 실패 시 재시도 횟수 |
| `CLAIM_MODE` | false | `--claim` 지정 시 true |

### 시그널 프로토콜

task 상태는 시그널 파일로 추적한다. `mv`를 사용하여 원자적으로 전환한다.

| 상태 | 파일 | 생성 시점 |
|------|------|-----------|
| 실행 중 | `{task-id}.running` | task 시작 직후 (worker가 생성) |
| 완료 | `{task-id}.done` | task 성공 완료 시 |
| 실패 | `{task-id}.failed` | task 실패 시 |

## 전제조건 확인

```bash
# tmux 환경 감지
[ -n "$TMUX" ] && command -v tmux > /dev/null
```

tmux 세션 밖이면 에러를 출력하고 중단한다. (tmux 없이 병렬 실행이 필요하면 `/agent-pool`을 사용하라.)

### 플랫폼 감지 및 변수 초기화

```bash
# 플랫폼 감지
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$(uname -r)" == *Microsoft* || "$(uname -r)" == *microsoft* ]]; then
  PLATFORM="windows"
  TEMP_DIR="${TEMP:-${TMP:-/tmp}}"
else
  PLATFORM="unix"
  TEMP_DIR="/tmp"
fi

# 세션 이름 확보 (psmux 필수, tmux도 안전)
SESSION=$(tmux display-message -p '#{session_name}')
```

> ⚠️ **Windows(psmux) 호환**: psmux는 현재 세션을 자동 추론하지 않으므로, 모든 tmux 명령에 `${SESSION}:` prefix가 필수이다. Unix tmux에서도 명시하면 안전하다.

기존 동명 창 확인:
```bash
tmux list-windows -F '#{window_name}'
```
동일 이름 창이 있으면 사용자에게 확인 후 정리한다.

## 1. Task 입력

### 분기: manifest 유무 판단

- `$ARGUMENTS`에 manifest 파일 경로가 있으면 → **1-B. Manifest 파싱**으로 진행
- 파일 경로가 없으면 → **1-A. 대화형 Task 수집**으로 진행

### 1-A. 대화형 Task 수집 (manifest 없을 때)

사용자에게 병렬로 실행할 작업 리스트를 질문한다:

> 어떤 작업들을 병렬로 실행할까요? 작업 목록을 알려주세요.
> (작업 간 의존성이 있으면 함께 알려주세요.)

사용자 응답을 파싱하여 manifest + prompt 파일을 자동 생성한다:

1. **window_name** 자동 결정: 작업 성격에서 짧은 이름 추출 (예: `analysis`, `refactor`)
2. **prompt 파일 생성**: 각 task별로 `{TEMP_DIR}/{window_name}-task-{N}.txt` 파일에 프롬프트 저장
3. **manifest 생성**: `{TEMP_DIR}/{window_name}-manifest.md`

```markdown
# Configuration
- team_size: 3
- window_name: {자동 결정}

## Tasks

### task-1
- depends: (none)
- prompt_file: {TEMP_DIR}/{window_name}-task-1.txt
```

- task id는 `task-1`, `task-2`, ... 순서로 자동 부여
- 사용자가 의존성을 언급하지 않으면 모든 task의 `depends`를 `(none)`으로 설정 (전부 병렬)
- 생성한 내용을 사용자에게 보여주고 확인 후 진행

### 1-B. Manifest 파싱

manifest 파일을 Read 도구로 읽는다.

#### Manifest 형식

```markdown
# Configuration
- team_size: 3
- window_name: my-work
- signal_dir: {TEMP_DIR}/claude-signals/my-work

## Tasks

### task-1
- depends: (none)
- prompt_file: {TEMP_DIR}/task-1.txt

### task-2
- depends: task-1
- prompt_file: {TEMP_DIR}/task-2.txt

### task-3
- depends: (none)
- prompt_file: {TEMP_DIR}/task-3.txt
```

**Configuration 필드**:
| 필드 | 필수 | 기본값 | 설명 |
|------|------|--------|------|
| team_size | N | 3 | worker 수 (`--team-size`가 우선) |
| window_name | Y | - | tmux window 이름 |
| signal_dir | N | `{TEMP_DIR}/claude-signals/{window_name}` | 시그널 디렉토리 |

**Task 필드**:
| 필드 | 필수 | 설명 |
|------|------|------|
| depends | N | 의존 task ID (쉼표 구분). `(none)` 또는 생략 시 의존 없음 |
| prompt_file | Y | worker에게 전달할 프롬프트 파일 경로 |

### 의존성 분석

depends 기반으로 실행 레벨을 산출한다:

```
Level 0: depends가 없거나 모두 완료 (즉시 시작 가능)
Level 1: Level 0 task에 의존
Level 2: Level 1 task에 의존
...
```

같은 Level의 task는 병렬 실행한다.

## 2. 환경 구성

### 시그널 디렉토리

```bash
mkdir -p {SIGNAL_DIR}
mkdir -p {SIGNAL_DIR}/discoveries
```

### tmux 창 및 pane 생성

`LEADER_MODE`에 따라 분기한다.

#### (A) 리더 없음 (기본, `--leader` 미지정)

모든 pane이 worker이다. `WORKER_OFFSET = 0`.

1. **tmux window 생성 (pane 0 = worker1)**:
   ```bash
   tmux new-window -t "${SESSION}" -n "{window_name}" -c "{작업 디렉토리}" \
     "cd {작업 디렉토리} && claude --dangerously-skip-permissions"
   # window 이름 보호 (프로세스명으로 덮어씌워지는 것 방지)
   tmux set-option -w -t "${SESSION}:{window_name}" automatic-rename off
   tmux set-option -w -t "${SESSION}:{window_name}" allow-rename off
   ```

2. **나머지 worker pane 생성** (TEAM_SIZE-1개):
   ```bash
   for i in $(seq 2 {TEAM_SIZE}); do
     tmux split-window -t "${SESSION}:{window_name}" -h \
       "cd {작업 디렉토리} && claude --dangerously-skip-permissions"
   done
   tmux select-layout -t "${SESSION}:{window_name}" tiled
   ```

3. **pane 생성 검증**:
   ```bash
   ACTUAL_PANES=$(tmux list-panes -t "${SESSION}:{window_name}" | wc -l | tr -d ' ')
   if [ "$ACTUAL_PANES" -ne "$TEAM_SIZE" ]; then
     echo "ERROR: expected ${TEAM_SIZE} panes, got ${ACTUAL_PANES}"
     # 부족한 pane 재생성 시도
     for i in $(seq $((ACTUAL_PANES + 1)) ${TEAM_SIZE}); do
       tmux split-window -t "${SESSION}:{window_name}" -h \
         "cd {작업 디렉토리} && claude --dangerously-skip-permissions"
     done
     tmux select-layout -t "${SESSION}:{window_name}" tiled
   fi
   ```

4. **pane ID 수집** (이후 모든 명령에 pane_id 사용):
   ```bash
   PANE_MAP=$(tmux list-panes -t "${SESSION}:{window_name}" -F '#{pane_index}:#{pane_id}')
   # 예: "0:%7\n1:%8\n2:%9"
   # PANE_IDS 배열로 저장: PANE_IDS[0]="%7", PANE_IDS[1]="%8", ...
   ```
   - pane 0~TEAM_SIZE-1: worker

5. **pane 라벨 설정** (pane_id 기반):
   ```bash
   tmux set-option -w -t "${SESSION}:{window_name}" pane-border-status top
   tmux set-option -w -t "${SESSION}:{window_name}" pane-border-format " #{pane_index}: #{@label} "

   for i in $(seq 0 $((TEAM_SIZE-1))); do
     tmux set-option -p -t "${PANE_IDS[$i]}" @label "worker$((i+1)) 대기"
   done
   ```

#### (B) 리더 있음 (`--leader` 지정)

pane 0은 리더(호출자)용 빈 셸이다. `WORKER_OFFSET = 1`.

1. **tmux window 생성 (pane 0 = 리더)**:
   ```bash
   tmux new-window -t "${SESSION}" -n "{window_name}" -c "{작업 디렉토리}"
   # window 이름 보호
   tmux set-option -w -t "${SESSION}:{window_name}" automatic-rename off
   tmux set-option -w -t "${SESSION}:{window_name}" allow-rename off
   ```

2. **worker pane 생성** (TEAM_SIZE개):
   ```bash
   for i in $(seq 1 {TEAM_SIZE}); do
     tmux split-window -t "${SESSION}:{window_name}" -h \
       "cd {작업 디렉토리} && claude --dangerously-skip-permissions"
   done
   tmux select-layout -t "${SESSION}:{window_name}" tiled
   ```

3. **pane 생성 검증**:
   ```bash
   EXPECTED_PANES=$((TEAM_SIZE + 1))  # 리더 + worker
   ACTUAL_PANES=$(tmux list-panes -t "${SESSION}:{window_name}" | wc -l | tr -d ' ')
   if [ "$ACTUAL_PANES" -ne "$EXPECTED_PANES" ]; then
     echo "ERROR: expected ${EXPECTED_PANES} panes, got ${ACTUAL_PANES}"
     for i in $(seq $((ACTUAL_PANES)) ${TEAM_SIZE}); do
       tmux split-window -t "${SESSION}:{window_name}" -h \
         "cd {작업 디렉토리} && claude --dangerously-skip-permissions"
     done
     tmux select-layout -t "${SESSION}:{window_name}" tiled
   fi
   ```

4. **pane ID 수집** (이후 모든 명령에 pane_id 사용):
   ```bash
   PANE_MAP=$(tmux list-panes -t "${SESSION}:{window_name}" -F '#{pane_index}:#{pane_id}')
   # PANE_IDS 배열로 저장: PANE_IDS[0]="%5"(리더), PANE_IDS[1]="%6", ...
   ```
   - pane 0: 리더 (호출자)
   - pane 1~TEAM_SIZE: worker

5. **pane 라벨 설정** (pane_id 기반):
   ```bash
   tmux set-option -w -t "${SESSION}:{window_name}" pane-border-status top
   tmux set-option -w -t "${SESSION}:{window_name}" pane-border-format " #{pane_index}: #{@label} "

   tmux set-option -p -t "${PANE_IDS[0]}" @label "리더"
   for i in $(seq 1 {TEAM_SIZE}); do
     tmux set-option -p -t "${PANE_IDS[$i]}" @label "worker${i} 대기"
   done
   ```

## 3. Task 할당 프로토콜

⚠️ **tmux send-keys는 긴 문자열을 잘라버린다.** 프롬프트를 반드시 파일로 전달한다.

### 할당 — 3단계

> ⚠️ `{paneId}`는 반드시 pane ID(`%N` 형식, 예: `%7`)를 사용한다. `{window_name}.{index}` 형식은 psmux에서 불안정하다.

```bash
# 1단계: pane 라벨 업데이트
tmux set-option -p -t {paneId} @label "worker{N} {task-id}"

# 2단계: Escape로 깨운 뒤 짧은 지시 전송
tmux send-keys -t {paneId} Escape
sleep 1
tmux send-keys -t {paneId} '{prompt_file} 파일을 Read 도구로 읽고 그 안의 작업을 수행하라.' Enter

# 3단계: 할당 수신 검증 (15초 후)
sleep 15
PANE_OUTPUT=$(tmux capture-pane -t {paneId} -p -S -5 2>/dev/null)
if echo "$PANE_OUTPUT" | grep -qE '(Musing|Thinking|Drizzling|Running|⏺)'; then
  echo "worker 활성 확인"
else
  echo "worker 미응답 — 재전송"
  tmux send-keys -t {paneId} Escape
  sleep 1
  tmux send-keys -t {paneId} i
  sleep 1
  tmux send-keys -t {paneId} '{prompt_file} 파일을 Read 도구로 읽고 그 안의 작업을 수행하라.' Enter
fi
```

> **왜 Escape를 보내는가?** Claude Code가 idle/churned 상태에 빠지면 send-keys 입력을 무시한다. Escape를 먼저 전송해야 입력 수용 상태로 복귀한다.

### 초기 할당

Level 0 task부터 최대 TEAM_SIZE개에게 각 1건씩 할당한다.

### 3-B. Claim 기반 할당 (`--claim` 모드)

`CLAIM_MODE`가 true이면 리더가 push하는 대신 worker가 자율적으로 다음 task를 가져간다.
**상세**: `references/claim-mode.md` 참조.

## 4. 모니터링 및 재활용

### 시그널 파일 감지

각 task별로 Bash `run_in_background`로 폴링한다:

```bash
while [ ! -f {SIGNAL_DIR}/{task-id}.done ] && [ ! -f {SIGNAL_DIR}/{task-id}.failed ]; do sleep 10; done
if [ -f {SIGNAL_DIR}/{task-id}.done ]; then echo "DONE:{task-id}"; cat {SIGNAL_DIR}/{task-id}.done
elif [ -f {SIGNAL_DIR}/{task-id}.failed ]; then echo "FAILED:{task-id}"; cat {SIGNAL_DIR}/{task-id}.failed
fi
```

### Pane 재활용 (시그널 감지 후)

시그널 파일 감지 후 아래 순서를 **정확히** 따른다:

#### DONE 시그널인 경우
1. **시그널 내용 확인**: `cat {SIGNAL_DIR}/{task-id}.done`
2. **컨텍스트 초기화**:
   ```bash
   tmux send-keys -t {paneId} Escape
   sleep 1
   tmux send-keys -t {paneId} '/clear' Enter
   sleep 10
   tmux send-keys -t {paneId} Enter
   ```
3. **다음 task 할당**: 의존성이 해소된 다음 task를 "3. Task 할당 프로토콜"에 따라 1건 할당
4. **모든 task 완료 시**: "5. 완료 처리"로 이동

#### FAILED 시그널인 경우
1. **시그널 내용 확인**: `cat {SIGNAL_DIR}/{task-id}.failed`
2. **재시도 판단**: 해당 task의 재시도 횟수 < `MAX_RETRIES`이면:
   - `.failed` 파일 삭제
   - 컨텍스트 초기화 후 **같은 task를 다시 할당** (재시도 횟수 +1)
3. **재시도 초과 시**:
   - task를 실패로 확정, 의존 task는 스킵 처리
   - 컨텍스트 초기화 후 대기 큐에서 다음 task 할당

### 백업: 창 닫힘 감지

시그널 감지가 실패할 경우를 대비한 안전장치:
```bash
while true; do
  if ! tmux list-windows -F '#{window_name}' | grep -q "^{window_name}$"; then
    echo "WINDOW_CLOSED:{window_name}"
    break
  fi
  sleep 30
done
```

### 백업: Worker 하트비트 감지

tmux pane은 살아있지만 claude 프로세스가 정지한 경우를 감지한다. 각 task의 `.running` 파일 갱신 시각을 확인한다.

> **⚠️ 타임아웃과 하트비트 주기는 반드시 정합해야 한다.** worker가 N분 간격으로 하트비트를 보내면 타임아웃은 최소 3N 이상이어야 한다. 타임아웃이 하트비트 주기보다 짧으면 정상 작동 중인 task가 stale로 오판되어 중복 실행이 발생한다.

```bash
# 각 실행 중인 task별로 run_in_background
HEARTBEAT_TIMEOUT=600  # 초 (10분). worker는 2분 간격으로 하트비트.
while [ -f {SIGNAL_DIR}/{task-id}.running ] && [ ! -f {SIGNAL_DIR}/{task-id}.done ] && [ ! -f {SIGNAL_DIR}/{task-id}.failed ]; do
  # 플랫폼별 파일 수정 시각 조회
  if [ "$PLATFORM" = "windows" ]; then
    LAST_MOD=$(stat -c %Y {SIGNAL_DIR}/{task-id}.running 2>/dev/null || date -r {SIGNAL_DIR}/{task-id}.running +%s 2>/dev/null || echo 0)
  else
    LAST_MOD=$(stat -f %m {SIGNAL_DIR}/{task-id}.running 2>/dev/null || echo 0)
  fi
  NOW=$(date +%s)
  if [ $((NOW - LAST_MOD)) -gt $HEARTBEAT_TIMEOUT ]; then
    echo "STALE:{task-id}"
    break
  fi
  sleep 60
done
```

STALE 감지 시: FAILED와 동일하게 처리 (재시도 또는 실패 확정).

> worker 프롬프트에 하트비트 지시를 **반드시** 포함한다:
> `작업 중 2분 간격으로 touch {SIGNAL_DIR}/{task-id}.running 을 Bash로 실행하라.`
> 이 지시가 없으면 하트비트 감지가 작동하지 않으므로, 하트비트 감지 자체를 비활성화해야 한다.

### 중간 발견 공유 (discoveries)

worker가 작업 중 다른 worker에게 유용한 정보를 발견하면 `{SIGNAL_DIR}/discoveries/`에 파일을 남긴다:

```bash
echo '{발견 내용}' > {SIGNAL_DIR}/discoveries/{task-id}-{주제}.md
```

worker 프롬프트에 아래 지시를 포함할 수 있다:
> `작업 전 {SIGNAL_DIR}/discoveries/ 디렉토리의 파일들을 읽어 다른 worker의 발견사항을 참고하라. 작업 중 공유할 만한 발견(공통 설정, API 변경, 스키마 수정 등)이 있으면 같은 디렉토리에 파일을 남겨라.`

**용도**: 한 worker가 공유 스키마를 변경하면 다른 worker가 이를 즉시 인지. 단독 실행 대비 경계 불일치 감소.

### ⚠️ 필수 규칙

- **1건씩 할당**: 복수 할당 시 통제 불가
- **시그널 감지 전 /clear 금지**: 진행 중인 작업이 중단된다
- **올바른 흐름**: 1건 할당 → 시그널 대기 → /clear → 다음 1건 할당
- **시그널 대기는 Bash `run_in_background`로 실행**: 리더 블로킹 방지

## 5. 완료 처리

모든 task의 시그널 파일을 확인한 후:

### Worker 종료

`WORKER_OFFSET`에 따라 worker pane 범위가 달라진다. pane_id(`%N`)를 사용한다.

```bash
# 리더 없음: WORKER_OFFSET=0, 범위 0~TEAM_SIZE-1
# 리더 있음: WORKER_OFFSET=1, 범위 1~TEAM_SIZE
for i in $(seq {WORKER_OFFSET} $((WORKER_OFFSET + TEAM_SIZE - 1))); do
  tmux send-keys -t "${PANE_IDS[$i]}" Escape 2>/dev/null
  sleep 1
  tmux send-keys -t "${PANE_IDS[$i]}" '/exit' Enter 2>/dev/null
done
sleep 5
```

### 완료 시그널

```bash
cat > {SIGNAL_DIR}/_all.done.tmp << 'EOF'
[완료]
- 전체 task: {총 수}
- 성공: {성공 수}
- 실패: {실패 수}
EOF
mv {SIGNAL_DIR}/_all.done.tmp {SIGNAL_DIR}/_all.done
```

### 결과 보고

사용자 또는 호출 스킬에게 결과를 출력한다:
```
## Team Mode 실행 결과
- window: {window_name}
- 전체: {총 task 수}
- 성공: {성공 수}
- 실패: {실패 수}
```
