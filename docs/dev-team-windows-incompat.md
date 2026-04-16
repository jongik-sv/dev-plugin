# `/dev-team` Windows 호환성 문제 분석

> 조사 일자: 2026-04-16
> 환경: Windows 11 Pro + psmux 3.3.2 + Claude Code 2.1.109 + dev-tools 1.4.4
> 프로젝트: `D:\mes\aps-batch-mailer`
> 조사 범위: `C:\Users\DKSYSTEMS\.claude\plugins\cache\dev-tools\dev\1.4.4\scripts\wp-setup.py` 및 관련 스크립트

## 요약

`/dev-team` 스킬은 설계상 "tmux 세션 + bash pane"을 가정하고 만들어졌다. 네이티브 Windows(psmux + cmd.exe 기본 쉘)에서는 **스킬 문서가 "⚠️ 부분 지원"이라고 표기한 것과 달리 실질적으로 동작하지 않는다**. `wp-setup.py`가 worktree/프롬프트 파일까지는 생성하지만, 이후 tmux window spawn 단계에서 조용히 실패하며 사용자에게 실패를 알리지 않는다. 또한 스크립트 내부의 `python3` 서브프로세스 호출이 Microsoft Store의 `python3` 스텁에 가로채여 **전부 rc=9009로 실패**하지만 `check=False`로 무시되어 wbs 상태 필터링이 전혀 동작하지 않는 잠재적 데이터 손상 경로가 있다.

## 재현 조건

| 항목 | 값 |
|------|-----|
| OS | Windows 11 Pro 10.0.26200 |
| 터미널 멀티플렉서 | psmux 3.3.2 (WinGet: `marlocarlo.psmux`) |
| `tmux` 바이너리 | `C:\Users\DKSYSTEMS\AppData\Local\Microsoft\WinGet\Links\tmux.exe` = psmux.exe 심볼릭 링크 |
| Claude Code pane 쉘 | Git Bash (`/d/mes/...`, `/c/...`) |
| psmux 기본 pane 쉘 | cmd.exe (추정 — `default-shell` 미설정) |
| psmux `bash -c` 호출 시 | WSL bash (`/mnt/d/...`, `/mnt/c/...`) |
| Python 실행기 | `python` (정상), `python3` (Microsoft Store 스텁으로 가로채짐) |
| Claude CLI | `C:\Users\DKSYSTEMS\.local\bin\claude.exe` |

---

## 이슈 분류

### 🔴 R1. `python3` 서브프로세스가 전체 rc=9009 실패 (사일런트 데이터 손상)

**파일/위치**: `wp-setup.py` lines 288, 304, 317, 323, 327

**증상**:
```python
r = run_cmd(["python3", wbs_parse, wbs_path, tsk_id, "--field", "status"],
            capture=True, check=False)
status = r.stdout.strip()
if "[xx]" in status:
    continue
```

Windows에서 `python3`는 기본 PATH에 "App Execution Aliases"로 등록된 Microsoft Store 스텁이다. 스텁은 실행 시 다음을 출력하고 즉시 rc=9009로 종료한다:
```
Python was not found; run without arguments to install from the Microsoft Store...
```

**직접 검증**:
```bash
python -c "import subprocess; r = subprocess.run(['python3', '--version'], capture_output=True, text=True); print('rc:', r.returncode, 'out:', repr(r.stdout), 'err:', repr(r.stderr))"
```
출력:
```
rc: 9009 out: '' err: 'Python was not found; run without arguments to install from the Microsoft Store...'
```

