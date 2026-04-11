# ECC vs DDTR 워크플로우 비교 분석

**날짜**: 2026-04-11
**비교 대상**: Everything Claude Code (ECC) commands/agents vs dev-plugin DDTR 사이클

## 비교 범위

### ECC 측
| 항목 | 파일 |
|------|------|
| `/plan` | commands/plan.md |
| `/tdd` | commands/tdd.md → skills/tdd-workflow/SKILL.md |
| `/code-review` | commands/code-review.md |
| `/build-fix` | commands/build-fix.md |
| `/e2e` | commands/e2e.md → skills/e2e-testing/SKILL.md |
| `/security-scan` | skills/security-scan/SKILL.md |
| `/refactor-clean` | commands/refactor-clean.md |
| `/update-docs` | commands/update-docs.md |
| architect 에이전트 | agents/architect.md |
| database-reviewer 에이전트 | agents/database-reviewer.md |

### DDTR 측
| 단계 | 파일 |
|------|------|
| dev-design `[dd]` | skills/dev-design/SKILL.md |
| dev-build `[im]` | skills/dev-build/SKILL.md |
| dev-test | skills/dev-test/SKILL.md |
| dev-refactor `[xx]` | skills/dev-refactor/SKILL.md |

---

## 1. dev-design vs `/plan` + `architect`

| 관점 | dev-design | ECC | 상태 |
|------|-----------|-----|------|
| 요구사항 재진술 | ✅ | ✅ | 적용 완료 |
| 리스크 식별 | ✅ | ✅ | 적용 완료 |
| 트레이드오프 분석 | ✅ | ✅ architect: Pros/Cons/Alternatives/Decision | 적용 완료 |
| 아키텍처 안티패턴 감지 | ❌ | ✅ architect: Red Flags 목록 | 불필요 (Task 단위에 과함) |
| ADR | ❌ | ✅ architect: 결정 기록 양식 | 불필요 (프로젝트 레벨 별도 스킬) |

### ~~도입 추천: 트레이드오프 분석 (순위 5)~~ → 적용 완료

template.md에 "설계 결정" 섹션 추가, SKILL.md 프롬프트 산출물에 항목 5 추가.

---

## 2. dev-build vs `/tdd` + `/build-fix`

| 관점 | dev-build | ECC | 상태 |
|------|----------|-----|------|
| RED→GREEN | ✅ | ✅ (REFACTOR 포함) | 설계상 분리 (OK) |
| RED 게이트 강화 | ✅ | ✅ 컴파일타임/런타임 RED 구분 | 적용 완료 |
| 커버리지 기준 | ✅ | ✅ 80%+, 크리티컬 100% | 적용 완료 (Dev Config quality_commands.coverage) |
| 빌드 에러 가드레일 | ✅ | ✅ build-fix: 동일 에러 3회→중단 등 | 적용 완료 (느슨한 버전) |
| E2E 테스트 코드 작성 | ✅ | ✅ /tdd에 포함 | 적용 완료 (작성만, 실행은 dev-test) |
| 빌드 시스템 자동 감지 | Dev Config로 외부화 | 자동 감지 | dev-plugin이 더 유연 |

### ~~도입 추천 A: 빌드 루프 가드레일 (순위 1)~~ → 적용 완료

dev-build SKILL.md에 가드레일 추가. ECC 원안보다 느슨하게 조정:
- 같은 테스트 **3회** 실패 시 중단 (원안 2회)
- **regression** 시에만 되돌림 + 다른 접근 1회 시도 (원안: 실패 수 증가 시 즉시 되돌림)
- design.md에 없는 파일 필요 시 이유 기록 후 **계속 진행** (원안: 중단)

### ~~도입 추천 B: 커버리지 확인 (순위 4)~~ → 적용 완료

Dev Config에 `### Quality Commands` 테이블 추가 (`quality_commands.coverage`).
dev-build TDD 순서 5번에 커버리지 확인 단계 추가. wbs-parse.py 파서 확장 완료.

---

## 3. dev-test vs `/e2e` + `/code-review`

| 관점 | dev-test | ECC | 상태 |
|------|---------|-----|------|
| 모델 에스컬레이션 | ✅ Haiku→Sonnet | ❌ | dev-plugin 우위 |
| 재시도 예산 | ✅ 최대 6회 | ❌ | dev-plugin 우위 |
| 경계 교차 검증 | ✅ consumer/producer 확인 | ❌ | dev-plugin 우위 |
| Flaky 테스트 감지 | ❌ | ✅ e2e: 10회 중 N회 통과율 | 불필요 (DDTR은 단발 실행) |
| 아티팩트 캡처 | ❌ | ✅ e2e: screenshot/video/trace | 불필요 (CI가 아닌 로컬 개발) |
| Lint/Typecheck 실행 | ✅ | ✅ code-review Phase 4 | 적용 완료 (Dev Config quality_commands) |
| 보안 리뷰 | ❌ | ✅ code-review: OWASP 등 | 별도 스킬로 분리 |

