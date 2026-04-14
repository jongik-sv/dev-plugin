# 스킬 감사 프롬프트 (범용)

플러그인 내 특정 스킬과 그 다운스트림(스크립트·소비 스킬·참조 파일) 간의 **불합리·중복·애매모호·드리프트**를 찾아내기 위한 감사 프롬프트. 서브에이전트(Explore/general-purpose)에 그대로 붙여 실행하거나, 서로 다른 에이전트·모델에 병렬 투입해 교차검증한다.

스킬별 재사용을 위해 "입력 변수" 블록을 먼저 채운 뒤 프롬프트 본문을 투입하도록 구성되어 있다.

## 사용 방법

1. **입력 변수 채우기** — 아래 "입력 변수" 블록의 `{{...}}` 자리를 감사 대상 정보로 치환한다. `TARGET_SKILL_PATH`는 필수, 나머지는 가능한 한 채운다 (비어 있으면 에이전트가 탐색한다).
2. **단독 실행**: `Agent(subagent_type="Explore", thoroughness="very thorough", prompt=<치환된 본문>)`
3. **교차검증**: 같은 프롬프트를 서로 다른 에이전트(Explore + general-purpose) 또는 다른 모델에 동시 투입 → 공통 finding만 신뢰도 상승, 불일치 finding은 재검토.
4. **결과 처리**: 반환된 JSON의 `findings`를 severity 순으로 정렬 후 high부터 순차 수정. 각 수정은 플러그인 캐시(`~/.claude/plugins/marketplaces/<marketplace-name>/`) 동기화 필수.

## 갱신 이력

- 2026-04-14: 초안 작성 (WBS 스킬 감사용)
- 2026-04-14: 차원 16 추가 — 체인 캐스케이드 누락(cross-skill cascade gap)
- 2026-04-14: **범용화** — 입력 변수 블록 도입, WBS 전용 예시를 일반 패턴으로 치환

---

## 입력 변수 (감사 전 반드시 기입)

```yaml
TARGET_SKILL_PATH: "{{예: /Users/jji/project/dev-plugin/skills/wbs/SKILL.md — 감사 대상 스킬의 SKILL.md 절대경로}}"

TARGET_REFERENCES:
  # 이 스킬이 소유한 references/ · 템플릿 파일 목록 (SKILL.md가 직접 Read하는 것)
  - "{{예: skills/wbs/references/dev-config-template.md}}"
  - "{{예: skills/wbs/references/*.md, skills/wbs/template.md 등}}"

DOWNSTREAM_CONSUMERS:
  # 이 스킬의 산출물(wbs.md, state.json, design.md 등)을 읽거나 소비하는 다른 스킬·스크립트
  - "{{예: scripts/wbs-parse.py}}"
  - "{{예: skills/dev/SKILL.md}}"
  - "{{예: skills/dev-team/SKILL.md}}"

UPSTREAM_CONTRACTS:
  # 이 스킬이 준수해야 하는 상위 규약·공용 참조
  - "{{예: references/state-machine.json}}"
  - "{{예: references/test-commands.md}}"
  - "{{예: CLAUDE.md (프로젝트 전역 원칙)}}"

CROSS_SKILL_PROPERTIES:
  # 이 스킬 + 다운스트림 체인 전체에 걸쳐 유지되어야 하는 횡단 속성.
  # 차원 16(체인 캐스케이드)의 점검 대상. 해당 스킬에 UI/네트워크/보안/데이터 계약 등 횡단 속성이 없으면 빈 배열.
  - "{{예: reachability — fullstack/frontend Task는 메뉴·라우터 배선이 강제되어야 함}}"
  - "{{예: idempotency — 재실행 시 동일 결과}}"

SKILL_PURPOSE_SUMMARY: "{{1~2줄: 이 스킬이 하는 일과 출력물. 감사자가 'LLM이 이 스킬을 결정적·일관적으로 실행할 수 있는가'를 판정할 기준선}}"
```

