# dev-team-sequential: `/dev-team --sequential` 순차 WP 모드 - 설계

## 요구사항 확인

- `/dev-team`에 `--sequential` 플래그를 추가하여 WP를 한 번에 하나씩 순차 실행하되, WP 내부는 기존과 동일한 tmux 팀원 병렬 구조를 유지한다.
- 워크트리를 생성하지 않고 현재 브랜치·저장소 루트에서 직접 작업하므로, WP 완료 후 머지 절차가 불필요하다.
- watchdog/autopsy/signal 프로토콜은 기존 그대로 사용하며, WP 간 순서는 인자 순서 또는 `--resumable-wps` 결과 순서를 따른다.

## 타겟 앱

- **경로**: N/A (단일 앱 — CLI/플러그인 레이어 변경)
- **근거**: UI 없음. Python 스크립트·SKILL.md 수정만으로 구현 가능.

## 구현 방향

3곳의 분기 지점을 최소 수정으로 처리한다. (A) `args-parse.py`에 `--sequential` 플래그 파싱 추가, (B) `wp-setup.py`에 `sequential_mode` config 필드를 추가하여 True면 worktree 생성·brach 생성을 스킵하고 `wt_path="."` 강제, (C) `skills/dev-team/SKILL.md`에 순차 루프 분기 섹션 추가 및 머지 스킵 처리. `wp-leader-prompt.md`에 `{MODE_NOTICE}` 치환 변수를 추가하여 WP 리더에게 "현재 브랜치 직접 커밋" 안내를 조건부 삽입한다.

## 파일 계획

**경로 기준:** 프로젝트 루트 기준.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/args-parse.py` | `dev-team` 스킬에 `--sequential`/`--seq`/`--one-wp-at-a-time` 플래그 파싱 추가. `options.sequential: bool` 필드를 JSON 출력에 추가 | 수정 |
| `scripts/wp-setup.py` | config에 `sequential_mode: bool` 필드 추가. True면 git worktree add / branch 생성 스킵, `wt_path = repo_root(=".")` 강제. resume 시 cross-worktree 시그널 복원 로직을 wbs.md `[xx]` 기반으로 대체 | 수정 |
| `skills/dev-team/SKILL.md` | 순차 모드 분기 섹션 추가 (전제조건 고지, 실행 모드 분기, 순차 루프, 머지 스킵) | 수정 |
| `skills/dev-team/references/config-schema.md` | `sequential_mode: bool (default: false)` 필드 문서화 | 수정 |
| `skills/dev-team/references/wp-leader-prompt.md` | `{MODE_NOTICE}` 치환 변수 추가 (순차 모드 조건부 안내문) | 수정 |
| `skills/dev-help/SKILL.md` | `/dev-team --sequential` 사용 예시 및 선택 기준 추가 | 수정 |
| `CLAUDE.md` | Layer 3 설명에 `--sequential` 모드 언급 | 수정 |
| `README.md` | `/dev-team` 섹션에 `--sequential` 모드 언급 | 수정 |

## 진입점 (Entry Points)

N/A (CLI/스킬 레이어 변경. UI 없음)

## 주요 구조

### A. `args-parse.py` — `--sequential` 플래그 파싱

**위치**: 기존 `--on-fail` 파싱 블록(line 155-162) 직후에 추가.

```python
elif tok in ("--sequential", "--seq", "--one-wp-at-a-time"):
    opt_sequential = True
```

`options` dict에 `"sequential": opt_sequential` 필드 추가 (초기값 `False`).

### B. `wp-setup.py` — `sequential_mode` 분기

**config 필드 읽기** (line 186 근방 `config.get(...)` 블록에 추가):
```python
sequential_mode = config.get("sequential_mode", False)
```

**Worktree 섹션 분기** (line 250-268 대체):

```python
# --- 1. Worktree (또는 sequential_mode: repo root 직접 사용) ---
if sequential_mode:
    # 워크트리 없음 — 저장소 루트에서 직접 작업
    wt_path = "."
    resume_mode = False  # signal dir은 항상 fresh start or based on state.json
    print(f"[{wp_id}] sequential_mode: skip worktree, wt_path=repo_root")
