---
name: dev-test
description: "Task/Feature 테스트 단계. 단위 + E2E 테스트 실행, 실패 시 수정 반복. 사용법: /dev-test [SUBPROJECT] TSK-00-01"
---

# /dev-test - 테스트 실행

인자: `$ARGUMENTS` ([SUBPROJECT] + TSK-ID)
- 예: `TSK-00-01`, `p1 TSK-00-01`

> **호출자 바이패스**: 프롬프트에 `DOCS_DIR`과 (`TSK_ID` 또는 `FEAT_DIR`)가 명시된 경우, "0. 인자 파싱"과 "모델 선택" 섹션을 스킵하고 바로 "실행 절차"로 진행한다.
>
> **SOURCE 분기**: `SOURCE=feat` + `FEAT_DIR` + `FEAT_NAME` 전달 시 feat 모드, 아니면 wbs 모드. 기본값은 wbs.
>
> **⚠️ Feature 모드 진입은 `/feat`를 거쳐야 한다.** `/feat`가 `feat-init.py`로 feat_dir을 생성/확인한 뒤 FEAT_DIR을 전달한다. phase 스킬 직접 호출 시 `SOURCE=feat`를 손으로 지정하지 말 것.

## 0. 인자 파싱

Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/args-parse.py dev-test $ARGUMENTS
```
JSON 출력에서 `docs_dir`, `tsk_id`를 확인한다. 에러 시 사용자에게 보고 후 종료.

## 모델 선택 및 자동 에스컬레이션

이 Phase의 **기본 모델은 Haiku** (`"haiku"`)이다.

- 호출자(`/dev`, DDTR 등)가 `model` 파라미터를 명시하면 해당 모델을 사용
- 직접 실행(`/dev-test TSK-XX-XX`) 시 Haiku 기본 적용
- 가장 기계적인 루프(에러 파싱→수정→재실행)이므로 Haiku로 충분

**자동 에스컬레이션**: 1차 Haiku 실행이 실패하면 **2차부터 Sonnet으로 자동 승격**한다 (2·3차 모두 Sonnet). Haiku는 shallow fix(테스트 약화·단일 파일 한정 수정)로 회귀를 만들 위험이 있어 재시도 단계에서는 Sonnet이 근본 원인 분석까지 수행한다.

## 재시도 예산 체계 (2층 구조)

| 층위 | 단위 | 예산 | 모델 | 책임 주체 |
|------|------|------|------|-----------|
| **시도 (attempt)** | 서브에이전트 1회 호출 | 최대 **3회** | 1회차 `haiku`, 2·3회차 `sonnet` (근본 원인 분석) | 호출자(`/dev-test` 본체). 시도 사이에 이전 시도의 실패 요약만 전달하여 재스폰 |
| **수정-재실행 사이클** | 단일 시도 내부에서 "코드 수정 + 실패한 테스트만 재실행" 1회 | 시도당 **최대 1회** | 시도 모델 상속 | 서브에이전트. 1회 사이클 후 여전히 실패하면 즉시 보고 |

3회를 초과하는 재시도는 금지한다. 본문의 "수정 예산", "내부 재실행", "추가 반복"은 모두 **수정-재실행 사이클**과 동일한 의미다 (단일 테스트 유형 실패 시 시도 1→2→3 순으로 진행. 케이스 A 성공 분기 / 케이스 B는 단계 3 본문 참조).

### Systematic-debugging 게이트 (escalation 전 강제 단계)

시도 1 실패 → 시도 2(escalation)로 넘어가기 직전, `scripts/debug-evidence.py collect`를 호출하여 4단계 evidence(에러 raw / 재현 가능성 / 최근 변경 / 컴포넌트 경계 로깅)를 수집한 뒤 `state.json.phase_history` 마지막 entry의 `debug_evidence` 필드에 합성한다. evidence 없이 escalation 진입은 금지된다 — `references/state-machine.json`의 `_debug_required_before_escalation` 메타가 활성화 기준이다.

```bash
# 시도 1 실패 직후, 시도 2 스폰 전
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/debug-evidence.py collect \
  --phase test \
  --target {ARTIFACT_DIR} \
  --error-file /tmp/test-stdout.txt \
  --reproduce {always|conditional|once} \
  [--component "auth-api:401 from /login"] \
  > /tmp/debug-evidence-{ID}.json

python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-transition.py {DOCS_DIR}/wbs.md {TSK-ID} test.fail \
  --debug-evidence /tmp/debug-evidence-{ID}.json
