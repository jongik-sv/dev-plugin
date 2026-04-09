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

## 0. 인자 파싱 — 서브프로젝트 감지 (공통 규칙)

`$ARGUMENTS`를 공백으로 토큰화한 뒤 첫 번째 토큰을 검사한다:

1. 토큰이 없거나 `--`로 시작 → 서브프로젝트 없음, `DOCS_DIR=docs`
2. `^(WP|TSK)-` 패턴 → 서브프로젝트 없음, `DOCS_DIR=docs` (토큰은 그대로 유지)
3. 그 외 문자열 → 서브프로젝트 이름 후보
   - `docs/{토큰}/` 디렉토리 존재 → `SUBPROJECT={토큰}`, `DOCS_DIR=docs/{토큰}`, 해당 토큰을 `$ARGUMENTS`에서 제거
   - 존재하지 않음 → 에러 보고 후 종료 (`docs/{토큰}/ 디렉토리가 없습니다`)

이후 모든 경로(`wbs.md`, `tasks/...`)는 `{DOCS_DIR}` 기준이며, tmux 창 이름과 시그널 경로에 서브프로젝트 정보를 포함시켜 충돌을 방지한다.

- `WINDOW_SUFFIX`: 서브프로젝트 있으면 `-{SUBPROJECT}`, 없으면 `` (빈 문자열)
- tmux 창 이름: `{WP-ID}{WINDOW_SUFFIX}` (예: `WP-04-p1`)
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
| `WP_LEADER_MODEL` | `haiku` | WP 리더 claude 프로세스의 모델. `--model opus` 시 `opus` |
| `WORKER_MODEL` | `sonnet` | Worker pane claude 프로세스의 모델. `--model opus` 시 `opus` |

> `--team-size N` 옵션으로 변경 가능. 아래 문서에서 `{TEAM_SIZE}`로 참조.
> `--model opus` 옵션으로 변경 가능. 아래 모델 전파 체계를 따른다.

### 모델 전파 체계 (docs/model-selection.md 기준)

```
--model opus 미지정 (기본):
  팀리더 (현재 세션)     → 사용자 기본 모델
  WP 리더 (tmux window) → Haiku   (순수 스케줄링/시그널 감시)
  Worker (tmux pane)    → Sonnet  (DDTR 오케스트레이션)
  Phase 서브에이전트      → 설계=Sonnet, 개발=Sonnet, 테스트=Haiku, 리팩토링=Sonnet

--model opus 지정:
  전 계층 Opus
```
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

# 서브프로젝트 감지 결과 반영
# (위 "0. 인자 파싱"에서 결정된 SUBPROJECT/DOCS_DIR/WINDOW_SUFFIX 사용)
DOCS_DIR="${DOCS_DIR:-docs}"
WINDOW_SUFFIX="${WINDOW_SUFFIX:-}"
```

## 실행 절차

### 1. WP 선정 및 Task 수집

#### 인자 파싱
- 위 "0. 인자 파싱"에서 이미 `SUBPROJECT`/`DOCS_DIR`이 결정되어 있다
- 남은 `$ARGUMENTS`에서 WP-ID 목록과 `--team-size N` 옵션을 추출한다
- WP-ID가 없으면 자동 선정 로직 실행

#### 인자가 있는 경우
- 각 WP-ID에 대해 `{DOCS_DIR}/wbs.md`에서 `## {WP-ID}:` 섹션을 찾는다

#### 인자가 없는 경우 (자동 선정)
1. `{DOCS_DIR}/wbs.md`에서 `progress: 100%`가 아닌 모든 WP를 수집
2. 각 WP의 하위 Task 중 status가 `[ ]`, `[dd]`, `[im]` 중 하나이고, depends가 모두 충족된(`[xx]` 또는 해당 WP 외부에서 이미 완료) Task가 1개 이상 있는 WP를 **실행 가능 WP**로 판정 (재개 대상 포함)
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

#### (A) tmux 환경 — 셋업 스크립트 사용 ← 권장

**tmux 환경 감지**:
```bash
[ -n "$TMUX" ] && command -v tmux > /dev/null
```

