---
name: dev-test
description: "WBS Task 테스트 단계. 단위 + E2E 테스트 실행, 실패 시 수정 반복. 사용법: /dev-test TSK-00-01"
---

# /dev-test - 테스트 실행

인자: `$ARGUMENTS` (TSK-ID, 예: TSK-00-01)

## 실행 절차

### 1. Task 정보 수집
- `docs/wbs.md`에서 `### $ARGUMENTS:` 헤딩을 찾아 domain 확인
- `docs/tasks/{TSK-ID}/design.md`에서 관련 파일 목록 파악

### 2. 테스트 실행 (서브에이전트 위임)
Agent 도구로 서브에이전트를 실행한다 (mode: "auto"):

**프롬프트 구성**:
```
다음 Task의 테스트를 실행하고 모두 통과시켜라.

Task: {TSK-ID}
Domain: {domain}

## QA 체크리스트
docs/tasks/{TSK-ID}/design.md의 "QA 체크리스트" 섹션을 읽고, 각 항목을 테스트로 검증한다.

## 절차
1. domain에 맞는 테스트 실행:
   - backend: `bundle exec rspec`
   - frontend: `npm run test`
   - sidecar: `uv run pytest`
   - fullstack: 위 전부 실행
2. 실패하는 테스트가 있으면 **경계 교차 검증** 후 코드 수정:
   - 테스트 기대값(consumer)과 실제 구현(producer)을 **동시에** 읽는다
   - 함수 시그니처, 반환 타입, 필드명 등 계약이 일치하는지 확인
   - 단순 로직 버그인지, 경계 불일치(boundary mismatch)인지 구분하여 수정
3. 다시 테스트 실행
4. 최대 3회 반복. 3회 후에도 실패하면 실패 내역을 보고
   - 실패 보고 시 pass/fail/unverified 항목으로 구분하여 기록
5. QA 체크리스트의 각 항목에 대해 pass/fail 판정을 기록

## 결과 작성
docs/tasks/{TSK-ID}/test-report.md 파일에 작성한다.
양식은 .claude/skills/dev-test/template.md를 따른다.
```

### 3. 완료 보고
- 테스트 결과 요약을 사용자에게 출력 (WBS 상태 변경 없음)