```

3회 시도 후에도 실패하여 bypass로 진행할 때, `bypassed_reason`은 `debug-evidence.py bypass-reason --evidence /tmp/debug-evidence-{ID}.json` 출력으로 채운다. "tests still failing" 같은 빈 사유 금지.

근본 원인 분석을 강제하므로 escalation이 "더 큰 모델로 같은 곳 두드리기"가 되지 않는다.

**실제 테스트 명령 실행 횟수 ≠ 사이클 수**: 위 예산은 **수정-재실행 사이클 수**이지 `pytest`/`vitest` 같은 명령 실행 횟수가 아니다. 한 시도 안에서 사이클 1회를 소진하지 않은 채 여러 명령이 실행될 수 있다:

- **케이스 A 성공 경로**: 단위 수정 → 단위 재실행 통과 → **E2E → 정적 검증이 이어서 실행**됨. 이 연장 실행은 새 사이클을 소비하지 않지만, E2E/정적 검증에서 실패해도 **수정 예산이 이미 소진되었으므로 추가 수정 없이 실패를 보고**한다(단계 3 케이스 A 참조).
- **최악 시나리오(한 시도 내부)**: 단위(최초) → 단위(수정 후 재실행) → E2E → 정적 검증 = **최대 4개 명령** / 사이클 1회.

서브에이전트 실행 시 Agent 도구의 `model` 파라미터에 해당 모델 값을 지정한다.

## 실행 절차

### 1. Task/Feature 정보 수집 (source 분기)

#### (A) SOURCE=wbs (기본)
Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md {TSK-ID}
```
JSON 출력에서 domain을 확인한다. `ARTIFACT_DIR={DOCS_DIR}/tasks/{TSK-ID}`, `{ARTIFACT_DIR}/design.md`에서 관련 파일 목록을 파악한다.

#### (B) SOURCE=feat
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py --feat {FEAT_DIR} --status
```
`ARTIFACT_DIR={FEAT_DIR}`, `{ARTIFACT_DIR}/design.md`에서 domain과 파일 목록을 파악한다.

### 1-5. UI E2E 정합성 게이트 (서브에이전트 스폰 전 차단)

lect 사고(v1.4.1)에서 도출된 구조적 방어막이다. UI 도메인에서 E2E 명령이 누락된 채 "silent skip"으로 통과되는 것을 막는다.

**Step A — Dev Config 로드**:

SOURCE=wbs:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md - --dev-config
```