else:
    # 기존 병렬 모드: worktree 생성 or resume
    wt_path = f".claude/worktrees/{wt_name}"
    resume_mode = False
    branch_check = run_cmd(["git", "branch", "--list", f"dev/{wt_name}"], capture=True, check=False)
    if os.path.isdir(wt_path) and branch_check.stdout.strip():
        # ... (기존 health check + resume 로직 그대로)
        resume_mode = True
    else:
        run_cmd(["git", "worktree", "add", wt_path, "-b", f"dev/{wt_name}"])
```

**rerere 섹션**: `sequential_mode`가 True이면 `--worktree .`로 호출 (repo root에서 실행). 기존 `wt_path_abs`가 `os.path.abspath(".")` = repo root가 되므로 기존 호출 코드 그대로 동작.

**Signal restore 섹션** (line 287-315 대체):

`sequential_mode=True`일 때 cross-worktree scan(`glob(".claude/worktrees/*/")`)은 의미없으므로, **직접 wbs.md를 스캔**하는 경로로 대체:

```python
if resume_mode and not sequential_mode:
    # 기존 cross-worktree 시그널 복원 (병렬 모드에서만)
    for wt_dir in glob.glob(".claude/worktrees/*/"):
        ...  # 기존 로직 그대로

if sequential_mode:
    # 워크트리 없음 — wbs.md의 [xx]/[dd] 상태를 직접 읽어 시그널 복원
    # (이전 WP 실행 결과가 메인 wbs.md에 직접 반영되므로)
    with open(wbs_path, "r", encoding="utf-8") as f:
        main_wbs_text = f.read()
    for m in re.finditer(r'TSK-\d+(?:-\d+)+', main_wbs_text):
        tsk = m.group()
        done_path = os.path.join(shared_signal_dir, f"{tsk}.done")
        design_done_path = os.path.join(shared_signal_dir, f"{tsk}-design.done")
        for line in main_wbs_text.splitlines():
            if tsk not in line:
                continue
            if "[xx]" in line:
                if not os.path.exists(done_path):
                    pathlib.Path(done_path).write_text("resumed-sequential\n", encoding="utf-8")
                if not os.path.exists(design_done_path):
                    pathlib.Path(design_done_path).write_text("resumed-sequential\n", encoding="utf-8")
                break
            if ("[dd]" in line or "[im]" in line) and not os.path.exists(design_done_path):
                pathlib.Path(design_done_path).write_text("resumed-sequential\n", encoding="utf-8")
                break
```

> 이 로직은 기존 병렬 모드의 cross-worktree scan(line 292-315)과 동일한 패턴을 wbs.md 단일 파일에 적용한 것이다. `.failed` 삭제 / stale `.running` 삭제는 두 모드 공통 (`resume_mode or sequential_mode` 조건으로 실행).

**tmux spawn 섹션** (line 501-593): `worktree_abs`를 `os.path.abspath(wt_path)`로 계산하는데, `sequential_mode`에서 `wt_path="."` → `worktree_abs=repo_root`이 자동으로 맞아 떨어진다. 별도 분기 불필요.

**Prompt 파일 저장 경로**: 기존 코드가 `.claude/worktrees/{wt_name}-prompt.txt` 등에 쓰는데, `sequential_mode`일 때는 이 디렉토리가 없다. 따라서:

```python
if sequential_mode:
    prompt_dir = os.path.join(temp_dir, "seq-prompts")
else:
    prompt_dir = ".claude/worktrees"
os.makedirs(prompt_dir, exist_ok=True)

