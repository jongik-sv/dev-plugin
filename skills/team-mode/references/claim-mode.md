# Claim 기반 할당 (`--claim` 모드)

`CLAIM_MODE`가 true이면 리더가 push하는 대신 worker가 자율적으로 다음 task를 가져간다. 작업 시간 편차가 클 때 자연스럽게 로드밸런싱된다.

## 큐 구조 — task별 파일 방식

> ⚠️ 공유 텍스트 파일(`queue.txt`)을 사용하지 않는다. `head`+`sed`는 비원자적이라 두 worker가 같은 task를 가져갈 수 있다.

리더가 `{SIGNAL_DIR}/queue/` 디렉토리에 task별 파일을 생성한다:
```bash
mkdir -p {SIGNAL_DIR}/queue
echo '{prompt_file}' > {SIGNAL_DIR}/queue/{task-id}
```

## Worker 프롬프트 (Claim 모드)

각 worker의 초기 프롬프트에 아래 지시를 포함한다:

```
너는 claim 모드 worker이다. 아래 절차를 반복하라:

1. 다음 task를 원자적으로 claim한다:
   CLAIMED=""
   for F in {SIGNAL_DIR}/queue/*; do
     [ -f "$F" ] || continue
     TASK_ID=$(basename "$F")
     # mkdir은 POSIX에서 원자적 — 성공한 worker만 claim 획득
     if mkdir {SIGNAL_DIR}/claimed-$TASK_ID 2>/dev/null; then
       PROMPT_FILE=$(cat "$F")
       rm "$F"
       CLAIMED=$TASK_ID
       break
     fi
   done
   if [ -z "$CLAIMED" ]; then echo 'IDLE' > {SIGNAL_DIR}/worker-{N}.idle; exit; fi

2. 시작 시그널: echo 'started' > {SIGNAL_DIR}/$CLAIMED.running

3. prompt_file을 Read 도구로 읽고 작업을 수행한다.

4. 완료 시그널:
   - 성공: echo '완료' > {SIGNAL_DIR}/$CLAIMED.done.tmp && mv {SIGNAL_DIR}/$CLAIMED.done.tmp {SIGNAL_DIR}/$CLAIMED.done
   - 실패: echo '실패: {에러}' > {SIGNAL_DIR}/$CLAIMED.failed.tmp && mv {SIGNAL_DIR}/$CLAIMED.failed.tmp {SIGNAL_DIR}/$CLAIMED.failed

5. /clear 후 1단계로 돌아간다.
```

> **왜 mkdir인가?** `mkdir`은 POSIX에서 원자적으로 성공/실패한다. 두 worker가 동시에 같은 task를 claim하려 해도 `mkdir`은 하나만 성공시킨다. `flock`은 macOS에서 불안정하고, `ln`은 일부 파일시스템에서 비원자적이다.

## 리더 역할 (Claim 모드)

리더는 task 할당 대신:
1. 의존성이 해소된 task를 `{SIGNAL_DIR}/queue/{task-id}` 파일로 추가
2. 시그널 파일을 감시하여 완료/실패 추적
3. task 완료 시 의존성이 해소되는 새 task를 큐에 추가
4. 모든 worker가 `.idle` 시그널을 보내면 "5. 완료 처리"로 이동
