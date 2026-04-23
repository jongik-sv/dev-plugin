---
name: dev-seq
description: "WP 단위 순차 개발 (tmux/워크트리 없음, 현재 세션·현재 브랜치). 사용법: /dev-seq WP-04 또는 /dev-seq p1 WP-01 WP-02 또는 /dev-seq WP-04 --on-fail strict"
---

# /dev-seq - WP 단위 순차 개발

인자: `$ARGUMENTS` ([SUBPROJECT] + WP-ID + 옵션)
- SUBPROJECT: (옵션) 하위 프로젝트 폴더 이름. 예: `p1` → `docs/p1/` 하위에서 동작
- WP-ID: 0개 이상 (공백 구분). 생략 시 `--resumable-wps` 결과 자동 선정
- `--model opus`: 전 단계 Opus 모델 사용 (미지정 시 Phase별 권장 모델 자동 적용)
- `--on-fail strict|bypass|fast`: 테스트 실패 시 동작 모드 (기본값: `bypass`)

예:
- `/dev-seq WP-04` — 기본 `docs/` 사용, 권장 모델 적용
- `/dev-seq p1 WP-01 WP-02` — 서브프로젝트 `docs/p1/`에서 2개 WP 순차 실행
- `/dev-seq WP-04 --on-fail strict` — 테스트 실패 시 전체 중단

> ⚠️ `/dev-seq`는 **현재 브랜치에 직접 커밋**합니다. 격리가 필요하면 `/dev-team`(tmux+워크트리)을 사용하세요.

> **관련 스킬**: 병렬 팀 개발은 `/dev-team` (tmux + 워크트리). 개별 Task 하나만 돌리려면 `/dev {TSK-ID}`. `/dev-seq`는 WP 범위 순차 오케스트레이터로, 내부적으로 `/dev`와 동일한 DDTR 사이클 + Phase 서브에이전트를 재사용한다.

## 자율 실행 원칙 (Non-Interactive by Default)

`/dev-seq`는 **자율형 개발 워크플로우**다. 실행 중 발생하는 의사결정은 오케스트레이터가 합리적 기본값을 선택해 즉시 진행하고 **결과만 요약 보고**한다. 사용자에게 "어떻게 할까요?"를 묻지 않는다.

### 메타 규칙

1. **기본값 우선** — 옵션 생략·모호한 상황은 아래 표의 "기본 동작"으로 자동 결정.
2. **진행 우선** — 한 task/WP가 막혀도 전체를 멈추지 않는다. 해당 단위만 스킵(bypass)하고 나머지 계속 진행.
3. **되돌릴 수 있는 쪽 선택** — 손실이 적고 재시도 가능한 쪽을 택한다.
4. **증거 보존** — 자동 결정은 state.json `phase_history` 및 최종 요약 보고에 기록.
5. **리스크 구간만 예외** — 전제조건 미충족 등 자동 결정이 위험한 경우에만 중단 (아래 "예외" 참조).

### 런타임 의사결정 기본값

| 상황 | 기본 동작 |
|------|-----------|
| WP-ID 생략 | `--resumable-wps` 결과 **전부 자동 선정** 후 순차 실행 |
| `--model` 생략 | Phase별 권장 모델 자동 적용 (설계=Opus/Sonnet, 개발=Sonnet, 테스트=Haiku, 리팩토링=Sonnet) |
| `--on-fail` 생략 | `bypass` 자동 적용 (에스컬레이션 소진 시 임시완료 → 다음 task 진행) |
| Task 실패 | `ON_FAIL` 정책에 따라 진행/중단 자체 판단 (strict=중단, bypass=Opus 재시도 후 bypass, fast=즉시 bypass) |
| 그 외 이견·모호 | 위 원칙(기본값 / 진행 / 되돌릴 수 있는 쪽)에 따라 자체 판단, 요약 보고에 기록 |