SOURCE=feat:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py --feat {FEAT_DIR} --dev-config {DOCS_DIR}
```

**Step B — `effective_domain` 판정** (1차 라벨 + 2차 휴리스틱 재분류):

- 1차: 단계 1에서 추출한 `domain`
- 2차: `domain`이 frontend/fullstack이 아닌데도 `{ARTIFACT_DIR}/design.md`에 UI 키워드가 포함되어 있으면 `effective_domain = frontend`로 재라벨

UI 키워드 (대소문자 무시, **단어 경계 매칭**): `button`, `click`, `render`, `form`, `input`, `component`, `modal`, `page`, `screen`, `Playwright`, `Cypress`, `@testing-library`, `화면`, `버튼`, `클릭`, `입력`, `렌더`, `컴포넌트`, `페이지`, `모달`

매칭 규칙:
- 영문 키워드는 `\b{keyword}\b` (word boundary) 정규식으로 검사. 예: `render`는 매칭하되 `surrender`, `tender`, `gender`는 매칭하지 않음. `click`은 매칭하되 `heptoclick`은 제외
- 한국어 키워드는 word boundary가 없으므로 그대로 substring 매칭하되, 금지어 목록과 조합해 오탐을 줄임 (현재 예외 없음)
- 검색 범위: design.md의 마크다운 본문(제목/표/문단/리스트) + 인라인 코드. **fenced 코드 블록(```…```)과 HTML 주석(`<!-- ... -->`)은 제외** — 코드 샘플에 우발적으로 등장하는 라이브러리 식별자가 재분류를 트리거하는 것을 방지

design.md를 Read 도구로 읽고 위 규칙으로 1개 이상 매칭되면 UI 도메인으로 간주한다. 이유: dev-design이 domain을 "default"/"backend"로 잘못 라벨링해도 실제로 UI 작업이면 게이트가 걸려야 함. 경계 사례(예: 기술 문서에서 "재렌더링 성능"이 본문에 등장)는 서브에이전트가 judgement call로 판단하되, 확신이 서지 않으면 frontend로 재라벨링하여 안전한 쪽(E2E 게이트 강화)으로 기울인다.

**Step C — E2E 명령 존재 확인**:

`effective_domain`이 frontend 또는 fullstack인 경우, Dev Config JSON의 `domains[{effective_domain}].e2e_test`를 확인:

- **값이 null/빈 값이면**: 서브에이전트 스폰하지 않고 즉시 아래 절차 실행:
  1. 사용자에게 안내 메시지 출력:
     ```
     ❌ {effective_domain} 도메인 E2E 테스트 명령이 정의되지 않았습니다.
     UI 기능은 E2E 검증 없이 통과 처리할 수 없습니다 (v1.4.1부터).

     해결 방법:
     1. Dev Config의 {effective_domain}.e2e-test 칸에 실제 명령 정의
        예: `pnpm --filter @myapp/e2e test`, `npx playwright test`
     2. 고의로 skip (권장 X): placeholder 명령 정의
        예: `python3 -c "pass"` (크로스플랫폼, git diff에 의도가 남음)
        주의: `/bin/true`는 Windows에서 실패하므로 지양

     Dev Config 파일 위치:
     - WBS: {DOCS_DIR}/wbs.md의 ## Dev Config 섹션 Domains 표
     - Feature: {FEAT_DIR}/dev-config.md 또는 프로젝트 wbs.md
     ```
  2. `test.fail` 전이 스크립트 실행 (단계 3의 SOURCE 분기 명령 사용):
     ```bash
     # SOURCE=wbs
     python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-transition.py {DOCS_DIR}/wbs.md {TSK-ID} test.fail
     # SOURCE=feat
     python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-transition.py --feat {FEAT_DIR} test.fail
     ```
  3. 본 Phase 즉시 종료. 이후 단계(2~4)는 건너뛴다.

- **값이 있으면** (실제 명령 또는 명시적 placeholder): 단계 2로 진행

> **기억**: Step B에서 판정한 `effective_domain`은 단계 2-2(결과 검증)에서도 동일하게 사용한다. 단계 2 서브에이전트 프롬프트에는 `effective_domain`이 아닌 원래 `domain`을 전달한다 (서브에이전트는 재분류 사실을 알 필요 없음).

> **build와의 키워드 동기화**: Step B의 UI 키워드 목록은 dev-build Step 0 진입 판정(tdd-prompt-template.md)의 기준과 대응된다. build는 `{DOMAIN}`(원본 라벨)으로 Step 0/E2E 작성 여부를 결정하고, 본 게이트는 `effective_domain`(재분류)으로 검증하므로 다음 역전이 발생할 수 있다:
>
> - **build가 UI로 판정(domain=frontend/fullstack) → test도 UI로 판정**: 정상 경로, 양쪽 모두 실행.
> - **build는 비-UI로 판정(domain=backend/default) → test는 재분류로 UI**: 본 게이트에서 `e2e_test` 부재 또는 E2E 파일 부재로 `test.fail` 차단. 호출자는 상태 `[im]` 유지, dev-build로 되돌아가 재작업 필요(사용자 판단으로 domain 수정 후 `/dev-build` 재실행 또는 bypass).
> - **build가 UI로 판정 → test는 비-UI로 판정**: 본 게이트 스킵, 작성된 E2E는 단계 2에서 함께 실행됨.
>
> 즉 본 게이트가 reachability cascade의 최종 검증점이며, 실패 시 build 재작업으로 롤백되지 않고 `[im]` 상태에 머문 채 사용자 개입을 요구한다.

### 1-6. Pre-E2E 컴파일 게이트 (서브에이전트 스폰 전 차단)

`effective_domain`이 frontend 또는 fullstack인 경우, E2E 실행 전에 **대상 앱이 컴파일되는지** 확인한다. 컴파일 불가 상태에서 E2E를 실행하면 서버 미기동 → 타임아웃 → 재시도의 루프로 수십 분이 낭비된다.

**Step A — typecheck 명령 확인**:

단계 1-5에서 이미 로드한 Dev Config JSON의 `quality_commands.typecheck`를 확인한다.

**Step B — 컴파일 검증 실행**:

- `typecheck`가 정의되어 있으면: `run-test.py 120`으로 래핑하여 실행
  ```bash
  python3 ${CLAUDE_PLUGIN_ROOT}/scripts/run-test.py 120 -- {typecheck 명령}
  ```
  Bash `timeout`: **180000** (180초 = run-test.py 120초 + 60초 버퍼). Bash 기본값(120초)을 그대로 쓰면 run-test.py와 동시 만료되어 HINT 진단이 끊긴다.
- `typecheck`가 null이면: Step B를 건너뛰고 단계 2로 진행 (검증 불가이므로 통과 처리)

**Step C — 결과 판정**:

- **통과 (exit 0)**: 단계 2로 진행
- **실패 (exit ≠ 0)**: 서브에이전트 스폰하지 않고 **Step D(원인 분류)**로 진행

**Step D — 원인 분류 (Build regression vs Pre-existing)**:

컴파일 에러가 이 Task/Feature의 코드에서 발생한 것인지 판별한다. 자동화 워크플로우에서 pre-existing 에러로 인해 영원히 멈추는 것과, build regression을 자동 복구하는 것을 구분하기 위함.

1. typecheck 출력에서 **에러가 발생한 파일 경로**를 추출한다 (TS 에러: `src/path/file.ts(line,col):` 패턴 등)
2. `{ARTIFACT_DIR}/design.md`의 "파일 계획" 테이블에서 **이 Task/Feature가 생성/수정한 파일 목록**을 추출한다
3. 교집합 판정:
   - **교집합 있음 → Build regression**: 이 Task의 코드가 컴파일을 깨뜨렸다
   - **교집합 없음 → Pre-existing**: 에러가 이 Task 범위 밖의 파일에서 발생

**Step E — Build regression 자동 복구 (최대 1회)**:

교집합이 있는 경우, Build Phase를 **1회** 재실행하여 자동 복구를 시도한다:

1. `build_retry` 카운터를 확인한다 (최초 진입 시 0)
2. **`build_retry == 0`** (첫 번째 시도):
   - `build_retry = 1`로 설정
   - dev-build 서브에이전트를 재실행한다. 프롬프트에 컴파일 에러 컨텍스트를 포함:
     ```
     ${CLAUDE_PLUGIN_ROOT}/skills/dev-build/SKILL.md를 Read 도구로 읽고 "실행 절차"를 따르라.
     SOURCE={SOURCE}
     DOCS_DIR={DOCS_DIR}
     {TSK_ID 또는 FEAT_NAME/FEAT_DIR}

     ## 컴파일 에러 수정 요청 (Test Phase에서 회귀)
     이전 Build에서 단위 테스트는 통과했으나, typecheck(전체 컴파일)에서 아래 에러가 발생했다.
     에러 파일이 이 Task/Feature의 파일 계획에 포함되어 있어 Build regression으로 판정됨.
     단위 테스트를 유지하면서 컴파일 에러를 수정하라.

     typecheck 에러:
     {출력 마지막 30줄}
     ```
   - Build 서브에이전트 완료 후 **Step B(컴파일 검증)를 다시 실행**
   - 통과하면 단계 2로 진행
   - 여전히 실패하면 `build_retry == 1`이므로 Step F로

3. **`build_retry == 1`** (재시도 소진):
   - Step F로 진행 (최종 실패)

**Step F — 최종 실패 (Pre-existing 또는 복구 실패)**:

1. 사용자에게 안내 메시지 출력:
   ```
   ❌ Pre-E2E 컴파일 게이트 실패: typecheck에서 에러가 발견되었습니다.
   컴파일되지 않는 상태에서 E2E는 서버 미기동으로 반드시 타임아웃됩니다.

   분류: {Build regression (복구 실패) | Pre-existing (Task/Feature 범위 밖)}

   typecheck 출력:
   {run-test.py의 stdout 마지막 30줄}

   에러 파일: {에러 파일 목록}
   파일 계획: {design.md 파일 목록}
   교집합: {있음/없음}

   해결 방법:
   - Build regression: /dev-build {TSK-ID} 또는 /feat {name} --only build
   - Pre-existing: 컴파일 에러를 수동 수정 후 /dev-test {TSK-ID} 또는 /feat {name} --only test
   ```
2. `test.fail` 전이 스크립트 실행 (단계 3의 SOURCE 분기 명령 사용)
3. 본 Phase 즉시 종료. 이후 단계(2~4)는 건너뛴다.

> **단계 2.5 정적 검증과의 관계**: 단계 2.5의 typecheck는 "코드 수정 후 regression 검증" 용도로 유지한다. 이 게이트는 "E2E 진입 전 blocker 사전 차단" 용도이며 서로 다른 시점에서 다른 목적을 수행한다.

### 1-7. E2E 서버 lifecycle 관리 (서브에이전트 스폰 전)

E2E 테스트에서 서버 기동과 테스트 실행을 분리한다. 서버 기동 실패를 별도 에러로 감지하고, 재시도 시 서버 재기동 오버헤드를 제거한다.

**Step A — Dev Config에서 서버 정보 확인**:

단계 1-5에서 로드한 Dev Config JSON의 `domains[{effective_domain}].e2e_server`와 `domains[{effective_domain}].e2e_url`을 확인한다.

- **둘 다 정의됨**: Step B로 진행
- **하나라도 미정의(null)**: 이 단계를 건너뛰고 단계 2로 진행 (Playwright/Cypress가 서버를 내부적으로 관리). `E2E_SERVER_MANAGED=false`

**Step B — 서버 상태 확인**:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/e2e-server.py check --url {e2e_url}
```