---

## 프롬프트 본문

```
# 목적
플러그인 `{{PLUGIN_NAME}}` 의 스킬 `{{TARGET_SKILL_PATH}}` 를 감사(audit)한다. 목표는 이 스킬이 LLM에 의해 결정적·일관적으로 실행되도록, 그리고 다운스트림 스킬·스크립트·참조 파일과 드리프트 없이 맞물리도록 만드는 데 방해가 되는 요소를 모두 찾아내는 것이다.

이 스킬의 역할: {{SKILL_PURPOSE_SUMMARY}}

# 1차 감사 대상 (주 파일)
- {{TARGET_SKILL_PATH}}
{{TARGET_REFERENCES를 - 경로 로 한 줄씩}}

# 2차 감사 대상 (정합성 검증용 참조)
다운스트림 소비자:
{{DOWNSTREAM_CONSUMERS를 - 경로 로 한 줄씩}}

상위 규약:
{{UPSTREAM_CONTRACTS를 - 경로 로 한 줄씩}}

# 감사 차원 (빠짐없이 점검)

1. **논리적 모순(contradiction)** — 같은 문서 내에서, 또는 SKILL.md와 참조 파일/스크립트 간에 서로 어긋나는 규칙이 있는가?
   예: SKILL.md가 X를 요구하지만 스크립트는 Y로 계산, 템플릿의 예시가 본문 규칙을 위반 등.

2. **중복(duplication) 및 드리프트 위험** — 같은 정보가 두 곳 이상에 있어 한쪽만 수정하면 어긋나는 지점.
   예: 필드 목록, 기본값, 임계값, 명령 포맷 등이 여러 파일에 하드코딩.

3. **애매모호(ambiguity)** — LLM이 두 가지 이상으로 해석할 수 있는 서술.
   특히 "적절히", "필요하면", "고려한다", 판정 기준 없는 "복잡한", 정량 기준 없는 "큰/작은", "충분한" 등을 의심한다.
   각 애매 표현에 대해 "이 문장을 LLM이 A/B로 해석하면 각각 어떤 결과물이 나오나?"를 보여라.

4. **MECE 위반** — 분류·분기 표(도메인 구분, 카테고리 구분, 상태 전이 등)의 행들이 상호배타인가? 전체를 포괄하는가?
   회색지대·중복 영역이 있는 분기 표를 적발한다.

5. **결정 규칙 공백(decision gap)** — 규칙이 다루지 않는 현실적 경우.
   "이 스킬이 처리해야 할 실제 입력 중, 문서의 분류 표에 해당하지 않는 케이스"를 3개 이상 상상해 보고, 각각을 LLM이 어떻게 처리할지 예측하라.

6. **검증 불가능(untestable) 기준** — 사람이 리뷰하더라도 참/거짓 판정이 불가능한 서술.
   예: "설계 판단이 복잡한 Task", "적절히 작은 모듈" 같은 질적 기준은 정량화되어 있는가?

7. **다운스트림 드리프트** — SKILL.md가 생성·가정하는 출력 포맷이 다운스트림 스크립트/스킬이 실제로 파싱·소비하는 포맷과 일치하는가?
   - 선언 필드 목록 vs 파서 지원 필드 목록
   - 예시와 본문 규칙 간 일치
   - 섹션 위치/헤딩 레벨/구분 기호 가정

8. **리소스 누수 / orphan 참조** — SKILL.md가 언급하는 파일·섹션·명령·옵션이 실존하는지.
   경로, 스크립트 옵션명, 환경변수, 템플릿 파일 등을 실제로 열어 존재 여부 확인.

9. **기준 임계값의 실효성** — "대규모 vs 중소규모", "높음 vs 낮음", "opus vs sonnet" 같은 이분 판정의 기준이 자주 충돌할 텐데, 타이브레이커가 있는가? 기준 간 우선순위가 명시되어 있는가?

10. **완성도 기준(Definition of Done) 충돌** — 서로 대립할 수 있는 완성도 기준(예: "자기 완결성" vs "최대 크기")이 동시에 요구될 때 어느 쪽을 우선하는지 명시되어 있는가?

11. **직교성(orthogonality) 주장 검증** — "X, Y, Z는 독립적으로 선택한다"고 선언된 축들이 실제로 상관관계 있는가? 상관관계가 있다면 문서에 명시되어 있는가?
    예: `category=infrastructure`이면 `domain=infra`가 사실상 강제되는데 문서엔 독립 축처럼 설명.

12. **에러·실패 경로의 침묵** — 행복 경로 외의 지침이 있는가?
    - 필수 입력 누락
    - 외부 명령/스크립트 실행 실패
    - 부분적 상태(이전 실행이 중간에 중단)
    - 충돌하는 사용자 입력

13. **특수 모드 / 분기 완결성** — SKILL.md 내의 특수 모드(예: view-only, dry-run, estimate-only 등)가 본문 단계들과 일관되게 작동하는가? 분기 이후에 실행되면 안 되는 단계가 확실히 스킵되는가?

14. **예시의 신뢰성** — 출력 형식 예시가 본문 규칙을 전부 충족하는가? 예시에 있는 필드가 "속성 목록"에 전부 나오는가? 반대도?

15. **토큰 낭비 / SSOT 위반** — 같은 설명이 본문과 템플릿·참조 파일에 중복되어 있다면, "Single Source of Truth"로 일원화 가능한지. 각 서브에이전트 호출 시 로딩되는 문서 크기가 필요 이상인지.

16. **체인 캐스케이드 누락 (cross-skill cascade gap)** — 이 스킬만 수정해서는 해결되지 않는 횡단 요구사항이 있는가?

    입력 변수의 `CROSS_SKILL_PROPERTIES`를 기반으로 점검한다. 각 속성별로:
    - 이 스킬(spec/plan 레이어)에서 **요구**로 선언되는가?
    - 중간 스킬(design/build 레이어)에서 **계획·구현**으로 연결되는가?
    - 종단 스킬(test/verify 레이어)에서 **검증·게이트**로 강제되는가?
    - 하나라도 빠지면 그 속성은 "체인 캐스케이드 누락" 상태이며 단일 지점 수정으로 해결 불가. finding의 `fix_proposal`에 **삽입 지점 N개**를 명시하라.

    예시 케이스:
    - UI reachability(진입점 배선): WBS spec + design template + test gate 3곳 모두 필요. build 단독 삽입 불가.
    - 멱등성(idempotency): 실행 전 사전조건 체크 + 실행 중 상태 기록 + 재진입 분기. 한 곳에서만 보장 불가.
    - 보안 경계(예: PII 마스킹): 입력 검증 + 로깅 필터 + 테스트 픽스처 전반 필요.

    역방향 케이스도 점검한다: 상위 스킬이 생성해야 하는데 다운스트림에만 규칙이 있어 "dangling 참조"가 발생할 수 있는 속성.

# 보고 형식 (엄수)

다음 JSON을 마크다운 코드블록 안에 담아 출력한다. 각 finding은 **증거 인용(2줄 이내)**과 **정확한 file:line**을 반드시 포함한다.

{
  "audit_metadata": {
    "target_skill": "{{TARGET_SKILL_PATH}}",
    "date": "YYYY-MM-DD",
    "dimensions_covered": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16],
    "total_findings": 0,
    "by_severity": { "high": 0, "medium": 0, "low": 0 }
  },
  "findings": [
    {
      "id": "F01",
      "dimension": "애매모호",
      "severity": "high | medium | low",
      "title": "한 줄 제목",
      "location": "skills/<skill-name>/SKILL.md:132-140",
      "evidence": "파일에서 직접 인용한 원문 2줄 이내",
      "problem": "이 서술이 왜 문제인지. 특히 LLM이 A/B로 해석 시 각각의 결과를 구체적으로 제시",
      "impact": "다운스트림 스킬/스크립트에 미치는 영향 (예: 파서가 NULL 반환, 병렬 분배 시 wait 실패 등)",
      "fix_proposal": "최소 변경으로 해결하는 구체적 수정안 — 문장/표/숫자 단위로 제시. 차원 16(체인 캐스케이드) finding은 여러 파일 삽입 지점 모두 나열.",
      "requires_sync_to_cache": true,
      "related_existing_findings": []
    }
  ],
  "dropped_candidates": [
    { "what": "처음에 의심했지만 실제로는 문제 아님", "reason": "왜 기각했는지" }
  ]
}

# 제약

- 추측 금지. 모든 finding은 파일 내용을 읽어 인용한 근거가 있어야 한다.
- 증거 없이 "개선하면 좋을 것 같다" 류의 finding은 작성하지 않는다.
- 새 기능 제안(스코프 확장) 금지. 기존 규칙의 불합리/중복/애매 개선에만 집중한다.
- 한국어로 작성하되 코드/경로/식별자는 원문 유지.
- Severity 기준:
  - high: 다운스트림 실패 또는 서로 다른 결과물을 만들어낼 규칙 충돌/공백
  - medium: LLM 해석 편차로 품질이 불안정해지는 애매성/중복
  - low: 가독성·일관성 수준의 정비
- 발견 수는 품질 우선. 억지로 채우지 않는다. 그러나 high가 0이라고 자신 있게 말하려면 **16개 감사 차원을 모두 커버했음**을 `audit_metadata.dimensions_covered`에 명시해야 한다.
- 차원 16 관련 finding은 `fix_proposal`에 **삽입 지점을 스킬/파일 단위로 2개 이상** 나열한다. 단일 파일 수정으로 해결 가능하면 차원 16이 아니라 다른 차원으로 분류하라.

# 시작

먼저 1차 감사 대상 파일을 전부 읽고, 2차 대상에서 SKILL.md가 언급하는 지점만 발췌해서 확인하라. `CROSS_SKILL_PROPERTIES`가 정의되어 있으면 각 속성별로 체인 전체의 cascade 상태를 먼저 그려본 뒤, 그 결과를 차원 16 findings에 반영하라. 그 다음 위 16개 차원을 순회하며 findings를 작성하라.
```

