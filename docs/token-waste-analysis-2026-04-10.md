# Token Waste 심층 분석 — 2026-04-10

dev-team 3WP × 5tasks (15 tasks) 기준으로 실행 흐름을 추적하여 토큰 낭비 패턴을 식별.

---

## 실행 체인과 계층별 컨텍스트 규모

```
[Layer 0] 팀리더 ← dev-team/SKILL.md (374줄, ~5,300 tok)
  │
  ├─ wp-setup.py (스크립트, 토큰 무관)
  │
  ├─[Layer 1] WP리더 ← wp-leader-prompt.md (261줄, ~3,700 tok) + Task블록
  │   │
  │   └─[Layer 2] Worker ← ddtr-prompt-template.md (~58줄, ~850 tok)
  │       │
  │       └─[Layer 3] /dev ← dev/SKILL.md (123줄, ~1,810 tok)
  │           │
  │           ├─[Layer 4a] Design  ← dev-design/SKILL.md (82줄, ~1,010 tok)
  │           ├─[Layer 4b] Build   ← dev-build/SKILL.md (79줄, ~955 tok)
  │           ├─[Layer 4c] Test    ← dev-test/SKILL.md (115줄, ~1,950 tok)
  │           └─[Layer 4d] Refactor← dev-refactor/SKILL.md (78줄, ~910 tok)
  │
  ├─[Layer 1] WP리더 #2 (동일 구조)
  └─[Layer 1] WP리더 #3 (동일 구조)
```

**Task 1건의 instruction 토큰**: ~8,200 tok (DDTR + /dev + 4 Phase)
**WP 1개 overhead**: ~9,000 tok (리더 프롬프트 + 팀리더 분담분)
**3WP × 5tasks 전체**: ~8,200 × 15 + ~9,000 × 3 = **~150,000 tok** (instruction만)

---

## W1. [Impact: 매우 높음] "Prompt Composition Middleware" 안티패턴

### 문제

`/dev` 오케스트레이터가 각 Phase별 SKILL.md를 **읽고** → 내용을 **가공하여** → 서브에이전트 프롬프트로 **출력**한다. 서브에이전트는 그 프롬프트를 **입력**으로 받아 실행. 사실상 같은 정보가 3번 토큰으로 소비된다.

```
현재 흐름 (Phase 1 기준):

/dev Claude:
  [INPUT]  dev/SKILL.md 123줄 ← /dev 전체 로드
  [INPUT]  dev-design/SKILL.md 82줄 ← "절차를 따른다"를 위해 읽기
  [INPUT]  wbs-parse.py 출력 ← Task 블록 파싱
  [OUTPUT] 서브에이전트 프롬프트 ~30줄 ← 위 내용을 재구성하여 출력
                                          ~~~~~~~~~~~
Design 서브에이전트:
  [INPUT]  프롬프트 ~30줄 ← /dev가 만든 프롬프트 수신
  [INPUT]  wbs-parse.py 재실행 ← Task 정보 다시 파싱 (SKILL.md가 지시)
  [INPUT]  design template 읽기
  [실행]
```

**낭비 구간**: /dev가 dev-design/SKILL.md를 읽는 ~1,010 tok + 프롬프트 재구성 출력 ~600 tok = **~1,600 tok/Phase**

4 Phase × 1,600 = **~6,400 tok/task**, 15 tasks = **~96,000 tok**

### 개선안: "Read-and-Execute" 위임 패턴

```
개선 흐름:

/dev Claude:
  [INPUT]  dev/SKILL.md ~70줄 (Phase별 상세 제거, 위임 지시만)
  [OUTPUT] 서브에이전트 프롬프트 ~5줄:
    "${CLAUDE_PLUGIN_ROOT}/skills/dev-design/SKILL.md를 Read하고 절차를 실행하라.
     DOCS_DIR={DOCS_DIR}, TSK_ID={TSK-ID}
     Task 블록: [여기에 포함]"

Design 서브에이전트:
  [INPUT]  프롬프트 ~5줄
  [INPUT]  dev-design/SKILL.md 82줄 ← 서브에이전트가 직접 읽음
  [실행]
```

**변화**:
- /dev가 Phase SKILL.md를 읽을 필요 없음 (4 × ~1,000 tok 절감)
- /dev 프롬프트 출력이 ~30줄 → ~5줄 (4 × ~500 tok 절감)
- dev/SKILL.md 자체도 123줄 → ~70줄로 축소 가능 (~800 tok 절감)
- 서브에이전트가 SKILL.md를 직접 읽으므로 정보 손실 없음

