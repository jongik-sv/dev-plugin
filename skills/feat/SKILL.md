---
name: feat
description: "WBS 독립 Feature 전체 개발 사이클. WBS가 없는 즉석 기능/버그/리팩토링에 사용. 이름 생략 시 자동 생성. 사용법: /feat [name] [description] 또는 /feat <name> --only design"
---

# /feat - Feature 개발 전체 사이클 (WBS 독립)

`/dev`의 형제 명령어. WBS Task 대신 **독립 Feature** 단위로 설계→TDD구현→테스트→리팩토링 사이클을 실행한다.

- 산출물: `{DOCS_DIR}/features/{feat_name}/` (spec.md, design.md, test-report.md, refactor.md, state.json)
- 상태 저장: `state.json` (사이드카, 단일 소스). WBS 모드의 `docs/tasks/{TSK-ID}/state.json`과 **동일 스키마·동일 DFA** — `${CLAUDE_PLUGIN_ROOT}/references/state-machine.json`을 공유한다. `phase_start`/실패 시 status 유지/재진입 규칙 모두 `/dev`와 동일 (`/dev/SKILL.md` "Phase 간 실패 게이트" 참조).
- 레거시 `status.json` 자동 마이그레이션: `feat-init.py`와 `wbs-transition.py` 양쪽이 **idempotent 하게** `status.json → state.json` 리네임을 수행한다 (이미 `state.json`이 있으면 스킵). 따라서 재개를 여러 번 실행해도 충돌하지 않는다.
- 사용 시점: WBS가 없는 즉석 기능 추가, 버그 수정, 프로토타입, 오픈소스 기여, 단독 리팩토링.

인자: `$ARGUMENTS` ([SUBPROJECT] + [name] + [description...])

**이름 입력 규칙**:
- 단일 토큰(`rate-limiter`, `login`, `login-2fa`) → 그대로 이름으로 사용
- 하이픈 포함 토큰 + 추가 설명(`rate-limiter "Add rate limit"`) → 이름 + 설명 분리
- 자연어/다중 토큰/대문자·공백 포함 → 전체를 설명으로 취급, 이름은 kebab-case 슬러그로 자동 생성
- 슬러그 생성 실패(비-ASCII만 있음) → `feat-YYYYMMDD-HHMMSS` timestamp fallback
- 중복 이름 감지 시: 명시 이름은 **재개 모드**, 자동 생성 이름은 **timestamp 접미사 추가**로 신규 생성

## 제약 사항

- **이름 규칙**: kebab-case (`^[a-z][a-z0-9-]*$`). 대문자·공백·특수문자 금지. 자동 생성도 동일.
- **dev-team 비지원**: Feature는 병렬 팀 개발 대상이 아니다. 개별 Feature로 운영한다.
- **WBS 승격 미지원**: 본 버전에서는 Feature → WBS Task 변환을 지원하지 않는다.

## Dev Config

Feature 모드는 다음 우선순위로 Dev Config를 로드한다:

1. `{feat_dir}/dev-config.md` — 이 Feature 전용 로컬 오버라이드 (파일 전체가 `## Dev Config` 섹션 하나로 구성)
2. `{DOCS_DIR}/wbs.md`의 `## Dev Config` 섹션 — 프로젝트 공용 설정
3. `${CLAUDE_PLUGIN_ROOT}/references/default-dev-config.md` — 전역 기본값

로컬 오버라이드가 필요한 예: 이 Feature만 특정 테스트 러너를 사용하거나, 다른 도메인 가이드를 적용해야 하는 경우. 그 외에는 프로젝트 wbs.md나 기본값으로 충분하다.

