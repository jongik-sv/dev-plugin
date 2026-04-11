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

## 1. Feature 초기화 (이름 자동 생성 포함)

Bash 도구로 실행한다. **반드시 `feat_name`이 아닌 `feat_name_arg`를 사용**한다 — 빈 이름일 때 `-`로 자동 치환되어 있어 쉘 워드 스플리팅 버그를 방지한다:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/feat-init.py {DOCS_DIR} {feat_name_arg} {feat_description}
```

> 과거 버그: 템플릿에 `{feat_name}`을 쓰면 이름이 비어 있을 때 빈 토큰이 사라져 `feat-init.py docs 레이트 리미터 추가` 처럼 호출되고 `레이트`가 이름으로 잘못 인식되어 kebab-case 검증 실패 → 폴더 미생성. `feat_name_arg`는 항상 `-` 또는 유효한 이름이므로 안전하다.

JSON 출력에서 추출 (`args-parse.py`와 동일한 키 이름 사용 — audit 4-7 해결):
- `source`: 항상 `"feat"` (스키마 정렬용)
- `feat_name`: 최종 Feature 이름 (자동 생성되었을 수도 있음) — **이후 모든 단계에서 이 값을 사용한다**
- `feat_dir`: Feature 디렉토리 경로 (예: `docs/features/rate-limiter`)
- `spec_path`: spec.md 경로
- `state_path`: state.json 경로
- `mode`: `"created"` (신규) 또는 `"resume"` (기존)
- `auto_generated`: `true`면 이름이 설명에서 슬러그로 생성됨
- `fallback_used`: `true`면 슬러그 생성 실패로 timestamp fallback 사용됨

**사용자 안내 출력** (mode/auto_generated에 따라):

| 조건 | 출력 메시지 |
|------|-------------|
| `mode="created"` + `auto_generated=false` | `"Feature '{feat_name}' 생성됨. 요구사항은 {spec_path}에 있습니다. 설계를 시작합니다."` |
| `mode="created"` + `auto_generated=true` + `fallback_used=false` | `"Feature 이름 자동 생성: '{feat_name}' (설명에서 슬러그). 필요 시 {spec_path}를 편집하세요. 설계를 시작합니다."` |
| `mode="created"` + `auto_generated=true` + `fallback_used=true` | `"Feature 이름 자동 생성: '{feat_name}' (설명에서 슬러그 생성 불가 → timestamp fallback). 더 의미 있는 이름으로 변경하려면 디렉토리명과 state.json의 name 필드를 수정하세요. 설계를 시작합니다."` |
| `mode="resume"` | `"Feature '{feat_name}' 재개. 현재 상태에 따라 적절한 Phase부터 진행합니다."` |

**이름 우선순위**: 이후 모든 단계에서 사용할 `feat_name`은 **feat-init.py 출력의 `feat_name`**이다. `args-parse.py`의 `feat_name`은 자동 생성 케이스에서 비어 있을 수 있으므로, 두 스크립트가 동일한 키 이름을 쓰더라도 **post-init 값(feat-init.py 출력)이 우선**한다.

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

## 3. 모델 선택

`/dev`와 동일 원칙:

| Phase | 기본 모델 | Agent `model` 값 |
|-------|-----------|-------------------|
| Design | Opus | `"opus"` |
| Build | Sonnet | `"sonnet"` |
| Test | Haiku | `"haiku"` |
| Refactor | Sonnet | `"sonnet"` |

`options.model`이 있으면 전 단계 해당 모델.

**설계는 Haiku 금지** — `options.model=haiku`이면 Design Phase만 `sonnet`으로 자동 대체한다 (설계는 판단이 필요하므로 Haiku로 실행하지 않는다). 오케스트레이터(`/dev`, `/feat`)와 `dev-design` 내부에 동일 가드가 있으며, 오케스트레이터가 **먼저** 차단하여 사용자가 설계가 haiku로 실행된다고 오해하는 것을 방지한다.

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

모델 기본값(Design Opus / Build Sonnet / Test Haiku / Refactor Sonnet)과 Haiku 금지 규칙(Design 한정)은 위 "3. 모델 선택"과 동일하며, `/dev`도 같은 규칙을 사용한다.

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
