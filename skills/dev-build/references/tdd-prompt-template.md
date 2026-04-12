# TDD Build 프롬프트 템플릿

`skills/dev-build/SKILL.md` 2단계에서 서브에이전트에 전달하는 프롬프트 본문. 치환 변수: `{REQUIREMENT_SOURCE}`, `{DESIGN_CONTENT}`, `{SOURCE}`, `{DOCS_DIR}`, `{FEAT_DIR}`.

```
다음 요구사항을 TDD 방식으로 구현하라.

{REQUIREMENT_SOURCE}

{DESIGN_CONTENT}

## TDD 순서 (반드시 준수)
1. design.md의 QA 체크리스트 기반으로 단위 테스트를 먼저 작성
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
`${CLAUDE_PLUGIN_ROOT}/references/test-commands.md`의 "단위 테스트" 섹션 참조.

### E2E 테스트 — 코드 작성만 (실행하지 않음)
`${CLAUDE_PLUGIN_ROOT}/references/test-commands.md`의 "E2E 테스트" 섹션을 참조하여 domain에 e2e_test가 정의되어 있으면:

#### Step 1: E2E Convention Discovery (필수 — 코드 작성 전 반드시 수행)

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

#### Step 2: E2E 테스트 코드 작성

Discovery에서 파악한 정보를 **반드시** 반영하여 작성한다:
- **파일 위치**: discovery에서 확인한 `testDir` 하위에 생성 (추측하지 않는다)
- **URL 패턴**: discovery에서 확인한 baseURL/환경변수 패턴을 그대로 사용
- **코드 패턴**: 기존 테스트 파일의 셀렉터·fixture·helper 패턴을 따른다
- design.md의 QA 체크리스트 중 통합 케이스를 E2E 테스트 코드로 작성한다
- E2E 테스트를 이 단계에서 실행하지 않는다 — 실행과 검증은 dev-test가 수행한다

e2e_test가 null이면 이 단계를 건너뛴다.

## 규칙
- 기존 코드의 패턴과 컨벤션을 따른다
- 불필요한 파일을 생성하지 않는다
- 모든 단위 테스트 통과가 목표이다. 가드레일에 의해 미해결 테스트가 있으면 결과를 FAIL로 보고한다
- E2E는 실행하지 않으므로 통과 기준에 포함하지 않는다

## 가드레일
- 같은 테스트가 3회 연속 같은 이유로 실패하면 해당 테스트 수정을 중단하고 나머지 구현을 계속한다 (test.skip 등 코드 변경 금지)
- 이전에 통과하던 테스트가 수정 후 실패하면 (regression) 되돌리고 다른 접근을 1회 시도한다. 재발하면 되돌리고 원인 보고
- design.md에 없는 파일이 필요하면 생성 이유를 결과 보고에 기록하고 계속 진행한다

## 결과 보고
양식은 ${CLAUDE_PLUGIN_ROOT}/skills/dev-build/template.md를 참고한다.
```