현재 세션이 **팀리더** 역할을 한다. 셋업 스크립트(`scripts/wp-setup.sh`)로 worktree 생성, 프롬프트/manifest 생성, tmux spawn을 **일괄 처리**한다.

> ⚠️ 스크립트가 생성하는 모든 시그널 경로는 `SHARED_SIGNAL_DIR` (프로젝트 레벨) 하나만 사용한다.
> per-WP 디렉토리(예: `claude-signals/WP-01-p1`)는 생성하지 않는다.

1. **config JSON 생성** — `{TEMP_DIR}/wp-setup-config.json`을 Write 도구로 작성한다:
   ```json
   {
     "project_name": "{PROJECT_NAME}",
     "window_suffix": "{WINDOW_SUFFIX}",
     "temp_dir": "{TEMP_DIR}",
     "shared_signal_dir": "{SHARED_SIGNAL_DIR}",
     "docs_dir": "{DOCS_DIR}",
     "wbs_path": "{DOCS_DIR}/wbs.md",
     "session": "{SESSION}",
     "model_override": "{MODEL_OVERRIDE 또는 빈 문자열}",
     "worker_model": "{WORKER_MODEL}",
     "wp_leader_model": "{WP_LEADER_MODEL}",
     "plugin_root": "{PLUGIN_ROOT}",
     "wps": [
       {
         "wp_id": "WP-01",
         "team_size": {TEAM_SIZE},
         "tasks": ["TSK-01-01", "TSK-01-02"],
         "execution_plan": "Level 0: TSK-01-01 (즉시)\nLevel 1: TSK-01-02 (TSK-01-01 의존)"
       }
     ]
   }
   ```
   - `{PROJECT_NAME}`: `$(basename "$(pwd)")`
   - `{PLUGIN_ROOT}`: 이 플러그인의 루트 디렉토리 (`${CLAUDE_PLUGIN_ROOT}` 또는 절대 경로)
   - `wps[].tasks`: 해당 WP의 모든 TSK-ID 배열 (`[xx]` 포함 — 스크립트가 자동 필터링)
   - `wps[].execution_plan`: 2단계에서 산출한 레벨별 실행 계획 텍스트

2. **셋업 스크립트 실행**:
   ```bash
   bash "${PLUGIN_ROOT}/scripts/wp-setup.sh" "${TEMP_DIR}/wp-setup-config.json"
   ```

   스크립트가 **자동** 수행하는 작업:
   | 작업 | 생성 파일 |
   |------|-----------|
   | worktree 생성 (또는 재개 감지 + 시그널 복원) | `.claude/worktrees/{WT_NAME}/` |
   | wbs.md에서 task 블록 추출 + DDTR 프롬프트 치환 | `{TEMP_DIR}/task-{TSK-ID}.txt` |
   | WP 리더 프롬프트 치환 | `.claude/worktrees/{WT_NAME}-prompt.txt` |
   | team manifest 생성 | `{TEMP_DIR}/team-manifest-{WT_NAME}.md` |
   | runner script + tmux window spawn | `.claude/worktrees/{WT_NAME}-run.sh` |

   > `[xx]` 상태 Task는 자동 제외. 모든 Task가 `[xx]`인 WP는 즉시 `.done` 시그널 생성 후 스킵.

