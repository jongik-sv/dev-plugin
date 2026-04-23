# 결과 통합 — 머지 절차 (팀리더)

## (A) 개별 WP 조기 머지 — WP 완료 즉시 실행

다른 WP가 아직 실행 중이더라도, 완료된 WP는 즉시 머지할 수 있다.
`{SHARED_SIGNAL_DIR}/{WT_NAME}.done` 시그널 파일이 생성되면 해당 WP를 머지한다
(`{WT_NAME}` = `{WP-ID}{WINDOW_SUFFIX}`).

### 0. 산출물 검증 (머지 전 필수)

**미커밋 변경 강제 커밋** (산출물 파일 소실 방지):
```bash
UNCOMMITTED=$(git -C .claude/worktrees/${WT_NAME} status --short 2>/dev/null)
if [ -n "$UNCOMMITTED" ]; then
  git -C .claude/worktrees/${WT_NAME} add -A
  git -C .claude/worktrees/${WT_NAME} commit -m "chore: ${WT_NAME} pre-merge uncommitted changes"
fi
```

WP 내 모든 Task에 대해 아래 파일이 존재하는지 확인한다:
- `{DOCS_DIR}/tasks/{TSK-ID}/design.md` — 설계 산출물
- `{DOCS_DIR}/tasks/{TSK-ID}/test-report.md` — 테스트 결과
- `{DOCS_DIR}/tasks/{TSK-ID}/refactor.md` — 리팩토링 내역
- `{DOCS_DIR}/wbs.md` 해당 Task의 status가 `[xx]`인지 확인

누락된 산출물이 있으면 시그널 내용과 대조하여 판단:
- 시그널에 실패 내용이 있으면 → 해당 Task를 부분 완료로 기록
- 파일은 없지만 시그널은 성공이면 → WP 리더에게 재확인 요청 후 진행

### 1. tmux 창 종료

`graceful-shutdown.py --no-marker`로 해당 WP 창을 정상 종료한다 (Escape → `/exit` → kill-window). 헬퍼가 absolute `window_id`(`@N`)로 타겟을 해석하므로 `session:name` prefix 매칭 폴백으로 팀리더 자기 window를 지우는 사고를 방지한다(self-protection은 기본 ON):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/graceful-shutdown.py \
  "${SESSION}" "${WT_NAME}" "${SHARED_SIGNAL_DIR}" \
  --no-marker --reason merge-cleanup
