# WP 리더 최종 정리

이 파일은 모든 Task 완료/실패/스킵 처리 후에 실행한다.

## WP 레벨 busy 시그널 (monitor 대시보드용)

머지 또는 WP 단위 테스트 **시작 직전** — `.running` 파일을 직접 생성한다:

```python
# busy 시작 (머지 전)
python3 -c "
import pathlib
p = pathlib.Path('{SHARED_SIGNAL_DIR}/{WT_NAME}.running')
p.write_text('merge', encoding='utf-8')
"
# busy 시작 (테스트 전)
python3 -c "
import pathlib
p = pathlib.Path('{SHARED_SIGNAL_DIR}/{WT_NAME}.running')
p.write_text('test', encoding='utf-8')
"
```

머지 또는 테스트 **완료 직후** (성공/실패 무관) — `.running` 파일을 삭제한다:

```python
# busy 종료 (머지/테스트 완료 후)
python3 -c "
import pathlib
p = pathlib.Path('{SHARED_SIGNAL_DIR}/{WT_NAME}.running')
p.unlink(missing_ok=True)
"
```

> **주의**: 이 `.running` 파일은 dev-monitor 대시보드 스피너 표시용이다.
> `_wp_busy_set()` 헬퍼가 `^WP-\\d{2}$` 패턴으로 이 파일을 감지하여 해당 WP 카드에 스피너를 표시한다.
> WP 리더 최종 완료 시에는 별도로 `{WT_NAME}.done` 시그널을 생성해야 한다 (아래 단계 4 참조).
> 삭제(unlink, missing_ok=True)는 파일이 없어도 오류 없이 진행된다.

```
⚠️ **필수**: 아래 순서대로 실행하라. 대기하거나 사용자 입력을 기다리지 마라.

## Worker 종료

각 worker pane에 대해 **개별 Bash 호출**로 종료한다 (sleep 사용 금지):
```bash
tmux send-keys -t {paneId} Escape
```
```bash
{PYTHON_BIN} {PLUGIN_ROOT}/scripts/send-prompt.py {paneId} --slash-command exit
```
모든 worker에 `/exit`을 보낸 뒤, 프로세스 정리:
```bash
for pane in "${PANE_IDS[@]:1}"; do
  PANE_PID=$(tmux display-message -t "$pane" -p '#{pane_pid}' 2>/dev/null)
  [ -n "$PANE_PID" ] && pkill -TERM -P "$PANE_PID" 2>/dev/null