- **exit 0 (running)**: 서버 이미 실행 중. `E2E_SERVER_MANAGED=true` 기록, 단계 2로 진행
- **exit 1 (not_running)**: Step C로 진행

**Step C — 서버 기동**:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/e2e-server.py start --cmd "{e2e_server}" --url {e2e_url} --timeout 120
```
Bash `timeout`: 180000 (180초 = start 내부 120초 + 60초 버퍼)

- **exit 0 (started/already_running)**: `E2E_SERVER_MANAGED=true` 기록, 단계 2로 진행
- **exit 1 (server_crashed/timeout)**: 서버 기동 실패 → BLOCKER로 처리:
  1. JSON 출력의 `log_tail`에서 에러 원인 확인
  2. 사용자에게 안내:
     ```
     ❌ E2E 서버 기동 실패: {e2e_server} → {e2e_url}

     상태: {status} (server_crashed: 프로세스 즉시 종료 / timeout: {timeout}초 내 응답 없음)

     서버 로그 (마지막 20줄):
     {log_tail}

     해결 방법:
     1. 서버 명령을 수동 실행하여 에러 확인: {e2e_server}
     2. Dev Config의 e2e-server/e2e-url 값이 올바른지 확인
     ```
  3. `test.fail` 전이 스크립트 실행 (단계 3의 SOURCE 분기 명령 사용)
  4. 본 Phase 즉시 종료. 이후 단계(2~4)는 건너뛴다.

> **`E2E_SERVER_MANAGED` 효과**: true일 때 서브에이전트 프롬프트에 "E2E 서버 상태" 섹션을 추가하여, 이미 기동된 서버를 사용하도록 안내한다. 프로젝트의 E2E config에 `reuseExistingServer: true` (Playwright) 또는 이에 상응하는 설정이 필요하다.

### 2. 테스트 실행 (서브에이전트 위임)
Agent 도구로 서브에이전트를 실행한다 (model: 호출자 지정값 또는 `"haiku"`, mode: "auto"):

**프롬프트 구성**:
```
다음 요구사항의 테스트를 실행하고 모두 통과시켜라.