```

> `--no-marker`는 `.shutdown` 마커를 쓰지 않아 "사용자 종료" 경로와 구분된다 (머지 트리거/재개 로직에 영향 없음).

> ⚠️ 팀리더가 직접 `pkill`이나 `taskkill`을 실행하지 마라 — 다른 세션의 claude 프로세스를 오살할 수 있다. WP 리더의 cleanup 절차(`wp-leader-cleanup.md`)가 pane별 자식 프로세스를 정리한다. 테스트 프로세스는 `run-test.py`가 프로세스 그룹 단위로 자동 정리한다.

### 2. 코드 리뷰 확인

코드 리뷰는 WP 리더가 완료 전에 `/codex:review` 슬래시 명령(SlashCommand 도구 호출)으로 수행한다 (`wp-leader-cleanup.md` 참조). Skill 도구가 아니다.
시그널 파일의 리뷰 항목을 확인한다:
- **approve** / **needs-attention(수정됨)** → merge 진행
- **스킵** (일부 Task 실패/bypass) → 기본 정책(`on-fail=bypass`)이면 **자동 머지 진행** (bypass된 task도 의존성 충족으로 판정됨 → 머지 대상). 실패 Task 목록은 최종 요약 보고에 포함한다. `on-fail=strict`일 때만 머지 스킵하고 사용자 보고.

### 3. 머지 실행

1. main에 미커밋 변경이 있으면 먼저 커밋
2. 머지:
```bash
git merge --no-ff dev/${WT_NAME} -m "Merge dev/${WT_NAME}: {WP 제목} ({TSK-ID 목록})"
```
3. 충돌 발생 시 — 다음 **4단계 순서**로 처리한다 (자율 실행 원칙):

   **3-1. rerere 자동 해결 확인**

   `git rerere`는 이전에 기록된 충돌 해결 패턴을 자동 재적용한다.
   rerere가 활성화되어 있으면 (`git config rerere.enabled true`, 또는 `init-git-rerere.py` 실행 완료 상태) 다음 명령으로 자동 해결을 시도한다:
   ```bash
   # rerere가 자동 해결한 파일 확인
   git rerere
   # 해결 완료 여부 판별 (UU/AA/DD 패턴이 없으면 전부 해결됨)
   git status --short | grep -E "^(UU|AA|DD)"
   ```
   위 grep 결과가 비어 있으면 rerere가 모든 충돌을 해결한 것이므로 `git add -A && git commit` 후 3-4단계를 건너뛴다.

   **3-2. 머지 드라이버 시도**

   rerere로 해결되지 않은 잔존 충돌에 대해 `.gitattributes`에 등록된 머지 드라이버를 확인한다.
   머지 드라이버가 설정된 파일 유형(예: `state.json`, `wbs.md`)은 드라이버가 자동 3-way 병합을 시도한다.
   (`init-git-rerere.py` 및 `.gitattributes` 설정은 TSK-06-02, TSK-06-03 참조)
   ```bash
   # 드라이버 적용 후 잔존 충돌 재확인
   git status --short | grep -E "^(UU|AA|DD)"
   ```
   이 결과도 비어 있으면 드라이버가 모든 잔존 충돌을 해결한 것이다 → `git add -A && git commit`.

   **3-3. 충돌 로그 저장**

   rerere와 드라이버로도 해결되지 않은 충돌이 남아 있으면 즉시 로그를 저장하고 abort한다.
   충돌 로그는 `docs/merge-log/` 디렉토리에 JSON 형식으로 저장한다:

   ```python
   # 충돌 로그 저장 예시 (Python stdlib 기반 — 세 플랫폼 공통)
   import json, datetime, pathlib, subprocess

   # 잔존 충돌 파일 목록 추출
   result = subprocess.run(
       ["git", "status", "--short"],
       capture_output=True, text=True
   )
   conflict_files = [
       line[3:].strip()
       for line in result.stdout.splitlines()
       if line[:2] in ("UU", "AA", "DD")
   ]

   # base_sha: 현재 머지 베이스 커밋 해시
   base_sha = subprocess.run(
       ["git", "merge-base", "HEAD", f"dev/{WT_NAME}"],
       capture_output=True, text=True
   ).stdout.strip()

   utc_str = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
   log_entry = {
       "wt_name": WT_NAME,          # 예: "WP-01"
       "utc": utc_str,              # 예: "20260502T143022Z"
       "conflicts": conflict_files, # 예: ["docs/monitor-v3/wbs.md"]
       "base_sha": base_sha,        # 예: "a1b2c3d4..."
       "result": "aborted",         # "aborted" | "resolved"
   }

   log_dir = pathlib.Path("docs/merge-log")
   log_dir.mkdir(parents=True, exist_ok=True)  # 디렉토리 없으면 자동 생성
   log_path = log_dir / f"{WT_NAME}-{utc_str}.json"
   log_path.write_text(
       json.dumps(log_entry, ensure_ascii=False, indent=2),
       encoding="utf-8"
   )
   print(f"충돌 로그 저장 완료: {log_path}")
   ```

   **충돌 로그 JSON 스키마:**
   ```json
   {
     "wt_name":   "<워크트리 이름, 예: WP-01>",
     "utc":       "<UTC 타임스탬프, 예: 20260502T143022Z>",
     "conflicts": ["<충돌 파일 경로 1>", "<충돌 파일 경로 2>"],
     "base_sha":  "<머지 베이스 커밋 SHA>",
     "result":    "aborted | resolved"
   }
   ```

   > **학습 데이터 축적**: `docs/merge-log/`에 쌓인 JSON 파일은 이후 드라이버 개선·rerere 훈련 데이터로 활용된다. 커밋에 포함하여 영구 보존한다.

   **3-4. abort 실행**

   로그 저장 완료 후 즉시 abort한다. 사용자 수동 해결을 대기하지 않는다:
   ```bash
   git merge --abort
   ```
   워크트리(`.claude/worktrees/${WT_NAME}/`)와 브랜치(`dev/${WT_NAME}`)는 **보존**한다 (사후 수동 머지 가능). 충돌 파일 목록, 로그 경로, abort 사유를 최종 요약 보고에 기록한다.

4. 워크트리 + 브랜치 정리 (머지 성공 시):
   머지가 완료된 WP는 재시작 시 다시 실행할 필요가 없으므로, 즉시 정리한다:
   ```bash
   git worktree remove --force .claude/worktrees/${WT_NAME}
   git branch -d dev/${WT_NAME}
   rm -f .claude/worktrees/${WT_NAME}-prompt.txt .claude/worktrees/${WT_NAME}-init.txt .claude/worktrees/${WT_NAME}-cleanup.txt .claude/worktrees/${WT_NAME}-run.py .claude/worktrees/${WT_NAME}-worker.py
   rm -f ${TEMP_DIR}/team-manifest-${WT_NAME}.md
   ```
   머지 실패/건너뛴 WP의 워크트리는 보존한다 (재시도 대비).
5. `{DOCS_DIR}/wbs.md`에서 해당 WP의 `- progress:` 값 업데이트

---

## (B) 전체 완료 머지 — 모든 WP 완료 후 실행

모니터링에서 `ALL_TEAM_MEMBERS_DONE`을 수신하면 팀리더가 아직 머지되지 않은 WP들을 순차 머지한다:

1. 각 worktree 브랜치의 변경사항을 확인 (`git log main..dev/${WT_NAME} --oneline`)
2. main 브랜치에 순차적으로 머지 (`git merge --no-ff dev/${WT_NAME}`)
   - 머지 순서: 의존성 하위 WP부터
3. 머지 후 충돌 여부 확인 — 충돌 발생 시 다음 **4단계 순서**로 처리한다:

   **3-1. rerere 자동 해결 확인**

   ```bash
   git rerere
   git status --short | grep -E "^(UU|AA|DD)"
   ```
   결과가 비어 있으면 rerere 해결 완료 → `git add -A && git commit` 후 다음 WP 진행.

   **3-2. 머지 드라이버 시도**

   rerere 미해결 파일에 대해 `.gitattributes` 드라이버가 자동 3-way 병합을 시도한다.
   ```bash
   git status --short | grep -E "^(UU|AA|DD)"
   ```
   결과가 비어 있으면 드라이버 해결 완료 → `git add -A && git commit` 후 다음 WP 진행.

   **3-3. 충돌 로그 저장**

   rerere와 드라이버로도 해결되지 않은 잔존 충돌은 (A) §3 "3-3. 충돌 로그 저장"의 Python 예시 명령을
   동일하게 사용하여 `docs/merge-log/{WT_NAME}-{UTC}.json`에 저장한다.

   **3-4. abort 실행 후 다음 WP 진행**

   ```bash
   git merge --abort
   ```
   워크트리/브랜치는 보존한다. 충돌 파일 목록, 로그 경로, abort 사유를 최종 요약 보고에 기록.
   이후 다음 WP 머지를 계속 진행한다 (사용자 수동 해결을 대기하지 않는다).

4. 충돌 없이 머지 성공한 경우: 다음 브랜치 머지를 계속 진행한다.

5. 개별 WP 정리 (조기 머지(A)에서 이미 정리된 WP는 건너뛴다):
   각 머지 성공 WP에 대해:
   ```bash
   git worktree remove --force .claude/worktrees/${WT_NAME}
   git branch -d dev/${WT_NAME}
   rm -f .claude/worktrees/${WT_NAME}-prompt.txt .claude/worktrees/${WT_NAME}-init.txt .claude/worktrees/${WT_NAME}-cleanup.txt .claude/worktrees/${WT_NAME}-run.py .claude/worktrees/${WT_NAME}-worker.py
   rm -f ${TEMP_DIR}/team-manifest-${WT_NAME}.md
   ```
   머지 실패/건너뛴 WP의 워크트리는 보존한다 (재시도 대비).
6. 공유 리소스 정리:
   모든 WP가 머지 성공한 경우:
   ```bash
   rm -rf ${SHARED_SIGNAL_DIR}
   rm -f ${TEMP_DIR}/task-*.txt
   ```
   머지 실패 WP가 있으면 시그널 디렉토리와 task 프롬프트는 보존한다 (재시도 시 필요).
7. `{DOCS_DIR}/wbs.md`에서 각 WP의 `- progress:` 값을 업데이트
8. 전체 결과 요약 보고:
   - WP별 완료 Task 수
   - 성공/실패 현황
   - 머지 결과

---

## (C) WP-06 재귀 주의 — WP-06 전용 특수 케이스

> **이 섹션은 WP-06 (monitor-v3) Task 진행 중에만 적용된다.**
> 다른 WP 팀리더는 이 섹션을 무시한다.

WP-06은 본 플러그인 자체의 기능(`merge-preview`, rerere, 머지 드라이버)을 **구현하는** Task를 포함한다.
따라서 WP-06이 완료되기 전까지 해당 기능들은 아직 구현 중이거나 미활성 상태일 수 있다 (TRD §3.12.8).

**WP-06 머지 시 팀리더 주의사항:**

1. **rerere 비활성 가능성**: `init-git-rerere.py` (TSK-06-02)가 완료되지 않았으면 rerere 단계를 건너뛴다.
   `git config --get rerere.enabled` 출력이 `true`가 아니면 3-1 단계를 skip한다.

2. **머지 드라이버 미설정 가능성**: TSK-06-03의 `.gitattributes` + 드라이버 스크립트가 없으면
   3-2 드라이버 단계를 건너뛴다.
   ```bash
   # 드라이버 설정 여부 확인
   git config --get merge.wbs-state.driver || echo "드라이버 미설정"
   ```

3. **자기 구현 기능 재귀 사용 금지**: WP-06 Task 진행 중에 `merge-preview.py`를 머지 미리보기에 사용하지 않는다.
   스크립트가 불완전하거나 테스트 중인 상태일 수 있으므로 수동으로 `git diff` 확인을 대신 사용한다.

4. **수동 3-way 충돌 해결 허용**: rerere와 드라이버가 모두 비활성인 경우,
   잔존 충돌은 로그 저장 + abort 후 팀리더가 수동으로 `git checkout --theirs / --ours` 또는
   편집기를 통해 3-way 해결한 뒤 커밋한다.
   이 경우 충돌 로그의 `result` 필드를 `"resolved"`로 기록한다.

> **요약**: WP-06 진행 중에는 rerere·드라이버 의존 없이 수동 3-way 충돌 해결이 가능해야 한다.
> 기능 구현이 완료된 이후의 `/dev-team` 실행부터 본 절차의 자동화 기능이 활성화된다.
