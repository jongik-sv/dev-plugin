# TSK-06-01: merge-preview.py 작성 + dev-build 워커 프롬프트 통합 - 설계

## 요구사항 확인
- `scripts/merge-preview.py`: `git merge --no-commit --no-ff` 시뮬레이션 후 반드시 `--abort`로 원상복구. stdout으로 `{"clean": bool, "conflicts": [...], "base_sha": str}` JSON 출력.
- exit code: 0 (클린), 1 (충돌), 2 (워크트리 dirty). `--remote origin`, `--target main` 옵션, 기본값 동일.
- `skills/dev-build/SKILL.md`의 워커 프롬프트 `tdd-prompt-template.md`에 Task `[im]` 진입 전 merge-preview 실행 단계 추가.

## 타겟 앱
- **경로**: N/A (단일 앱, scripts/ 및 skills/dev-build/ 직접 수정)
- **근거**: 플러그인 자체 스크립트 및 스킬 파일 수정

## 구현 방향
- `scripts/merge-preview.py` 신규 작성: Python 3 stdlib + subprocess. `git merge --no-commit --no-ff origin/main` 시뮬레이션 후 `git merge --abort` 보장 (try/finally 패턴). 충돌 파일은 `git diff --name-only --diff-filter=U`로 수집, hunk 정보는 `git diff --diff-filter=U` 파싱.
- 워크트리 dirty 감지: `git status --porcelain` 출력 비어있지 않으면 exit 2.
- `base_sha`: `git merge-base HEAD {remote}/{target}` 출력.
- `skills/dev-build/references/tdd-prompt-template.md`의 `## TDD 순서` 섹션 앞에 "Step -1: Merge Preview" 단계를 삽입하여 `[im]` 진입 전 병합 충돌 사전 확인.

## 파일 계획

**경로 기준:** 프로젝트 루트 기준

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/merge-preview.py` | git merge 시뮬레이션 + JSON 출력 + abort 보장 | 신규 |
| `scripts/test_merge_preview.py` | 4개 테스트 케이스 (clean, conflicts, dirty, skill-grep) | 신규 |
| `skills/dev-build/references/tdd-prompt-template.md` | merge-preview 실행 단계 삽입 | 수정 |

## 진입점 (Entry Points)
N/A — infrastructure 도메인, UI 없음

## 주요 구조

- **`check_worktree_clean(repo_root: Path) -> bool`**: `git status --porcelain` 실행, 출력 비면 True. 비어 있지 않으면 stderr에 경고 출력 후 `sys.exit(2)`.
- **`get_base_sha(remote: str, target: str, repo_root: Path) -> str`**: `git merge-base HEAD {remote}/{target}` → SHA 반환.
- **`simulate_merge(remote: str, target: str, repo_root: Path) -> tuple[bool, list[dict]]`**: `git fetch {remote} {target}` → `git merge --no-commit --no-ff {remote}/{target}`. `MERGE_HEAD` 파일 존재 여부(또는 returncode) 로 결과 판정. try/finally에서 `git merge --abort` 실행 (이미 클린 병합이면 abort는 no-op로 안전).
- **`parse_conflicts(repo_root: Path) -> list[dict]`**: `git diff --diff-filter=U` 출력 파싱 → `[{"file": str, "hunks": [str]}]`.
- **`main()`**: argparse로 `--remote`, `--target` 파싱 → 순서대로 호출 → JSON stdout 출력 → exit code 결정.

## 데이터 흐름
CLI 인자(`--remote`, `--target`) → `check_worktree_clean` → `get_base_sha` → `simulate_merge`(try/finally) → `parse_conflicts` → JSON stdout 출력 → exit code (0/1/2)

## 설계 결정 (대안이 있는 경우만)

- **결정**: `git merge --no-commit --no-ff` 후 `git merge --abort`를 try/finally로 래핑
- **대안**: `git worktree add` 임시 워크트리에서 시뮬레이션
- **근거**: 임시 워크트리는 disk I/O 비용 + 정리 실패 시 잔여물 위험이 있으므로 동일 워크트리에서 abort 패턴이 더 단순하고 부작용 없음

- **결정**: hunk 정보는 `git diff --diff-filter=U` 원문 라인 배열로 저장
- **대안**: hunk를 구조체로 완전 파싱 (start_line, length 등)
- **근거**: 소비자(모니터 대시보드)는 파일명과 충돌 존재 여부만 즉시 필요; 원문 라인 보존으로 미래 확장 가능

## 선행 조건
- git 바이너리가 PATH에 존재해야 함
- 현재 디렉토리 또는 `--repo` 지정 디렉토리가 git 리포지토리여야 함
- `{remote}/{target}` 브랜치가 원격에 존재해야 함 (fetch 후 FETCH_HEAD 참조)

## 리스크
- **HIGH**: `git merge --abort` 실패 시 워크트리 상태 오염 — `MERGE_HEAD` 존재 여부로 abort 필요성을 판단하고, abort도 실패하면 즉시 exit하며 상세 에러를 stderr에 출력
- **MEDIUM**: `git fetch` 실패 (네트워크 없음, 원격 없음) — subprocess returncode 체크로 감지, 에러 JSON을 clean=false로 출력하고 exit 1
- **LOW**: 대용량 충돌 diff 출력 — hunk 라인 수 제한 없이 모두 수집 (메모리 감수, 스크립트 용도는 로컬 개발 환경)

## QA 체크리스트
dev-test 단계에서 검증할 항목:

- [ ] (정상 케이스) `test_merge_preview_clean_merge`: 클린 병합 시 exit 0, stdout JSON `{"clean": true, "conflicts": [], "base_sha": <sha>}` 반환
- [ ] (충돌 케이스) `test_merge_preview_detects_conflicts`: 충돌 시 exit 1, `conflicts` 배열에 충돌 파일 포함, `clean: false`
- [ ] (에러 케이스) `test_merge_preview_dirty_worktree_exits_2`: uncommitted 변경 있을 때 exit 2, stderr에 경고 메시지 포함
- [ ] (통합 케이스) `test_dev_build_skill_contains_merge_preview_step`: `skills/dev-build/references/tdd-prompt-template.md`에 `merge-preview.py` 문자열이 포함됨 (grep 검증)
- [ ] (부작용 없음) 시뮬레이션 후 워크트리가 원래 상태로 복구됨 (MERGE_HEAD 없음, git status clean)
- [ ] (기본값) `--remote`, `--target` 미지정 시 `origin`, `main`으로 동작
