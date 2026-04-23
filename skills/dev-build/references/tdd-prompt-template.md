# TDD Build 프롬프트 템플릿

`skills/dev-build/SKILL.md` 2단계에서 서브에이전트에 전달하는 프롬프트 본문. 치환 변수: `{REQUIREMENT_SOURCE}`, `{DESIGN_CONTENT}`, `{SOURCE}`, `{DOCS_DIR}`, `{FEAT_DIR}`, `{DOMAIN}`.

> **domain 주입 필수**: `{DOMAIN}`은 `wbs-parse.py`의 `domain` 필드(WBS 모드) 또는 spec/design에서 추출한 도메인 값(Feature 모드). 호출자가 반드시 주입한다. 결정 실패 시 `default`로 설정한다.
>
> **design.md 섹션명 참조 규약 (SSOT)**: 본 템플릿이 언급하는 design.md 섹션명 — "진입점 (Entry Points)", "파일 계획", "QA 체크리스트" — 은 `skills/dev-design/template.md`가 정의하는 섹션 헤딩과 동일해야 한다. design 템플릿이 개정되면 본 파일의 섹션 참조도 동기화한다 (섹션명은 dev-design 템플릿이 SSOT).

```
다음 요구사항을 TDD 방식으로 구현하라.

{REQUIREMENT_SOURCE}

{DESIGN_CONTENT}

## TDD 순서 (반드시 준수)

### Step -1 — Merge Preview (충돌 사전 확인)

**`[im]` 진입 전 반드시 실행한다.** `scripts/merge-preview.py`로 현재 브랜치와 `origin/main` 간 병합 충돌을 시뮬레이션하고, 충돌이 감지되면 즉시 `build.fail`로 보고한다.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/merge-preview.py --remote origin --target main
```

- exit 0 (clean=true): 충돌 없음 — 다음 단계로 진행한다.
- exit 1 (clean=false): 충돌 감지 — JSON의 `conflicts` 배열에 충돌 파일 목록을 포함하여 `build.fail`로 보고한다. 충돌을 먼저 해소한 뒤 `/dev-build`를 재실행하라.
- exit 2: uncommitted 변경 있음 — stash 또는 commit 후 재실행하라.
- 스크립트 미존재(`No such file`): 이 단계를 건너뛰고 다음 단계를 진행한다 (선택적 가드레일).

> 이 단계는 zero side-effect 시뮬레이션(`git merge --no-commit --no-ff` + 반드시 `--abort`)이므로 실제 브랜치 상태를 변경하지 않는다.

### Step 0 — 라우터/메뉴 선행 수정 (UI 도메인 진입점 구현)

**진입 조건**: `{DOMAIN}`이 `fullstack` 또는 `frontend`인 경우 실행한다. 그 외 도메인(`backend`, `default`, `docs`, `test` 등)은 이 단계를 건너뛴다.

> **책임 경계 (설계 게이트 vs 빌드 구현)**:
> - dev-design의 2-1 게이트는 **설계 완성도**(진입점 섹션·라우터/메뉴 파일 계획의 완전성) 검증이다. 이를 통과해야 status가 `[dd]`로 전이된다.
> - dev-build Step 0는 **설계의 실제 코드 적용**(라우터·메뉴에 라우트·링크 실제 등록) 검증이다.
> - 둘 다 UI 도메인의 reachability 보장을 위한 필수 관문이며, 하나라도 미충족하면 build는 `build.fail`로 보고한다.

design.md의 "진입점 (Entry Points)" 섹션과 "파일 계획" 표에 라우터·메뉴 파일이 명시되어 있으면, **테스트를 작성하기 전에** 다음을 먼저 적용한다:

1. 라우터 파일에 신규 라우트/페이지를 등록한다 (빈 페이지 컴포넌트라도 좋다 — 후속 구현으로 채워진다).
2. 메뉴/사이드바/네비게이션 파일에 사용자 진입 경로를 추가한다 (label, href, 권한·역할 조건 등 포함).
3. 이 단계가 끝난 뒤에야 E2E 테스트 코드(Step 2)에서 "메뉴 클릭 → 목표 페이지 도달" 시나리오를 작성할 수 있다.

Step 0를 생략하면 E2E 테스트가 클릭할 진입점이 없어 Red를 낼 수 없거나, URL 직접 진입으로 우회하여 reachability gate가 의미 없어진다.

**설계 누락 판정 기준** — 다음 중 하나라도 해당되면 "불완전"으로 간주한다:

