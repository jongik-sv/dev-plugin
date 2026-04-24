---
name: dev-team
description: "WP(Work Package) 단위로 하위 Task들을 병렬 분배하여 개발. 사용법: /dev-team [SUBPROJECT] WP-04 또는 /dev-team p1 WP-01 또는 /dev-team p1 (자동 선정) 또는 /dev-team WP-04 --team-size 5 또는 /dev-team --sequential WP-01 WP-02"
---

# /dev-team - WP 단위 팀 병렬 개발

인자: `$ARGUMENTS` ([SUBPROJECT] + WP-ID + 옵션)
- SUBPROJECT: (옵션) 하위 프로젝트 폴더 이름. 예: `p1` → `docs/p1/` 하위에서 동작
- WP-ID: 1개 이상 (공백 구분). 생략 시 자동 선정
- `--team-size N`: 개발팀원 수 (기본값: 3)
- `--model opus`: 전 단계 Opus 모델 사용 (미지정 시 Phase별 권장 모델 자동 적용)
- `--on-fail strict|bypass|fast`: 테스트 실패 시 동작 모드 (기본값: `bypass`)
- `--sequential` / `--seq` / `--one-wp-at-a-time`: **순차 WP 모드** — WP를 한 번에 하나씩 실행. 워크트리 없음, 현재 브랜치에 직접 커밋. WP 내부 병렬(팀원 pane)은 유지.

예:
- `/dev-team WP-04` — 기본 `docs/` 사용, 권장 모델 적용
- `/dev-team p1 WP-01` — 서브프로젝트 `docs/p1/` 사용
- `/dev-team p1 WP-01 WP-02 --team-size 5`
- `/dev-team p1` — 서브프로젝트 `docs/p1/`에서 자동 선정
- `/dev-team p1 WP-01 --model opus` — 전 단계 Opus
- `/dev-team WP-04 --on-fail strict` — 테스트 실패 시 중단(강력 검증)
- `/dev-team WP-04 --on-fail fast` — 테스트 실패 시 즉시 다음 진행(속도 우선)
- `/dev-team --sequential WP-01 WP-02 WP-03` — 순차 모드: WP 하나씩, 워크트리 없음
- `/dev-team --sequential` — 순차 모드 자동 WP 선정
- `/dev-team --seq --team-size 5 WP-01` — 순차 모드 + 팀원 5명

## 자율 실행 원칙 (Non-Interactive by Default)

`/dev-team`은 **자율형 개발 워크플로우**다. **실행 중 발생하는 모든 의사결정은 팀리더가 가장 합리적인 기본값을 선택해 즉시 진행한다.** 사용자에게 "어떻게 할까요?"를 묻지 않는다 — 선택·판단·정책 결정을 스스로 수행하고 **결과를 요약 보고**한다.

### 메타 규칙

1. **기본값 우선** — 옵션이 생략되거나 상황이 모호하면 아래 표의 "✅ 기본 동작" 또는 안전한 쪽으로 자동 결정.
2. **진행 우선** — 한 task/WP가 막혀도 전체를 멈추지 않는다. 해당 단위만 스킵(abort/bypass)하고 나머지 계속 진행.
3. **되돌릴 수 있는 쪽 선택** — 두 선택지가 비슷하면 **손실이 적고 재시도 가능한 쪽** 선택 (예: 머지 충돌 시 main 오염보다 `--abort` + 워크트리 보존).
4. **증거 보존** — 자동 결정은 반드시 `.done` 시그널 본문·autopsy 덤프·최종 요약 보고에 기록하여 사후 추적 가능하게 한다.
5. **리스크 구간만 예외** — 파괴적·비가역적이면서 자동 선택이 위험한 경우(전제조건 미충족 등)에만 중단. 아래 "예외" 리스트로 한정한다.

### 런타임 의사결정 기본값

