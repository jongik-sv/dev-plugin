# dev-design 스킬 감사 보고서 — 2026-04-14

**감사 대상:** `/Users/jji/project/dev-plugin/skills/dev-design/SKILL.md` + 하위 참조 + 다운스트림 소비자
**감사 방법:** `docs/skill-audit-prompt.md` (범용 감사 프롬프트) 기반, Explore 서브에이전트 전수 조사
**결과:** 6 findings (high 2, medium 3, low 1)

---

## 0. 감사 범위

### 1차 (주 파일)
- `skills/dev-design/SKILL.md`
- `skills/dev-design/template.md`
- `skills/dev-design/references/design-prompt-template.md`

### 2차 (정합성 검증)
- 다운스트림: `skills/dev-build/SKILL.md`, `skills/dev-build/references/tdd-prompt-template.md`, `skills/dev-test/SKILL.md`, `skills/dev-refactor/SKILL.md`, `scripts/wbs-transition.py`, `scripts/wbs-parse.py`
- 상위 규약: `skills/wbs/SKILL.md`, `skills/dev/SKILL.md`, `skills/feat/SKILL.md`, `references/state-machine.json`, `references/default-dev-config.md`, `references/test-commands.md`, `CLAUDE.md`

### Cross-skill properties (체인 전반 횡단 속성)
- reachability (진입점 배선 강제) — design → build → test
- 파일 계획 일관성
- SOURCE 추상화 (wbs ↔ feat)
- 모델 선택 체인 (CLI > wbs.md model: > 자동 스코어링)
- 상태 전이 ([dd]→[im])

---

## 1. 요약 테이블

| ID | 차원 | Severity | 제목 | 단일 파일 수정? |
|----|------|----------|------|----------------|
| F01 | 애매모호 | **HIGH** | Haiku 금지 규칙의 "대체" 주체 불명확 | ✅ SKILL.md |
| F02 | 다운스트림 드리프트 | **HIGH** | Entry Points 검증이 design.ok 이후에야 발견되어 되돌릴 수 없음 | ✅ SKILL.md |
| F03 | 논리적 모순 | MEDIUM | `design-prompt-template.md`의 `{SOURCE}` 변수 무효 선언 | ✅ design-prompt-template.md |
| F04 | 다운스트림 드리프트 | MEDIUM | "파일 계획" 경로 기준 미정의 (모노레포 혼동) | ✅ design-prompt-template.md + template.md |
| F05 | **체인 캐스케이드** | MEDIUM | Reachability가 3개 스킬에 분산되지만 단계별 강제 메커니즘 부재 | ❌ 3곳 동시 |
| F06 | 검증 불가능 | LOW | "구체적 경로"의 구체성 기준 미정의 | ✅ template.md |

---

## 2. Findings 상세 및 수정안

### F01. Haiku 모델 금지 규칙의 "대체" 주체 불명확 [HIGH]

**위치:** `skills/dev-design/SKILL.md:31`

**문제:**
> "설계는 판단이 필요하므로 **Haiku 금지** (호출자가 `haiku`를 지정해도 Sonnet으로 대체)"

"대체"의 구현 주체가 정의되지 않음 — 호출자(`/dev`, `/feat`)가 차단하는지, dev-design 서브에이전트 내부에서 재설정하는지 불명확. Agent 도구의 `model` 파라미터에 haiku가 전달되면 누가 가로채는가?

**임팩트:**
- Haiku 요청이 서브에이전트까지 전달되면 저품질 설계 생산
- 다운스트림 dev-build가 불완전한 설계를 기반으로 구현

**수정안:**

`skills/dev-design/SKILL.md`의 "모델 선택" 섹션(line 29-33)을 다음으로 교체:

```markdown
## 모델 선택

- 기본값: Sonnet (범용 설계)
- `--model` CLI 또는 `wbs.md - model:` 필드로 Opus 강제 가능
- **Haiku 금지** — 설계는 판단이 필요함
  - **구현:** 호출자가 Agent 도구 호출 시 `model` 파라미터를 결정한다. 호출자가 `haiku`를 전달하거나 자동 스코어링이 `haiku`를 반환하면, **호출 직전에 `sonnet`으로 강제 변환**한다. 이 규칙은 `/dev`, `/feat`, `/dev-team`의 WP 리더에서 일관되게 적용한다.
```

또한 `/dev`, `/feat`, `/dev-team`의 해당 호출 지점에서 "Haiku 감지 시 Sonnet으로 강제"를 명시해야 한다. (이들 스킬 내 모델 결정 섹션은 이미 "Haiku 금지"를 알고 있지만, 강제 변환 코드가 있는지 확인 필요)

---

### F02. Entry Points 검증의 타이밍 역전 [HIGH]