---

## 사용 예시 — 다른 스킬 감사하기

가령 `dev-design` 스킬을 감사하려면 입력 변수를 다음과 같이 채운다:

```yaml
TARGET_SKILL_PATH: "/Users/jji/project/dev-plugin/skills/dev-design/SKILL.md"
TARGET_REFERENCES:
  - "skills/dev-design/template.md"
  - "skills/dev-design/references/design-prompt-template.md"
DOWNSTREAM_CONSUMERS:
  - "skills/dev-build/SKILL.md"
  - "skills/dev-build/references/tdd-prompt-template.md"
  - "skills/dev-test/SKILL.md"
  - "scripts/wbs-transition.py"
UPSTREAM_CONTRACTS:
  - "skills/wbs/SKILL.md"
  - "scripts/wbs-parse.py"
  - "references/state-machine.json"
  - "references/default-dev-config.md"
CROSS_SKILL_PROPERTIES:
  - "reachability — design의 Entry Points 섹션이 dev-build Step 0과 dev-test reachability gate로 연결되는지"
  - "파일 계획 일관성 — design.md의 파일 계획이 build에서 실제 구현 범위로 사용되는지"
SKILL_PURPOSE_SUMMARY: "WBS Task 또는 Feature spec으로부터 design.md를 생성하는 스킬. DDTR 체인의 D(Design) 단계."
```

이후 프롬프트 본문의 `{{TARGET_SKILL_PATH}}` 등을 치환하여 에이전트에 투입한다.