1. design.md에 "진입점 (Entry Points)" 섹션이 존재하지 않음
2. 섹션이 존재하지만 "N/A" 또는 공란으로만 구성됨
3. 다음 4개 항목 중 하나라도 비어있음: 사용자 진입 경로, URL/라우트, 수정할 라우터 파일, 수정할 메뉴·네비게이션 파일
4. "파일 계획" 표에 라우터 파일(경로 키워드: `router`/`routes`/`App.tsx` 등) 또는 메뉴·네비게이션 파일(`sidebar`/`nav`/`menu` 등) 행이 누락됨

(동일 기준을 dev-design 2-1 게이트가 설계 시점에 적용한다. 본 Step 0의 검증은 **legacy design.md**(2-1 게이트 도입 이전 생성) 또는 **수동 편집으로 게이트를 우회한 design.md**에 대한 최종 안전망이다. 정상 워크플로우에서는 2-1 게이트에서 이미 차단된다.)

**설계 누락 시 조치** — 위 판정에서 하나라도 true면 **어떤 구현도 시작하지 말고** 다음 형식으로 결과 보고에 기록한다:

```
[FAIL] design.md의 진입점/파일 계획이 불완전합니다.
누락 항목: <위 판정 기준 1~4 중 해당하는 항목을 구체적으로 명시>
조치: /dev-design 재실행 또는 design.md 수동 보완 후 /dev-build 재실행 필요.
```

이 보고는 `build.fail` 이벤트로 기록되어 status가 `[dd]`에 머무른다 (상태 역전 없음). 사용자는 design.md를 보완한 뒤 `/dev-build`로 재진입하거나 `/dev-design`으로 재설계를 지시할 수 있다.

### [im] 완료 후 — Merge Preview 파일 기록

**`[im]` 단계 완료 직후 (상태 전이 전) 1회 실행한다.** 실패해도 Task 실패로 간주하지 않는다. **결과를 읽거나 해석하지 마시오** — 이 명령의 stdout/JSON을 LLM이 확인하거나 판단 근거로 사용하지 않는다.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/merge-preview.py --output {DOCS_DIR}/tasks/{TSK-ID}/merge-preview.json \
  --remote origin --target main || true
