# TSK-02-02: i18n 프레임워크 + 언어 토글 UI - 테스트 보고

## 실행 요약

| 구분        | 통과 | 실패 | 합계 |
|-------------|------|------|------|
| 단위 테스트 | N/A  | 0    | 0    |
| E2E 테스트  | 0    | 0    | 0    |

**상태**: 테스트 실행 자체가 차단됨 (게이트 실패)

## 차단 사유 (1-5 UI E2E Conformity Gate)

### Gate Status
- **Domain**: fullstack (UI 도메인)
- **E2E 테스트 명령**: null (정의되지 않음)
- **게이트 판정**: FAIL

### 상세 내용
Task TSK-02-02는 fullstack 도메인으로, design.md에 다음과 같은 UI 관련 구현이 포함되어 있습니다:
- 헤더 우측 `<nav class="lang-toggle">` 토글 SSR 렌더
- `<h2>` 섹션 heading 번역
- URL 쿼리 파라미터(`?lang=ko|en`) 기반 상태 관리
- 클릭 기반 언어 전환 UI

이는 fullstack(backend+frontend 통합) 도메인의 필수 E2E 검증 대상입니다.

### 해결 방법
`docs/monitor-v3/wbs.md`의 **## Dev Config** 섹션에서 `fullstack.e2e_test` 필드를 정의하십시오:

```markdown
## Dev Config

### Domains

| Domain   | Unit Test | E2E Test | E2E Server | E2E URL |
|----------|-----------|----------|-----------|---------|
| backend  | `pytest -q scripts/` | - | - | - |
| frontend | `pytest -q scripts/` | - | - | - |
| fullstack| `pytest -q scripts/` | **`pytest -q scripts/test_monitor_e2e.py::test_monitor_i18n_*`** | **http://localhost:7000** | **http://localhost:7000** |
| infra    | - | - | - | - |
```

**대안 (권장하지 않음)**: 고의로 E2E를 skip하려면:
```markdown
fullstack | `pytest -q scripts/` | `python3 -c "pass"` | - | - |
```
주의: 이 경우 QA 체크리스트의 E2E 검증 항목(#94-95)은 `unverified`로 기록되며, UI 기능이 실제 동작하지 않을 위험이 있습니다.

## QA 체크리스트

### 단위 테스트 (dev-build에서 구현됨)
- [ ] `_t("ko", "work_packages")` → `"작업 패키지"` (단위 테스트 미실행 - 게이트 차단)
- [ ] `_t("en", "work_packages")` → `"Work Packages"` (단위 테스트 미실행 - 게이트 차단)
- [ ] `render_dashboard(model)` 기본값 `lang="ko"` 적용 (단위 테스트 미실행 - 게이트 차단)

### E2E 테스트 (게이트 차단으로 미실행)
- [ ] `unverified` — E2E 테스트 명령 미정의로 skip. 다음 항목을 검증하려면 Dev Config에 e2e_test 정의 필수:
  - 헤더 우측 `[ 한 | EN ]` 토글 클릭 → URL `?lang=en` 추가 → 영문 heading 렌더 확인
  - 언어 토글 `<nav class="lang-toggle">` 브라우저 화면 렌더 확인
  - `?lang=en&subproject=billing` 쿼리 유지 확인

### 정적 검증
- (미실행 - 단위 테스트 미실행으로 인해 스킵)

## 권고사항

1. **즉시 해결**: Dev Config에 `fullstack.e2e_test` 명령을 추가하고 `/dev TSK-02-02`로 재실행
   ```bash
   # 예시: 대시보드 SSR 렌더 + 클라이언트 상호작용 검증
   e2e_test: "pytest -q scripts/test_monitor_e2e.py::test_monitor_i18n_ko_default tests/e2e/i18n-toggle.spec.ts"
   ```

2. **대체 방법**: 현재 프로젝트가 E2E 환경을 갖추지 않았으면, 단위 테스트 후 수동 검증으로 진행 가능 (bypass 고려)

3. **참고**: v1.4.1부터 UI 도메인 Task는 E2E 게이트가 필수입니다. 이는 v1.4.0의 lect 사고(E2E 위장 실행)를 방어하기 위한 조치입니다.

---

**Phase**: test (dev-test SKILL.md 실행 절차 1-5 "UI E2E Conformity Gate" 차단)  
**Status**: test.fail (상태 전이: `[im]` 유지)  
**Last Event**: test.fail @ 2026-04-22T13:16:21Z
