---
name: agent-pool
description: "에이전트 풀(agent pool, 에이전트 pool) — N개의 서브에이전트를 병렬 실행하는 풀 패턴. 슬롯 유지 방식. '에이전트 풀로 작업해', 'agent pool로 돌려' 등의 요청 시 이 스킬을 사용한다. 사용법: /agent-pool [task-file] [--pool-size N]"
---

# /agent-pool - 서브에이전트 병렬 풀

하나의 세션 안에서 N개의 서브에이전트를 동시 실행하고, 하나가 완료되면 즉시 대기 큐에서 다음을 투입하여 슬롯을 항상 N개로 유지하는 패턴이다. 개발, 분석, 문서 생성 등 다양한 작업을 병렬로 처리할 수 있다.

인자: `$ARGUMENTS` (옵션)
- 첫 번째 인자: task 파일 경로 (선택)
- `--pool-size N`: 동시 실행 에이전트 수 (기본값: 5)

**task 파일이 없으면** 대화에서 작업 리스트를 수집하여 자동 생성한다 (→ "1-A. 대화형 Task 수집" 참조).

## 0. 설정 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `POOL_SIZE` | 5 | 동시 실행 에이전트 수 (슬롯 상한) |
| `TEMP_DIR` | `/tmp` (Unix) / `$TEMP` (Windows) | 임시 파일 루트 디렉토리 |
| `SIGNAL_DIR` | `{TEMP_DIR}/agent-pool-signals` | 시그널 파일 디렉토리 |
| `MAX_RETRIES` | 1 | task 실패 시 재시도 횟수 |

### 시그널 프로토콜

task 상태는 시그널 파일로 추적한다. `mv`를 사용하여 원자적으로 전환한다.

| 상태 | 파일 | 생성 시점 |
|------|------|-----------|
| 실행 중 | `{task-id}.running` | task 시작 직후 |
| 완료 | `{task-id}.done` | task 성공 완료 시 |
| 실패 | `{task-id}.failed` | task 실패 시 |

## 1. Task 입력

### 분기: task 파일 유무 판단

- `$ARGUMENTS`에 파일 경로가 있으면 → **1-B. Task 파일 파싱**으로 진행
- 파일 경로가 없으면 → **1-A. 대화형 Task 수집**으로 진행

### 1-A. 대화형 Task 수집 (task 파일 없을 때)

사용자에게 병렬로 실행할 작업 리스트를 질문한다:

> 어떤 작업들을 병렬로 실행할까요? 작업 목록을 알려주세요.
> (작업 간 의존성이 있으면 함께 알려주세요.)

사용자 응답을 파싱하여 `{TEMP_DIR}/agent-pool-tasks.json` 파일을 자동 생성한다:

```json
{
  "tasks": [
    {
      "id": "task-1",
      "prompt": "사용자가 설명한 작업 내용을 그대로 포함",
      "depends": []
    }
  ]
}
```

- task id는 `task-1`, `task-2`, ... 순서로 자동 부여
- 사용자가 의존성을 언급하지 않으면 모든 task의 `depends`를 `[]`로 설정 (전부 병렬)
- 생성한 파일 내용을 사용자에게 보여주고 확인 후 진행

### 1-B. Task 파일 파싱

task 파일 경로를 Read 도구로 읽는다. 두 가지 형식을 지원한다.

#### JSON 형식
```json
{
  "tasks": [
    {
      "id": "task-1",
      "prompt": "이 작업을 수행하라...",
      "depends": []
    },
    {
      "id": "task-2",
      "prompt": "이 작업을 수행하라...",
      "depends": ["task-1"]
    }
  ]
}
```

#### Markdown 형식
```markdown
### task-1
- depends: (none)
- prompt: |
    이 작업을 수행하라...

### task-2
- depends: task-1
- prompt: |
    이 작업을 수행하라...
```

파싱 후 각 task에서 추출: `id`, `prompt`, `depends`

## 2. 의존성 분석

depends 기반으로 실행 레벨을 산출한다:

```
Level 0: depends가 없거나 모두 완료된 task (즉시 시작 가능)
Level 1: Level 0 task에 의존
Level 2: Level 1 task에 의존
...
```