**예상 절감**: ~5,000 tok/task × 15 tasks = **~75,000 tok**

---

## W2. [Impact: 높음] Task 블록 5~7회 반복 읽기

하나의 Task 블록(~15-30줄, ~300 tok)이 실행 체인에서 반복적으로 파싱/전달된다:

| 횟수 | 위치 | 행위 |
|------|------|------|
| 1 | wp-setup.py | wbs-parse.py로 추출 → DDTR 프롬프트에 삽입 (스크립트, 무비용) |
| 2 | WP리더 프롬프트 | all_task_blocks로 전체 Task 블록 포함 (~300 × N tok) |
| 3 | /dev 오케스트레이터 | wbs-parse.py --block 재실행 (dev/SKILL.md:59) |
| 4 | dev-design 서브에이전트 | wbs-parse.py 재실행 (dev-design/SKILL.md:36) |
| 5 | dev-build 서브에이전트 | wbs-parse.py 재실행 (dev-build/SKILL.md:36) |
| 6 | dev-test 서브에이전트 | wbs-parse.py 재실행 (dev-test/SKILL.md:48) |
| 7 | dev-refactor 서브에이전트 | wbs-parse.py 재실행 (dev-refactor/SKILL.md:36) |

**낭비**: 3~7번은 중복. Worker가 이미 DDTR 프롬프트에 Task 블록을 가지고 있고, /dev는 Worker의 컨텍스트를 상속하므로 wbs-parse.py 재실행이 불필요.

**예상 절감**: ~1,200 tok/task × 15 = **~18,000 tok**

### 개선안

- DDTR 프롬프트에서 `/dev` 호출 시 Task 블록을 인자로 전달
- 각 Phase SKILL.md에 "호출자가 Task 블록을 전달한 경우 wbs-parse.py 스킵" 조건 추가
- 또는 W1의 "Read-and-Execute" 패턴 적용 시, /dev가 Task 블록 1회만 파싱하여 서브에이전트 프롬프트에 포함

---

## W3. [Impact: 높음] WP리더 프롬프트 — 60%가 전체 실행 중 1회만 사용

wp-leader-prompt.md 261줄(~3,700 tok)의 시간대별 사용 분석:

| 구간 | 줄수 | 토큰 | 사용 시점 | 사용 빈도 |
|------|------|------|-----------|-----------|
| 초기화 (pane 생성, resume) | 59-99 | ~700 | 시작 30초 | **1회** |
| 경로 변수 + 규칙 | 29-35, 257-261 | ~250 | 전체 | 참조용 |
| 할당 프로토콜 | 101-130 | ~500 | 할당 시 | 반복 |
| 모니터링 + 재활용 | 132-163 | ~600 | 완료 감지 시 | 반복 |
| 실패 처리 | 182-190 | ~200 | 실패 시 | 0~수회 |
| cross-WP 의존 | 192-197 | ~150 | 특정 Task만 | 0~수회 |
| 최종 정리 + 시그널 | 199-255 | ~900 | 종료 시 | **1회** |

**시작/종료 전용 구간**: ~1,600 tok → 수시간 동안 컨텍스트에 잔류하나 해당 시점 이외 미사용

### 개선안: 프롬프트 분할

```
wp-leader-core.md    (~100줄, ~1,500 tok) — 항상 필요한 변수/할당/모니터링
wp-leader-init.md    (~50줄, ~700 tok)    — "Read하고 초기화 실행 후 진행"
wp-leader-cleanup.md (~60줄, ~900 tok)    — "모든 Task 완료 시 Read하고 실행"
```

초기 컨텍스트: 1,500 tok (현재 3,700 tok 대비 **60% 감소**)

**예상 절감**: ~2,200 tok/WP × 3 WP = **~6,600 tok** (장시간 컨텍스트 점유 해소)

---

## W4. [Impact: 높음] dev-team SKILL.md — 활용률 40%

374줄(~5,300 tok) 중 특정 시점에만 사용되는 구간:

| 구간 | 줄수 | 토큰 | 사용 시점 |
|------|------|------|-----------|
| 아키텍처 다이어그램 | 119-139 | ~400 | 이해용, 1회 |
| config JSON 스키마 | 154-177 | ~500 | config 작성 시 1회 |
| 비tmux 폴백 (B) | 221-233 | ~300 | tmux 없을 때만 |
| 결과 통합 5(A) | 262-355 | ~1,700 | WP 완료 시 |
| 결과 통합 5(B) | 357-375 | ~400 | 전체 완료 시 |