## 0. 인자 파싱

Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/args-parse.py feat $ARGUMENTS
```
JSON 출력에서 추출:
- `docs_dir`: 저장소 루트 (`docs` 또는 `docs/p1`)
- `feat_name`: Feature 이름 (비어 있을 수 있음 — 그 경우 feat-init.py가 자동 생성)
- `feat_name_arg`: **feat-init.py에 넘길 이름 인자** (비어 있으면 자동으로 `-`). 1단계에서 이 필드를 사용하라.
- `feat_description`: Feature 설명 (신규 생성 시 spec.md에 기록)
- `options.only`: 특정 단계만 실행 (design|build|test|refactor)
- `options.model`: 모델 오버라이드

**에러 처리**:
- `feat_name`과 `feat_description`이 **모두** 비어 있으면: `"Feature 정보가 없습니다. 사용법: /feat <name> 또는 /feat \"설명\""`
- 이름 형식 오류 (`args-parse.py`가 stderr로 보고) 시: 해당 메시지를 그대로 사용자에게 전달 후 종료.

## 1. Feature 이름 확정 + 초기화

### 1-1. 이름 확정 (오케스트레이터 직접 수행)

`feat_name`이 비어 있으면 (설명만 제공된 경우) 오케스트레이터가 **의미 기반 이름**을 생성한다:

1. `feat_description`에서 핵심 개념을 추출하여 영문 kebab-case 이름을 만든다
   - 규칙: `^[a-z][a-z0-9-]*$`, 최대 40자
   - 예: `"로그인 2FA 기능 추가"` → `login-2fa`, `"API 레이트 리미터"` → `api-rate-limiter`
2. `{DOCS_DIR}/features/` 하위에 동일 이름이 이미 존재하면 재개 모드로 전환 (신규 이름 생성 아님)

`feat_name`이 이미 있으면 (사용자 명시) 이 단계를 건너뛴다.

### 1-2. 디렉토리 생성

확정된 이름으로 `feat-init.py` 호출:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/feat-init.py {DOCS_DIR} {확정된_feat_name} {feat_description}
```

JSON 출력에서 먼저 `ok` 필드를 확인한다:

- `ok == false` → **즉시 중단**. `error` 필드 내용을 그대로 사용자에게 보고:
  ```
  ❌ Feature 초기화 실패: {error}
  ```
  대표 실패 케이스 (feat-init.py 스펙 기준):
  - `docs dir not found: ...` — `{DOCS_DIR}`이 실존하지 않음 (상위 오케스트레이터의 인자 파싱 오류 또는 경로 오타)
  - `이름과 설명이 모두 비어 있습니다. ...` — `feat_name`·`feat_description` 둘 다 공란
  - `invalid feature name: ... — kebab-case required ...` — 이름 형식 위반 (사용자 입력 또는 1-1 자동 생성 실패)

- `ok == true` → 아래 필드를 후속 단계에서 사용:
  - `source`: 항상 `"feat"`
  - `feat_name`: 최종 Feature 이름 — **이후 모든 단계에서 이 값을 사용한다**
  - `feat_dir`: Feature 디렉토리 경로 (예: `docs/features/rate-limiter`)
  - `spec_path`: spec.md 경로
  - `state_path`: state.json 경로
  - `mode`: `"created"` (신규) 또는 `"resume"` (기존)

**사용자 안내 출력** (`ok == true` 인 경우):

| 조건 | 출력 메시지 |
|------|-------------|
| `mode="created"` | `"Feature '{feat_name}' 생성됨. 설계를 시작합니다."` |
| `mode="resume"` | `"Feature '{feat_name}' 재개. 현재 상태에 따라 적절한 Phase부터 진행합니다."` |

## 1-3. Intake (신규 Feature 한정 — 적극 질문 모드)

> ⚠️ **이 단계만 dev-plugin의 자율 결정 정책 예외**다. 다른 모든 진입점은 묻지 않고 자율 진행한다.

`feat-init.py`가 `mode="created"`를 반환하면(신규 Feature) **spec.md 본문 작성 직전에** AskUserQuestion 도구로 요구사항을 적극적으로 끌어낸다. `mode="resume"`면 이 단계를 **완전히 건너뛴다** (spec.md가 이미 있고 사용자가 이전에 의도를 지정했음).

### 권장 질문 시퀀스 (순차 실행, 3~5개)

1. **목적 (kind)** — 무엇을 하려는가
   - feature (신규 기능)
   - bugfix (버그 수정)
   - refactor (구조 개선, 동작 보존)
   - perf (성능 개선)
   - docs (문서/주석)
   - Other (자유 입력 시 사용자가 선택)

2. **성공 기준 (acceptance)** — 완료를 어떻게 판단하는가
   - 단위 테스트 + E2E 모두 통과
   - 특정 정량 지표 충족 (사용자가 Other로 명시)
   - UI 시각 확인 (frontend 한정)
   - 기존 회귀 없음 (refactor 한정)