대상: {TSK-ID 또는 FEAT_NAME}
Domain: {domain}

## 조기 중단 조건 (BLOCKER — retry 대상 아님)
다음 중 하나라도 해당하면 수정-재실행 사이클을 소비하지 말고 즉시 실패 보고하라:
- 서버/앱이 컴파일되지 않음 (TS errors, schema mismatch, import 에러 등)
- webServer가 기동 불가 (프로세스가 exit code ≠ 0으로 즉시 종료)
- 동일한 에러 메시지로 2회 연속 타임아웃
- run-test.py 출력에 `[run-test] HINT: COMPILE_ERROR` 또는 `HINT: SERVER_CRASH`가 포함
이 경우 test-report.md의 실패 사유 첫 줄에 **BLOCKER**를 명시한다.

## Bash 도구 타임아웃
테스트 명령을 Bash 도구로 실행할 때 반드시 `timeout` 파라미터를 설정한다 (상세·SSOT: `${CLAUDE_PLUGIN_ROOT}/references/test-commands.md` "실행 래핑" 섹션):
- 단위 테스트: `timeout: 360000` (360초 = run-test.py 300초 + 60초 버퍼)
- E2E 테스트: `timeout: 360000` (360초 = run-test.py 300초 + 60초 버퍼)
Bash 기본값(120초)은 run-test.py 타임아웃(300초)보다 짧아서 Bash가 먼저 프로세스를 죽이고 HINT 진단이 끊긴다.

{E2E_SERVER_MANAGED=true인 경우 아래 섹션을 프롬프트에 추가한다}
## E2E 서버 상태
서버가 이미 기동 중 ({e2e_url}). reuseExistingServer: true로 순수 테스트만 실행한다.
서버 기동은 완료되었으므로 webServer 관련 에러(EADDRINUSE, 기동 타임아웃)가 발생하면 BLOCKER로 보고한다.

## QA 체크리스트
{ARTIFACT_DIR}/design.md의 "QA 체크리스트" 섹션을 읽고, 각 항목을 테스트로 검증한다.

## 절차

### 단계 1: 단위 테스트
`${CLAUDE_PLUGIN_ROOT}/references/test-commands.md`의 "단위 테스트" 섹션을 참조하여 domain에 맞는 단위 테스트를 실행한다. 모든 명령은 `run-test.py 300`으로 래핑하고 Bash `timeout: 360000`을 적용한다 (위 "Bash 도구 타임아웃" 섹션 참조).

**실패 시 E2E 테스트와 정적 검증을 건너뛰고 즉시 단계 3으로 이동**한다 (실패가 확실한 상태에서 E2E는 토큰·시간 낭비이므로 먼저 단위 테스트를 고친 뒤 E2E를 실행한다).

### 단계 2: E2E 테스트 (단위 테스트 통과 시에만 실행)
**단위 테스트가 모두 통과한 경우에만** E2E 테스트를 실행한다.
`${CLAUDE_PLUGIN_ROOT}/references/test-commands.md`의 "E2E 테스트" 섹션을 참조한다. 모든 명령은 `run-test.py 300`으로 래핑하고 Bash `timeout: 360000`을 적용한다.

**명령 존재 여부**:
- Dev Config의 `domains[{domain}].e2e_test`가 **정의되어 있으면**: 해당 명령을 run-test.py로 래핑하여 실행
- null인 경우 처리는 domain에 따라 다르다 (`${CLAUDE_PLUGIN_ROOT}/references/test-commands.md` 참조) — frontend/fullstack은 호출자가 단계 1-5에서 이미 차단했으므로, 이 시점에 null을 만나면 backend/default 도메인이며 "N/A — {domain} domain"으로 기록하고 계속 진행