**비활성 구간**: ~3,300 tok (전체의 62%)

### 개선안: reference 파일 분리

```
dev-team/SKILL.md           (~150줄, ~2,000 tok) — 핵심 흐름만
dev-team/references/merge-procedure.md  — 5(A)/(B) 머지 절차
dev-team/references/config-schema.md    — JSON 스키마 예시
```

팀리더의 초기 컨텍스트: ~2,000 tok (현재 5,300 tok 대비 **62% 감소**)

**예상 절감**: ~3,300 tok (팀리더 컨텍스트 점유 해소)

---

## W5. [Impact: 중간] Phase SKILL.md 보일러플레이트 반복

4개 Phase 스킬에 동일 구조의 보일러플레이트가 반복:

| 보일러플레이트 | 줄수/스킬 | 토큰/스킬 | × 4 Phase |
|---------------|-----------|-----------|-----------|
| args-parse.py 호출 패턴 | ~7줄 | ~150 | ~600 |
| 모델 선택 설명 | ~8줄 | ~200 | ~800 |
| wbs-parse.py Task 정보 수집 | ~5줄 | ~120 | ~480 |
| wbs-update-status.py 호출 | ~4줄 | ~100 | ~400 |
| **소계** | ~24줄 | ~570 | **~2,280** |

이 보일러플레이트는 `/dev`에서 서브에이전트로 호출될 때 대부분 불필요 (오케스트레이터가 이미 파싱/모델 결정 완료).

**Task 당**: ~2,280 tok (4 Phase 스킬 로드 시)
**15 tasks**: **~34,200 tok**

### 개선안: 호출자 컨텍스트 바이패스

각 Phase SKILL.md 상단에 조건 분기 추가:

```
호출자가 아래 변수를 모두 전달한 경우, "0. 인자 파싱"과 "모델 선택" 섹션을 스킵한다:
- DOCS_DIR, TSK_ID, DOMAIN, MODEL → 바로 "실행 절차"로 진행
```

또는 W1 개선안 적용 시 이 문제도 자동 해소됨 (서브에이전트가 필요한 부분만 읽음).

---

## W6. [Impact: 중간] 도메인별 테스트 명령 4중 복제

동일한 테스트 명령이 4개 파일에 분산:

| 파일 | 소비자 | 실제 필요 |
|------|--------|-----------|
| dev/SKILL.md:79,88-89 | 오케스트레이터 | **불필요** — 직접 테스트 실행 안 함 |
| dev-build/SKILL.md:60-63 | Build 서브에이전트 | 필요 (단위 테스트만) |
| dev-test/SKILL.md:68-81 | Test 서브에이전트 | 필요 (단위 + E2E) |
| dev-refactor/SKILL.md:60-62 | Refactor 서브에이전트 | 필요 (단위 테스트만) |

**dev/SKILL.md의 테스트 명령** (~5줄, ~150 tok)은 서브에이전트에 전달되지 않으므로 순수 낭비.

또한 명령이 변경되면 4곳을 모두 수정해야 하며, 실제로 이번 수정에서 dev/SKILL.md만 미갱신됨 (skill-review C-1 참조).

### 개선안: 참조 파일로 통합

```
references/test-commands.md:
  ## 단위 테스트
  - backend: bundle exec rspec --exclude-pattern "spec/features/**/*,spec/system/**/*"
  - frontend: npm run test
  - sidecar: uv run pytest -m "not e2e"
  - fullstack: backend → frontend → sidecar 순차 (fail-fast)
  - database / infra / docs: N/A

  ## E2E 테스트
  - backend: bundle exec rspec spec/features spec/system
  - frontend: npm run test:e2e (Missing script → npx playwright test)
  - sidecar: uv run pytest -m e2e
  - fullstack: backend → frontend → sidecar 순차 (fail-fast)
  - database / infra / docs: N/A
```

각 Phase 스킬에서 `"Read ${CLAUDE_PLUGIN_ROOT}/references/test-commands.md"` 참조.
dev/SKILL.md에서는 테스트 명령 목록 자체를 제거.

**예상 절감**: ~150 tok/task (dev/SKILL.md) + 유지보수 일관성 확보