**연쇄 효과 (모두 실제로 발생한 것을 확인)**:
1. **`[xx]` 완료 Task 필터링 불능**: `status=""` → `"[xx]" in ""` == False → 이미 완료된 TSK-01-01에 대해서도 DDTR 프롬프트(`task-TSK-01-01.txt`)가 생성됨. 실제로 `C:\Users\DKSYSTEMS\AppData\Local\Temp\task-TSK-01-01.txt`가 2836바이트로 생성된 것을 확인.
2. **`design.done` 오생성**: `status=""` → `"[ ]" in ""` == False → else 분기 진입 → "design already done"으로 간주하여 `TSK-01-01-design.done`, `TSK-01-02-design.done`, ..., `TSK-02-03-design.done` 6개 전부 signal 디렉토리에 생성됨. **설계가 전혀 진행되지 않은 task를 "설계 완료"로 위조**.
3. **Task block 비어 있음**: `all_task_blocks += task_block`에서 `task_block=""` → WP 리더 프롬프트에 Task 상세가 비어 있는 상태로 주입됨 (단, 리더가 `/dev` 스킬을 호출하면 wbs.md를 직접 읽으므로 최종 실행에는 영향이 적다).
4. **cross-WP 의존성 `.done` pre-create 실패**: 다른 WP에 속하는 완료 의존성(`TSK-01-01`)을 자동 완료 시그널로 만들어두는 로직(lines 285-308)이 작동 안 함.

**상태**: 재현 완료, 데이터 손상 흔적 신호 디렉토리에 잔존.

**근본 원인**: Windows의 "App Execution Aliases" 기능은 사용자가 수동 비활성화하지 않는 한 `python3` 를 Microsoft Store로 가로챈다. `wp-setup.py`는 모든 Python 서브프로세스 호출에 하드코딩된 `"python3"`를 사용한다.

**수정 방향 (upstream 수정 필요)**: `sys.executable`을 사용하도록 변경.
```python
run_cmd([sys.executable, wbs_parse, ...], ...)
```

---

### 🔴 R2. 생성된 bash 스크립트가 CRLF 줄끝을 가짐

**파일/위치**: `wp-setup.py` line 452
```python
with open(runner_path, "w", encoding="utf-8") as f:
    f.write(runner_content)
```

**증상**: Python의 `open(path, "w", ...)`는 Windows에서 기본적으로 text 모드로 동작하며 `\n`을 `\r\n`으로 변환한다. 생성된 `.claude/worktrees/WP-01-run.sh`에는 CRLF가 포함되어 bash가 다음과 같이 실패한다:
```
.claude/worktrees/WP-01-run.sh: line 2: cd: $'.claude/worktrees/WP-01\r': No such file or directory
.claude/worktrees/WP-01-run.sh: line 3: exec: claude: not found
```
`\r` 문자가 cd의 인자 끝에 포함되어 `WP-01\r`이라는 존재하지 않는 디렉토리를 찾게 된다.

**직접 검증**:
```python
python -c "
with open('/tmp/test.sh','w',encoding='utf-8') as f: f.write('#!/bin/bash\ncd foo\n')
with open('/tmp/test.sh','rb') as f: print(f.read())
"
# b'#!/bin/bash\r\ncd foo\r\n'
```
실제 생성된 `WP-02-run.sh`도 CRLF 3개 포함으로 확인.

**수정 방향**: `open(runner_path, "w", encoding="utf-8", newline="\n")` 또는 binary 모드로 직접 `\n` write. 추가로 `ddtr prompt`, `manifest`, `wp-leader-prompt.txt` 등 모든 `.write()` 호출부도 동일한 문제가 잠재해 있음 (bash로 execute되는 것은 runner.sh 뿐이므로 체감 버그는 하나).

---

### 🔴 R3. psmux pane 기본 쉘이 cmd.exe → `.sh` runner를 실행할 수 없음

**증상**: `wp-setup.py`가 정상 경로로 `tmux new-window -t "0:" -n WP-01 .claude/worktrees/WP-01-run.sh` 를 호출하면 psmux는 window 생성까지는 성공(rc=0)하지만, 내부적으로 `default-shell`에 runner 경로를 passing 하는데 psmux의 기본 쉘이 **cmd.exe**이다. cmd.exe는 `.sh` 파일을 실행할 수 없고 `.claude`를 보자마자 다음 오류로 pane이 죽는다:

```
'.claude'은(는) 내부 또는 외부 명령, 실행할 수 있는 프로그램, 또는
배치 파일이 아닙니다.
```

**직접 검증**: `remain-on-exit on` 설정 후 `wp-setup.py`를 재실행하고 죽은 pane의 출력을 `tmux capture-pane -t %28 -p`로 추출. 위 Windows cmd.exe 한글 오류 메시지가 캡처됨. Worker pane들(split-window로 생성)도 동일하게 cmd.exe에서 `cd 'path' && claude --...` bash 문법을 파싱하지 못해 `파일 이름, 디렉터리 이름 또는 볼륨 레이블 구문이 잘못되었습니다` 오류로 죽음.

**확인된 쉘 매트릭스**:
| 상황 | 실제 쉘 |
|------|---------|
| 현재 Claude Code 세션의 Bash 도구 | Git Bash (`BASH=/usr/bin/bash`, 경로 `/d/mes/`) |
| psmux `new-window "<raw-command>"` 실행 시 | cmd.exe (default-shell) |
| psmux pane 안에서 `bash -c '...'` 명시 호출 시 | WSL bash (`BASH_VERSION=5.2.21`, 경로 `/mnt/d/`) |
| Git Bash를 psmux에서 띄우려면 | `default-shell` 명시 설정 필요 |

`default-shell`, `default-command` 모두 `tmux show-options -g` 결과 비어 있음.

**연쇄 효과**:
- wp-setup.py의 `tmux spawn` 단계가 "성공"을 보고하지만 실제로는 **모든 pane이 즉시 사망**
- `remain-on-exit off`가 기본이라 사망한 window는 자동 정리되어 `tmux list-windows`에서는 흔적조차 없음 → 사용자는 "왜 아무 일도 안 일어났지?"만 경험
- 워크트리/프롬프트는 남아 있어서 재실행 시 `resume` 경로로 탐지됨 → 계속 같은 실패 반복

**수정 방향**:
1. runner 스크립트를 cmd.exe에서 직접 실행 가능한 `.bat` 형태로 생성하거나
2. spawn 시 명시적으로 `bash -l` 또는 `bash -c "bash /path/to/run.sh"`로 감싸서 bash 강제
3. 혹은 Git Bash 경로를 `default-shell`로 자동 설정

---

### 🟡 R4. Git Bash `/c/...` 경로가 WSL bash에서는 유효하지 않음

**증상**: R3의 해결책으로 "`bash -c`로 감싸면 된다"고 생각해서 runner 스크립트에서 다음과 같이 작성했다가:
```bash
exec /c/Users/DKSYSTEMS/.local/bin/claude.exe ...
```
psmux pane에서 실행하면 `No such file or directory`로 실패한다.

**원인**: psmux가 실행하는 `bash`는 WSL bash이고, WSL의 파일시스템 뷰에서는 `C:\` 드라이브가 `/mnt/c/` 로 마운트되어 있다. `/c/Users/...`는 WSL에서는 존재하지 않는다.

**직접 검증**:
```bash
tmux new-window -d -t 0 -n DIAG "bash -c 'echo PATH=\$PATH; ls -la /c/Users/DKSYSTEMS/.local/bin/claude.exe 2>&1'"
# SHELL=/bin/bash
# BASH_VERSION=5.2.21(1)-release
# PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:...:/mnt/c/Users/DKSYSTEMS/.local/bin:...
# ls: cannot access '/c/Users/DKSYSTEMS/.local/bin/claude.exe': No such file or directory
```

Git Bash와 WSL bash의 드라이브 경로 규칙 차이:

| 쉘 | 드라이브 경로 규칙 |
|----|-------------------|
| Git Bash (MSYS2) | `/c/...`, `/d/...` (Cygwin 스타일) |
| WSL | `/mnt/c/...`, `/mnt/d/...` |
| cmd.exe / PowerShell | `C:\...`, `D:\...` |

**연쇄 효과**: Claude Code Bash 도구(Git Bash)에서 작성한 모든 상대/절대 경로가 psmux 안쪽 WSL bash에서는 무효. 혼란도가 매우 높음.

---

### 🟡 R5. `detect_mux()`가 psmux를 tmux로 오인

**파일/위치**: `wp-setup.py` lines 42-48
```python
def detect_mux() -> str | None:
    if shutil.which("tmux") and os.environ.get("TMUX"):
        return "tmux"
    if shutil.which("psmux"):
        return "psmux"
    return None