wp_leader_out     = os.path.join(prompt_dir, f"{wt_name}-prompt.txt")
init_file_abs     = os.path.abspath(os.path.join(prompt_dir, f"{wt_name}-init.txt"))
cleanup_file_abs  = os.path.abspath(os.path.join(prompt_dir, f"{wt_name}-cleanup.txt"))
```

### C. `skills/dev-team/SKILL.md` — 순차 모드 분기

#### C-1. 인자 파싱 섹션 (0-1)

`options.sequential`을 추출 변수에 추가:
```
- `options.sequential` → `SEQUENTIAL_MODE` (true/false)
```

#### C-2. 전제조건 섹션에 순차 모드 고지 추가

기존 "플랫폼 지원 및 시그널 경로" 항목 뒤에 추가:

```markdown
- **`--sequential` 모드**: 워크트리 없이 현재 브랜치에 직접 커밋한다.
  동시 진행 WP가 없으므로 브랜치 분리가 불필요하다. WP 간 충돌 위험은 WP를 한 번에
  하나씩 실행함으로써 차단된다. 이 모드를 사용하기 전에 현재 브랜치에 커밋되지 않은
  변경이 없는지 확인하라 (`git status`).
```

#### C-3. 4단계 "DDTR 프롬프트 파일 생성 및 팀 spawn" 섹션에 분기 추가

기존 config JSON 작성 전 분기 인트로 삽입:

```markdown
> **실행 모드 분기**: `SEQUENTIAL_MODE=true`이면 "순차 모드 실행 루프"를 따른다.
> `false`이면 아래 기존 절차(병렬 일괄 spawn + wait 병렬)를 따른다.
```

**순차 모드 실행 루프** 섹션 (새 하위섹션):

```markdown
#### 4-S. 순차 모드 실행 루프 (`SEQUENTIAL_MODE=true`)

WP 목록을 인자 순서대로 (또는 `--resumable-wps` 결과 순서대로) 하나씩 처리한다.
각 WP에 대해 다음을 순서대로 수행한다:

1. **skip 판단**: 해당 WP의 모든 Task가 `[xx]`이면 skip하고 다음 WP로.
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {WP-ID} --tasks-pending
   ```
   결과가 빈 배열이면 해당 WP skip.

2. **config JSON 작성** (`{TEMP_DIR}/wp-setup-config.json`):
   - `sequential_mode: true` 필드 포함
   - `wps` 배열에 현재 WP 1개만 포함 (배열에 복수 WP 넣지 않음)
   - 스키마는 `config-schema.md` 참조. `{MODE_NOTICE}` 치환 값:
     `"⚠️ 순차 모드: 현재 브랜치({BRANCH})에 직접 커밋하라. 워크트리 없음. 머지 불필요."`
     (브랜치 명은 `git rev-parse --abbrev-ref HEAD`로 취득)

3. **wp-setup.py 실행**:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/wp-setup.py" "${TEMP_DIR}/wp-setup-config.json"
   ```
   스크립트가 자동으로 수행하는 작업 (sequential_mode=true 시):
   - worktree / branch 생성 **스킵**
   - `wt_path="."` (repo root)로 tmux spawn
   - wbs.md 기반 시그널 복원 (이전 WP의 [xx] 상태 반영)
   - DDTR 프롬프트·manifest 생성

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
```

#### C-4. 5단계 "결과 통합 (팀리더)" 섹션에 분기 추가

기존 머지 절차 호출 전에:

```markdown
> **순차 모드** (`SEQUENTIAL_MODE=true`): 워크트리가 없으므로 머지 절차를 건너뛴다.
> 모든 Task 커밋은 이미 현재 브랜치에 누적되어 있다. 아래 최종 요약 보고만 수행한다.
```

최종 요약 보고에 포함할 항목 (순차 모드 전용):
- 실행된 WP 목록 및 각 WP의 완료/bypass/실패 Task 수
- `"머지 없음 (순차 모드 — 현재 브랜치에 직접 커밋됨)"` 명시
- WP 간 실행 시간 (각 WP의 wall-clock 시간)

### D. `wp-leader-prompt.md` — `{MODE_NOTICE}` 치환 변수

**경로 변수 섹션** 끝에 추가 (현재 line 36-43 근방):

```
- MODE_NOTICE = {MODE_NOTICE}
  (비어 있으면 병렬 모드 / 내용이 있으면 순차 모드 안내. `wp-setup.py`가 치환)