| 상황 | ❌ 하지 말 것 | ✅ 기본 동작 |
|------|---------------|--------------|
| WP-ID 생략 | "어떤 WP를 실행할까요?" 확인 | `--resumable-wps` 결과 **전부 자동 선정** 후 시작 (선정 결과는 안내 메시지로만 표시) |
| `--team-size` 생략 | 팀원 수 확인 | `TEAM_SIZE=3` 자동 적용. **모든 WP에 동일 적용** — 특정 WP의 Task 수가 3보다 적어도 해당 WP만 축소하지 않는다. 남는 팀원은 다음 Phase/의존 Task를 선행하거나 대기 상태로 두어 레벨 전환 속도를 우선한다. 축소하려면 사용자가 `--team-size N`을 명시해야 한다. |
| `--model` 생략 | 모델 선택 프롬프트 | Phase별 권장 모델 자동 적용 (설계=Opus, 개발=Sonnet, 테스트=Haiku, 리팩토링=Sonnet) |
| `--on-fail` 생략 | 실패 정책 확인 | `bypass` 자동 적용 (에스컬레이션 소진 시 임시완료 → 다음 task 진행) |
| 기존 워크트리 발견 | "재개/새로 시작?" 확인 | `wp-setup.py`가 자동 resume (시그널 복원 프로토콜 적용) |
| 일부 Task 실패 + 나머지 완료 | "merge할까요?" 확인 | bypass된 task는 DONE과 동일 처리, 자동 머지 진행 |
| 코드 리뷰 "needs-attention" | 사용자 판단 요청 | 자동 수정 시도 후 머지 진행 (`wp-leader-cleanup.md` 참조) |
| git 머지 충돌 | 사용자 수동 해결 대기 | **즉시 `git merge --abort` + 해당 WP 스킵** (워크트리·브랜치 보존, 다음 WP 계속) — 충돌 내역은 최종 요약 보고에 포함 |
| 머지 전 산출물(design/test-report/refactor) 누락 | "재확인 해주세요" 요청 | 시그널 내용과 대조 → 실패면 부분 완료 기록, 성공이면 로그만 남기고 진행 |
| WP 리더 사망(Leader Death) | "어떻게 할까요?" 확인 | `leader-watchdog.py` 데몬이 자동 감지(폴링당 토큰 0) → autopsy 덤프 + 팀원 작업 settle 대기(기본 최대 2h) → `.needs-restart` 시그널 → 팀리더가 자동 재시작(`wp-setup.py` resume). 기본 재시도 한도 `MAX_WP_RESTART=3` 소진 시 부분 머지로 전환 |
| autopsy 원인 불명(1차 진단 실패) | 전체 transcript 덤프 승인 요청 | `--transcript-tail 50` 자동 실행 (≈100 KB). tail-50으로도 불명이면 사용자에게 전체 덤프 옵션을 **선택지로 제시만** 하고 `/dev-team`은 종료 — 더 이상 대기하지 않음 |
| 그 외 실행 중 이견·모호 | 사용자 지시 대기 | 위 원칙(기본값 / 진행 / 되돌릴 수 있는 쪽)에 따라 자체 판단, 결정 내용을 요약 보고에 기록 |

**예외** — 아래 상황만 중단한다. 자동 결정이 위험하거나 입력 자체가 잘못된 경우:
- **tmux 미설치 / 비-tmux 환경**: 즉시 중단 + 안내 (전제조건 미충족, 자동 복구 불가)
- **`/dev-team`에 Feature 토큰 전달**: 즉시 중단 + `/feat` 안내 (입력 오류)
- **git repo 아님**: 즉시 중단 + `git init` 안내 (전제조건 미충족)

> 🎯 핵심: 진행 중 "어떻게 할까요?" 질문 금지. 판단은 팀리더가 하고 **결과만 요약 보고**한다. 사용자는 사후에 요약 보고와 시그널/autopsy 증거로 개입 지점을 판단한다.

## 0. 인자 파싱 및 설정

### 0-1. 인자 파싱

Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/args-parse.py dev-team $ARGUMENTS
```
JSON 출력에서 추출:
- `docs_dir`, `subproject`, `wp_ids[]`, `options.team_size`, `options.model`, `options.on_fail`
- `options.sequential` → `SEQUENTIAL_MODE` (true/false)
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
| `MAX_WP_RESTART` | 3 | WP 리더 사망 시 watchdog/팀리더가 수행하는 자동 재시작 최대 횟수. 초과 시 partial-merge 경로로 전환 (`{WT_NAME}.restart-attempts` 파일로 카운트) |
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

> **검증 시점**: 아래 모든 항목은 `0-1`(인자 파싱)과 `0-2`(설정 변수 초기화)가 완료된 **직후**, "실행 절차 1. WP 선정"을 시작하기 **직전**에 순서대로 수행한다. 한 항목이라도 미충족이면 WP 선정·워크트리 생성·프롬프트 생성 등 모든 후속 절차를 실행하지 않고 즉시 중단한다 (리소스 부분 할당 금지).

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

- **`--sequential` 모드**: 워크트리 없이 현재 브랜치에 직접 커밋한다.
  - 동시 진행 WP가 없으므로 브랜치 분리가 불필요하다.
  - WP 간 충돌 위험은 WP를 한 번에 하나씩 실행함으로써 차단된다.
  - WP 내부는 기존과 동일한 tmux 팀원 병렬 구조를 유지한다.
  - ⚠️ 사용 전에 현재 브랜치에 커밋되지 않은 변경이 없는지 확인하라 (`git status`).
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

### 워크트리 사전 동기화 점검 (수동)

기존 워크트리(`.claude/worktrees/WP-*`)에서 진행된 작업 결과가 master `wbs.md` / `docs/tasks/`에 반영되지 않았다면, `wp-setup.py`가 미설계·미구현으로 잘못 판정해 **워커가 기존 산출물을 덮어쓸 수 있다**. **`/dev-team` 시작 전 다음 명령으로 점검**한다:

```bash
for wt in .claude/worktrees/WP-*; do
  [ -d "$wt" ] || continue
  WP=$(basename "$wt")
  echo "=== $WP ==="
  git -C "$wt" diff master -- docs/wbs.md | head -20
  git -C "$wt" log master..HEAD --oneline -- docs/tasks/ 2>/dev/null | head -10
