# WP 리더 Interrupt 복구 실패 이슈

> 날짜: 2026-04-09
> 발생 위치: WP-05 리더 (Sonnet, tmux pane 0)
> 심각도: 중간 — 수동 재시작 필요

## 증상

WP 리더가 초기화(tmux pane 생성) 도중 interrupted 되고, 사용자가 "계속"이라고
응답하자 **리더가 초기화를 재개하지 않고 직접 개발(Worker 역할)을 시작**했다.

결과:
- Worker pane 3개는 빈 상태로 방치
- 리더가 직접 코드를 작성 (gantt-bar.tsx 등)
- 시그널 파일 미생성, 커밋 없음
- 팀리더(상위)는 완료를 감지할 수 없는 상태

## 근본 원인

1. **컨텍스트 손실**: Claude 프로세스가 interrupt 후 재개될 때, "초기화 단계 중이었다"는
   실행 상태를 잃어버림. 프롬프트 전체는 유지되지만 "지금 어디까지 했는지"는 사라짐.

2. **자가 역할 확인 미비**: 프롬프트에 "리더는 직접 개발하지 않는다"는 규칙은 있으나,
   interrupt 후 "내가 지금 리더인지, 초기화를 했는지" 확인하는 체크포인트가 없음.

3. **Pane 상태 미검증**: 재개 시 `tmux list-panes`로 Worker가 활성인지 확인하는
   절차가 없어서, Worker가 없는 상태에서도 Task 수행을 시도함.

## 해결 방안

### 1. 프롬프트에 "재개 체크포인트" 추가 (권장)

WP 리더 프롬프트의 "초기화" 섹션 **앞**에 아래 블록을 추가:

```
## 상태 자가 진단 (매 응답 시작 시)

작업을 시작하거나 재개할 때 반드시 아래를 확인하라:

1. 내가 pane 0 (리더)인가?
   ```bash
   tmux display-message -t "{SESSION}:{WT_NAME}.0" -p '#{pane_id}'
   ```

2. Worker pane이 존재하는가?
   ```bash
   PANE_COUNT=$(tmux list-panes -t "{SESSION}:{WT_NAME}" -F '#{pane_id}' | wc -l | tr -d ' ')
   if [ "$PANE_COUNT" -le 1 ]; then
     echo "WORKER_MISSING — 초기화 미완료. 초기화 섹션부터 재실행"
   fi
   ```

3. WORKER_MISSING이면 "초기화" 섹션으로 돌아가라. 절대 직접 개발하지 마라.
```

### 2. Runner 스크립트에 pane 사전 생성

현재 runner 스크립트는 리더만 실행하고, 리더가 pane을 생성한다.
대안: `wp-setup.sh`가 **Worker pane까지 미리 생성**하고 Claude 프로세스를 idle 상태로
시작시킨 뒤, 리더에게 pane_id 목록을 전달한다.

```bash
# wp-setup.sh 내에서 Worker pane 사전 생성
for i in $(seq 1 $TEAM_SIZE); do
  tmux split-window -t "${SESSION}:${WT_NAME}" -h \
    "cd ${WT_PATH} && claude --dangerously-skip-permissions --model ${WORKER_MODEL}"
done
tmux select-layout -t "${SESSION}:${WT_NAME}" tiled
```

장점: 리더의 초기화 부담 감소, interrupt 취약점 제거
단점: Worker가 idle 상태로 토큰을 소비할 수 있음

### 3. 초기화 완료 시그널 도입

리더가 초기화를 완료하면 `.initialized` 시그널을 생성:

```bash
echo "initialized" > {SHARED_SIGNAL_DIR}/{WT_NAME}.initialized
```

재개 시 이 시그널의 유무로 초기화 완료 여부를 판단:

```bash
if [ ! -f {SHARED_SIGNAL_DIR}/{WT_NAME}.initialized ]; then
  echo "초기화 미완료 — 초기화부터 재실행"
fi
```

## 임시 대응 (현재)

리더가 Worker가 된 것이 발견되면:
1. WP 창 종료 (`tmux kill-window`)
2. Worktree/브랜치/시그널 정리
3. `wp-setup.sh`로 재실행

## 우선순위

- **즉시 적용**: 방안 1 (프롬프트 체크포인트) — 변경 최소, 효과 즉시
- **다음 릴리스**: 방안 2 (pane 사전 생성) — 구조적 해결
- **선택 적용**: 방안 3 (초기화 시그널) — 방안 2와 조합 시 최적