순환 의존이 감지되면 에러를 보고하고 중단한다.

## 3. 풀 실행

### 시그널 디렉토리 생성

```bash
rm -rf {SIGNAL_DIR} && mkdir -p {SIGNAL_DIR}
```

### 초기 launch

Level 0 task 중 최대 `POOL_SIZE`개를 선택하여 **동시에** Agent 도구로 실행한다:

각 Agent 호출 시:
- **description**: "{task-id} 실행"
- **run_in_background**: true
- **mode**: "auto"
- **prompt**:
  ```
  아래 작업을 수행하라.

  ## 시작 처리 (필수 — 가장 먼저 실행)
  echo 'started' > {SIGNAL_DIR}/{task-id}.running

  {task의 prompt 내용}

  ## 완료 처리 (필수)
  작업이 끝나면 반드시 아래 명령을 Bash 도구로 실행하라:
  - 성공 시: echo '완료' > {SIGNAL_DIR}/{task-id}.done.tmp && mv {SIGNAL_DIR}/{task-id}.done.tmp {SIGNAL_DIR}/{task-id}.done
  - 실패 시: echo '실패: {에러 내용}' > {SIGNAL_DIR}/{task-id}.failed.tmp && mv {SIGNAL_DIR}/{task-id}.failed.tmp {SIGNAL_DIR}/{task-id}.failed
  ```

초기 launch 후 남은 task는 대기 큐에 넣는다.

### 모니터링 루프

launch한 각 task에 대해 **개별적으로** 시그널 파일을 감시한다 (Bash `run_in_background`):

```bash
while [ ! -f {SIGNAL_DIR}/{task-id}.done ] && [ ! -f {SIGNAL_DIR}/{task-id}.failed ]; do sleep 5; done
if [ -f {SIGNAL_DIR}/{task-id}.done ]; then echo "DONE:{task-id}"
elif [ -f {SIGNAL_DIR}/{task-id}.failed ]; then echo "FAILED:{task-id}"; cat {SIGNAL_DIR}/{task-id}.failed
fi
```

### 슬롯 보충 (핵심 패턴)

시그널 감지 시 아래 순서를 따른다:

**DONE 시그널**:
1. 해당 task를 **완료** 목록에 추가
2. 대기 큐에서 **의존성이 모두 충족된** task를 찾는다
3. 찾은 task를 즉시 Agent 도구로 launch (`run_in_background: true`)
4. 새 task에 대한 시그널 모니터링도 시작

**FAILED 시그널 또는 시그널 없이 종료**:
1. 해당 task의 재시도 횟수를 확인한다
2. `재시도 < MAX_RETRIES`이면:
   - `.failed` 파일을 삭제하고 동일 task를 다시 launch
   - 재시도 횟수 +1
3. `재시도 >= MAX_RETRIES`이면:
   - 해당 task를 **실패** 목록에 추가
   - 이 task에 의존하는 하위 task를 모두 **스킵** 처리
   - 대기 큐에서 다음 task를 찾아 슬롯 보충

**⚠️ 배치 단위로 기다리지 않는다.** 1개 완료 → 1개 투입으로 항상 `POOL_SIZE`개 슬롯을 채운다.

### 전체 완료 판정

- 모든 task가 완료/실패/스킵 목록에 들어가면 종료

## 4. 에러 처리

| 상황 | 처리 |
|------|------|
| `.failed` 시그널 감지 | 재시도 횟수 < MAX_RETRIES → 재실행, 아니면 실패 확정 |
| Agent 종료 + 시그널 없음 | `.failed`와 동일하게 처리 (재시도 또는 실패 확정) |
| 의존 task 실패 | 하위 task 스킵, 최종 보고에 포함 |
| 과반 task 실패 | 사용자에게 계속 진행 여부 확인 |

## 5. 완료 보고

모든 task 처리 후 사용자에게 결과를 출력한다:

```
## Agent Pool 실행 결과
- 전체: {총 task 수}
- 성공: {성공 수}
- 실패: {실패 수}
- 스킵: {스킵 수} (의존 실패)
```

시그널 디렉토리를 정리한다:
```bash
rm -rf {SIGNAL_DIR}
```