```

프롬프트 본문 적절한 위치(예: "경로 변수" 섹션 바로 위)에 삽입:

```
{MODE_NOTICE}
```

`wp-setup.py`의 `substitute_vars()` 함수에 `{MODE_NOTICE}` 키 추가:

```python
"{MODE_NOTICE}": kwargs.get("mode_notice", ""),
```

`sub_kwargs`에 `mode_notice` 전달:
- `sequential_mode=True`인 경우:  
  `mode_notice = f"⚠️ 순차 모드: 워크트리 없음. 현재 브랜치({current_branch})에 직접 커밋하라. 머지 절차 없음."`
- `sequential_mode=False`인 경우:  
  `mode_notice = ""`  (병렬 모드는 기존 안내 없음)

`current_branch`는 config 생성 시점에 팀리더가 `git rev-parse --abbrev-ref HEAD`로 취득하여 config JSON의 `current_branch` 필드로 전달. `wp-setup.py`는 이 값을 `config.get("current_branch", "")` 로 읽는다.

## 데이터 흐름

```
사용자: /dev-team --sequential WP-01 WP-02
  → args-parse.py: options.sequential=true
  → SKILL.md 팀리더: SEQUENTIAL_MODE=true 분기
    → for each WP:
        config.json (sequential_mode=true, wps=[단일WP])
        → wp-setup.py: skip worktree, wt_path=".", spawn tmux
        → signal-helper wait {WT_NAME}.done
        → graceful-shutdown --no-marker
  → 최종 요약 (머지 없음 명시)
