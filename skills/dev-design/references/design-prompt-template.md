# Design 프롬프트 템플릿

`skills/dev-design/SKILL.md` 2단계에서 서브에이전트에 전달하는 프롬프트 본문. 치환 변수: `{REQUIREMENT_SOURCE}`, `{DOCS_DIR}`, `{SOURCE}`, `{FEAT_DIR}`, `{ARTIFACT_DIR}`.

**치환 규칙 — SOURCE 분기 블록 (호출자가 치환):**

아래 본문에 있는 `<!-- WBS-ONLY ... /WBS-ONLY -->` 블록과 `<!-- FEAT-ONLY ... /FEAT-ONLY -->` 블록은 호출자가 `{SOURCE}` 값에 따라 **둘 중 하나만 유지하고 다른 하나는 블록째 제거**한 뒤 서브에이전트에 전달한다. 마커 줄도 함께 제거한다. 서브에이전트는 `{SOURCE}` 토큰을 받지 않아야 하며, 자신이 어느 모드인지 추론할 필요가 없다.

- `SOURCE=wbs` → `<!-- WBS-ONLY -->` 블록 본문만 유지, `<!-- FEAT-ONLY -->` 블록은 통째 제거
- `SOURCE=feat` → `<!-- FEAT-ONLY -->` 블록 본문만 유지, `<!-- WBS-ONLY -->` 블록은 통째 제거

```
다음 요구사항을 설계하라. 코드를 작성하지 말고 설계만 한다.

{REQUIREMENT_SOURCE}

<!-- WBS-ONLY -->
참고 문서: {DOCS_DIR}/PRD.md, {DOCS_DIR}/TRD.md
<!-- /WBS-ONLY -->
<!-- FEAT-ONLY -->
참고 문서: spec.md 외 추가 참조 없음. 필요 시 프로젝트 내 기존 코드만 참고한다.
<!-- /FEAT-ONLY -->

## Step 0: 프로젝트 구조 파악 (모노레포 타겟 디렉토리 Discovery)

파일 계획을 작성하기 **전에** 프로젝트의 앱/패키지 구조를 파악하여 코드를 작성할 타겟 디렉토리를 특정한다. 이 단계를 건너뛰면 모노레포에서 잘못된 앱에 코드를 작성하게 된다.

1. **프로젝트 루트 구조 확인**: Glob 도구로 루트 `package.json` (또는 `pnpm-workspace.yaml`, `lerna.json`, `Cargo.toml` 등)을 읽고 workspaces/packages 목록을 추출
2. **앱 디렉토리 스캔**: `apps/` 또는 `packages/` 하위 디렉토리를 ls로 확인. 각 앱의 `package.json` name 필드를 읽어 역할 파악
3. **타겟 앱 특정**: 요구사항 키워드(admin, dashboard, web, api, mobile 등)와 앱 이름/설명을 매칭하여 타겟 앱을 결정
4. **단일 앱 프로젝트**: workspaces가 없거나 앱이 1개면 이 단계를 자동 스킵

파악한 타겟 앱을 산출물의 "타겟 앱" 필드에 명시한다.

**경로 기준 (전 산출물 공통):** 파일 경로를 기록할 때는 **프로젝트 루트 기준**으로만 작성한다. 타겟 앱이 `apps/X`이면 모든 경로에 `apps/X/` 접두어를 포함한다. 예: `apps/admin-web/src/pages/profile.tsx` (O), `src/pages/profile.tsx` (X). 단일 앱이어도 루트 기준으로 작성한다.

**진입점 필수 체크 (`domain=fullstack` 또는 `domain=frontend`):**
설계 완료 전에 다음을 확인한다. 하나라도 누락되면 design.md를 수정한 뒤 제출한다. 호출자(dev-design 스킬)는 design.ok 발행 전에 이 항목들을 다시 검증하므로, 누락 시 재작성이 강제된다.
- [ ] "진입점" 섹션이 "N/A"가 아님 (UI Task인 이상 반드시 실제 내용)
- [ ] 사용자 진입 경로가 메뉴/버튼 클릭 시퀀스 형태로 명시됨 (단순 URL만 제시 금지)
- [ ] URL/라우트가 정확히 기재됨
- [ ] "파일 계획" 표에 **라우터 파일**이 루트 기준 구체 경로로 포함됨
- [ ] "파일 계획" 표에 **메뉴/네비게이션 파일**이 루트 기준 구체 경로로 포함됨

산출물:
1. 요구사항 확인 — 원천 문서에서 도출한 핵심 요구사항 (2~3줄). 해석이 맞는지 사후 검증용
2. 타겟 앱 — 모노레포 내 코드를 작성할 앱 경로 (예: `apps/admin-web`). 단일 앱이면 "N/A (단일 앱)"
3. 생성/수정할 파일 목록과 각 파일의 역할 — 파일 경로는 반드시 **프로젝트 루트 기준**으로 작성 (타겟 앱 접두어 포함)
4. 주요 함수/클래스/컴포넌트 이름과 책임
5. 데이터 흐름 요약 (입력 → 처리 → 출력)
6. 설계 결정 — 구현 방식에 대안이 있는 경우만 기록. 결정/대안/근거를 각 1줄씩. 대안이 없으면 생략
7. 의존성 및 선행 조건
8. 리스크 — 구현 시 주의할 위험 요소를 HIGH/MEDIUM/LOW로 분류. dev-build가 사전에 인지하고 회피하도록
9. QA 체크리스트 — dev-test에서 검증할 항목 (정상/엣지/에러/통합 케이스). 각 항목은 pass/fail로 판정 가능한 구체적 문장으로 작성

domain별 설계 가이드:
프로젝트의 설계 가이드를 먼저 로드한다. SOURCE에 따라 명령이 다르다.

**SOURCE=wbs**:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md - --dev-config
```

**SOURCE=feat** (fallback chain: feat-local → wbs.md → default):
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py --feat {FEAT_DIR} --dev-config {DOCS_DIR}
```

JSON 출력의 `design_guidance[{domain}]`에 해당 domain의 아키텍처 가이드가 있으면 그에 따라 설계한다. 없으면 `design_guidance[default]`로 fallback하고, 그것도 없으면 프로젝트의 기존 코드 패턴을 분석하여 적절한 구조를 판단한다. feat 모드는 `source` 필드(`feat-local`/`wbs`/`default`)로 어느 설정이 적용되었는지 알 수 있다.

결과를 {ARTIFACT_DIR}/design.md 파일로 작성하라.
양식은 ${CLAUDE_PLUGIN_ROOT}/skills/dev-design/template.md를 따른다.
```