done
```

## 정리 절차

0. **초기화 시그널 정리**:
   ```bash
   rm -f {SHARED_SIGNAL_DIR}/{WT_NAME}.initialized
   ```

1. **미커밋 변경 확인 및 커밋**:
   ```bash
   git status --short
   ```
   미커밋 변경이 있으면 `git add` + `git commit`

2. **코드 리뷰** (모든 Task 성공 시에만):
   일부 Task가 실패했거나 스킵된 경우 이 단계를 건너뛴다.

   > ⚠️ **호출 방법 주의**: `/codex:review`는 **슬래시 명령(command)**이다. **스킬(Skill tool)이 아니다.** 반드시 아래 3-3 단계처럼 SlashCommand 도구로 호출하라. `Skill(codex:review)`로 호출하면 `disable-model-invocation`이라 실패한다.

   **3-1. codex 플러그인 설치 여부 확인** (Bash):
   ```bash
   find ~/.claude/plugins -maxdepth 6 -type d -name "codex" 2>/dev/null | head -1
   ```

   **3-2. codex 미설치인 경우** (위 명령 출력이 비어 있음):
   아래 에러 메시지를 **반드시 출력**하고 이 단계를 건너뛴 뒤 단계 4로 진행한다. `REVIEW_STATUS`를 `"스킵 (/codex:review 미설치)"`로 기록한다:
   ```bash
   echo "⚠️  [wp-leader-cleanup] /codex:review 명령을 찾을 수 없습니다." >&2
   echo "⚠️  codex 플러그인이 설치되어 있지 않아 코드 리뷰를 건너뜁니다." >&2
   echo "⚠️  설치하려면 codex 플러그인을 /plugin install 로 추가하세요." >&2
   ```
   > wp-leader는 여기서 **중단하지 않는다.** 미설치 경고를 출력한 뒤 단계 4(팀리더 보고)로 정상 진행한다. 팀리더에게 보내는 `.done` 시그널의 "리뷰" 필드에 `스킵 (/codex:review 미설치)`를 기록하여 사용자가 원인을 추적할 수 있게 한다.

   **3-3. codex 설치된 경우**: SlashCommand 도구로 `/codex:review --base main --wait` 를 실행한다. (Skill 도구 금지 — 위 주의사항 참조.)

   verdict가 `needs-attention`이고 Critical/High severity findings가 있으면:
   Agent 도구로 서브에이전트를 실행한다 (model: `"sonnet"`, mode: "auto"):
   ```
   아래 코드 리뷰 결과의 Critical/High 이슈를 수정하라.

   [/codex:review 결과 붙여넣기]

   ## 규칙
   - Critical/High severity만 수정한다. Medium/Low는 무시.
   - 수정 후 단위 테스트 실행하여 통과 확인.
   - 테스트 실패 시 수정을 되돌린다 (git checkout .)
   - 커밋: 테스트 통과한 경우만 git add -A && git commit -m "review: {수정 요약}"
   ```
   Medium/Low만 있으면 수정 없이 진행한다.

   `REVIEW_STATUS`를 리뷰 결과에 맞춰 기록한다: `approve` | `needs-attention(수정됨)` | `needs-attention(수정실패-롤백)`.

3. **브라우저 visible 검증 (brw-test)**:

   헤드리스 측정만으로 완료 보고 금지. `references/browser-verify.md` 을 Read하여 절차대로 수행한다:
   - Pre-flight: `pkill -f 'user-data-dir=.*mcp-chrome-'` 로 잔존 Chrome 정리 (profile lock 방지)
   - `mcp__plugin_playwright_playwright__*` MCP 사용 (ecc extension MCP는 확장 필요로 이 환경 불가)
   - 구현한 주요 컴포넌트/페이지를 실제 렌더링 후 screenshot + `document.styleSheets` 로드 확인
   - Screenshot은 `docs/tasks/{TSK-ID}/screenshots/` 에 저장
   - NG 판정 시 (자율 실행 원칙): 먼저 자동 수정을 시도한다. 자동 수정 실패 시 **NG로 기록하고 진행** — 사용자 에스컬레이션 대기 금지. 최종 `.done` 시그널의 `brw-test` 필드에 `NG — 자동수정실패 — {원인 요약}`를 포함시켜 팀리더가 사후 판단할 수 있게 한다.

   결과는 `BRW_TEST_RESULT` 변수에 기록한다 (`OK — ...` 또는 `NG — ...`).

4. **팀리더에게 완료 보고** (시그널 파일, **절대 경로 사용**):
   > 시그널 파일 이름은 `{WT_NAME}.done`

   **모든 Task 성공 시**:
   ```bash
   cat > {SHARED_SIGNAL_DIR}/{WT_NAME}.done.tmp << 'EOF'
   [{WT_NAME} 완료]
   - 완료 Task: {완료된 TSK-ID 목록}
   - 테스트: {통과 수}/{전체 수}
   - 리뷰: {REVIEW_STATUS — approve | needs-attention(수정됨) | needs-attention(수정실패-롤백) | 스킵 (/codex:review 미설치) | 스킵 (Task 실패)}
   - 커밋: {최신 커밋 해시}
   - brw-test: {BRW_TEST_RESULT — OK 또는 NG, screenshot 경로 + styleSheets 수 + 콘솔 error 요약}
   - 특이사항: {있으면 기록, 없으면 "없음"}
   EOF
   mv {SHARED_SIGNAL_DIR}/{WT_NAME}.done.tmp {SHARED_SIGNAL_DIR}/{WT_NAME}.done
   ```

   **일부 Task 실패 시에도 반드시 보고** (나머지 Task가 모두 완료/실패/스킵된 상태):
   ```bash
   cat > {SHARED_SIGNAL_DIR}/{WT_NAME}.done.tmp << 'EOF'
   [{WT_NAME} 부분 완료]
   - 완료 Task: {완료된 TSK-ID 목록}
   - 실패 Task: {실패한 TSK-ID 목록}
   - 스킵 Task: {의존 실패로 스킵된 TSK-ID 목록}
   - 커밋: {최신 커밋 해시}
   - 특이사항: {실패 원인 요약}
   EOF
   mv {SHARED_SIGNAL_DIR}/{WT_NAME}.done.tmp {SHARED_SIGNAL_DIR}/{WT_NAME}.done
   ```
   > ⚠️ `{SHARED_SIGNAL_DIR}`은 팀리더가 프롬프트에 포함시킨 절대 경로이다. 상대 경로(`../.signals/`) 사용 금지.
   > ⚠️ 실패 Task가 있더라도 반드시 `.done` 시그널을 생성하라. 팀리더가 무한 대기하는 것을 방지한다.

5. **브라우저 tab 종료**: `mcp__plugin_playwright_playwright__browser_close` 호출 (Chrome 프로세스는 MCP가 유지, 다음 WP의 Pre-flight pkill에서 처리)

6. **리더 자신 종료**: 위 Worker 종료 완료 확인 후 종료

**⚠️ 금지사항**:
- 시그널 파일 생성 후 추가 입력을 기다리지 마라
- 모든 Task 완료 → 시그널 생성 → 팀원 종료 → 자신 종료를 **중단 없이 연속 실행**하라
```