```

## 설계 결정

### 결정 1: `wt_path="."` 시 prompt 파일 저장 경로

- **결정**: `sequential_mode=True`이면 `{TEMP_DIR}/seq-prompts/` 하위에 prompt 파일 저장
- **대안**: `.claude/worktrees/` 디렉토리를 강제 생성하여 기존 경로 그대로 사용
- **근거**: 워크트리 없는 모드에서 `.claude/worktrees/`를 생성하면 사용자에게 혼란을 줄 수 있음. `TEMP_DIR` 하위는 temp 파일로 명확하고 이미 `task-*.txt`가 저장되는 위치임.

### 결정 2: 순차 루프 내 resume 판단

- **결정**: WP 진입 시 `wbs-parse.py --tasks-pending` 결과가 빈 배열이면 해당 WP를 skip
- **대안**: signal-helper로 `{WT_NAME}.done`이 이미 존재하는지 확인
- **근거**: wbs.md `[xx]` 상태가 단일 진실 원천. `--tasks-pending`은 state.json을 참조하므로 더 정확. wp-setup.py 자체도 이 로직을 내부적으로 갖고 있으나, 팀리더가 사전에 판단해 spawn 자체를 건너뛰는 것이 더 명확하고 불필요한 tmux window 생성을 방지한다.

### 결정 3: `--resumable-wps` vs 인자 순서 — 순서 결정 로직

- **결정**: WP가 명시적으로 인자로 주어지면 **인자 순서** 그대로 실행. WP 인자가 없으면 `--resumable-wps` 결과 순서(WBS 파일 내 등장 순서)를 사용. 자동 위상정렬(dep-analysis.py 기반 레벨 순서)은 follow-up.
- **대안**: 항상 dep-analysis.py로 위상정렬하여 자동 순서 결정
- **근거**: 1차 구현 범위(spec.md "범위 제외" 항목). 위상정렬은 WP 간 의존성이 명시된 경우 유용하지만, 의존성 없이 독립적인 WP가 대부분인 현실에서는 인자 순서가 더 직관적이다.

### 결정 4: `--sequential`와 `--resumable-wps` 조합 시 순서

- **결정**: `--sequential` + WP 인자 없음 → `--resumable-wps` 목록을 **WBS 파일 내 등장 순서**로 정렬하여 순차 실행
- **대안**: dep-analysis.py의 레벨 순서로 정렬
- **근거**: `--resumable-wps` 결과는 이미 "실행 가능(의존 해소된)" WP 목록이므로 별도 위상정렬 없이 WBS 파일 순서가 합리적 기본값. WP 간 의존성이 있을 경우 사용자가 WP 인자를 명시적으로 지정하면 됨.

## 선행 조건

- Python 3 표준 라이브러리만 사용 (기존 스크립트와 동일)
- tmux 또는 psmux (기존 `/dev-team` 전제조건과 동일)
- git 저장소 (기존 `/dev-team` 전제조건과 동일)

## 리스크

- **LOW**: `wt_path="."` 시 `worktree_abs = os.path.abspath(".")` = repo root. `leader_spawn`/`worker_spawn`의 `cd "{worktree_abs}"` 명령은 이미 repo root에 있으므로 no-op이지만 정상 동작함. 검증 필요.
- **LOW**: `sequential_mode=True`일 때 `.claude/worktrees/{wt_name}-prompt.txt` 경로에서 `{TEMP_DIR}/seq-prompts/{wt_name}-prompt.txt`로 저장 경로가 바뀌므로, Graceful Shutdown 섹션에서 "보존 대상" 경로 설명도 순차 모드 주석 추가 필요.
- **LOW**: `--no-marker` graceful-shutdown이 psmux 환경에서 no-op이므로(CLAUDE.md 명시), Windows psmux 사용자는 WP window가 남아있을 수 있음. 기존 병렬 모드와 동일한 수준의 한계이므로 별도 대응 없음.
- **LOW**: `sequential_mode=True`에서 `resume_mode`가 항상 False인 점 — 실제로 signal 복원은 wbs.md 스캔으로 수행하므로 기능적으로 동등. 코드에서 `resume_mode` 변수 용도가 "cross-worktree scan 트리거"로만 쓰이므로 False 고정이 올바름.

## QA 체크리스트

- [ ] `args-parse.py dev-team --sequential WP-01` 실행 시 `options.sequential=true` 반환
- [ ] `args-parse.py dev-team --seq WP-01` 및 `--one-wp-at-a-time WP-01`도 동일하게 `options.sequential=true` 반환
- [ ] `args-parse.py dev-team WP-01` (플래그 없음) 시 `options.sequential=false` 반환
- [ ] `wp-setup.py` 에 `sequential_mode=true` config 전달 시 `.claude/worktrees/` 하위 디렉토리가 생성되지 않음
- [ ] `wp-setup.py` sequential_mode=true 시 tmux window의 cwd가 repo root로 spawn됨
- [ ] `wp-setup.py` sequential_mode=false 시 기존 병렬 모드 동작(worktree 생성) 회귀 없음
- [ ] SKILL.md 순차 루프: WP-01 window 먼저 뜨고 .done 후 window 정리 → WP-02 window 뜨는 순서 확인
- [ ] 모든 Task state.json이 `[xx]`로 종결되고 commit이 현재 브랜치에 누적됨
- [ ] `.claude/worktrees/` 디렉토리가 생성되지 않음 (sequential 모드 E2E)
- [ ] Resume: WP-01 진행 중 Ctrl-C → 재실행 → WP-01 resume(미완 task만) 후 WP-02 이어짐
- [ ] 병렬 모드 회귀: `/dev-team WP-01 WP-02` (플래그 없음) 시 기존 병렬+worktree+merge 동작 변경 없음
- [ ] `wp-leader-prompt.md`에서 `{MODE_NOTICE}`가 순차 모드일 때 브랜치명 포함 안내문으로 치환됨
- [ ] 병렬 모드에서 `{MODE_NOTICE}`가 빈 문자열로 치환됨 (기존 프롬프트에 노이즈 없음)
- [ ] `config-schema.md`에 `sequential_mode` 필드 문서화 확인