**위치:**
- `skills/dev-design/template.md:21-31` (진입점 필수 포함 규칙)
- `skills/dev-build/references/tdd-prompt-template.md:14-22` (Step 0 검증)

**문제:**

template.md는 "UI가 있는 Task는 라우터·메뉴 파일을 반드시 포함해야 한다"고 선언하지만, 검증은 dev-build Step 0에서 수행된다. 이 시점에 이미:
- `design.ok` 이벤트 발생 → 상태 `[dd]`로 전이 완료
- `state.json`의 `status.phase_start = "build"`로 기록

dev-build가 Step 0에서 누락을 발견하면 "설계 재요청"을 보고(tdd-prompt-template.md:22)하지만, **상태를 [dd]로 되돌릴 메커니즘이 없다**. 사용자는 `/dev` 재실행 시 phase_start="build"로 재진입하여 동일한 오류 반복.

**임팩트:**
- 진입점 누락 설계는 build 단계에서만 발견되는데, 되돌리기 경로가 없어 사용자 혼동
- dev-test reachability gate도 이미 결함 있는 설계 기반이므로 의미 없음

**수정안:**

`skills/dev-design/SKILL.md`의 "실행 절차" 섹션에 **Step 2-1. design.md 형식 검증**을 추가:

```markdown
### 2-1. design.md 형식 검증 (design.ok 이벤트 전)

서브에이전트가 design.md를 생성하면, design.ok 이벤트를 발생시키기 **전에** 다음을 검증한다:

**공통 검증:**
- [ ] "파일 계획" 표에 최소 1행 존재
- [ ] "QA 체크리스트" 섹션 존재 (비어있지 않음)

**UI Task 추가 검증 (domain=fullstack 또는 frontend):**
- [ ] "진입점 (Entry Points)" 섹션이 "N/A"가 아님
- [ ] "진입점" 섹션에 사용자 경로 + URL/라우트 + 라우터 파일 + 메뉴 파일이 모두 명시됨
- [ ] "파일 계획" 표에 라우터 파일(경로에 `router`/`routes`/`App.tsx` 등 포함)이 최소 1개 존재
- [ ] "파일 계획" 표에 메뉴·네비게이션 파일(경로에 `sidebar`/`nav`/`menu` 등 포함)이 최소 1개 존재

검증 실패 시:
- design.md를 수정하도록 서브에이전트에 재지시 (같은 세션 내)
- 재지시 2회 실패 시 오류 보고 및 design.ok 이벤트 발생 보류
- 이 단계를 통과하지 못하면 상태 전이 금지
```

---

### F03. design-prompt-template.md의 `{SOURCE}` 변수 무효 선언 [MEDIUM]

**위치:** `skills/dev-design/references/design-prompt-template.md:1-5, 12-13`

**문제:**

헤더는 `{SOURCE}`를 치환 변수로 선언하지만 본문에는 "(WBS 모드 한정)" 주석만 존재하고 실제 조건부 분기 로직이 없음. 서브에이전트가 프롬프트를 수신했을 때 feat 모드인지 wbs 모드인지 런타임 판단 불가.

**임팩트:**
- feat 모드에서 `{DOCS_DIR}/PRD.md`, `{DOCS_DIR}/TRD.md` 참조 지시가 그대로 전달되면, 해당 파일이 존재하지 않아 서브에이전트가 혼동하거나 불필요한 오류 리포트 생성

**수정안:**

`skills/dev-design/references/design-prompt-template.md`에서 `{SOURCE}` 사용 방식을 명시적으로:

**옵션 A (호출자 치환):** 호출자가 {SOURCE} 값에 따라 해당 블록만 치환하여 전달.

```markdown
헤더에 추가:
**치환 규칙:** 호출자는 아래 `<!-- WBS-ONLY -->` 블록을 SOURCE=wbs일 때만 유지하고, SOURCE=feat이면 통째로 제거하여 전달한다.

본문 line 12 부근:
<!-- WBS-ONLY -->
참고 문서: {DOCS_DIR}/PRD.md, {DOCS_DIR}/TRD.md
<!-- /WBS-ONLY -->
```

**옵션 B (런타임 조건):** 프롬프트가 `{SOURCE}`를 직접 참조.

```markdown
참고 문서: (SOURCE={SOURCE}이므로)
- SOURCE=wbs인 경우: {DOCS_DIR}/PRD.md, {DOCS_DIR}/TRD.md 를 참조
- SOURCE=feat인 경우: spec.md 이외 추가 문서 참조하지 않음
```

권장: **옵션 A** (호출자가 치환하여 서브에이전트 혼동 방지, 토큰 절감)

---

### F04. "파일 계획" 경로 기준 미정의 [MEDIUM]