```

**증상**: Windows에서 `tmux`와 `psmux`는 **동일한 실행 파일의 WinGet 심볼릭 링크**다. `shutil.which("tmux")`는 `C:\Users\DKSYSTEMS\AppData\Local\Microsoft\WinGet\Links\tmux.exe`를 반환하는데 이것이 psmux 바이너리다. `TMUX` 환경변수도 psmux 세션 시작 시 설정된다(`/tmp/psmux-9848/default`). 따라서 `detect_mux()`는 `"tmux"`를 반환하고, wp-setup.py는 진짜 tmux인 것처럼 동작하는 branch로 진입한다.

**검증**:
```bash
type tmux  # tmux is /c/.../WinGet/Links/tmux
type psmux # psmux is /c/.../WinGet/Links/psmux
tmux info | head -3  # psmux 3.3.2 (Windows) — "psmux"임이 버전 문자열로 드러남
```

**연쇄 효과**: wp-setup.py는 psmux 전용 분기(lines 509-512, 주석 `# psmux support — similar commands, may need adjustment`)가 존재하지만 진입하지 않는다. tmux 분기가 실행되면서 split-window / set-option 등 psmux가 부분적으로만 호환하는 명령들을 호출한다.

**수정 방향**: `tmux -V` 또는 `tmux info` 출력에서 "psmux" 문자열을 검사하여 정확히 분기.

---

### 🟡 R6. psmux 분기가 미완성 — split-window/레이블/prompt 주입 부재

**파일/위치**: `wp-setup.py` lines 509-512
```python
elif mux == "psmux" and session:
    run_cmd(["psmux", "new-window", "-t", f"{session}:", "-n", wt_name, runner_path], check=False)
    print(f"[{wp_id}] spawn: psmux window {wt_name}")
```

**증상**: psmux 분기는 사실상 `new-window` 한 줄만 실행한다. 다음이 모두 누락되어 있다:
- worker pane split-window (팀원 N명 생성)
- pane label 설정
- pane-border 설정
- `automatic-rename off`
- pane ID 수집 → `pane-ids-{wt_name}.txt`
- 실제 레이아웃 tiled

**결과**: 만약 R5 수정으로 이 분기가 진입하더라도 worker pane이 생성되지 않아 WP 리더가 tmux send-keys로 Task를 할당할 대상이 존재하지 않음 → WP 리더가 무한 대기.

---

### 🟡 R7. runner/worker 명령이 bash 문법 의존

**파일/위치**: `wp-setup.py` lines 448-451, 477-478
```python
runner_content = f"""#!/bin/bash
cd "$(dirname "$0")/{wt_name}"
exec claude --dangerously-skip-permissions --model {wp_leader_model} "$(<../{wt_name}-prompt.txt)"
"""
# ...
run_cmd(["tmux", "split-window", "-t", win_target, "-h",
         f"cd '{wt_abs_path}' && claude --dangerously-skip-permissions --model {worker_model}"])
```

사용된 bash 문법:
- `"$(dirname "$0")"` — 이중 중첩 명령 치환 (bash/POSIX)
- `"$(<file)"` — bash 확장 `$(< file)`으로 파일 내용 치환 (POSIX 아님)
- `cd path && cmd` — chain (cmd.exe는 `&`)
- 작은 따옴표로 감싼 경로 — cmd.exe는 작은 따옴표를 인자 경계로 취급하지 않음