**예외** — 아래 두 가지만 즉시 중단:
- **`/dev-seq`에 Feature 토큰 전달**: `args-parse.py`가 `source=feat` 감지 시 자동 차단 (입력 오류)
- **git repo 아님**: `git rev-parse --is-inside-work-tree` 실패 시 중단 + `git init` 안내

> 🎯 핵심: 진행 중 확인 질문 금지. 판단은 오케스트레이터가 하고 **결과만 요약 보고**한다.

## 0. 인자 파싱 및 설정

### 0-1. 인자 파싱

Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/args-parse.py dev-seq $ARGUMENTS
```
JSON 출력에서 추출: `docs_dir`, `subproject`, `wp_ids[]`, `options.model`, `options.on_fail`.

> `args-parse.py`는 `dev-seq`에 `--team-size`가 주어지면 즉시 에러로 종료한다(순차 실행 전용). `feat:NAME` 토큰도 같은 경로에서 차단된다.

### 0-2. 설정 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `DOCS_DIR` | `docs` 또는 `docs/{SUBPROJECT}` | wbs/PRD/TRD/tasks 경로 루트 |
| `SOURCE` | `wbs` (고정) | WBS 모드 전용 |
| `MAX_ESCALATION` | 1 | Task 실패 시 Opus 에스컬레이션 횟수 (소진 후 `ON_FAIL` 정책 적용) |
| `ON_FAIL` | `bypass` | 테스트 실패 시 동작. `strict`=전체 중단, `bypass`=에스컬레이션→임시완료, `fast`=즉시 임시완료 |
| `MODEL_OVERRIDE` | (없음) | `--model opus` 지정 시 `opus`. 미지정 시 Phase별 권장 모델 자동 적용 |

### 0-3. 모델 전파 체계

| 계층 | 기본 (`--model` 미지정) | `--model opus` |
|------|-------------------------|----------------|
| 오케스트레이터 (현재 세션) | 사용자 기본 모델 | Opus |
| Phase 서브에이전트 | 설계=Opus(복잡도↑)/Sonnet(복잡도↓), 개발=Sonnet, 테스트=Haiku, 리팩토링=Sonnet | 전 계층 Opus |

> 💡 Design 모델은 `/dev`와 동일하게 `wbs-parse.py --complexity`의 `recommended_model`로 판정한다 (`options.model`이 없을 때). Haiku 지정 시 Design만 Sonnet으로 자동 대체.

## 전제조건 확인

> **검증 시점**: 0-1(인자 파싱)과 0-2(설정 변수) 완료 **직후**, "실행 절차 1. WP 선정" 시작 **직전**에 순서대로 수행. 한 항목이라도 미충족이면 즉시 중단 (리소스 부분 할당 금지).

- **WBS 모드 전용** — `/dev-seq`는 Feature 모드를 지원하지 않는다. `args-parse.py`가 `source=feat`을 감지하면 자동 차단하며, 사용자는 아래 메시지를 보게 된다:
  > ❌ `/dev-seq`은 WBS 모드 전용입니다. Feature 개발은 `/feat {NAME}`으로 실행하세요.

- **git repo 확인**:
  ```bash
  git rev-parse --is-inside-work-tree
  ```
  실패 시 다음 메시지 출력 후 중단:
  > ❌ git 저장소가 아닙니다. `git init` 후 다시 실행하세요.

> tmux / 워크트리 / 시그널 디렉토리 / 플랫폼 감지 등 `/dev-team`의 병렬 인프라 전제조건은 `/dev-seq`에 해당하지 않는다. 현재 세션·현재 브랜치에서 그대로 실행된다.

## 실행 절차

### 1. WP 선정

#### WP-ID가 없는 경우 (자동 선정)

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md - --resumable-wps
```
JSON 출력의 실행 가능 WP 목록을 **전부 자동 선정**하고 다음 포맷으로 안내:
```
🤖 자동 선정 WP: [WP-01, WP-02, ...] (총 N개) — 순차 실행합니다.
```
목록이 비어 있으면 "실행 가능 WP 없음"을 보고하고 종료.

