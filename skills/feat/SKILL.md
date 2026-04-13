---
name: feat
description: "WBS 독립 Feature 전체 개발 사이클. WBS가 없는 즉석 기능/버그/리팩토링에 사용. 이름 생략 시 자동 생성. 사용법: /feat [name] [description] 또는 /feat <name> --only design"
---

# /feat - Feature 개발 전체 사이클 (WBS 독립)

`/dev`의 형제 명령어. WBS Task 대신 **독립 Feature** 단위로 설계→TDD구현→테스트→리팩토링 사이클을 실행한다.

- 산출물: `{DOCS_DIR}/features/{feat_name}/` (spec.md, design.md, test-report.md, refactor.md, state.json)
- 상태 저장: `state.json` (사이드카, WBS 모드의 `docs/tasks/{TSK-ID}/state.json`과 동일 스키마). DFA는 `/dev`와 동일 (`references/state-machine.json`). 레거시 `status.json`은 resume 시 자동 리네임된다.
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

JSON 출력에서 추출:
- `source`: 항상 `"feat"`
- `feat_name`: 최종 Feature 이름 — **이후 모든 단계에서 이 값을 사용한다**
- `feat_dir`: Feature 디렉토리 경로 (예: `docs/features/rate-limiter`)
- `spec_path`: spec.md 경로
- `state_path`: state.json 경로
- `mode`: `"created"` (신규) 또는 `"resume"` (기존)

**사용자 안내 출력**:

| 조건 | 출력 메시지 |
|------|-------------|
| `mode="created"` | `"Feature '{feat_name}' 생성됨. 설계를 시작합니다."` |
| `mode="resume"` | `"Feature '{feat_name}' 재개. 현재 상태에 따라 적절한 Phase부터 진행합니다."` |

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

### 3-1. 복잡도 판정 (오케스트레이터 직접 수행)

`options.model`이 없고 Design Phase를 실행할 때, **오케스트레이터가 직접** spec.md와 프로젝트 구조를 빠르게 확인하여 복잡도를 판정한다:

1. `{feat_dir}/spec.md`를 Read로 읽는다
2. 아래 신호를 확인한다:

| 신호 | 조건 | 점수 |
|------|------|------|
| **도메인** | spec.md `## 도메인` 값: default/backend→0, frontend→+1, fullstack→+2 | 0~2 |
| **키워드** | spec.md 본문에 아키텍처/마이그레이션/인프라/통합/리팩토링 등 | +2 |
| **영향 범위 추정** | 프로젝트 구조(package.json, 모노레포 여부)를 빠르게 확인하여 수정 대상이 다수 패키지에 걸치면 | +1 |

임계값: **3점 이상 → Opus**, 미만 → **Sonnet**

사용자에게 한 줄 알림:
```
ℹ️  Design 모델: {model} (복잡도 {score}점, 요인: {factors})
```

### 3-2. Phase별 모델

| Phase | 기본 모델 | Agent `model` 값 |
|-------|-----------|-------------------|
| Design | **복잡도 기반** (Sonnet 또는 Opus) | 3-1 결과 |
| Build | Sonnet | `"sonnet"` |
| Test | Haiku | `"haiku"` |
| Refactor | Sonnet | `"sonnet"` |

`options.model`이 있으면 전 단계 해당 모델.

**설계는 Haiku 금지** — `options.model=haiku`이면 Design Phase만 `sonnet`으로 자동 대체한다.

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