#### ⚠️ E2E 우회 금지 (모든 위반은 test.fail)

E2E 실행 중 아래 행위는 **절대 금지**다. lect 사고(v1.4.1)에서 서브에이전트가 환경 에러를 N/A로 합리화하고 `playwright test --list`로 위장 실행한 전례가 있으므로 명시적으로 막는다.

1. **환경 에러 → N/A 대체 금지**
   `.env` 파일 누락, `DATABASE_URL` 에러, 포트 충돌, `webServer` 미기동, 빌드 산출물 부재, Docker 컨테이너 미실행 등 **환경 문제로 테스트가 실행되지 못하면 무조건 `test.fail`로 보고**한다.
   "E2E 환경 미구성으로 N/A 처리", "테스트 인프라 부재로 skip" 같은 문구를 test-report.md에 쓰면 안 된다. 환경 문제는 사용자가 고쳐야 할 문제이지 서브에이전트가 판단할 문제가 아니다.

2. **명령 대체 금지**
   Dev Config의 `e2e_test` 필드에 정의된 **정확한 명령**을 run-test.py로 래핑하여 실행한다. 다음과 같은 "실행 시늉" 명령으로 바꾸지 마라:
   - `playwright test --list`, `--dry-run`, `--help`, `--reporter=list`
   - `grep`으로 테스트 파일 존재 여부만 확인
   - `ls`로 디렉토리 구조만 확인
   - `npx <tool> --version`
   실제 실행이 불가능하면 "왜 불가능한지"를 test.fail 사유로 명시한다.

3. **자체 판단 skip 금지**
   "이 환경에선 E2E가 의미 없다", "설정이 부족해서 실행 불가", "테스트 파일이 구형 base라 skip", "WP 간 의존성 미해결" 같은 판단은 모두 서브에이전트 권한 밖이다. 그런 상황은 `test.fail`로 보고하여 사용자가 결정하게 한다.

**환경 에러 발생 시 test-report.md 기록 형식**:
```
## 실행 요약
| 구분        | 통과 | 실패 | 합계 |
|-------------|------|------|------|
| 단위 테스트 | N    | 0    | N    |
| E2E 테스트  | 0    | M    | M    | ← N/A 아니고 fail

## E2E 실패 사유 (환경 에러)
- {구체적 에러 메시지 1-3줄}
- 재실행에 필요한 조치:
  1. {사용자가 고칠 항목 1}
  2. {사용자가 고칠 항목 2}
```

### 테스트 출력 제한
`${CLAUDE_PLUGIN_ROOT}/references/test-commands.md`의 "출력 제한" 섹션 참조.

### 단계 2.5: 정적 검증 (단위 테스트 통과 + Dev Config에 정의된 경우만)
**단위 테스트가 모두 통과한 경우에만** 실행한다. Dev Config의 `quality_commands`에 lint, typecheck가 정의되어 있으면 실행한다. SOURCE에 따라 로드 명령이 다르다:
- SOURCE=wbs: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md - --dev-config`
- SOURCE=feat: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py --feat {FEAT_DIR} --dev-config {DOCS_DIR}`

JSON 출력의 `quality_commands.lint`, `quality_commands.typecheck`를 확인한다.
- 정의된 명령만 실행한다 (없는 항목은 건너뛴다)
- 경고(warning)는 기록만 한다
- 에러가 있으면 단계 3에서 테스트 실패와 함께 수정한다

### 단계 3: 실패 수정

**경계 교차 검증 원칙** (모든 케이스 공통):
- 테스트 기대값(consumer)과 실제 구현(producer)을 **동시에** 읽는다
- 함수 시그니처, 반환 타입, 필드명 등 계약이 일치하는지 확인
- 단순 로직 버그인지, 경계 불일치(boundary mismatch)인지 구분하여 수정

**케이스 A — 단위 테스트 실패로 진입**:
1. 경계 교차 검증 후 코드 수정 (**수정-재실행 사이클 1회 소진**)
2. **단위 테스트만 재실행** (E2E는 아직 미실행이므로 재실행 대상 아님)
3. 결과 분기:
   - **통과**: 단계 2(E2E) → 단계 2.5(정적 검증)를 이어서 실행. 이 연장 실행은 새 사이클을 소비하지 않지만, E2E/정적 검증에서 실패하면 **수정-재실행 사이클 예산이 이미 소진되었으므로 추가 수정 없이** 실패 내역을 보고
   - **여전히 실패**: E2E 미실행 상태로 실패 보고. "단위 실패로 E2E skip" 명시. 추가 사이클 금지