#### WP-ID가 있는 경우

입력된 순서대로 순차 실행 대상으로 확정. 각 WP는 아래 2~5단계를 거쳐 처리된다.

### 2. 의존성 분석 및 실행 순서 결정

각 WP에 대해:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {WP-ID} --tasks-pending \
  | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dep-analysis.py
```

- `circular`가 비어있지 않으면 해당 WP를 **즉시 중단**(`ON_FAIL`과 무관) + 순환 목록 보고 → 다음 WP로 이동.
- `levels`를 레벨 오름차순, 레벨 내는 선언 순서대로 **평탄화**해 Task 배열을 만든다 (병렬 실행 금지 — 항상 1개 Task씩).

### 3. 아키텍처

```
오케스트레이터(현재 세션·현재 브랜치) → WP 순회 → Task 순회 → Phase 순회(Design→Build→Test→Refactor)
각 Phase = Agent 도구로 dev-design/build/test/refactor 서브에이전트 1회 호출
```

tmux pane / 워크트리 / WP 리더 / 시그널 파일 / 머지 절차 **없음**. 모든 상태 전이는 Phase 서브에이전트 내부에서 `wbs-transition.py`가 state.json에 기록한다.

### 4. Task 실행 루프 (핵심)

각 Task에 대해 다음을 순서대로 수행한다.

#### 4-1. 재개 판단 및 의존 검사

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {TSK-ID} --phase-start
```

- `status == "[xx]"` → 이미 완료, **스킵** + "already-done" 카운트 증가 (다음 Task).
- 의존 Task 중 하나라도 `[xx]`/`bypassed` 아니면 → **스킵** + "dep-not-ready" 기록 (다음 Task).
- 그 외에는 반환된 `start_phase`(`design`/`build`/`test`/`refactor`)부터 Phase 루프 시작.

#### 4-2. Phase 루프

`start_phase`부터 Refactor까지 순서대로, **Agent 도구**로 `dev-design`/`dev-build`/`dev-test`/`dev-refactor` 서브에이전트를 1회씩 호출한다.

**공통 prompt 템플릿** (`{SKILL}`만 Phase별로 치환):
```
${CLAUDE_PLUGIN_ROOT}/skills/{SKILL}/SKILL.md를 Read 도구로 읽고 "실행 절차"를 따르라.
SOURCE=wbs
DOCS_DIR={DOCS_DIR}
TSK_ID={TSK-ID}

[Task 블록]   # design/build에만 첨부 — wbs-parse.py --block으로 추출
```

