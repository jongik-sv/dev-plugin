# WP 리더 초기화 절차

이 파일은 WP 리더 시작 시 1회만 실행한다. 완료 후 이 내용은 잊어도 된다.

```
## 재개 모드 처리

Task를 할당하기 전에 worktree 내 {DOCS_DIR}/wbs.md를 읽어 각 Task의 status를 확인한다:
- `[xx]` 상태: 할당하지 않는다. 시그널이 없으면 생성한다:
  `echo "resumed" > {SHARED_SIGNAL_DIR}/<해당-TSK-ID>.done`
  `echo "resumed" > {SHARED_SIGNAL_DIR}/<해당-TSK-ID>-design.done`
- `[dd]`, `[im]` 상태: 팀원에게 할당한다. DDTR 프롬프트의 "상태 확인 및 Phase 재개" 로직이 중간 Phase부터 재개한다.
  설계는 이미 완료이므로 `-design.done` 시그널이 없으면 생성한다:
  `echo "resumed" > {SHARED_SIGNAL_DIR}/<해당-TSK-ID>-design.done`
- `[ ]` 상태: 정상 할당.

모든 Task가 이미 `[xx]`이면 즉시 완료 보고(시그널) 후 종료한다.

## 1. 팀원 pane 확인

⚠️ 가장 먼저 이 섹션을 실행하라. Worker pane은 wp-setup.py가 사전 생성한다. 여기서는 확인만 한다.
⚠️ **절대 `tmux split-window`로 pane을 직접 생성하지 마라** — 이중 생성 버그 방지.

**변수 확인**:
- SESSION = {SESSION}
- WORKER_MODEL = {WORKER_MODEL}
- SIGNAL_DIR = {SHARED_SIGNAL_DIR} (**team-mode 기본값 사용 금지**)
- MAX_RETRIES = 1

**pane 존재 확인**:
```bash
ACTUAL=$(tmux list-panes -t "{SESSION}:{WT_NAME}" -F '#{pane_id}' | wc -l | tr -d ' ')
EXPECTED=$(({TEAM_SIZE} + 1))
echo "현재 pane: ${ACTUAL}, 필요: ${EXPECTED}"
```

- `ACTUAL >= EXPECTED` → pane 준비 완료. "pane ID 수집"으로 진행.
- `ACTUAL < EXPECTED` → wp-setup.py가 아직 pane 생성 중이다. **10초 후 재확인**:
  ```bash
  sleep 10 && tmux list-panes -t "{SESSION}:{WT_NAME}" -F '#{pane_id}' | wc -l | tr -d ' '
  ```
  재확인 후에도 부족하면 오류를 보고하고 계속 진행한다.

**pane ID 수집** (이후 모든 명령에 pane_id 사용):
```bash
PANE_IDS=($(tmux list-panes -t "{SESSION}:{WT_NAME}" -F '#{pane_id}'))
# PANE_IDS[0]=리더(자신), PANE_IDS[1~]=worker
```

**초기화 완료 시그널 생성**:
```bash
echo "initialized at $(date)" > {SHARED_SIGNAL_DIR}/{WT_NAME}.initialized.tmp
mv {SHARED_SIGNAL_DIR}/{WT_NAME}.initialized.tmp {SHARED_SIGNAL_DIR}/{WT_NAME}.initialized
```

초기화 완료. 본문 프롬프트의 "2. Task 할당"으로 돌아가라.
```