**위치:**
- `skills/dev-design/template.md:13-19`
- `skills/dev-build/references/tdd-prompt-template.md:25-39`

**문제:**

design.md의 "파일 계획" 표는 파일 경로를 나열하지만, 경로가 **프로젝트 루트 기준**인지 **타겟 앱 기준 상대경로**인지 명시되지 않음. 모노레포에서 타겟 앱이 `apps/admin-web`일 때, `src/pages/profile.tsx`(앱 기준)와 `apps/admin-web/src/pages/profile.tsx`(루트 기준)가 혼용될 수 있음.

**임팩트:**
- dev-build 서브에이전트가 잘못된 위치에 파일 생성
- 특히 WBS Task의 "타겟 앱" 필드와 "파일 계획" 경로가 동일 기준인지 보장되지 않음

**수정안:**

`skills/dev-design/template.md`의 "파일 계획" 표 위에 경로 기준 명시:

```markdown
## 파일 계획

**경로 기준:** 모든 경로는 **프로젝트 루트 기준 절대 경로**로 작성한다. 예: `apps/admin-web/src/pages/profile.tsx` (O), `src/pages/profile.tsx` (X). 모노레포에서 타겟 앱이 `apps/X`이면 경로 접두어 `apps/X/`를 반드시 포함한다.

| 파일 경로 | 역할 | 신규/수정 |
|----------|------|----------|
| apps/admin-web/src/pages/profile.tsx | 프로필 페이지 컴포넌트 | 신규 |
| apps/admin-web/src/routes.ts | 라우트 등록 | 수정 |
```

`skills/dev-design/references/design-prompt-template.md`에도 동일 규칙을 Step 0 말미에 추가.

---

### F05. Reachability 체인 캐스케이드 누락 [MEDIUM, 차원 16]

**위치 (3곳):**
- `skills/dev-design/template.md:19, 26-32` (진입점 요구)
- `skills/dev-build/references/tdd-prompt-template.md:16-22` (Step 0 Reachability)
- `skills/dev-test/SKILL.md:68-91` + `skills/dev-test/template.md:62` (E2E 클릭 경로)

**문제:**

Reachability 속성은 design/build/test 세 스킬에 각각 선언되지만, 단계 간 강제 메커니즘이 분리되어 있음:

- **design:** "라우터·메뉴 파일 포함"만 요구. 진입점 섹션 구체성 기준 없음 (F06과 연계).
- **build:** Step 0에서 라우터/메뉴 등록 지시하지만, design에 정보 부족 시 "재요청 보고"만 수행 — 이미 phase=build 상태 (F02와 연계).
- **test:** UI 키워드 기반 E2E 게이트는 dev-test에서만 적용되며, design.md의 QA 체크리스트가 "클릭 경로 검증" 항목을 포함하도록 **요구하지 않음**.

하나라도 빠지면 체인이 무너짐. 단일 파일 수정 불가.

**임팩트:**
- design에서 진입점 명시 누락 → build가 라우터 수정 안 함 → test의 클릭 경로 게이트 실패 → 이 때 이미 되돌릴 수 없는 상태
- 반대로 design은 완벽하지만 build가 누락 → test에서야 발견

**수정안 (3곳 동시 삽입):**

**1) `skills/dev-design/references/design-prompt-template.md`** — Step 0 말미에 진입점 필수 체크 추가:

```markdown
**진입점 필수 체크 (domain=fullstack 또는 frontend):**
설계 완료 전에 다음을 확인한다:
- [ ] "진입점" 섹션이 "N/A"가 아님
- [ ] 사용자 경로(메뉴/버튼 클릭 시퀀스)가 URL과 함께 명시됨
- [ ] "파일 계획" 표에 라우터 파일이 구체적 경로로 포함됨
- [ ] "파일 계획" 표에 메뉴/네비게이션 파일이 구체적 경로로 포함됨

하나라도 누락 시 설계를 수정한 뒤 제출한다.
```

**2) `skills/dev-build/references/tdd-prompt-template.md`** — Step 0의 "설계 재요청" 분기를 명확화 (line 22 근처):

```markdown
design.md에 진입점/라우터/메뉴 정보가 부족하면, 구현을 진행하지 않고 다음을 보고한다:

```
[FAIL] design.md의 진입점/파일 계획이 불완전합니다.
누락 항목: <구체적으로 명시>
조치: /dev-design 재실행 또는 설계 수정 후 재진행 필요.
```

이 보고는 `build.fail` 이벤트로 기록되며, 사용자가 design.md를 보완한 뒤 `/dev-build` 재실행 또는 `/dev-design`으로 되돌릴 수 있다.
```