```

### Step 1 — 단위 테스트

1. design.md의 QA 체크리스트 기반으로 단위 테스트를 먼저 작성한다. QA 체크리스트가 base이며, 프로젝트 기존 테스트 관례·도메인 표준 패턴을 반영하여 필요한 edge case를 추가할 수 있다. QA에 없는 테스트를 추가한 경우 결과 보고의 "비고"에 목록과 추가 이유를 기록한다.
2. 테스트를 실제로 실행하여 실패를 확인 (Red)
   - 작성만 하고 실행하지 않은 테스트는 Red로 인정하지 않는다
   - 컴파일 실패 자체가 Red 신호인 경우는 인정한다
   - Red가 확인되기 전까지 프로덕션 코드를 작성하지 마라
3. 테스트를 통과하는 최소한의 코드 구현 (Green)
4. 테스트를 실행하여 전부 통과 확인
5. 커버리지 확인 (Dev Config에 정의된 경우만)
   Dev Config의 `quality_commands.coverage`가 있으면 실행한다. SOURCE에 따라 로드 명령이 다르다:
   - SOURCE=wbs: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md - --dev-config`
   - SOURCE=feat: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py --feat {FEAT_DIR} --dev-config {DOCS_DIR}`
   - 커버리지 명령을 실행하고 결과를 기록한다
   - design.md의 "파일 계획"에 나열된 파일이 커버되는지 확인한다
   - 미커버 파일이 있으면 추가 테스트를 작성한다
   - 커버리지 명령이 없으면 이 단계를 건너뛴다

## domain별 테스트
### 단위 테스트 — Red→Green 실행
`${CLAUDE_PLUGIN_ROOT}/references/test-commands.md`의 "단위 테스트" 섹션 참조. 참조 파일이 존재하지 않으면 `${CLAUDE_PLUGIN_ROOT}/references/default-dev-config.md`의 도메인 기본 명령으로 fallback한다.

### E2E 테스트 — 코드 작성만 (실행하지 않음)
`${CLAUDE_PLUGIN_ROOT}/references/test-commands.md`의 "E2E 테스트" 섹션을 참조하여 **`{DOMAIN}`이 `fullstack` 또는 `frontend`이고** Dev Config에 `e2e_test`가 정의되어 있으면 아래 단계를 진행한다.

`{DOMAIN}`이 그 외(`backend`/`default`/`docs`/`test` 등)인 경우 E2E 코드를 작성하지 않고 이 섹션을 건너뛴다 — 이 경우 `e2e_test` 값이 정의되어 있어도 무시한다 (dev-test 1-5의 effective_domain 게이트와 동일 기준).

> 상위 "TDD 순서 > Step 0 (라우터/메뉴 선행 수정)"이 완료된 상태에서만 아래 E2E 코드 작성을 시작한다. 진입 수단(메뉴·라우터)이 없는 페이지에 대해 E2E를 작성하면 reachability gate(메뉴 클릭 경로 강제)를 만족할 수 없다.

#### E2E Step 1: Convention Discovery (필수 — 코드 작성 전 반드시 수행)

E2E 테스트 코드를 작성하기 **전에** 프로젝트의 기존 E2E 설정과 패턴을 파악한다. 이 단계를 건너뛰면 잘못된 위치·URL·패턴으로 테스트를 작성하게 된다.

1. **E2E config 파일 찾기**: Glob 도구로 `**/playwright.config.*` 또는 `**/cypress.config.*`를 검색한다. 찾으면 Read로 읽고 다음을 추출:
   - `testDir` → E2E 테스트 파일 위치
   - `baseURL` 또는 `webServer.url` → 테스트 대상 URL/포트
   - `use.baseURL` → Playwright의 경우 여기에 정의될 수 있음
   - 환경변수 참조 (`process.env.XXX`) → 실제 사용되는 env var 이름

2. **기존 E2E 테스트 파일 확인**: `testDir` 경로 하위에서 Glob으로 `**/*.spec.{ts,js}` 또는 `**/*.test.{ts,js}`를 검색한다. 1-2개 파일을 Read로 읽고 다음 패턴을 파악:
   - URL 접근 방식 (`page.goto()` 인자가 상대경로인지, 환경변수인지, 하드코딩인지)
   - 셀렉터 컨벤션 (`data-testid`, role, CSS selector 등)
   - fixture / helper 사용 패턴
   - 파일 명명 규칙

3. **config 파일을 못 찾은 경우**: Dev Config의 `e2e_test` 명령에서 config 경로 힌트를 추출한다 (예: `--config e2e/playwright.config.ts`). 그래도 없으면 프로젝트 루트에서 `package.json`의 `scripts` 섹션을 읽어 E2E 관련 스크립트를 확인한다.

#### E2E Step 2: 테스트 코드 작성

Discovery에서 파악한 정보를 **반드시** 반영하여 작성한다:
- **파일 위치**: discovery에서 확인한 `testDir` 하위에 생성 (추측하지 않는다)
- **URL 패턴**: discovery에서 확인한 baseURL/환경변수 패턴을 그대로 사용
- **코드 패턴**: 기존 테스트 파일의 셀렉터·fixture·helper 패턴을 따른다
- **Reachability (fullstack/frontend 필수)**: 목표 페이지로의 진입은 메뉴/버튼/링크 **클릭 경로**로 작성한다. `page.goto('/target-path')` 류의 URL 직접 진입은 초기 진입점(로그인 화면 등) 또는 인증 쿠키 주입 같은 시나리오 요구에만 허용한다 (상세 규칙은 `references/test-commands.md` "Reachability 강제").
- design.md의 QA 체크리스트 중 통합 케이스를 E2E 테스트 코드로 작성한다
- E2E 테스트를 이 단계에서 실행하지 않는다 — 실행과 검증은 dev-test가 수행한다

e2e_test가 null이면 이 단계를 건너뛴다.

## 규칙
- 기존 코드의 패턴과 컨벤션을 따른다
- 불필요한 파일을 생성하지 않는다
- 모든 단위 테스트 통과가 목표이다. 가드레일에 의해 미해결 테스트가 있으면 결과를 FAIL로 보고한다
- E2E는 실행하지 않으므로 통과 기준에 포함하지 않는다

## 가드레일
- **같은 테스트 케이스**(테스트 함수/`it`/`test` 블록 이름이 동일)가 **3회 연속** 수정-재실행되었는데 실패 원인의 **root cause가 동일**(에러 메시지의 핵심 키워드 또는 스택 트레이스 최상단 원인이 변하지 않음)하면, 해당 테스트 수정을 중단하고 나머지 구현을 계속한다. 다른 테스트의 수정 시도는 이 카운터를 초기화하지 않는다 (동일 케이스 기준). test.skip 등 코드 변경 금지.
- 이전에 통과하던 테스트가 수정 후 실패하면 (regression) 되돌리고 다른 접근을 1회 시도한다. 재발하면 되돌리고 원인 보고
- design.md에 없는 파일이 필요하면 생성 이유를 결과 보고에 기록하고 계속 진행한다

## 결과 보고
양식은 ${CLAUDE_PLUGIN_ROOT}/skills/dev-build/template.md를 참고한다.
```