3. **WP별 완료 감지 및 조기 머지**:
   팀리더는 각 WP의 시그널 파일을 Bash `run_in_background`로 감시한다:
   ```bash
   WT_NAME="{WP-ID}${WINDOW_SUFFIX}"
   while [ ! -f "${SHARED_SIGNAL_DIR}/${WT_NAME}.done" ]; do sleep 15; done
   echo "WP_DONE:${WT_NAME}"
   cat "${SHARED_SIGNAL_DIR}/${WT_NAME}.done"
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

> ⚠️ 상대 경로(`../.signals/`) 사용 금지 — worktree 내부에서 상대 경로는 `{TEMP_DIR}/claude-signals/{PROJECT_NAME}/`가 아닌 worktree 내부의 다른 위치로 해석될 수 있다.

---

### WP 리더 프롬프트

`.claude/worktrees/{WP-ID}-prompt.txt`를 생성한다.
**템플릿**: `references/wp-leader-prompt.md` 파일을 Read하여 `{WP-ID}`, `{TEAM_SIZE}`, `{SHARED_SIGNAL_DIR}` 등 변수를 치환한다.

### 5. 결과 통합 (팀리더)

#### (A) 개별 WP 조기 머지 — WP 완료 즉시 실행

다른 WP가 아직 실행 중이더라도, 완료된 WP는 즉시 머지할 수 있다.
`{SHARED_SIGNAL_DIR}/{WT_NAME}.done` 시그널 파일이 생성되면 해당 WP를 머지한다
(`{WT_NAME}` = `{WP-ID}{WINDOW_SUFFIX}`).

0. **산출물 검증** (머지 전 필수):
   WP 내 모든 Task에 대해 아래 파일이 존재하는지 확인한다:
   - `{DOCS_DIR}/tasks/{TSK-ID}/design.md` — 설계 산출물
   - `{DOCS_DIR}/tasks/{TSK-ID}/test-report.md` — 테스트 결과
   - `{DOCS_DIR}/tasks/{TSK-ID}/refactor.md` — 리팩토링 내역
   - `{DOCS_DIR}/wbs.md` 해당 Task의 status가 `[xx]`인지 확인

   누락된 산출물이 있으면 시그널 내용과 대조하여 판단:
   - 시그널에 실패 내용이 있으면 → 해당 Task를 부분 완료로 기록
   - 파일은 없지만 시그널은 성공이면 → WP 리더에게 재확인 요청 후 진행

1. 해당 WP의 tmux 창(window) 종료 (pane_id 기반):
```bash
for PANE_ID in $(tmux list-panes -t "${SESSION}:${WT_NAME}" -F '#{pane_id}'); do
  tmux send-keys -t "${PANE_ID}" Escape 2>/dev/null
  sleep 1
  tmux send-keys -t "${PANE_ID}" '/exit' Enter 2>/dev/null
done
sleep 3
tmux kill-window -t "${SESSION}:${WT_NAME}" 2>/dev/null
```

2. main에 미커밋 변경이 있으면 먼저 커밋
3. 머지 실행:
```bash
git merge --no-ff dev/${WT_NAME} -m "Merge dev/${WT_NAME}: {WP 제목} ({TSK-ID 목록})"
```
4. 충돌 발생 시: 수동 해결 후 `git add` + `git commit --no-edit`
5. worktree + 브랜치 정리:
```bash
git worktree remove --force .claude/worktrees/${WT_NAME}
git branch -d dev/${WT_NAME}
```
6. `{DOCS_DIR}/wbs.md`에서 해당 WP의 `- progress:` 값 업데이트

#### (B) 전체 완료 머지 — 모든 WP 완료 후 실행

모니터링에서 `ALL_TEAM_MEMBERS_DONE`을 수신하면 팀리더가 아직 머지되지 않은 WP들을 순차 머지한다:

1. 각 worktree 브랜치의 변경사항을 확인 (`git log main..dev/${WT_NAME} --oneline`)
2. main 브랜치에 순차적으로 머지 (`git merge --no-ff dev/${WT_NAME}`)
   - 머지 순서: 의존성 하위 WP부터
3. 머지 후 충돌 여부 확인
   - 충돌 발생 시: 사용자에게 보고하고 수동 해결 요청 후 대기
   - 충돌 없으면: 다음 브랜치 머지 진행
4. 모든 머지 완료 후 정리:
   - 시그널 디렉토리 정리: `rm -rf ${TEMP_DIR}/claude-signals/${PROJECT_NAME}${WINDOW_SUFFIX}`
   - 남은 worktree 정리: `git worktree remove --force .claude/worktrees/${WT_NAME} && git branch -d dev/${WT_NAME}`
5. `{DOCS_DIR}/wbs.md`에서 각 WP의 `- progress:` 값을 업데이트
6. 전체 결과 요약 보고:
   - WP별 완료 Task 수
   - 성공/실패 현황
   - 머지 결과