**3) `skills/dev-design/template.md` 또는 `skills/dev-test/references/`** — QA 체크리스트 기본 구조에 UI 필수 항목 추가:

```markdown
## QA 체크리스트

...(기존 항목)...

**fullstack/frontend Task 필수 (E2E 테스트에서 검증):**
- [ ] (클릭 경로) 메뉴/사이드바/버튼을 클릭하여 목표 페이지 도달 (URL 직접 입력 금지)
- [ ] (화면 렌더링) 핵심 UI 요소가 브라우저에서 실제 표시됨
```

이 QA 체크리스트 항목이 design.md에 들어가면, dev-test가 E2E 시나리오 작성 시 참조할 수 있음.

---

### F06. "구체적 경로"의 구체성 기준 미정의 [LOW]

**위치:** `skills/dev-design/template.md:29-30`

**문제:**

template.md는 진입점 섹션 예시로 "수정할 라우터 파일: (예: `apps/web/src/app/settings/profile/page.tsx`)"를 제시하지만, "얼마나 구체적이어야 하는가"의 기준이 없음.

**임팩트:**
- 서브에이전트가 항목별로 상세도 다르게 기입 → dev-build Step 0 수행 품질 불균등

**수정안:**

`skills/dev-design/template.md`의 "진입점" 섹션에 구체성 기준 명시:

```markdown
## 진입점 (Entry Points)

**작성 기준:** 각 항목을 구체적 식별자까지 기입한다.

- 사용자 진입 경로: 클릭할 메뉴/버튼명을 순서대로 (예: "로그인 → 좌측 사이드바 '설정' 클릭 → '프로필' 탭 클릭")
- URL/라우트: 정확한 경로 (예: `/settings/profile`)
- 수정할 라우터 파일: 파일 경로 + 수정 위치 (예: `apps/web/src/routes.ts`의 `routes` 배열에 `/settings/profile` 추가)
- 수정할 메뉴·네비게이션 파일: 파일 경로 + 수정할 변수/컴포넌트명 (예: `apps/web/src/components/Sidebar.tsx`의 `navItems` 배열)
- 연결 확인 방법: E2E에서 검증할 클릭 시퀀스 (예: "사이드바 → '설정' 클릭 → '프로필' 탭 클릭 → URL이 `/settings/profile`로 변경됨")
```

---

## 3. 기각된 의심 (dropped_candidates)

| 의심 | 기각 이유 |
|------|----------|
| dev-design이 feat 모드에서 spec.md를 읽지 않을 가능성 | SKILL.md 1단계(B)에서 "spec.md를 Read 도구로 읽어 추출"로 명시됨. 추측 오류. |
| 모델 선택 시 Opus 기준(3점 이상)이 /dev와 /feat 간 불일치 | 모두 `wbs-parse.py --complexity`에 위임. 상위 레이어에서 동일 처리. |
| `template.md`와 `design-prompt-template.md`의 지시 불일치 | 목적이 다름: template은 결과물 형식, prompt는 생성 절차. 자연스러운 차이. |
| wbs.md의 `model` 필드와 `--complexity` 점수 간 우선순위 모호 | CLAUDE.md + /dev SKILL.md에 명확히 "`--model` > `- model:` > 자동" 체인 명시. |

---

## 4. 적용 순서 제안

1. **F01 (HIGH)** — SKILL.md 모델 선택 섹션 수정 + `/dev`, `/feat`, `/dev-team` 호출 지점 확인 (단일 파일 + 호출자 검증).
2. **F02 (HIGH)** — SKILL.md에 Step 2-1 형식 검증 추가. 상태 전이 역전 문제 해결.
3. **F05 (MEDIUM, 체인 캐스케이드)** — 3곳 동시 패치. F02 수정과 일부 중복되므로 **F02 다음에 연계 처리** 권장.
4. **F03 (MEDIUM)** — design-prompt-template.md에 SOURCE 치환 규칙 명시 (옵션 A).
5. **F04 (MEDIUM)** — template.md + design-prompt-template.md에 경로 기준 추가.
6. **F06 (LOW)** — template.md 진입점 섹션에 구체성 기준 명시.

**모든 수정 후 필수:**
- 플러그인 캐시 동기화: `~/.claude/plugins/marketplaces/dev-tools/`
- feat 모드 스모크 테스트 (F03 검증)
- fullstack Task로 dev-design → dev-build 흐름 검증 (F02, F05 검증)

---

## 5. 수정하지 않을 항목 (범위 외)

- 새 기능 추가 (예: design.md 자동 검증 CLI 도구 신설)
- 템플릿 전면 재설계
- 모델 선택 로직 변경 (Opus/Sonnet 분기 기준은 이미 명확)

이 보고서는 **기존 규칙의 불합리/중복/애매 개선**에만 집중한다.
