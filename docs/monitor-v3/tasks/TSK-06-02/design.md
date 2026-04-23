# TSK-06-02: init-git-rerere.py + dev-team 자동 호출 - 설계

## 요구사항 확인
- `scripts/init-git-rerere.py` 신규 스크립트 작성 — `git config rerere.enabled true`, `rerere.autoupdate true` 설정 및 `merge.state-json-smart.*`, `merge.wbs-status-smart.*` 드라이버 4개 등록 (idempotent)
- `{CLAUDE_PLUGIN_ROOT}` 경로는 환경변수에서 동적으로 해결하며, 설정이 이미 동일 값이면 no-op 처리하고 로그를 출력한다
- `scripts/wp-setup.py`의 워크트리 생성 직후(step 1 완료 후)에 자동 호출되어 각 WP 워크트리의 `.git/config`에만 설정을 적용한다

## 타겟 앱
- **경로**: N/A (단일 앱)
- **근거**: 플러그인 루트 `scripts/` 하위 인프라 스크립트이며 앱 패키지 구조 없음

## 구현 방향
- `scripts/init-git-rerere.py` 신규 생성: CLI 인수로 `--worktree`(선택, 기본 CWD) 수신, 6개의 `git config` 명령을 `git -C {worktree} config --local ...` 방식으로 실행 — git worktree의 `.git`이 파일이어도 정상 동작
- Idempotent 처리: 각 설정을 실행 전 `git -C {worktree} config --local --get {key}`로 현재 값을 조회하고, 이미 동일하면 `[no-op]` 로그 후 스킵
- `{PLUGIN}` 경로 치환: `os.environ.get("CLAUDE_PLUGIN_ROOT")` 우선, 없으면 스크립트 자신의 `__file__` 위치에서 `scripts/` 부모 디렉터리로 자동 유추 (`pathlib.Path(__file__).parent.parent`)
- `scripts/wp-setup.py` 수정: step 1 (워크트리 생성/검증) 완료 직후, step 2 (Signal dir) 진입 전에 `init-git-rerere.py`를 `subprocess.run([sys.executable, init_rerere_script, "--worktree", wt_path_abs])` 로 호출 (신규·재개 모두 실행)

## 파일 계획