done
```

**진척 발견 시 처리**:
- 진척이 의미 있으면 master에서 해당 status 변경·`design.md` 등을 cherry-pick 또는 수동 반영 후 `git commit`
- 노이즈(잘못된 커밋)이면 워크트리 브랜치를 reset

> ⚠️ **한계**: 워크트리 브랜치 tip에서도 산출물이 사라진 경우(과거 머지에서 잃은 경우)는 이 점검으로 감지되지 않는다. `git log --all -- docs/tasks/{TSK-ID}/*` + `git reflog` 로 직접 추적해야 한다.

## 실행 절차

### 1. WP 선정 및 Task 수집

#### WP-ID가 없는 경우 (자동 선정)

Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md - --resumable-wps
```
JSON 출력의 실행 가능 WP 목록을 **전부 자동 선정**하여 즉시 다음 단계로 진행한다 (자율 실행 원칙). 선정 결과는 다음 포맷으로 **안내 메시지로만** 출력한다:
```
🤖 자동 선정 WP: [WP-01, WP-02, ...] (총 N개) — 확인 없이 진행합니다.
```
사용자에게 "진행할까요?" 같은 확인을 받지 않는다. 선정 결과가 비어 있으면(실행 가능 WP 없음) 그때만 중단하고 사유를 보고한다.

#### WP-ID가 있는 경우

각 WP에 대해 Task 수집:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {WP-ID} --tasks-pending
```
JSON 출력에서 미완료 Task 목록을 확인한다.

### 1-b. category: feat Task 감지 및 별도 dispatch

각 WP에 대해 `--tasks-pending` 실행 **전에** feat Task 목록을 추출한다:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {WP-ID} --feat-tasks
```

출력 예시:
```json
[{"tsk_id": "TSK-01-02", "feat_name": "independent-feature-task", "title": "Independent Feature Task"}]
```

feat Task가 있으면 팀리더는 각 feat Task에 대해 **별도 tmux window를 spawn**한다 (worktree 없음, main 브랜치 기준):

```bash
# feat Task 1개당 1개 window — 현재 디렉토리(main 브랜치)에서 /feat 실행
tmux new-window -t {SESSION} -n "feat-{feat_name}"
tmux send-keys -t "{SESSION}:feat-{feat_name}" "claude --project-dir '{PROJECT_DIR}' '/feat {feat_name}'" Enter
```

**feat window 관리 규칙**:
- feat window는 WP window와 **별개**로 관리한다. WP DDTR 시그널 감시 루프(`signal-helper.py wait`)에 포함하지 않는다.
- feat window는 `/feat` 스킬 자체가 완료를 관리하므로 팀리더가 별도로 시그널을 감시할 필요가 없다.
- feat Task가 없는 WP에서는 이 단계를 건너뛴다.
- feat Task가 포함된 WP에서 `--tasks-pending`은 해당 feat Task를 자동 제외하므로 DDTR 할당 시 별도 필터링 불필요.

> `dep-analysis.py`는 `category: feat` Task를 completed 집합으로 처리하므로 다른 Task가 feat Task에 depends를 걸더라도 스케줄링이 차단되지 않는다. 단, feat Task 결과가 실제로 필요한 경우 실행 타이밍은 보장되지 않으므로 feat Task에 depends를 거는 설계는 피한다.

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

> **실행 모드 분기**: `SEQUENTIAL_MODE=true`이면 "4-S. 순차 모드 실행 루프"를 따른다. `false`이면 아래 기존 절차(병렬 일괄 spawn + wait 병렬)를 따른다.

현재 세션이 **팀리더** 역할을 한다. 셋업 스크립트(`scripts/wp-setup.py`)로 worktree 생성, 프롬프트/manifest 생성, tmux spawn을 **일괄 처리**한다.

> ⚠️ 스크립트가 생성하는 모든 시그널 경로는 `SHARED_SIGNAL_DIR` (프로젝트 레벨) 하나만 사용한다.

1. **config JSON 생성** — `${CLAUDE_PLUGIN_ROOT}/skills/dev-team/references/config-schema.md`를 Read하여 스키마를 확인하고, `{TEMP_DIR}/wp-setup-config.json`을 Write 도구로 작성한다.

2. **셋업 스크립트 실행**:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/wp-setup.py" "${TEMP_DIR}/wp-setup-config.json"
   ```

   스크립트가 **자동** 수행하는 작업:
   | 작업 | 생성 파일 | 템플릿 소스 |
   |------|-----------|-------------|
   | worktree 생성 (또는 재개 감지 + 시그널 복원) | `.claude/worktrees/{WT_NAME}/` | — |
   | wbs.md에서 task 블록 추출 + DDTR 프롬프트 치환 | `{TEMP_DIR}/task-{TSK-ID}.txt` | `references/ddtr-prompt-template.md` |
   | 미설계 task용 설계 전용 프롬프트 생성 | `{TEMP_DIR}/task-{TSK-ID}-design.txt` | `references/ddtr-design-template.md` |
   | WP 리더 프롬프트 치환 | `.claude/worktrees/{WT_NAME}-prompt.txt` | `references/wp-leader-prompt.md` |
   | team manifest 생성 | `{TEMP_DIR}/team-manifest-{WT_NAME}.md` | — |
   | tmux/psmux window spawn (leader + worker, team-mode 패턴) | — (직접 `cd {worktree} && claude ...` 실행) | — |

   > `{DOCS_DIR}`, `{SUBPROJECT}`, `{SHARED_SIGNAL_DIR}`, `{TSK-ID}`, `{WP-ID}`, `{WT_NAME}`, `{TEAM_SIZE}`, `{PLUGIN_ROOT}` 등 플레이스홀더는 모두 `wp-setup.py`가 config JSON 기반으로 치환한다. **팀리더(이 스킬)와 WP 리더는 이 파일들을 절대 직접 생성하거나 덮어쓰지 마라** — 재실행 시 `wp-setup.py`가 재개 모드에서 일관되게 재생성한다.

   > `[xx]` 상태 Task는 자동 제외. 모든 Task가 `[xx]`인 WP는 즉시 `.done` 시그널 생성 후 스킵.

3. **WP별 완료 감지 · 조기 머지 · 리더 사망 자동 재시작 (zero-LLM 감시)**:

   #### 3-a. WP당 1개의 watchdog 데몬 기동 (`leader-watchdog.py`)

   각 WP를 `wp-setup.py`로 spawn한 **직후** 팀리더는 별도 Python 데몬을 백그라운드로 띄운다. 이 데몬은 LLM을 거치지 않고 30초 주기로 tmux pane 상태·시그널 파일만 확인하므로 **폴링당 토큰 0**이다:

   ```bash
   nohup python3 ${CLAUDE_PLUGIN_ROOT}/scripts/leader-watchdog.py \
     "${SESSION}" "${WT_NAME}" "${SHARED_SIGNAL_DIR}" \
     --plugin-root "${CLAUDE_PLUGIN_ROOT}" \
     --config "${TEMP_DIR}/wp-setup-config.json" \
     --interval 30 \
     --confirm-streak 2 \
     --worker-settle-timeout 7200 \
     >> "${SHARED_SIGNAL_DIR}/${WT_NAME}.watchdog.stdout" 2>&1 &
   echo "watchdog: ${WT_NAME} pid=$!"
   ```

   Watchdog 동작(스크립트 내부, LLM 무관):
   1. 30초마다 leader pane 0 의 `#{pane_dead}` + window 존재 여부 확인
   2. **2회 연속** 사망 감지 시 실제 죽음으로 확정 (일시 flap 방지)
   3. `leader-autopsy.py` 자동 호출 → `docs/dev-team/autopsy/{WT_NAME}-{UTC_TS}/summary.txt` 생성
   4. 해당 WP의 `tasks[]` (config JSON에서 로드) 중 `.running` 하트비트가 살아있는(<5분) task가 모두 터미널 상태(`.done`/`.failed`/`.bypassed`) 또는 하트비트 stale이 될 때까지 대기 (기본 최대 2시간)
   5. `{SHARED_SIGNAL_DIR}/{WT_NAME}.needs-restart` 원자적 생성 후 자신은 종료

   Watchdog이 종료되는 조건: `.done`/`.shutdown`/`.failed`/`.needs-restart` 중 하나라도 감지 · window 자체가 사라짐 · 사망 확정 후 needs-restart 기록 완료.

   #### 3-b. 팀리더의 단일 대기 루프 (`signal-helper.py wait`)

   팀리더는 각 WP별로 Bash `run_in_background`로 **한 줄짜리** 대기를 돌린다. `wait`가 `.done`/`.failed`/`.bypassed`/`.needs-restart` 네 가지 터미널 상태 모두를 감지하므로 별도 백업 bash 루프가 필요 없다 (기존 30초 bash while-loop 제거):

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/signal-helper.py wait {WT_NAME} {SHARED_SIGNAL_DIR} 14400
   ```

   반환 첫 줄 분기:
   | 반환 | 의미 | 후속 |
   |------|------|------|
   | `DONE:{WT_NAME}` | 정상 완료 | 5단계(A) 조기 머지 |
   | `BYPASSED:{WT_NAME}` | 부분 완료, bypass 포함 | 5단계(A) 조기 머지 |
   | `FAILED:{WT_NAME}` | WP 중단 (strict 모드 등) | 요약 보고 |
   | `NEEDS_RESTART:{WT_NAME}` | **watchdog이 리더 사망 감지 → 자동 재시작 요청** | 3-c 재시작 절차 |

   #### 3-c. `NEEDS_RESTART:{WT_NAME}` 수신 시 자동 재시작 절차 (자율 실행 원칙)

   팀리더는 사용자 확인 없이 다음을 순서대로 수행한다. 시그널 body(≈1 KB JSON)만 Read하고 그 외에는 LLM 호출이 없다:

   1. **시그널 본문 Read** — `{SHARED_SIGNAL_DIR}/{WT_NAME}.needs-restart` (JSON)에서 `autopsy_dir`, `workers_settled`, `workers_still_active_on_timeout` 확인. 필요 시 autopsy summary 1건(`{autopsy_dir}/summary.txt`, <2 KB)만 Read하여 사유 파악.

   2. **재시작 시도 한도 체크** — `{SHARED_SIGNAL_DIR}/{WT_NAME}.restart-attempts` 파일의 정수를 읽고(없으면 0) +1 하여 다시 기록. 값이 `MAX_WP_RESTART` (기본 3) 이상이면 **4번으로 분기**(fallback). 이하이면 **5번**으로 진행.
      ```bash
      ATT_FILE="${SHARED_SIGNAL_DIR}/${WT_NAME}.restart-attempts"
      ATT=$(cat "$ATT_FILE" 2>/dev/null || echo 0); ATT=$((ATT + 1)); echo "$ATT" > "$ATT_FILE"
      ```

   3. **죽은 window 정리** — `graceful-shutdown.py --no-marker`로 잔존 pane(아직 살아있는 worker 포함) 안전 종료. `.needs-restart` 생성 시점에 이미 worker들은 settle 상태이므로 여기서 kill되더라도 in-flight 작업은 없다.
      ```bash
      python3 ${CLAUDE_PLUGIN_ROOT}/scripts/graceful-shutdown.py \
        "${SESSION}" "${WT_NAME}" "${SHARED_SIGNAL_DIR}" \
        --no-marker --reason leader-death-restart
      ```

   4. **(fallback — 한도 초과)** 재시작을 포기하고 기존 partial-merge 경로로 전환한다:
      - `.needs-restart`를 읽어 완료 Task 목록 추출 + wbs.md의 `[xx]` 상태로 재확인
      - `{WT_NAME}.done` (복구 시그널) 생성 — 포맷은 `references/signal-protocol.md` "Leader Death Recovery `.done` 포맷" 참조. body에 `restart_attempts={ATT}`와 `final=partial-after-restart-exhausted` 포함
      - 정상 머지 플로우로 진행 (`merge-procedure.md` 5단계(A))
      - 이 경로 진입 시 사용자에게 요약 보고에 "재시작 한도 소진 후 부분 머지로 전환" 명시

   5. **(정상 재시작)** 기존 config JSON으로 `wp-setup.py`를 **같은 인자** 그대로 다시 실행한다. 워크트리가 존재하므로 자동 resume 모드로 동작하여 완료된 Task(`.done` 시그널)은 스킵하고 미완료만 재할당한다:
      ```bash
      python3 ${CLAUDE_PLUGIN_ROOT}/scripts/signal-helper.py ack-restart "${WT_NAME}" "${SHARED_SIGNAL_DIR}"
      python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wp-setup.py "${TEMP_DIR}/wp-setup-config.json"
      ```
      > `ack-restart`는 `.needs-restart`를 제거하고 `.watchdog.log`를 `.watchdog.log.prev`로 회전시킨다. 이게 선행되어야 새 watchdog이 생성 즉시 종료되지 않는다.

   6. **새 watchdog 재기동** — 3-a와 동일 명령으로 watchdog을 다시 백그라운드 실행한다. 그리고 `signal-helper.py wait`도 재투입하여 다음 터미널 상태까지 대기한다 (현재 `wait` 프로세스는 `NEEDS_RESTART` 반환 후 이미 종료됨).

   #### 3-d. 요약 보고 시 기록 항목

   최종 요약 보고에 재시작 관련 필드를 포함한다:
   - WP별 재시작 횟수 (`{WT_NAME}.restart-attempts`)
   - 각 autopsy 덤프 경로
   - 재시작 한도 초과로 partial-merge된 WP 목록 (있는 경우)

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

1. **각 WP에 대해 `graceful-shutdown.py` 호출** (마커 생성 → Escape → `/exit` → 대기 → `kill-window`):
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/graceful-shutdown.py {SESSION} {WT_NAME} {SHARED_SIGNAL_DIR} --reason "user-shutdown"
   ```
   헬퍼는 absolute pane ID를 사용하므로 `${SESSION}:${WT_NAME}` target 파싱(점이 포함된 이름·psmux target-resolver 차이)에 영향 받지 않는다. `.shutdown` 마커가 다음 resume 시 `wp-setup.py`가 "사용자가 의도적으로 중단한 WP" 임을 식별하여 **`.done`과 구분**되게 한다 — Leader Death 경로(`.done` + 부분 머지)와 달리 **머지 트리거가 아니며**, 자동 제거 + state.json 기반 정상 재개된다.

2. **보존 대상** (절대 삭제하지 않는다):
   - 워크트리: `.claude/worktrees/{WT_NAME}/`
   - 브랜치: `dev/{WT_NAME}`
   - 프롬프트 파일: `{TEMP_DIR}/task-*.txt`, `.claude/worktrees/{WT_NAME}-prompt.txt`
   - 시그널 디렉토리: `{SHARED_SIGNAL_DIR}/`

3. **종료 보고**: 현재 진행 상황을 사용자에게 요약 보고 (WP별 완료/진행중/미시작 Task 수).

**Leader Death vs Graceful Shutdown vs Bypass 시그널 대비**:

| 경로 | 생성 시그널 | 머지 트리거 | Resume 동작 |
|------|------------|-------------|-------------|
| Leader Death — 자동 재시작(기본) | `.needs-restart` (watchdog이 기록) | ❌ (재시작 후 정상 `.done` 대기) | 팀리더가 `ack-restart` → `wp-setup.py` resume → 새 watchdog 기동 |
| Leader Death — 재시작 한도 초과(fallback) | `.done` (메타 포함) | ✅ 자동 조기 머지 (부분 완료) | 완료 Task만 머지, 미완료는 요약 보고에 기록 (수동 `/dev` 재실행) |
| Graceful Shutdown (사용자 중단) | `.shutdown` | ❌ 머지 안 함 | wp-setup.py가 `.shutdown` 제거 후 state.json 기반 정상 재개 |
| Task Bypass (에스컬레이션 소진) | `.bypassed` (task 레벨) | ❌ (WP `.done`에 포함) | 유지 — 의존 task 차단 해제, state.json `bypassed: true` |

> 워크트리와 프롬프트를 보존하면 이후 `/dev-team`을 다시 실행할 때 `wp-setup.py`가 기존 워크트리를 감지하여 재활용한다.

#### 4-S. 순차 모드 실행 루프 (`SEQUENTIAL_MODE=true`)

WP 목록을 인자 순서대로 (또는 `--resumable-wps` 결과 순서대로) 하나씩 처리한다. 각 WP에 대해 다음을 순서대로 수행한다:

1. **skip 판단**: 해당 WP의 모든 Task가 `[xx]`이면 skip하고 다음 WP로.
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {WP-ID} --tasks-pending
   ```
   결과가 빈 배열이면 해당 WP skip.

2. **config JSON 작성** (`{TEMP_DIR}/wp-setup-config.json`):
   - `sequential_mode: true` 필드 포함
   - `current_branch`: `git rev-parse --abbrev-ref HEAD`로 취득
   - `wps` 배열에 현재 WP **1개만** 포함 (복수 WP 넣지 않음)
   - 스키마는 `config-schema.md` 참조
   - `{MODE_NOTICE}` 치환 값은 `wp-setup.py`가 `current_branch` 기반으로 자동 생성

3. **wp-setup.py 실행**:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/wp-setup.py" "${TEMP_DIR}/wp-setup-config.json"
   ```
   스크립트가 자동으로 수행하는 작업 (sequential_mode=true 시):
   - worktree / branch 생성 **스킵**
   - `wt_path="."` (repo root)로 tmux spawn
   - wbs.md 기반 시그널 복원 (이전 WP의 [xx] 상태 반영)
   - DDTR 프롬프트·manifest 생성 (`TEMP_DIR/seq-prompts/` 하위)

4. **watchdog 기동** (기존과 동일):
   ```bash
   nohup python3 ${CLAUDE_PLUGIN_ROOT}/scripts/leader-watchdog.py \
     "${SESSION}" "${WT_NAME}" "${SHARED_SIGNAL_DIR}" \
     --plugin-root "${CLAUDE_PLUGIN_ROOT}" \
     --config "${TEMP_DIR}/wp-setup-config.json" \
     --interval 30 --confirm-streak 2 --worker-settle-timeout 7200 \
     >> "${SHARED_SIGNAL_DIR}/${WT_NAME}.watchdog.stdout" 2>&1 &
   ```

5. **완료 대기**:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/signal-helper.py wait {WT_NAME} {SHARED_SIGNAL_DIR} 14400
   ```
   반환 분기:
   - `DONE` / `BYPASSED` → 6번으로 진행
   - `FAILED` → 요약 보고에 기록, 다음 WP 계속 (`strict` 모드일 경우 루프 중단)
   - `NEEDS_RESTART` → 기존 3-c 재시작 절차 적용 (sequential 모드에서도 동일)

6. **window 정리** (graceful shutdown, 마커 없음):
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/graceful-shutdown.py \
     "${SESSION}" "${WT_NAME}" "${SHARED_SIGNAL_DIR}" \
     --no-marker --reason sequential-wp-done
   ```
   - `--no-marker`: `.shutdown` 마커를 생성하지 않음 (정상 완료이므로 resume 트리거 불필요)
   - window 종료 실패는 경고로만 처리하고 다음 WP로 진행

7. 다음 WP로 반복. 모든 WP 완료 후 **5단계 결과 통합**으로.

---

### 5. 결과 통합 (팀리더)

> **순차 모드** (`SEQUENTIAL_MODE=true`): 워크트리가 없으므로 머지 절차를 건너뛴다. 모든 Task 커밋은 이미 현재 브랜치에 누적되어 있다. 아래 최종 요약 보고만 수행한다.
>
> 순차 모드 요약 보고에 포함:
> - 실행된 WP 목록 및 각 WP의 완료/bypass/실패 Task 수
> - `"머지 없음 (순차 모드 — 현재 브랜치에 직접 커밋됨)"` 명시
> - WP 간 실행 시간 (각 WP의 wall-clock 시간)

`${CLAUDE_PLUGIN_ROOT}/skills/dev-team/references/merge-procedure.md`를 Read하여 머지 절차를 따른다.

WP 완료 시그널(`{SHARED_SIGNAL_DIR}/{WT_NAME}.done`) 감지 시 → **(A) 조기 머지** 실행.
모든 WP 완료 후 → **(B) 전체 완료 머지**로 미처리 WP 순차 머지.

---

## 6. 사망 원인 조사 (Post-mortem Investigation)

사용자가 **"WP 리더가 왜 죽었어" / "사망 원인 알아봐" / "autopsy 보여줘" / "dead leader 조사" / "리더 크래시 분석"** 등의 자연어로 요청하면 이 섹션을 따른다. 이때 dev-team이 활성 실행 중이든 이미 종료되었든 무관 — 덤프는 파일로 남는다.

### 6-1. 덤프 위치 및 선택

덤프는 항상 **`docs/dev-team/autopsy/{WT_NAME}-{UTC_TS}/`** 에 저장된다 (서브프로젝트 있으면 `docs/{SUBPROJECT}/dev-team/autopsy/`).

1. **덤프 목록 조회** (Bash):
   ```bash
   ls -lt docs/dev-team/autopsy/ 2>/dev/null || echo "(no autopsies yet)"
   ```
   출력 없으면 "아직 사망한 리더가 없거나 autopsy가 기록되지 않았습니다"로 응답하고 중단.

2. **조사 대상 결정**:
   - 사용자가 특정 WP 지정(예: "WP-02 리더") → `WP-02-*` glob 중 **가장 최근 타임스탬프** 선택
   - WP 미지정 → 가장 최근 덤프 1건 선택. 여러 건이 같은 질문 대상일 수 있으면 덤프 개수와 각 WP를 먼저 사용자에게 요약 보고

### 6-2. 1차 진단 — `summary.txt`만 Read

**반드시 `summary.txt`만 Read한다.** pane-scrollback / transcript 원본은 LLM이 직접 읽지 않는다 (토큰 소모 방지). summary.txt 용량은 2 KB 이하로 설계됨.

```
docs/dev-team/autopsy/{WT_NAME}-{UTC_TS}/summary.txt
```

summary.txt 구조와 진단 체크리스트:

| 섹션 | 확인 포인트 | 전형적 사망 원인 |
|------|-------------|------------------|
| `## pane scrollback — last 40 lines` | 마지막 tool/CLI 출력 | `API Error: 529` (rate limit), `context window exceeded`, Python traceback, `/exit` 오발송, `node: ENOMEM` |
| `## signals at death` → `running` | 사망 순간 진행 중이던 task | 특정 TSK에서 반복 사망 → 그 task가 원인 (프롬프트·테스트 명령 점검) |
| `## signals at death` → `failed` vs `done` | 진척도 대비 사망 시점 | failed 누적 후 사망 → 에스컬레이션 루프 폭주 의심 |
| `## git state` | 마지막 커밋 해시, 미커밋 유무 | 미커밋 누적 → 긴 쓰기 작업 중 사망 |

진단 결과는 다음 포맷으로 보고:
```
🔍 Autopsy 분석: {WT_NAME}-{UTC_TS}
- 의심 원인: {카테고리 — rate limit / context overflow / task 특정 / 외부 kill / 기타}
- 결정적 단서: {summary.txt에서 인용한 1-3줄}
- 사망 시점 진행 중 task: {running 시그널 목록}
- 권장 후속 조치: {재시도 / 프롬프트 수정 / 모델 변경 / transcript 보강 조사}
```

### 6-3. 2차 진단 — transcript 보강 (1차로 원인 특정 불가 시에만)

`summary.txt` 의 pane scrollback 만으로 원인 판단이 안 서면 **그때만** transcript를 끌어온다. 기본은 tail 50 메시지 (~100 KB):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/leader-autopsy.py {SESSION_HINT} {WT_NAME} {SHARED_SIGNAL_DIR} \
  --out-root docs/dev-team/autopsy \
  --worktree .claude/worktrees/{WT_NAME} \
  --project-dir .claude/worktrees/{WT_NAME} \
  --transcript-tail 50
```

> `--project-dir`는 **워크트리 경로**를 넘긴다 (WP 리더의 claude 세션 transcript 는 `~/.claude/projects/{encoded-worktree-path}/*.jsonl` 에 기록됨). 프로젝트 루트를 넘기면 팀리더 자신의 transcript가 잡혀 오답이 된다.
> `{SESSION_HINT}` / `{SHARED_SIGNAL_DIR}`는 이미 사망한 세션이어도 무관 — 새 덤프 디렉토리만 생성되고 tmux 호출은 실패해도 graceful하게 기록된다.

재호출로 새로 생긴 덤프 디렉토리의 `summary.txt` 를 다시 Read — 하단에 `transcript-tail.jsonl` 경로가 추가되어 있다. 사용자에게는 파일 경로만 안내하고 **LLM이 jsonl 원본을 직접 Read하지 마라** (수백 KB, 토큰 낭비). 사용자가 "그 내용 요약해줘" 같이 명시적으로 요구하면 그때만 `head -n 5 transcript-tail.jsonl` 로 샘플만 보고.

### 6-4. 조사 중단 조건

- 2차 진단(transcript-tail) 후에도 원인 불명 → 전체 덤프(`--include-transcript`, ~2-10 MB)는 **사용자가 명시 요청할 때만** 실행한다. dev-team 자체는 `--transcript-tail 50`까지만 자동 실행하고 여기서 조사 종료(자율 실행 원칙: 대기 금지). 사용자에게는 "전체 덤프가 필요하면 `--include-transcript`로 재호출하세요"라는 **안내만** 포함해 보고하고 프롬프트 대기하지 않는다.
- 사용자가 "그만", "stop", "충분해" 등으로 중단 요청 → 즉시 종료.
- 의심 원인이 특정 task 반복 사망으로 확인되면 → 해당 task의 프롬프트/테스트 명령 검토로 전환 제안하고 조사 종료.
