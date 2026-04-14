# dev-build 스킬 감사 보고서

- **대상:** `/Users/jji/project/dev-plugin/skills/dev-build/SKILL.md`
- **감사 일자:** 2026-04-14
- **감사 프롬프트:** `docs/skill-audit-prompt.md`
- **수행 에이전트:** Explore (very thorough)
- **커버 차원:** 1~16 전체

## 개요

| Severity | Count |
|----------|-------|
| high     | 6     |
| medium   | 6     |
| low      | 3     |
| **total** | **15** |

## CROSS_SKILL_PROPERTIES 점검 대상

1. reachability — design Entry Points → build Step 0 → test reachability gate 연쇄
2. 테스트 우선(TDD Red-Green) — design Test Strategy → build 실테스트 작성 → test-report
3. 상태 전이 — build 성공/실패/중단 경로와 `wbs-transition.py` 이벤트 매핑
4. 모델 선택 — `Build always Sonnet` 원칙 준수·노출 여부
5. bypass 메커니즘 — 반복 실패 시 dev-team이 호출하는 bypass 인지
6. Dev Config 계약 — build 테스트 명령과 wbs/feat 계약 체인 정합

---

## 전체 감사 결과 (JSON)

```json
{
  "audit_metadata": {
    "target_skill": "/Users/jji/project/dev-plugin/skills/dev-build/SKILL.md",
    "date": "2026-04-14",
    "dimensions_covered": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
    "total_findings": 15,
    "by_severity": {
      "high": 6,
      "medium": 6,
      "low": 3
    }
  },
  "findings": [
    {
      "id": "F01",
      "dimension": 1,
      "severity": "high",
      "title": "Model selection 규칙 충돌: CLAUDE.md vs SKILL.md의 Sonnet/Opus 정의 불일치",
      "location": "skills/dev-build/SKILL.md:27-32",
      "evidence": "SKILL.md: 기본 모델은 Sonnet, 호출자가 지정하면 그대로 사용 (Haiku 대체 없음)\nCLAUDE.md:75: Build/Refactor always Sonnet, Test always Haiku (with Sonnet escalation)",
      "problem": "SKILL.md의 '호출자 지정값 우선' 규칙이 CLAUDE.md의 'Build always Sonnet' 원칙과 충돌. LLM이 두 가지를 해석할 수 있음: (A) 호출자가 Haiku 지정 시 그대로 사용 → CLAUDE.md 위반, (B) Sonnet으로 강제 변환 → SKILL.md 명시사항 위반. 특히 /dev 호출자가 design phase에만 Haiku 강제 변환하고(dev/SKILL.md:70) build는 그대로 전달할 수 있다.",
      "impact": "불명확한 모델 정책으로 인해 dev-build가 의도하지 않은 모델에서 실행되거나, 호출자와 dev-build 간 모델 약속 위반으로 비결정적 결과 발생 가능.",
      "fix_proposal": "SKILL.md 29-31줄을 다음으로 수정: '호출자가 명시하면 해당 모델을 사용하되, CLAUDE.md의 \"Build always Sonnet\" 원칙(Haiku 금지) 확인하여 호출자가 Haiku 지정 시는 Sonnet으로 자동 변환한다'. 또는 호출자 책임으로 명확히: '호출자가 반드시 Sonnet 이상을 지정하도록 강제하며, dev-build는 전달받은 값을 신뢰한다'.",
      "requires_sync_to_cache": true,
      "related_existing_findings": ["F04"]
    },
    {
      "id": "F02",
      "dimension": 3,
      "severity": "high",
      "title": "E2E 작성 요구사항 애매모호: 'domain에 e2e_test가 정의되어 있으면' 조건 불명확",
      "location": "skills/dev-build/references/tdd-prompt-template.md:57-89",
      "evidence": "57줄: 'domain에 e2e_test가 정의되어 있으면'\n85줄: Reachability 규칙은 'fullstack/frontend 필수'",
      "problem": "domain이 backend인데 e2e_test가 정의되어 있으면? LLM이 두 가지로 해석: (A) domain 무시하고 e2e_test 명령만 보고 코드 작성 (Step 2 진행), (B) domain=backend이므로 건너뜀 (e2e_test는 정의만 무시). Step 0의 'fullstack/frontend Task 한정' 지시와 57줄의 'e2e_test가 정의되어 있으면' 사이에 우선순위가 없음. dev-test의 1-5 게이트(frontend/fullstack 강제)와도 일관성 검증 필요.",
      "impact": "reachability gate 우회 또는 불필요한 E2E 작성 → dev-test에서 실패하거나 QA 체크리스트 불일치.",
      "fix_proposal": "57줄 수정: '`domain`이 `fullstack` 또는 `frontend`이고 `e2e_test`가 정의되어 있으면:' (domain 조건 추가). 또는 명시적 fallback: '도메인별 처리: backend/default면 Step 2 건너뜀, frontend/fullstack면 e2e_test 존재 여부로 Step 2 진행 여부 판정'.",
      "requires_sync_to_cache": true,
      "related_existing_findings": ["F03", "F09"]
    },
    {
      "id": "F03",
      "dimension": 3,
      "severity": "high",
      "title": "Dev Config 로드 메커니즘 미명시: Step 1-1과 Step 1(domain별 테스트) 간 Dev Config 접근 순서 불명확",
      "location": "skills/dev-build/references/tdd-prompt-template.md:52-89",
      "evidence": "52줄: '## domain별 테스트' 섹션 (domain 존재 가정)\n43-50줄: 'Dev Config의 quality_commands.coverage' 참조 (Step 1에서 Dev Config 로드 필요)\n57줄: '${CLAUDE_PLUGIN_ROOT}/references/test-commands.md의 E2E 테스트 섹션 참조'",
      "problem": "tdd-prompt-template.md는 '서브에이전트에 전달되는 프롬프트 본문'인데, domain 값이 정의되지 않음. 본 템플릿이 domain별 테스트를 분기하려면 {DOMAIN} 치환 변수가 필요한데 SKILL.md 65-68줄의 치환 변수 목록에 없음. LLM이 (A) domain을 추측 또는 직접 계산, (B) design.md에서 추출하거나 (C) 건너뜀 중 선택 가능.",
      "impact": "domain 정보 부재로 E2E/커버리지 조건 판정 불가 → silent skip 또는 잘못된 조건 분기.",
      "fix_proposal": "SKILL.md 65-68줄에 domain 추출 로직 추가: '- `{DOMAIN}`: wbs-parse.py 출력의 domain 필드'. tdd-prompt-template.md 최상단에 domain 값 주입 요구사항 명시: '사전 조건: {DOMAIN}이 정의되어야 함. 정의 없으면 design.md에서 도메인 추론 또는 \\'default\\'로 처리'.",
      "requires_sync_to_cache": true,
      "related_existing_findings": ["F02"]
    },
    {
      "id": "F04",
      "dimension": 1,
      "severity": "high",
      "title": "Build fail vs design gate 재검증 기준 충돌: 설계 누락 시 build.fail 기록 규칙이 design phase 게이트와 중복",
      "location": "skills/dev-build/references/tdd-prompt-template.md:24-32 vs skills/dev-design/SKILL.md:79-99",
      "evidence": "tdd-prompt-template.md:24-32: '[FAIL] design.md의 진입점/파일 계획이 불완전합니다. ... build.fail 이벤트로 기록'\ndev-design/SKILL.md:94: 'dev-design이 다음을 검증한다... UI Task 추가 검증 ... 검증 실패 처리: 누락 항목 명시하여 재지시, 2회 실패하면 상태 전이 보류'",
      "problem": "dev-design은 Step 2-1에서 이미 진입점/파일 계획을 검증하고 게이트를 통과하지 못하면 design.ok 전이 없음 (상태 [ ] 유지). 그런데 tdd-prompt-template.md는 '레거시 design.md나 게이트 우회' 상황에서 build.fail로 기록하라고 함. 규칙 우선순위가 불명확: (A) 설계 게이트 통과 시만 build 진입 (gateway 믿음), (B) build도 재검증 (gateway 불신). 상태 머신에서도 [ ]에서 build.ok로 직접 전이는 불가능한데, '게이트 우회'를 어떤 시나리오로 가정하는지 명시 없음.",
      "impact": "다중 게이트로 인한 처리 로직 복잡화 및 설계 게이트 존재 이유 약화. 호출자가 design.md 검증을 믿지 못해 build에서도 재검증하면 코드 중복, 믿으면 누락 발견 지연.",
      "fix_proposal": "tdd-prompt-template.md 25줄의 '게이트 우회 상황' 설명을 명확히: '본 검증은 legacy design.md(dev-design 게이트 이전 생성) 또는 수동 design.md 편집으로 설계 게이트를 우회한 경우를 대비함. 정상 워크플로우에서는 dev-design의 2-1 게이트로 이미 차단됨.' 또는 조건 축소: '- 설계 누락 시 조치를 제거하고 build.fail 상황 자체를 설계 신뢰 기반으로 재정의'.",
      "requires_sync_to_cache": true,
      "related_existing_findings": ["F01"]
    },
    {
      "id": "F05",
      "dimension": 6,
      "severity": "medium",
      "title": "가드레일 기준 검증 불가능: '같은 이유로 3회 연속 실패' 판정 기준 미정의",
      "location": "skills/dev-build/references/tdd-prompt-template.md:97-100",
      "evidence": "'같은 테스트가 3회 연속 같은 이유로 실패하면 해당 테스트 수정을 중단'",
      "problem": "'같은 이유'의 정의가 없음. LLM이 (A) 에러 메시지 텍스트 정확 일치, (B) 근본 원인(예: 타입 오류) 분류, (C) 시간 순으로 '연속'인지 판정 등 다양하게 해석 가능. 예: 테스트 A 실패(원인 X) → 테스트 B 실패(원인 X) → 테스트 A 실패(원인 X)는 '연속'인가? 리뷰 시 '같은 이유'의 충족 여부를 판정 불가.",
      "impact": "가드레일이 명확한 기준 없이 작동하면 LLM이 조기에 포기할 수도, 반복할 수도 있음. 테스트 pass/fail 판정 편차 증가.",
      "fix_proposal": "'같은 이유로 3회 연속'을 '동일 테스트 케이스의 실패 이유(에러 메시지의 핵심 키워드 또는 스택 트레이스 root cause)가 변하지 않고 3회 연속 같은 케이스에서 반복'로 구체화. 또는 '수정 시도 N회 → test.skip 처리' 같은 행위 기반 기준으로 변경.",
      "requires_sync_to_cache": true,
      "related_existing_findings": []
    },
    {
      "id": "F06",
      "dimension": 7,
      "severity": "high",
      "title": "Template 출력 포맷 vs dev-test parser 일치 검증 누락: coverage/E2E 섹션 구조 미정의",
      "location": "skills/dev-build/template.md:24-27 vs skills/dev-test/template.md:1-30",
      "evidence": "build template 24-26줄: '## 커버리지 (Dev Config에 coverage 정의 시)' → 변수 채우기\ntest template 12-17줄: '## 정적 검증' (lint/typecheck, coverage 없음)",
      "problem": "build 단계가 생성하는 template.md의 '## 커버리지' 섹션을 test 단계가 참조하거나 파싱하는지 명시 없음. dev-test/SKILL.md는 이전 build의 template을 읽는가? 아니면 build가 dev-test가 기대하는 형식으로 작성해야 하는가? test/template.md에 coverage 섹션이 없으면, build가 작성한 coverage 데이터는 어디로 가는가?",
      "impact": "Coverage 정보 손실 또는 downstream 파서 실패. 다운스트림에서 이전 단계의 output을 확인할 수 없음.",
      "fix_proposal": "build template 24-27줄을 test template 구조에 맞춰 통합: test/template.md '## 정적 검증'에 coverage 행 추가, 또는 build가 test-report.md에 coverage 데이터를 병합하여 기록하도록 명시. SKILL.md에서 명확히: 'build가 생성한 coverage 데이터는 test 단계가 합산하여 최종 test-report.md에 기록'.",
      "requires_sync_to_cache": true,
      "related_existing_findings": []
    },
    {
      "id": "F07",
      "dimension": 7,
      "severity": "medium",
      "title": "E2E 코드 작성 출력 위치 미명시: 생성된 E2E 파일이 build artifact로 추적되지 않음",
      "location": "skills/dev-build/template.md:5-10 vs skills/dev-build/references/tdd-prompt-template.md:79-88",
      "evidence": "template.md 5-10: '생성/수정된 파일' 표 (E2E 파일 명시 가능)\ntdd-prompt-template.md 82: 'discovery에서 확인한 testDir 하위에 생성'",
      "problem": "build 단계가 E2E 코드를 작성하면, template.md의 '생성/수정된 파일' 표에 E2E 파일을 기록하는지 여부가 불명확. 기록한다면 신규/수정 구분은? 테스트 미실행이므로 '신규 (테스트 미검증)'인가? 또는 단위 테스트만 표에 넣고 E2E는 별도 추적인가?",
      "impact": "Build artifact 추적 불완전 → downstream 파서가 전체 변경 파일을 놓칠 수 있음. 리뷰어가 어느 E2E 파일이 build에서 생성되었는지 확인 불가.",
      "fix_proposal": "template.md '생성/수정된 파일' 표에 주석 추가: '(E2E 테스트 파일도 포함. 테스트 미실행 상태이므로 \\'신규 (build에서 작성, 실행 대기)\\'로 표기)' 또는 E2E는 별도 섹션 추가: '## E2E 테스트 파일 (build에서 작성, 실행은 dev-test에서)'.",
      "requires_sync_to_cache": true,
      "related_existing_findings": ["F06"]
    },
    {
      "id": "F08",
      "dimension": 8,
      "severity": "medium",
      "title": "참조 파일 검증: references/test-commands.md 존재 및 형식 의존성 미확인",
      "location": "skills/dev-build/references/tdd-prompt-template.md:54, 57 vs references/test-commands.md",
      "evidence": "tdd-prompt-template.md 54줄: '${CLAUDE_PLUGIN_ROOT}/references/test-commands.md의 \"단위 테스트\" 섹션 참조'\n57줄: 'E2E 테스트 섹션 참조'",
      "problem": "test-commands.md가 정의하는 'domain별 단위 테스트 명령', 'E2E 테스트 명령', 'fullstack_domains 목록' 등이 tdd-prompt-template.md에서 하드코딩된 구분(fullstack/frontend 체크)과 일관성 있는지 검증 필요. 예: test-commands.md에 domain=fullstack이 없으면, Step 0의 'fullstack/frontend' 조건 분기가 작동하지 않음.",
      "impact": "참조 파일 누락 또는 형식 변경 시 build 단계가 silently fail. 캐시된 문서와 실제 구현 드리프트 위험.",
      "fix_proposal": "SKILL.md 1-1에서 design.md 존재 확인과 유사하게, build의 2단계 초반에 'test-commands.md 존재 및 필수 섹션 확인' 단계 추가. 또는 기본값 제공: 'test-commands.md 로드 실패 시 default-dev-config.md의 도메인 정의로 fallback'.",
      "requires_sync_to_cache": true,
      "related_existing_findings": []
    },
    {
      "id": "F09",
      "dimension": 4,
      "severity": "medium",
      "title": "Step 0 조건의 MECE 위반: 'fullstack/frontend Task 한정' vs design.md의 실제 entry point 정의 관계 불명확",
      "location": "skills/dev-build/references/tdd-prompt-template.md:14-32",
      "evidence": "14줄: 'Step 0 — 라우터/메뉴 선행 수정 (fullstack/frontend Task 한정, UI 아닌 경우 skip)'\n24-32줄: '설계 누락 시 조치' 블록은 domain 조건이 없음 (모든 domain에 적용?)",
      "problem": "Step 0 조건: '(A) domain=fullstack/frontend AND (B) design.md에 라우터/메뉴 정의 있으면' 실행. 그런데 24-32줄의 '설계 누락 시 조치'는 domain 조건을 언급하지 않음. LLM이 (A) domain과 무관하게 항상 진입점 체크, (B) fullstack/frontend일 때만 체크 중 선택. 분류가 비상호배타적: domain=backend인데 design.md에 UI 진입점이 정의된 경우는? (dev-test 1-5의 keyword 재분류와도 연관)",
      "impact": "backend 작업에서도 Step 0 실행 또는 setup 누락 → E2E 테스트 작성 실패 또는 reachability gate 미충족.",
      "fix_proposal": "14줄을 수정: 'Step 0 — 라우터/메뉴 선행 수정 (fullstack/frontend Task, 또는 design.md의 진입점이 정의된 모든 Task)' 또는 명확한 로직: '(1) domain을 확인 OR (2) design.md의 UI 키워드 검사 (dev-test 1-5 기준과 동일) → 진입점 정의 여부 판정 → Step 0 진행 여부 결정'.",
      "requires_sync_to_cache": true,
      "related_existing_findings": ["F02"]
    },
    {
      "id": "F10",
      "dimension": 12,
      "severity": "medium",
      "title": "에러 경로 침묵: 설계 누락 detection 실패 시 처리 규칙 없음",
      "location": "skills/dev-build/references/tdd-prompt-template.md:24-32",
      "evidence": "'[FAIL] design.md의 진입점/파일 계획이 불완전합니다. ...' 형식으로 기록\nCondition 미정의: 어떤 경우를 '불완전'으로 판정하는가?",
      "problem": "design.md에 '진입점' 섹션이 'N/A'로 마무리되었다면? 또는 완전히 없다면? 또는 라우터는 있는데 메뉴는 없다면? 각 경우별 처리 규칙 없음. LLM이 자의적으로 판정 → 일관성 없음.",
      "impact": "설계 누락 detection의 편차로 일부는 build.fail, 일부는 silent skip. 같은 누락이 다르게 처리됨.",
      "fix_proposal": "24-32줄 이전에 '불완전 판정 기준'을 명시: '다음 중 하나라도 해당되면 불완전으로 간주: (1) \"진입점\" 섹션이 존재하지 않음, (2) 섹션이 있으나 \"N/A\"로만 구성, (3) 사용자 진입 경로/URL/라우터 파일/메뉴 파일 중 하나라도 비어 있음' 또는 design-gate의 2-1 검증 기준 직접 인용.",
      "requires_sync_to_cache": true,
      "related_existing_findings": ["F04"]
    },
    {
      "id": "F11",
      "dimension": 5,
      "severity": "medium",
      "title": "결정 규칙 공백: 단위 테스트 작성 순서 (design.md QA vs 기존 패턴) 우선순위 미정의",
      "location": "skills/dev-build/references/tdd-prompt-template.md:36",
      "evidence": "'design.md의 QA 체크리스트 기반으로 단위 테스트를 먼저 작성'",
      "problem": "project의 기존 단위 테스트 패턴/구조가 design.md의 QA와 다르다면? LLM이 (A) design.md 우선, (B) 기존 패턴 우선, (C) 둘 다 작성 중 선택 가능. 또한 design.md의 QA가 불완전하면(예: edge case 누락) LLM이 추가 테스트를 작성할지 안 할지 불명확.",
      "impact": "테스트 범위/깊이 편차 → 같은 Task도 다양한 커버리지로 구현 가능.",
      "fix_proposal": "36줄 다음에 우선순위 명시: 'design.md의 QA를 base로 삼되, 프로젝트 관례 및 도메인 표준 패턴을 반영하여 필요한 edge case를 추가할 수 있다. 추가한 테스트는 결과 보고의 \"비고\"에 기록한다.'",
      "requires_sync_to_cache": true,
      "related_existing_findings": []
    },
    {
      "id": "F12",
      "dimension": 14,
      "severity": "low",
      "title": "Template 예시 신뢰성: build/template.md의 표 예시가 fullstack/frontend Task만 반영",
      "location": "skills/dev-build/template.md:5-10, 17-22",
      "evidence": "'E2E 테스트 (작성만 — 실행은 dev-test)' 섹션 항상 존재\n예시에 frontend Task만 명시",
      "problem": "backend Task의 template은 E2E 섹션을 어떻게 채우는가? (N/A? 섹션 자체 생략?) 예시가 모든 domain을 커버하지 않으면 LLM이 다양하게 채울 수 있음.",
      "impact": "Backend build 결과의 일관성 낮음. 리뷰 시 '왜 E2E 섹션을 이렇게 채웠는가' 질문 증가.",
      "fix_proposal": "template.md에 주석 추가: '(주의: domain=backend 또는 e2e_test=null인 경우 E2E 테스트 섹션의 \\'파일 경로\\' 행을 \"N/A — {domain} domain\"으로 기록한다)' 또는 backend 전용 template 예시 추가.",
      "requires_sync_to_cache": true,
      "related_existing_findings": []
    },
    {
      "id": "F13",
      "dimension": 15,
      "severity": "low",
      "title": "SSOT 위반 가능성: design.md → build에 전달되는 domain/파일 정보 중복성",
      "location": "skills/dev-build/SKILL.md:65-68 vs skills/dev-build/references/tdd-prompt-template.md:43-50, 52-89",
      "evidence": "SKILL.md 65-68: '{DESIGN_CONTENT} = design.md 전문' 전달\ntdd-prompt-template.md: design.md의 파일 계획, QA, 진입점 여러 번 참조",
      "problem": "tdd-prompt-template.md가 design.md 전체를 받으면서 동시에 design.md의 여러 섹션(파일 계획, QA, 진입점)을 명시적으로 참조. 만약 design.md 스키마가 변경되면 두 곳을 수정해야 함. 예: '파일 계획'이 '파일 설명'으로 이름 변경 시 template과 동기화 필요.",
      "impact": "Maintenance 부담 증가. design.md 스키마 변경 시 캐시된 템플릿과 드리프트.",
      "fix_proposal": "design.md를 구조화된 JSON으로 전달하거나, 또는 tdd-prompt-template.md에서 '설계 파일의 \"파일 계획\" 섹션을 참조'라는 명시를 제거하고 design.md 전체 이해로 통일. 또는 wbs-parse.py가 design.md를 JSON 파싱하여 섹션별 추출본 제공 (SSOT 일원화).",
      "requires_sync_to_cache": true,
      "related_existing_findings": []
    },
    {
      "id": "F14",
      "dimension": 13,
      "severity": "low",
      "title": "특수 모드 미정의: dry-run/view-only 모드가 언급되지 않음",
      "location": "skills/dev-build/SKILL.md 전체",
      "evidence": "특수 모드(--dry-run, --view-only) 언급 없음\ndev/SKILL.md에서 --only 옵션만 정의",
      "problem": "dev-test/SKILL.md:1-5에 유사 구조가 있지만 build에는 없음. 사용자가 '구현 없이 설계만 확인' 후 build를 스킵하려면? 또는 '/dev --only design --only build' 같은 조합 옵션이 있는가?",
      "impact": "Workflow 유연성 부족. 특수 케이스 처리 규칙 부재.",
      "fix_proposal": "필요시 추가 (현재는 저우선도): '특수 모드: --dry-run (테스트 생성만, 실행 없음)', 또는 현 상태 유지하되 명시: '본 스킬은 --only 옵션으로만 선택 실행 가능하며, 부분 dry-run은 지원하지 않음'.",
      "requires_sync_to_cache": false,
      "related_existing_findings": []
    },
    {
      "id": "F16",
      "dimension": 16,
      "severity": "high",
      "title": "CROSS_SKILL cascade gap: Reachability (spec→design→build→test→transition) 체인 검증 불완전",
      "location": "skills/dev-build/SKILL.md:1-95, skills/dev-build/references/tdd-prompt-template.md:14-88, skills/dev-test/SKILL.md:68-126, skills/dev-design/SKILL.md:79-99, references/state-machine.json:44-52",
      "evidence": "spec(WBS/feat): entry-point 필드 → design: 진입점 섹션 검증 (2-1 gate) → build: Step 0 라우터/메뉴 적용 + E2E reachability → test: 1-5 effective_domain 재분류 및 reachability gate → state-machine: build.ok/fail, test.ok/fail 기록",
      "problem": "각 단계 사이의 reachability 계약이 이질적: (1) design의 gate는 '진입점 섹션 완성도' 검증이지만, build Step 0는 '실제 라우터/메뉴 코드 적용' 요구. 설계와 구현의 경계가 불명확. (2) test 1-5의 'effective_domain 재분류'는 build에 알려지지 않음 (build가 작성한 E2E가 test의 keyword 기준과 일치하는가?). (3) build.fail 시 상태가 [dd]에서 [dd]로 유지되므로 'reachability 미충족'으로 재실행하면 동일 build 단계부터 시작하는데, 실제로는 design 재작업 필요할 수 있음 (상태 롤백 불가). (4) state-machine.json에 reachability 관련 event 없음 (build.ok는 '테스트 통과'만 의미하고 reachability 검증 여부는 기록 안 함).",
      "impact": "Frontend/fullstack Task의 reachability 보장 역할이 분산되어 있으며, 어느 단계에서 실패 판정이 나면 이전 단계로의 롤백이 불가능. Orphan page 위험 (E2E는 통과하지만 실제 사용자는 접근 불가).",
      "fix_proposal": "두 지점 이상의 삽입 필요: (1) build/SKILL.md Step 0 설명에 'reachability 검증 책임 경계 명시': '설계 gate는 설계 완성도 검증, build Step 0는 실제 구현 적용 검증. 둘 다 fullstack/frontend Task 진행 필수 조건이며, 하나라도 미충족하면 build.fail.' (2) dev-test/SKILL.md 1-5에서 'build의 E2E와 test의 keyword 기준 동기화' 명시: 'build Step 0에서 \"UI 키워드\" 기반 domain 재분류를 하거나, test 1-5와 일관된 keyword 목록 제공'. (3) state-machine.json 또는 SKILL.md에서 'reachability 미충족 시 롤백 규칙' 명시: 'build Step 0/E2E 미충족 또는 test reachability gate 실패 시 status 롤백 여부 및 재실행 위치' 정의. (4) build fail/test fail 구분 명확화: 'test.fail 중 reachability gate 실패는 build 재작업 지시로 기록' 여부 검토.",
      "requires_sync_to_cache": true,
      "related_existing_findings": ["F02", "F09"]
    }
  ],
  "dropped_candidates": [
    {
      "what": "Source 분기(wbs vs feat)의 MECE 검증",
      "reason": "양 분기가 동일 DFA와 template 구조를 공유하며, 주 차이는 요구사항 원천(wbs.md vs spec.md)과 경로(tasks vs features)만. 동기화 메커니즘이 명확하고 SKILL.md에서 SOURCE 분기가 상호배타적으로 정의됨. 실제 차이는 파일 경로이므로 dimension 관점의 논리 모순 아님."
    },
    {
      "what": "Regression 정의(dev-test의 test.fail vs refactor.fail 구분)",
      "reason": "dev-build/SKILL.md 94줄: 'status는 [dd] 유지'. dev-refactor/SKILL.md는 refactor.fail로 [ts] 유지. 두 스킬이 각각의 실패 케이스를 별도 정의하고 있으므로 충돌 아님. 상태 머신도 같은 로직 (*.fail은 상태 유지)."
    },
    {
      "what": "Bypass mechanism과 build fail의 상호작용",
      "reason": "bypass는 dev-team 전용 기능 (state-machine.json 61-71줄). dev-build 스킬 자체는 bypass를 생성하지 않고, /dev 또는 /feat 오케스트레이터가 호출자 판단으로만 bypass 트리거. dev-build는 build.ok/fail만 보고하므로 연결점 없음."
    },
    {
      "what": "E2E 서버 lifecycle (e2e-server.py와 build E2E 작성의 연관)",
      "reason": "test-commands.md 76-84줄에서 'Dev Config의 e2e-server/e2e-url이 정의되면 dev-test가 미리 기동'. dev-build는 E2E 코드만 작성하고 실행하지 않으므로, 서버 lifecycle은 dev-test 책임. build와는 무관."
    }
  ]
}
```

---

## 권장 처리 순서

1. **High 우선 적용 (6건)**: F01(모델 정책) → F04(build vs design gate) → F03(domain 치환 변수) → F02(E2E 작성 조건) → F06(coverage template 연결) → F16(reachability cascade)
2. **Medium 정비 (6건)**: F05, F07, F08, F09, F10, F11
3. **Low 검토 (3건)**: F12, F13, F14

적용 후 플러그인 캐시(`~/.claude/plugins/marketplaces/dev-tools/`) 동기화 필수.