**경로 기준:** 모든 파일 경로는 프로젝트 루트 기준으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/init-git-rerere.py` | rerere + 머지 드라이버 4개 등록 스크립트 (idempotent, --git-dir 옵션) | 신규 |
| `scripts/test_init_git_rerere.py` | `test_init_git_rerere_idempotent`, `test_init_git_rerere_sets_drivers` 단위 테스트 | 신규 |
| `scripts/wp-setup.py` | step 1 완료 직후 `init-git-rerere.py` 호출 구문 추가 | 수정 |

## 진입점 (Entry Points)
N/A — UI 없는 인프라 스크립트. CLI 엔트리포인트는 `scripts/init-git-rerere.py` 자체이며 직접 실행 또는 `wp-setup.py`에서 서브프로세스로 호출된다.

## 주요 구조

- **`configure_rerere(worktree, plugin_root)`**: `git -C {worktree} config --local rerere.enabled true` + `rerere.autoupdate true` 설정. 각각 현재 값 조회 후 idempotent 처리. 반환값: `{changed: int, noop: int}`.
- **`configure_merge_drivers(worktree, plugin_root)`**: `merge.state-json-smart.driver`, `merge.state-json-smart.name`, `merge.wbs-status-smart.driver`, `merge.wbs-status-smart.name` 4개 설정. `{PLUGIN}` 자리를 `plugin_root`로 치환. 반환값: `{changed: int, noop: int}`.
- **`resolve_plugin_root()`**: `CLAUDE_PLUGIN_ROOT` 환경변수 → `Path(__file__).parent.parent` 순으로 유추. 유효한 `scripts/` 디렉터리 존재 시 반환, 없으면 stderr에 경고 후 `__file__` 기반 경로 사용.
- **`set_config_idempotent(worktree, key, value)`**: `git -C {worktree} config --local --get {key}` → 동일하면 `[no-op]` 출력 후 False 반환, 다르면 `git -C {worktree} config --local {key} {value}` 실행 후 True 반환.
- **`main()`**: argparse로 `--worktree`(기본 CWD) 수신, `configure_rerere` + `configure_merge_drivers` 순 호출, 변경/no-op 카운트 요약 출력, exit 0.

## 데이터 흐름
입력: `--worktree`(선택, 기본 CWD), 환경변수 `CLAUDE_PLUGIN_ROOT`(선택) → 처리: 각 `git -C {worktree} config --local` 키의 현재 값 조회 후 필요한 경우만 set → 출력: 변경/no-op 카운트 요약(stdout), 에러 시 stderr, exit code 0(성공)/1(실패)

## 설계 결정 (대안이 있는 경우만)

- **결정**: `--worktree` 인수(워크트리 디렉터리 경로)를 받아 `git -C {worktree} config --local` 방식으로 설정
- **대안**: `--git-dir`을 받아 `git --git-dir {git_dir} config --local` 방식 사용
- **근거**: git worktree의 `.git`은 파일(gitfile)이므로 `--git-dir`에 `.git` 경로를 직접 전달하면 동작 불능. `git -C {worktree}`는 git이 알아서 워크트리 내 `.git` 파일을 해석하므로 안전

- **결정**: `CLAUDE_PLUGIN_ROOT` 없을 때 `Path(__file__).parent.parent`로 자동 유추
- **대안**: 환경변수 없으면 에러 종료
- **근거**: 테스트 환경 및 직접 CLI 호출에서 환경변수 미설정 시에도 동작해야 하므로 fallback이 필요. `scripts/` 폴더 내 다른 스크립트(예: `dep-analysis.py`)도 동일 패턴 사용

- **결정**: `git config --local` 사용 (프로젝트 로컬 한정)
- **대안**: `--global` 또는 기본(scope 없음) 사용
- **근거**: constraint 명시 — "프로젝트 로컬 `.git/config` 만 수정"

## 선행 조건
- git 바이너리 설치 및 PATH에 존재 (`shutil.which("git")` 확인)
- 대상 경로가 유효한 git 저장소 (워크트리 `.git` 파일 포함)
- `scripts/merge-state-json.py`, `scripts/merge-wbs-status.py`는 이 Task에서 생성하지 않음 (TSK-06-03 산출물). 드라이버 **등록**만 이 Task의 범위 — 실제 드라이버 스크립트 파일 존재 여부를 검증하지 않음 (등록 자체는 독립)

## 리스크
- MEDIUM: `wp-setup.py`의 워크트리 경로에서 `.git`이 파일일 수 있음 (git worktree의 경우 `.git`은 파일, 디렉터리 아님). `git -C {wt_path} config --local ...`로 처리하면 `.git` 파일/디렉터리 여부 무관하게 동작 — `--git-dir` 대신 `-C {wt_path}` 방식으로 구현하면 이 문제를 우회할 수 있음. **설계 수정**: `--git-dir` 인수 대신 `--worktree` 인수(워크트리 경로)를 받고 `git -C {worktree}` 방식을 사용한다.
- LOW: `CLAUDE_PLUGIN_ROOT` 환경변수가 있어도 trailing slash 불일치로 경로 비교 오류 가능 — `pathlib.Path`로 정규화하여 방지
- LOW: 테스트에서 `git config --global`이 실수로 호출될 경우 사용자 전역 설정 오염 — `--local` 플래그 강제 사용으로 방지

## QA 체크리스트
dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

- [ ] (`test_init_git_rerere_sets_drivers`) 신규 git 저장소에서 실행 시 `rerere.enabled=true`, `rerere.autoupdate=true`, 드라이버 4개(`merge.state-json-smart.driver`, `merge.state-json-smart.name`, `merge.wbs-status-smart.driver`, `merge.wbs-status-smart.name`)가 모두 `.git/config`에 등록된다
- [ ] (`test_init_git_rerere_idempotent`) 동일한 저장소에 2회 연속 실행 시 두 번째 실행에서 모든 항목이 `[no-op]`으로 처리되고 exit 0을 반환한다
- [ ] 드라이버 driver 값에 `{plugin_root}/scripts/merge-state-json.py`와 `{plugin_root}/scripts/merge-wbs-status.py` 경로가 올바르게 치환된다 (임시 git 저장소 + 임의 plugin_root 환경변수로 검증)
- [ ] `--local` 플래그가 적용되어 전역(`~/.gitconfig`) 및 시스템 git 설정을 변경하지 않는다 (임시 HOME 디렉터리 격리로 검증)
- [ ] `CLAUDE_PLUGIN_ROOT` 환경변수 미설정 시 `Path(__file__).parent.parent` fallback이 작동하여 정상 실행된다
- [ ] git 바이너리 없는 환경에서 실행 시 명확한 에러 메시지를 출력하고 exit 1로 종료된다
- [ ] `wp-setup.py`의 step 1 완료 후 `init-git-rerere.py`가 호출되어 워크트리 경로 내 `rerere.enabled`가 `true`로 설정되는 것을 subprocess mock으로 검증한다
