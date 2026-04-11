# Design 프롬프트 템플릿

`skills/dev-design/SKILL.md` 2단계에서 서브에이전트에 전달하는 프롬프트 본문. 치환 변수: `{REQUIREMENT_SOURCE}`, `{DOCS_DIR}`, `{SOURCE}`, `{FEAT_DIR}`, `{ARTIFACT_DIR}`.

WBS 모드는 `{DOCS_DIR}/PRD.md`, `{DOCS_DIR}/TRD.md` 참조 구절을 유지하고 Feature 모드는 이 구절을 "spec.md 외 추가 참조 없음"으로 치환한다.

```
다음 요구사항을 설계하라. 코드를 작성하지 말고 설계만 한다.

{REQUIREMENT_SOURCE}

참고 문서 (WBS 모드 한정): {DOCS_DIR}/PRD.md, {DOCS_DIR}/TRD.md

산출물:
1. 요구사항 확인 — 원천 문서에서 도출한 핵심 요구사항 (2~3줄). 해석이 맞는지 사후 검증용
2. 생성/수정할 파일 목록과 각 파일의 역할
3. 주요 함수/클래스/컴포넌트 이름과 책임
4. 데이터 흐름 요약 (입력 → 처리 → 출력)
5. 설계 결정 — 구현 방식에 대안이 있는 경우만 기록. 결정/대안/근거를 각 1줄씩. 대안이 없으면 생략
6. 의존성 및 선행 조건
7. 리스크 — 구현 시 주의할 위험 요소를 HIGH/MEDIUM/LOW로 분류. dev-build가 사전에 인지하고 회피하도록
8. QA 체크리스트 — dev-test에서 검증할 항목 (정상/엣지/에러/통합 케이스). 각 항목은 pass/fail로 판정 가능한 구체적 문장으로 작성

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