**케이스 B — 단위 통과 후 E2E 또는 정적 검증 실패로 진입**:
1. 경계 교차 검증 후 코드 수정 (**수정-재실행 사이클 1회 소진**)
2. **실패한 테스트/검증만 재실행** (단위는 이미 통과했으므로 재실행 불필요)
3. 여전히 실패 시 실패 내역을 pass/fail/unverified로 보고. 추가 사이클 금지

**수정-재실행 사이클은 서브에이전트 시도당 최대 1회**. 추가 반복하지 마라 — 재시도(시도 수)는 상위에서 관리한다.

### 단계 4: QA 체크리스트 판정
각 항목에 pass/fail을 기록한다. 단위 실패로 E2E를 건너뛴 경우 E2E 항목은 `unverified`(사유: "단위 실패로 skip")로 기록.

## 결과 작성
{ARTIFACT_DIR}/test-report.md 파일에 작성한다.
양식은 ${CLAUDE_PLUGIN_ROOT}/skills/dev-test/template.md를 따른다.
단위 테스트와 E2E 테스트 결과를 구분하여 기록하고, QA 체크리스트 판정(pass/fail/unverified)도 포함한다.
단위 테스트 실패로 E2E를 건너뛴 경우 E2E 섹션에 "단위 실패로 skip"을 명시한다.
```

### 2-1. 재시도 에스컬레이션 (최대 3회 시도)

서브에이전트가 테스트 실패를 보고한 경우, 이전 시도의 **실패 요약(pass/fail 항목 목록)만** 새 프롬프트에 포함하여 재시도한다. 이전 시도의 전체 테스트 출력은 포함하지 않는다.

- **BLOCKER 감지**: 서브에이전트의 test-report.md 실패 사유에 **BLOCKER** 키워드가 포함되어 있으면 재시도하지 않고 즉시 최종 실패로 보고한다. 컴파일/환경 에러는 모델 승격으로 해결 불가 — 사용자 개입이 필요하다.
- **1회차**: `model: "haiku"` (또는 호출자가 지정한 모델) — 기계적 수정 시도
- **2회차**: `model: "sonnet"`으로 승격 + 실패 요약 포함하여 재실행 (근본 원인 분석)
- **3회차**: `model: "sonnet"` 유지 + 이전 시도들의 실패 요약 누적 전달
- **3회 후에도 실패**: 최종 실패로 보고. 추가 재시도하지 않는다.

> 토큰 절약: 재시도 프롬프트에는 이전 시도의 test-report.md 또는 pass/fail 요약만 포함한다. 전체 로그를 전달하지 마라.

### 2-2. 결과 검증 (호출자 재검증, v1.4.1부터)

서브에이전트가 test-report.md를 작성하고 복귀한 뒤, **호출자(`/dev-test` 본체)**가 test-report.md를 Read로 읽고 다음을 교차 검증한다. lect 사고에서 서브에이전트의 PASS 보고가 실제로는 위장 실행이었던 점을 방어하기 위한 두 번째 레이어다.

**검증: UI 도메인 N/A 탐지**

단계 1-5에서 판정한 `effective_domain`이 frontend 또는 fullstack인 경우:

1. test-report.md 본문에서 "E2E 테스트" 관련 행을 찾는다 (행 기반 검색, 코드 블록 포함)
2. 해당 행에 `N/A` 문자열이 포함되어 있으면:
   - 서브에이전트가 단계 2의 E2E 우회 금지 조항(1~3)을 위반한 것으로 간주
   - 서브에이전트의 pass/fail 판정을 무시하고 **호출자가 직접 `test.fail`로 전이**
   - 사용자 보고 메시지:
     ```
     ❌ E2E 결과 검증 실패: UI 도메인({effective_domain})인데 E2E 섹션이 "N/A"로 기록됨
     → 서브에이전트가 E2E 우회 금지 조항을 위반했습니다 (단계 2)
     → 재시도 에스컬레이션 대상이 아님 (환경·설정 문제이므로 사용자 개입 필요)

     test-report.md에 기록된 N/A 원인:
     {해당 행 또는 주변 컨텍스트}
     ```
   - `test.fail` 전이 스크립트 실행 후 본 Phase 종료. 재시도(단계 2-1) 적용하지 않음
3. N/A가 없으면 검증 통과 → 단계 3(상태 전이)로 정상 진행

**예외**: "단위 실패로 E2E skip"은 허용되는 N/A다. 이 경우는 이미 단위 테스트 실패로 `test.fail` 경로에 있고, 호출자가 별도 재검증할 필요 없이 그대로 단계 3으로 진행한다.

**검증 범위**: 현재는 "N/A 탐지"만 구현. 향후 확장으로 Playwright/Cypress/Vitest의 artifact(예: `playwright-report/results.json`의 `total` 필드)를 직접 읽어 실제 실행 개수를 교차 검증하는 레이어를 추가할 수 있으나, 프레임워크별 로직이 필요하므로 현 단계에서는 범위 외.

### 2-3. Verification Gate (test.ok 직전 필수)

서브에이전트가 모든 QA 체크리스트 pass를 보고했더라도, 실제 테스트 종료 코드와 산출물 존재를 verify-phase.py로 재검증한다. 차단 시 `test.ok` 호출하지 않는다.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify-phase.py \
  --phase test \
  --target {ARTIFACT_DIR} \
  --check unit_test:ok:exit=0,pass={U_PASS},fail={U_FAIL} \
  --check e2e_test:ok:exit=0,pass={E_PASS},fail={E_FAIL} \
  > /tmp/verify-test-{ID}.json
```

