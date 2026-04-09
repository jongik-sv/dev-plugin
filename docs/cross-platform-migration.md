# Cross-Platform Migration Plan: Bash → Python

## 목표

현재 bash 전용 helper scripts를 Python으로 전환하여 Mac/Linux/Windows 단일 소스 지원.

## 배경

| 항목 | 현재 (bash) | 전환 후 (Python) |
|------|-------------|-----------------|
| Windows 지원 | Git Bash/WSL 필요 | 네이티브 지원 |
| jq 의존성 | 필수 | 불필요 (표준 라이브러리) |
| awk 의존성 | 필수 | 불필요 |
| 유지보수 | 어려움 | 용이 |
| 단일 소스 | ❌ | ✅ |

## 전환 대상

### 완전 전환 (플랫폼 분기 없음)

| 스크립트 | 역할 | 비고 |
|---------|------|------|
| `scripts/signal-helper.sh` | 시그널 파일 원자적 생성/확인/대기 | `/tmp` 경로 문제 해결 |
| `scripts/wbs-parse.sh` | WBS Task/WP 추출 → JSON | jq 의존성 제거 |
| `scripts/args-parse.sh` | 인자 파싱 + 서브프로젝트 감지 → JSON | jq 의존성 제거 |
| `scripts/dep-analysis.sh` | 의존성 레벨 계산 (위상 정렬) → JSON | jq 의존성 제거 |

### 부분 전환 (플랫폼 분기 유지)

| 스크립트 | 역할 | 분기 이유 |
|---------|------|----------|
| `scripts/wp-setup.sh` | Worktree + 프롬프트 + tmux 셋업 | tmux/psmux spawn 부분은 OS별 분기 필요 |

## 구현 방법

### 파일 배치

```
scripts/
  signal-helper.py     # signal-helper.sh 대체
  wbs-parse.py         # wbs-parse.sh 대체
  args-parse.py        # args-parse.sh 대체
  dep-analysis.py      # dep-analysis.sh 대체
  wp-setup.py          # wp-setup.sh 대체
```

기존 `.sh` 파일은 삭제하거나, 호환성을 위해 Python을 호출하는 얇은 래퍼로 유지.

### 호출 방식 변경

Skills에서 bash 도구로 호출하는 방식은 동일하게 유지:

```bash
# 기존
bash ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.sh {DOCS_DIR}/wbs.md {WP-ID} --tasks-pending

# 변경 후
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {WP-ID} --tasks-pending
```

출력 형식(JSON) 동일 유지 → SKILL.md 내 파싱 로직 변경 불필요.

### 플랫폼 유틸리티 (공통)

```python
# scripts/_platform.py (공통 모듈)
import sys, tempfile, pathlib, os

TEMP_DIR = pathlib.Path(tempfile.gettempdir())
IS_WINDOWS = sys.platform == "win32"
```

### wp-setup.py 의 tmux/psmux 분기

```python
import shutil, os

def detect_mux():
    if shutil.which("tmux") and os.environ.get("TMUX"):
        return "tmux"
    elif shutil.which("psmux"):
        return "psmux"
    return None  # agent-pool 폴백

MUX = detect_mux()
```

- `MUX = "tmux"` → 기존 tmux 명령 실행
- `MUX = "psmux"` → 동일 명령, psmux로 실행 (Windows)
- `MUX = None` → runner 파일만 생성, 수동 실행 안내 (agent-pool 경로)

## psmux 호환성 확인 필요 항목

wp-setup.sh가 사용하는 tmux 명령 중 psmux 지원 여부를 사전 검증해야 함:

| tmux 명령 | psmux 지원? |
|-----------|------------|
| `new-window -t SESSION: -n NAME CMD` | 확인 필요 |
| `set-option -w -t TARGET automatic-rename off` | 확인 필요 |
| `split-window -t TARGET -h CMD` | 확인 필요 |
| `select-layout -t TARGET tiled` | 확인 필요 |
| `list-panes -t TARGET -F '#{pane_index}:#{pane_id}'` | 확인 필요 |
| `select-pane -t PANE_ID -T TITLE` | 확인 필요 |
| `display-message -p '#{session_name}'` | 확인 필요 |

미지원 항목이 있으면 `if MUX == "psmux":` 분기 추가.

## 의존성

Python 표준 라이브러리만 사용:
- `json`, `pathlib`, `subprocess`, `sys`, `os`, `argparse`, `tempfile`, `shutil`
- 추가 pip 패키지 없음

## 작업 순서

1. `signal-helper.py` — 가장 단순, 먼저 전환 (파일 원자적 쓰기, 존재 확인, 대기 루프)
2. `args-parse.py` — JSON 출력, SKILL.md 호출 방식 검증
3. `wbs-parse.py` — 가장 복잡 (마크다운 파싱, 위상 정렬 일부)
4. `dep-analysis.py` — wbs-parse 출력을 입력으로 받음
5. `wp-setup.py` — 마지막 (위 4개 완료 후, tmux/psmux 분기 포함)

각 단계마다:
- 기존 `.sh`와 동일한 입력/출력 검증
- Mac/Linux에서 테스트 후 Windows(또는 WSL 없는 환경)에서 검증

## SKILL.md 변경 범위

`bash ${CLAUDE_PLUGIN_ROOT}/scripts/*.sh` → `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/*.py` 로 일괄 치환.

영향받는 skills:
- `dev`, `dev-design`, `dev-build`, `dev-test`, `dev-refactor`
- `dev-team`, `agent-pool`, `team-mode`