**연쇄 효과**: R3과 겹침 — cmd.exe 기본 쉘에서는 어느 하나도 작동하지 않음. WSL bash로 강제해도 R4 경로 문제와 `claude` 바이너리 경로 문제가 남음.

---

### 🟡 R8. `$TEMP`와 Python `tempfile.gettempdir()` 시스템이 다르게 해석

**증상**:
| 환경 | `$TEMP` / tempdir |
|------|------------------|
| Git Bash | `/tmp` (Cygwin view로 `C:\Users\DKSYSTEMS\AppData\Local\Temp` 실제 경로) |
| Python `tempfile.gettempdir()` | `C:\Users\DKSYSTEMS\AppData\Local\Temp` (Windows 경로) |
| WSL bash | `/tmp` (WSL 내부 파일시스템 — Windows 디스크와 완전 분리) |

**문제**: config JSON의 `temp_dir`을 Windows 경로(`C:/Users/DKSYSTEMS/AppData/Local/Temp`)로 지정하면 wp-setup.py는 그 경로에 `task-*.txt`, `team-manifest-*.md`, `wp-setup-config.json`, `pane-ids-*.txt`를 저장한다. 그런데 pane 안쪽 WSL bash에서 `cat /tmp/task-...`로 접근하면 **전혀 다른 파일시스템**(`/tmp` = WSL VHDX 내부)을 보게 된다.

DDTR 프롬프트 파일 안의 signal 디렉토리 경로도:
```bash
echo 'started' > C:/Users/DKSYSTEMS/AppData/Local/Temp/claude-signals/aps-batch-mailer/TSK-01-01.running
```
WSL bash는 `C:/...`를 드라이브 경로로 해석하지 못해(Git Bash는 일부 해석) 현재 디렉토리 기준 상대 경로 `C:/Users/...`로 파일을 만든다.

**연쇄 효과**: 시그널 파일의 프로젝트 간 공유 가정이 깨짐. WP-01이 쓴 `.done` 파일을 팀리더(Claude Code Bash = Git Bash)가 읽을 수 없을 가능성. `signal-protocol.md`가 요구하는 rename 원자성도 저해.

---

### 🟡 R9. CLAUDE.md 환경 진단에서 `Is a git repository: false`로 시작

**증상**: 작업 디렉토리가 git 저장소가 아닌 상태로 `/dev-team`을 호출하면 `wp-setup.py`는 worktree 생성 시 `fatal: not a git repository`로 즉시 실패한다. 스킬의 "전제조건 확인" 섹션이 이를 사전에 검출하지만, 실패 메시지가 세부 재현 경로에 없다.

**완화**: 본 세션에서는 `git init` + 초기 커밋으로 수동 해결. 문서화 필요.

---

### 🟢 R10. Graceful shutdown 경로가 POSIX 쉘 명령을 가정

**파일/위치**: `/dev-team` 스킬 문서의 "사용자 종료 요청 시" 섹션
```bash
for PANE_ID in $(tmux list-panes -t "${SESSION}:${WT_NAME}" -F '#{pane_id}'); do
  tmux send-keys -t "${PANE_ID}" Escape 2>/dev/null
done
```

psmux는 `send-keys`에서 `Escape` 키워드를 tmux와 동일하게 해석하는지 불분명하며, 팀리더가 Git Bash에서 이 for 루프를 돌리더라도 내부 `tmux list-panes -t "0:WP-01"` 명령이 R5 경로 일관성 문제로 빈 결과를 낼 수 있다.

**영향**: 사용자가 "종료" 요청 시 `.shutdown` 마커만 남고 실제 pane 종료는 안 될 수 있음. 본 조사에서는 재현하지 않음.

---

## 상호작용 다이어그램 (버그가 겹쳐 실패하는 경로)