`{U_PASS}/{U_FAIL}/{E_PASS}/{E_FAIL}`은 단계 1-2의 run-test.py 출력에서 추출한 실측치. 단위/E2E 어느 쪽이라도 fail count > 0이면 `--check {NAME}:fail:...`로 전달. 종료 코드 1이면 test.ok로 진행하지 않고 단계 2-1 재시도 또는 test.fail 전이로 분기한다.

E2E가 N/A인 도메인(domain=backend without e2e_test)은 `--check e2e_test:ok:exit=0,pass=0,fail=0,skipped=1`로 명시.

상세 프로토콜: `${CLAUDE_PLUGIN_ROOT}/references/verification-protocol.md`.

### 3. 상태 전이

서브에이전트의 최종 판정(pass/fail/unverified) + verification gate 결과에 따라 전이 이벤트를 결정한다:
- 모든 QA 체크리스트 항목이 pass + verification 통과 → `test.ok` → `status=[ts]` (Refactor 대기)
- 하나라도 fail 또는 3회 재시도 후에도 실패 또는 verification 차단 → `test.fail` → status는 `[im]` 유지

**(A) SOURCE=wbs**:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-transition.py {DOCS_DIR}/wbs.md {TSK-ID} test.ok \
  --verification /tmp/verify-test-{ID}.json
# 실패 시: test.fail (verification footer 그대로 첨부 가능)
```

**(B) SOURCE=feat**:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-transition.py --feat {FEAT_DIR} test.ok \
  --verification /tmp/verify-test-{ID}.json
# 실패 시: test.fail
```

> 상태 전이 규칙은 `${CLAUDE_PLUGIN_ROOT}/references/state-machine.json`에 정의되어 있으며 두 모드가 동일한 DFA를 공유한다. verification footer가 phase_history 항목에 합성된다.

### 4. 완료 보고
- 성공: 테스트 결과 요약 출력. state.json의 `status=[ts]`, `last.event=test.ok`, phase_history 최신 항목에 verification footer 합성됨.
- 실패: 실패 항목과 `last.event=test.fail`을 보고. status는 `[im]` 유지.

### 자율 결정 기록

테스트 중 비자명한 자율 결정(테스트 케이스 추가 범위, mock 경계, 타임아웃 정책 등)은 `${CLAUDE_PLUGIN_ROOT}/scripts/decision-log.py append --target {ARTIFACT_DIR} --phase test ...`로 `decisions.md`에 적재한다.

### 5. 호출자 책임 (test.fail 이후 재진입 루프)

본 스킬은 test.fail 전이·보고까지만 책임진다. 이후 **루프 복귀는 호출자의 역할**이며, 구체 규칙은 `skills/dev/SKILL.md`의 "Phase 간 실패 게이트" 표에 정의되어 있다. 요지:

| 시나리오 | 호출자 동작 |
|---------|-----------|
| `test.fail` 일반 | 사용자에게 실패 보고 후 중단. `/dev {TSK-ID}` 재실행 시 `phase_start=test`로 자동 재개 (state-machine의 `[im]` 상태) |
| `test.fail` + 단계 1-5 UI 게이트 차단 (e2e_test 누락) | 사용자가 Dev Config 수정 또는 `/dev-build --only build`로 domain 재라벨 후 재실행 |
| `test.fail` + 단계 1-6 Pre-E2E 게이트 차단 (Build regression 자동 복구 실패) | 사용자가 컴파일 에러 수동 수정 후 `/dev {TSK-ID}` 재실행. 본 스킬이 Step E에서 dev-build를 1회 자동 재호출한 이력은 refactor 사이클과 무관 |
| `test.fail` + 2-2 결과 검증 차단 (E2E N/A 위반) | 재시도 에스컬레이션 대상 **아님** — 사용자가 환경/설정 수정 필요 |

호출자가 dev-build 재호출을 결정하는 책임은 **사용자 개입 이후**다. 본 스킬 내부에서 호출자 재진입 로직을 구현하지 않는다 (단계 1-6 Step E의 build 재호출은 "Pre-E2E 컴파일 자동 복구"라는 좁은 범위이며, test.fail 일반 루프가 아님).