### ~~도입 추천: Lint/Typecheck 검증 (순위 2)~~ → 적용 완료

Dev Config에 `### Quality Commands` 테이블 추가 (`quality_commands.lint`, `quality_commands.typecheck`).
dev-test SKILL.md에 단계 2.5 정적 검증 추가. wbs-parse.py 파서 확장 완료.

---

## 4. dev-refactor vs `/refactor-clean` + `/code-review`

| 관점 | dev-refactor | ECC | 상태 |
|------|-------------|-----|------|
| 리뷰 관점 | 7가지 (중복/길이/네이밍/불필요코드/타입안전성/성능/에러핸들링) | 7가지 (Correctness, Type Safety, Pattern, Security, Performance, Completeness, Maintainability) | 적용 완료 |
| 데드코드 감지 도구 | ❌ (수동) | ✅ knip, depcheck, ts-prune 등 | 낮은 우선순위 |
| 안전 등급 분류 | ❌ | ✅ SAFE/CAUTION/DANGER | 불필요 (Task 범위가 좁음) |
| 수정 후 테스트 | ✅ | ✅ | - |

### ~~도입 추천: 리뷰 관점 확장 (순위 3)~~ → 적용 완료

dev-refactor SKILL.md 리뷰 관점 4→7개로 확장 (타입 안전성, 성능, 에러 핸들링 추가). 문서 추천안과 동일하게 적용.

---

## 5. DDTR에 없는 ECC 기능 (파이프라인 외부)

| ECC 기능 | DDTR 해당 없음 | 판단 |
|----------|---------------|------|
| `/security-scan` | 보안 검사 | DDTR 밖에서 별도 스킬로 제공 가능 |
| `/update-docs` | 문서 자동 생성 | DDTR과 무관, 독립 스킬로 제공 가능 |
| `database-reviewer` | DB 전문 리뷰 | domain이 DB인 Task에서 dev-design이 참조할 수 있으나, 에이전트 통합은 과함 |

이들은 DDTR 파이프라인에 넣기보다 독립 스킬로 분리하는 것이 적절.

---

## 6. dev-plugin이 ECC보다 나은 점

| 관점 | dev-plugin | ECC |
|------|-----------|-----|
| 모델 라우팅 | 단계별 최적 모델 배정 (Design:Opus, Build:Sonnet, Test:Haiku, Refactor:Sonnet) | 모델 고정 또는 에이전트별 지정 |
| 자동 에스컬레이션 | Haiku→Sonnet 자동 승격 (dev-test) | 없음 |
| 재시도 예산 | 최대 6회, 명확한 탈출 조건 | 없음 (무한 가능) |
| 경계 교차 검증 | consumer/producer 동시 확인 (dev-test) | 없음 |
| 상태 추적 | WBS 상태 자동 업데이트 | 없음 (대화 맥락 의존) |
| 파이프라인 자동화 | dev → design → build → test → refactor 자동 연결 | 수동 연결 (/plan → /tdd → /code-review) |
| 병렬 실행 | dev-team으로 WP 단위 병렬 분배 | 없음 |
| 도메인별 설정 | Dev Config로 프로젝트별 테스트/설계 가이드 외부화 | 빌드 시스템 자동 감지 (범용적이나 커스터마이징 불가) |
| 토큰 절감 | 헬퍼 스크립트로 결정적 작업 위임 | LLM이 모든 작업 수행 |

---

## 도입 우선순위 종합

| 순위 | 항목 | 적용 대상 | 상태 |
|------|------|----------|------|
| 1 | 빌드 루프 가드레일 | dev-build | ✅ 적용 완료 (느슨한 버전) |
| 2 | Lint/Typecheck 검증 | dev-test + Dev Config | ✅ 적용 완료 (quality_commands) |
| 3 | 리뷰 관점 확장 | dev-refactor | ✅ 적용 완료 |
| 4 | 커버리지 확인 | dev-build + Dev Config | ✅ 적용 완료 (quality_commands) |
| 5 | 트레이드오프 분석 | dev-design | ✅ 적용 완료 |

추가 적용 (문서 원안 외):
| 항목 | 적용 대상 |
|------|----------|
| RED 게이트 강화 | dev-build |
| E2E 테스트 코드 작성 | dev-build (작성만, 실행은 dev-test) |
| Quality Commands 테이블 | Dev Config + wbs-parse.py |
| 워크트리 머지 후 정리 | merge-procedure.md |