```
사용자: /dev-team WP-01 WP-02
  │
  ▼
args-parse.py ── python3 호출 실패 ── [R1]
  │ (teamLeader가 python 직접 실행하여 성공)
  ▼
wp-setup.py
  │
  ├─ R1: 내부 python3 서브프로세스 전부 rc=9009
  │      → status/depends/task_block 전부 빈 문자열
  │      → [xx] 필터링 무력화
  │      → design.done 오생성 6건
  │
  ├─ worktree 생성 (정상)
  │
  ├─ R2: runner.sh CRLF로 저장
  │
  ├─ R5: detect_mux() → "tmux" 반환 (실제는 psmux)
  │
  └─ tmux new-window ... runner.sh
       │
       ▼ psmux window 생성 (rc=0)
       │
       ▼ pane 내부에서 runner.sh 실행 시도
         │
         ├─ R3: default-shell = cmd.exe
         │      → ".claude은(는) 내부 또는 외부 명령..."
         │      → pane 즉시 사망
         │
         └─ (설령 bash였어도) R4: /c/ 경로 WSL에서 무효
                           R7: $(< file) 문법 WSL bash에서 작동하나
                               claude.exe 경로 재지정 필요
         │
         ▼
  팀리더: tmux list-windows → 빈 결과 ("java"만 남음)
         remain-on-exit off → 사망 pane 자동 회수
         → 사용자에게 "spawn: tmux window WP-01"만 보이고 실제 실행 없음
```

---

## 환경별 영향 평가

| 환경 | 이슈 | 체감 결과 |
|------|------|-----------|
| macOS / Linux | — | 정상 동작 예상 |
| WSL2 내부 | R1(일부) | `python3`가 WSL Python 가리키면 정상. 권장 환경 |
| Windows + Git Bash + psmux | R1, R2, R3, R4, R5, R6, R7, R8 | **사실상 동작 불능** |
| Windows + WSL bash (WSL 안에서 호출) | R1(해결), R2(해결), R3(해결) | 정상 동작 가능성 높음 |

---

## 권장 조치

### 사용자(임시 우회)

1. **WSL2 환경으로 이동**: Windows에서 `wsl -d Ubuntu`로 진입 후 해당 디렉토리를 `/mnt/d/mes/aps-batch-mailer`로 접근해서 `/dev-team` 재호출. 스킬 문서상 완전 지원.
2. **순차 `/dev`로 폴백**: `/dev TSK-01-02`, `/dev TSK-01-03`, `/dev TSK-02-01`, `/dev TSK-02-02`, `/dev TSK-02-03`을 순차 실행. tmux 오케스트레이션 없이 동일 DDTR 플로우 수행.
3. **Python Store 스텁 제거** (R1만 해결): Windows 설정 → 앱 → 앱 실행 별칭 → `python3.exe`, `python.exe` 비활성화. 이후 `python3`이 정말로 찾을 수 없는 명령이 되어 `run_cmd`의 `check=False`가 rc≠0을 무시하므로 여전히 empty stdout 문제는 남지만, rc=9009의 가짜 성공은 사라짐.

### 플러그인 수정(upstream 제안)

| 이슈 | 변경 제안 | 파일 |
|------|----------|------|
| R1 | `"python3"` → `sys.executable` 전면 교체 | `wp-setup.py` |
| R1 | 서브프로세스 실패 시 `rc ≠ 0` 또는 `stdout == ""` 둘 다 에러로 처리 | `wp-setup.py` |
| R2 | 모든 `open("w", encoding="utf-8")`에 `newline="\n"` 추가 | `wp-setup.py` (그리고 `feat-init.py`, `signal-helper.py` 등 유사 스크립트도 동일 감사 필요) |
| R3 | Windows 감지 시 runner를 `.bat` 래퍼 생성 + `psmux new-window ... cmd /c run.bat` | `wp-setup.py` |
| R5 | `detect_mux()`가 `tmux -V` 출력에 `"psmux"` 포함되는지 검사 후 분기 | `wp-setup.py:42` |
| R6 | psmux 분기에 split-window, pane label, 레이아웃 설정 추가 | `wp-setup.py:509` |
| R7 | runner를 POSIX bash 의존에서 Python wrapper로 교체 고려 | `wp-setup.py` |
| R8 | config `temp_dir`/`shared_signal_dir`을 Windows/Unix 경로 변환 유틸로 정규화 | `_platform.py` 확장 |
| 공통 | "전제조건 확인"에서 `python3 --version` 실제 실행으로 검증 | skill 문서 |