3. **범위 경계 (scope, multiSelect=true)** — 어떤 영역을 건드리는가
   - backend
   - frontend
   - database / migration
   - config / 인프라
   - docs / 주석
   - tests only

4. **제약 (constraints)** — 절대 어겨선 안 되는 항목
   - 외부 의존성 추가 금지
   - 기존 API 호환성 유지
   - 특정 성능 임계값 (사용자가 Other로 명시)
   - 보안·권한 변경 금지

5. (조건부) **유사 기존 기능 (similar_existing)** — 코드 일부를 검색해 후보가 1개 이상이면 보여주고 "신규 vs 재사용" 선택. 0개면 이 질문을 건너뛴다.

> 질문은 한 번에 하나씩(`questions` 배열에 1~2개)만 보내는 것을 권장한다. 사용자 응답이 명확하면 다음 질문으로 진행, 모호하면 같은 주제로 보조 질문 1회 추가.

### Intake 결과 반영

응답을 받은 즉시 두 곳에 기록한다:

1. **spec.md 갱신** — feat-init.py가 만든 초기 spec.md를 다음 골격으로 덮어쓴다 (Edit 도구 사용):
   ```markdown
   # {feat_name}

   ## 목적
   {kind}: {feat_description}

   ## 성공 기준
   {acceptance}

   ## 도메인
   {scope의 첫 항목 — frontend/backend/fullstack 매핑}

   ## 범위 경계
   - 포함: {scope multiSelect 결과}
   - 제외: (intake에서 명시되지 않은 모든 영역)

   ## 제약
   {constraints}

   ## (선택) 유사 기존 기능
   {similar_existing 응답}
   ```

2. **decisions.md 적재** — intake 자체를 결정 entry로 남긴다:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/decision-log.py append \
     --target {feat_dir} \
     --phase feat-intake \
     --decision-needed "사용자 의도·범위·제약 명확화 (신규 Feature)" \
     --decision-made "kind={kind}, acceptance={acceptance}, scope={scope}, constraints={constraints}" \
     --rationale "AskUserQuestion intake 응답 그대로 반영" \
     --reversible yes
   ```

### Intake 종료 후

Intake가 끝나면 **즉시 자율 모드로 전환**한다. 이후 단계(2 Phase 재개 판단 → 4 실행 절차)는 사용자에게 더 묻지 않고 자율 진행한다. 모호 상황 발생 시 `decisions.md`에 적재만 하고 흐름을 멈추지 않는다.

## 2. Phase 재개 판단

Bash 도구로 실행:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py --feat {feat_dir} --phase-start
```

JSON 출력의 `start_phase`를 확인한다. `/dev`와 동일한 DFA를 사용하므로 상태값과 매핑도 동일하다:

| 현재 status | start_phase | 시작 Phase |
|-------------|-------------|-----------|
| `[ ]` | `design` | Phase 1 (Design) — 최초 실행 또는 설계 미완료 |
| `[dd]` | `build` | Phase 2 (Build) — 설계 완료, 빌드 대기/재시도 |
| `[im]` | `test` | Phase 3 (Test) — 빌드 완료, 테스트 대기/재시도 |
| `[ts]` | `refactor` | Phase 4 (Refactor) — 테스트 통과, 리팩토링 대기 |
| `[xx]` | `done` | `"이미 완료된 Feature입니다"` 출력 후 종료 |

> 실패는 상태를 되돌리지 않는다. `last` 필드가 실패 정보를 담는다 (`/dev/SKILL.md` 참조).

`options.only`가 있으면 해당 Phase만 실행 (재개 판단 무시).

## 3. 모델 선택 (복잡도 기반)

**Phase별 기본 모델·Haiku 금지 규칙·`options.model` 우선순위는 `/dev`와 동일하다** — `${CLAUDE_PLUGIN_ROOT}/skills/dev/SKILL.md`의 "모델 선택" 섹션이 단일 소스. 임계값(3점)과 domain/keyword 점수표도 그대로 공유한다.

### 3-1. Feature 복잡도 입력 매핑

`options.model`이 없고 Design Phase를 실행할 때, 오케스트레이터가 직접 spec.md와 프로젝트 구조를 확인하여 `/dev`와 동일한 점수 체계로 판정한다. 단 Feature에는 WBS 메타데이터가 없으므로 입력이 다르다:

| `/dev` 신호 | `/feat` 대응 | 판정 방법 |
|-------------|--------------|-----------|
| `depends` | **항상 0** | Feature에는 WBS 의존성 필드가 없음 |
| `domain` | spec.md `## 도메인` 라인의 값 | `default/backend`→0, `frontend`→+1, `fullstack`→+2, `docs/test`→-1 |
| 키워드 | spec.md 본문 (frontmatter·헤더 라인 제외) | 아키텍처/미들웨어/트랜잭션/WebSocket/FSM 등 `/dev`와 동일 패턴 매치 시 +2 |
| `category` | **항상 0** | Feature에는 WBS 카테고리 필드가 없음 |
| (추가) 영향 범위 | 모노레포의 `package.json` 개수 | 리포지토리 루트와 `packages/`, `apps/`, `services/` 등 하위에서 `package.json` 파일이 **3개 이상**이면 +1. 그 외 0. |

판정 절차:
1. `{feat_dir}/spec.md`를 Read로 읽어 `## 도메인` 값과 키워드 매치 여부 확인
2. Glob 도구로 `**/package.json`을 한 번 검색하여 개수 집계 (`node_modules/**` 제외)
3. 점수 합산 후 임계값(3점) 이상이면 Opus, 미만이면 Sonnet

사용자에게 한 줄 알림:
```
ℹ️  Design 모델: {model} (source: feat-auto, {score}점, 요인: {factors})
```

### 3-2. Phase별 모델

`/dev`와 완전히 동일. Design만 위 3-1로 판정, Build/Refactor는 Sonnet, Test는 Haiku. `options.model` 지정 시 전 단계 해당 모델 (단 Haiku 지정 시 Design은 Sonnet으로 자동 대체).

## 4. 실행 절차

각 Phase는 서브에이전트로 위임한다. **Phase 실행 절차/게이트/실패 프로토콜은 `/dev`와 완전히 동일** — `${CLAUDE_PLUGIN_ROOT}/skills/dev/SKILL.md`의 "Phase 간 실패 게이트" 및 "Phase 1~4" 섹션을 참조한다. feat 모드의 차이는 아래 매핑뿐이다.

**`/dev` → `/feat` 매핑**

| `/dev` (WBS) | `/feat` (Feature) |
|--------------|-------------------|
| `SOURCE=wbs` | `SOURCE=feat` |
| prompt에 `TSK_ID={TSK-ID}` | prompt에 `FEAT_NAME={feat_name}` + `FEAT_DIR={feat_dir}` |
| prompt 말미 `[Task 블록]` | 생략 — 하위 스킬이 `{FEAT_DIR}/spec.md`를 직접 읽음 |
| 게이트 명령 `wbs-parse.py {DOCS_DIR}/wbs.md {TSK-ID} --phase-start` | `wbs-parse.py --feat {feat_dir} --phase-start` |
| 실패 보고 `"{TSK-ID} {Phase} 실패 …"` | `"Feature '{feat_name}' {Phase} 실패 …"` |

각 Phase 서브에이전트 프롬프트 공통 구조:
```
${CLAUDE_PLUGIN_ROOT}/skills/{dev-design|dev-build|dev-test|dev-refactor}/SKILL.md를 Read 도구로 읽고 "실행 절차"를 따르라.
SOURCE=feat
DOCS_DIR={DOCS_DIR}
FEAT_NAME={feat_name}
FEAT_DIR={feat_dir}
```

모델 기본값(Design 복잡도 기반 / Build Sonnet / Test Haiku / Refactor Sonnet)과 Haiku 금지 규칙(Design 한정)은 위 "3. 모델 선택"과 동일하며, `/dev`도 같은 규칙을 사용한다.

## 5. --only 옵션 처리
- `--only design`: Phase 1만 실행
- `--only build`: Phase 2만 실행
- `--only test`: Phase 3만 실행
- `--only refactor`: Phase 4만 실행

## 6. 완료 보고

각 Phase 완료 시 한 줄 요약을 출력하고, 전체 완료 시 최종 상태와 산출물 경로를 보고한다:
```
✅ Feature '{feat_name}' 완료. 산출물: {feat_dir}/ (design.md, test-report.md, refactor.md)
```