Task 블록 추출(design/build 전):
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {TSK-ID} --block
```

**Phase 매핑 표** (dev/SKILL.md 라인 143-148과 동일):

| # | Phase | `subagent_type` | 기본 모델 | Task 블록 | 게이트 재확인 |
|---|-------|-----------------|-----------|-----------|---------------|
| 1 | Design | `dev-design` | `--complexity`의 `recommended_model` (haiku면 sonnet으로 대체) | ✅ | `status=[ ]`이면 실패·중단, `[dd]`이면 진행 |
| 2 | Build | `dev-build` | `sonnet` | ✅ | `last.event=build.fail`이면 실패, `[im]`이면 진행 |
| 3 | Test | `dev-test` | `haiku` | ❌ | `last.event=test.fail`이면 실패, `[ts]`이면 진행 |
| 4 | Refactor | `dev-refactor` | `sonnet` | ❌ | `[xx]`이면 완료, `refactor.fail`이면 실패 |

`--model opus` 지정 시 네 Phase 모두 Opus로 강제. Haiku 지정 시 Design만 Sonnet으로 대체.

> **중요**: Phase 호출은 반드시 **Agent 도구**(`Agent` 또는 `Task` 도구)를 사용한다. Skill 도구로 `/dev`를 재귀 호출하지 **않는다**. 이유:
> - (a) 컨텍스트 토큰 절약 — 오케스트레이터 세션이 각 Task의 DDTR 히스토리 전체를 떠안지 않고, 각 서브에이전트는 자신의 격리된 컨텍스트에서 완료 후 요약만 반환
> - (b) Phase별 모델 분리 — dev-design=Opus, dev-test=Haiku 등 Agent 호출 파라미터의 `model` 필드로 정확히 적용됨 (Skill 재귀 호출 시 모델 지정이 깨짐)

각 Phase 서브에이전트 호출 **직후** `wbs-parse.py --phase-start`를 다시 실행해 `last.event`를 확인한다:
- `*.ok` → 다음 Phase로 진행
- `*.fail` → "4-3. 실패 처리" 분기

#### 4-3. 실패 처리 (`*.fail` 감지 시)

`ON_FAIL` 정책에 따라 분기:

| `ON_FAIL` | 동작 |
|-----------|------|
| `fast` | 즉시 `wbs-transition.py {WBS} {TSK} bypass --reason "on-fail=fast"` 호출 → 다음 Task |
| `bypass` (기본) | 같은 Phase를 **Opus로 1회 재시도** (Agent 호출 시 `model: "opus"` override). 재시도 후 `--phase-start`로 재확인: 성공이면 다음 Phase, 실패면 `wbs-transition.py bypass` → 다음 Task |
| `strict` | 에스컬레이션 없이 **전체 중단** — 현재 Task 이후 모든 남은 Task 및 WP 실행 취소. 오케스트레이터는 최종 요약 후 종료 |

bypass 호출:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-transition.py {DOCS_DIR}/wbs.md {TSK-ID} bypass \
  --reason "{event}-fail after escalation (on-fail={ON_FAIL})"
```
이 호출이 state.json에 `bypassed: true`를 기록하므로 `dep-analysis.py`가 이후 Task에서 해당 의존을 충족으로 판정한다 (`references/state-machine.json._bypass_semantics` 참조).

#### 4-4. Task 완료 기록

상태 전이(`design.ok`/`build.ok`/`test.ok`/`refactor.ok`)는 각 Phase 서브에이전트 내부에서 `wbs-transition.py`가 state.json을 갱신하므로 **`/dev-seq` 오케스트레이터는 별도 기록 작업이 없다**. bypass만 4-3에서 오케스트레이터가 직접 호출한다.

### 5. WP별/최종 요약 보고

각 WP 종료 시 한 줄 요약:
```
[WP-01] done=N bypassed=N failed=N skipped=N (dep-not-ready=N, already-done=N) elapsed=Ts
```

모든 WP 처리 후 최종 요약:
```
✅ /dev-seq 완료
- 총 WP: N (성공 N, 부분완료 N, 중단 N)
- 총 Task: N (done N, bypassed N, skipped N)
- 실행 시간: T
- 현재 브랜치: {branch}
```

`strict` 모드로 중단된 경우에도 지금까지 처리된 카운트와 중단 사유(`{TSK-ID} {Phase} 실패`)를 동일 포맷으로 보고한다.

## Resume

중단 후 `/dev-seq {동일 인자}` 재실행 시 state.json(`[dd]`/`[im]`/`[ts]`/`[xx]`)을 기준으로 자동 재개된다:

- `wbs-parse.py --tasks-pending`이 `[xx]` 상태 Task를 자동 제외하므로 이미 완료된 Task는 스킵
- `--phase-start`가 Task별 시작 Phase를 반환하므로 실패 지점부터 재개
- 시그널 파일은 사용하지 않는다 (워크트리가 없으므로 불필요)

## 사용자 종료

`Ctrl-C`로 중단. 현재 실행 중인 Phase 서브에이전트가 종료될 때까지 대기한 뒤 오케스트레이터도 종료된다. state.json은 마지막으로 성공 완료된 Phase까지만 기록되어 있으므로 재실행 시 정확히 그 지점부터 재개된다.