### 최소 패치로 동작 가능성 확보 순서

1. **R1 수정** (`sys.executable` 사용) — 데이터 손상 방지 최우선
2. **R2 수정** (`newline="\n"`) — runner 스크립트가 bash에서 파싱 가능해짐
3. **R5 + R3 수정** — psmux 분기 진입 + cmd.exe 호환 runner 생성
4. **R6 보강** — worker pane split 추가

이 4가지만 고쳐도 Windows 네이티브에서 `/dev-team` 동작 가능성 상당히 회복될 것으로 추정. 다만 R4(경로 일관성)는 WSL bash 사용 시 여전히 남으므로 psmux default-shell을 Git Bash로 고정하는 것이 더 근본적.

---

## 부록 A: 재현 명령 모음

```bash
# R1 재현
python -c "import subprocess; r=subprocess.run(['python3','--version'],capture_output=True,text=True); print('rc=',r.returncode,'err=',repr(r.stderr[:80]))"

# R2 재현
python -c "
with open('/tmp/crlf-test.sh','w',encoding='utf-8') as f: f.write('#!/bin/bash\ncd foo\n')
import pathlib; print(pathlib.Path('/tmp/crlf-test.sh').read_bytes())
"

# R3 재현 (remain-on-exit로 사망 pane 보존)
tmux set-option -g remain-on-exit on
tmux new-window -d -t 0 -n TEST ".claude/worktrees/WP-01-run.sh"
# 직후 캡처
tmux list-panes -a -F '#{window_index}:#{window_name} dead=#{pane_dead}'
tmux capture-pane -t <dead-pane-id> -p

# R5 재현
type tmux && type psmux
tmux -V; tmux info | head -3

# R7 재현 (cmd.exe에서 bash 문법 실패)
cmd //c "cd 'D:/mes/aps-batch-mailer' && claude --version"
```

## 부록 B: 현재 상태 (2026-04-16 조사 종료 시점)

- Git 저장소: 초기화됨 (`ec3ab96 chore: initial commit`)
- 워크트리: `.claude/worktrees/WP-01`, `.claude/worktrees/WP-02` 존재
- 브랜치: `dev/WP-01`, `dev/WP-02` 존재
- 시그널 디렉토리: `C:/Users/DKSYSTEMS/AppData/Local/Temp/claude-signals/aps-batch-mailer/` — 오염된 `*-design.done` 6건 잔존
- DDTR 프롬프트: `task-TSK-01-01.txt` ... `task-TSK-02-03.txt` 생성됨 ([xx] 필터 누락으로 완료된 TSK-01-01도 포함)
- runner 스크립트: CRLF 복원하여 재생성됨 (`.claude/worktrees/WP-01-run.sh`, `WP-02-run.sh`)
- tmux windows: 모든 WP 창 정리됨, `java`만 남음
- 필요 시 정리 명령:
  ```bash
  rm -rf "C:/Users/DKSYSTEMS/AppData/Local/Temp/claude-signals/aps-batch-mailer"
  rm C:/Users/DKSYSTEMS/AppData/Local/Temp/task-TSK-*.txt
  git worktree remove --force .claude/worktrees/WP-01
  git worktree remove --force .claude/worktrees/WP-02
  git branch -D dev/WP-01 dev/WP-02
  ```