---

## W7. [Impact: 중간] 시그널 프로토콜 설명 3~4중 복제

시그널 프로토콜(`.running`/`.done`/`.failed`, `signal-helper.py` 사용법)이 여러 프롬프트에 반복:

| 위치 | 줄수 | 토큰 | 역할 |
|------|------|------|------|
| dev-team/SKILL.md:61-72 | 12줄 | ~400 | 팀리더용 (wait만 필요) |
| wp-leader-prompt.md 전반 | ~80줄 | ~1,500 | WP리더용 (wait+check 필요) |
| ddtr-prompt-template.md:16-57 | ~25줄 | ~500 | Worker용 (start/done/fail만 필요) |
| team-mode/SKILL.md:33-41 | ~10줄 | ~200 | team-mode 리더용 |
| agent-pool/SKILL.md:25-33 | ~10줄 | ~200 | agent-pool용 |

**총**: ~2,800 tok에 달하는 시그널 설명이 각 계층에서 자기 역할과 무관한 부분까지 포함.

### 개선안: 역할별 최소 스니펫

- **Worker**: "성공: `signal-helper.py done {id} {dir} "msg"`, 실패: `signal-helper.py fail {id} {dir} "msg"`, 시작: `echo started > {dir}/{id}.running`" — 3줄이면 충분
- **리더**: "대기: `signal-helper.py wait {id} {dir} {timeout}`, 확인: `signal-helper.py check {id} {dir}`" — 2줄이면 충분
- 전체 프로토콜 테이블은 `references/signal-protocol.md`로 분리

---

## W8. [Impact: 낮음] design.md 이중 읽기 (Phase 2)

dev/SKILL.md:76에서 오케스트레이터가 "design.md 내용을 포함하여 전달"하라고 지시.
dev-build/SKILL.md:38에서 서브에이전트가 "design.md를 Read 도구로 읽는다"고 지시.

프롬프트에 포함 + 서브에이전트가 직접 읽기 = design.md가 2회 소비.

W1 개선안 적용 시 자동 해소 (서브에이전트가 직접 읽으면 오케스트레이터가 포함할 필요 없음).

---

## 종합 절감 추정 (3WP × 5tasks)

| # | 패턴 | 절감/task | 절감/WP | 절감/전체 | 난이도 |
|---|------|----------|---------|-----------|--------|
| W1 | Prompt Composition 위임 | ~5,000 | ~25,000 | **~75,000** | 중 |
| W2 | Task 블록 중복 제거 | ~1,200 | ~6,000 | **~18,000** | 하 |
| W3 | WP리더 프롬프트 분할 | — | ~2,200 | **~6,600** | 중 |
| W4 | dev-team reference 분리 | — | — | **~3,300** | 하 |
| W5 | 보일러플레이트 바이패스 | ~2,280 | ~11,400 | **~34,200** | 하~중 |
| W6 | 테스트 명령 통합 | ~150 | ~750 | **~2,250** | 하 |
| W7 | 시그널 프로토콜 역할별 분리 | — | ~1,500 | **~4,500** | 하 |
| W8 | design.md 이중 읽기 | ~300 | ~1,500 | **~4,500** | W1에 포함 |
| | **합계** | | | **~148,350** | |

> 현재 15-task 실행의 instruction 토큰이 ~150,000 tok이므로, 위 최적화를 모두 적용하면 instruction 토큰을 **약 50% 절감** 가능.

---

## 우선순위 권장

### Phase 1 — 즉시 (낮은 난이도, 높은 효과)

1. **W4**: dev-team SKILL.md에서 머지 절차/config 스키마를 reference 파일로 분리
2. **W6**: 테스트 명령을 `references/test-commands.md`로 통합
3. **W7**: 시그널 프로토콜을 역할별 스니펫으로 축소

### Phase 2 — 단기 (구조 변경)

4. **W1**: dev/SKILL.md를 "Read-and-Execute" 위임 패턴으로 전환
   - dev/SKILL.md에서 Phase별 상세 제거, 서브에이전트에게 SKILL.md 직접 읽기 위임
   - W2, W5, W8이 자동 해소됨

### Phase 3 — 중기 (프롬프트 아키텍처)

5. **W3**: wp-leader-prompt.md를 core/init/cleanup으로 3분할
6. **W5**: Phase SKILL.md에 "호출자 바이패스" 조건 추가 (W1과 병행)
