# Skill 수정 리뷰 — 2026-04-10

수정된 스킬/스크립트 전체를 교차 검증하여 발견된 문제점과 모순 목록.

---

## Critical

### C-1. dev-team SKILL.md — Design 기본 모델이 Sonnet으로 남아있음

**위치**: `skills/dev-team/SKILL.md:54`

```
Phase 서브에이전트 → 설계=Sonnet, 개발=Sonnet, 테스트=Haiku, 리팩토링=Sonnet
```

**모순 대상**:
- `skills/dev/SKILL.md:29` — Design → Opus
- `skills/dev-design/SKILL.md:22` — 기본 모델은 Opus
- `skills/dev-team/references/wp-leader-prompt.md:35` — 설계=opus

**수정안**: `설계=Sonnet` → `설계=Opus`

---

### C-2. wp-leader-prompt.md — signal-helper.py `wait`에 존재하지 않는 `running` 파라미터

**위치**: `skills/dev-team/references/wp-leader-prompt.md:125-127`

```bash
python3 {PLUGIN_ROOT}/scripts/signal-helper.py wait {task-id} {SHARED_SIGNAL_DIR} 120 running
```
> "이 명령은 `.running` 시그널이 생길 때까지 최대 120초 대기한다."

**실제 동작**: `signal-helper.py`의 `wait` 명령은 `argv[4]`를 timeout으로 파싱하고 `argv[5]`(`running`)는 완전히 무시됨. `wait`는 `.done`/`.failed`만 감시하며, `.running` 대기 기능이 없음. 120초간 `.done`/`.failed`를 기다리게 되어 의도와 완전히 다른 동작.

**수정안**: signal-helper.py에 `wait-running` 명령을 추가하거나, 별도 폴링 로직으로 대체.

---

## High

### H-1. dev/SKILL.md Phase 2 — 여전히 "acceptance criteria" 참조

**위치**: `skills/dev/SKILL.md:77`

```
1. acceptance criteria 기반 테스트 먼저 작성
```

**모순**: `skills/dev-build/SKILL.md:55`는 이미 `"design.md의 QA 체크리스트 기반으로 테스트를 먼저 작성"`으로 변경됨. `dev/SKILL.md`만 구 용어가 남아있음.

**수정안**: `acceptance criteria` → `design.md의 QA 체크리스트`

---

### H-2. dev/SKILL.md Phase 3 — fullstack/frontend E2E 설명이 dev-test와 불일치

**위치**: `skills/dev/SKILL.md:88-89`

```
1. ...fullstack: 전부)
2. E2E ... frontend: `npm run test:e2e` → 실패 시 `npx playwright test` ...fullstack: 전부)
```

**모순**: `skills/dev-test/SKILL.md`의 변경사항이 반영되지 않음:
- fullstack: `backend → frontend → sidecar 순차 실행 (fail-fast)` — "전부"가 아님
- frontend E2E: `stderr에 "Missing script" 포함 시에만 npx playwright test 시도` — 단순 "실패 시"가 아님
- `database / infra / docs` domain은 N/A 처리 — 항목 자체 누락

**수정안**: dev/SKILL.md Phase 3 프롬프트 설명을 dev-test와 동기화.

---

### H-3. CLAUDE.md — helper scripts 테이블에 신규 스크립트 누락

**위치**: `CLAUDE.md:24-29`

누락 스크립트:

| Script | Purpose | Used by |
|--------|---------|---------|
| `scripts/wbs-update-status.py` | WBS Task status 변경 (원자적 교체) | dev-design, dev-build, dev-refactor |
| `scripts/cleanup-orphaned.py` | 고아 테스트 프로세스(vitest/tsc 등) 정리 | dev (Phase 전환 시) |

---

### H-4. CLAUDE.md — domain별 테스트 명령 미갱신

**위치**: `CLAUDE.md:71-73`

현재:
```
- `backend`: `bundle exec rspec`
- `sidecar`: `uv run pytest`
```

스킬에서의 실제 사용:
```
- `backend` 단위: `bundle exec rspec --exclude-pattern "spec/features/**/*,spec/system/**/*"`
- `backend` E2E:  `bundle exec rspec spec/features spec/system`
- `sidecar` 단위: `uv run pytest -m "not e2e"`
- `sidecar` E2E:  `uv run pytest -m e2e`
```

**수정안**: 단위/E2E 구분을 반영하거나, "자세한 명령은 각 스킬 참조" 안내 추가.

---

## Medium

### M-1. CLAUDE.md — agent-pool 시그널 디렉토리 경로 미갱신

**위치**: `CLAUDE.md:35`

```
agent-pool: ... signal files (`/tmp/agent-pool-signals/`).
```

**변경**: 타임스탬프 기반 `/tmp/agent-pool-signals-{YYYYMMDD-HHmmss}-$$`

---

### M-2. dev-team SKILL.md — config JSON 플레이스홀더 혼란

**위치**: `skills/dev-team/SKILL.md:164`

```json
"model_override": "{MODEL_OVERRIDE 또는 빈 문자열}",
```

다른 필드는 `{DOCS_DIR}`, `{SESSION}` 등 단순 형태인데 이 필드만 `또는 빈 문자열`이라는 설명이 섞여있음. Claude가 Write 도구로 작성하는 JSON이므로 기능 문제는 아니지만, 일관성을 위해 `{MODEL_OVERRIDE}`로 단순화하고 별도 주석으로 빈 문자열 가능 여부를 안내하는 것이 나음.

---

### M-3. dev-team 5(A) vs 5(B) — 머지 충돌 처리 정책 불일치

**5(A) 조기 머지** (`skills/dev-team/SKILL.md:349`):
```
충돌 발생 시: 수동 해결 후 `git add` + `git commit --no-edit`
```

**5(B) 전체 머지** (`skills/dev-team/SKILL.md:365`):
```
충돌 발생 시: 사용자에게 보고하고 수동 해결 요청.
60초 후 재확인 (최대 3회). 3회 초과 시 git merge --abort로 건너뛰기.
```

같은 머지 작업이나 충돌 처리 방식이 다름. 5(A)에도 타임아웃 로직을 적용하거나, 의도적 차이라면 그 이유를 명시해야 함.

---

## Low

### L-1. dev-build/dev-refactor — fullstack domain 테스트 명령 누락

**위치**:
- `skills/dev-build/SKILL.md:60-62` — backend, frontend, sidecar만 나열
- `skills/dev-refactor/SKILL.md:60-62` — 동일

`dev-test`에서는 fullstack에 대해 `"backend → frontend → sidecar 순차 실행 (fail-fast)"`으로 명시했으나, build/refactor에서는 fullstack domain을 만났을 때의 안내가 없음.

---

### L-2. plugin.json `skills` 배열 유효성

`plugin.json`에 `"skills"` 배열이 추가되었으나, 기존 스펙에서 이 필드가 공식 지원되는지 확인 필요. 기존에는 `keywords`만 있었음.

---

## 요약

| 심각도 | 건수 | 핵심 |
|--------|------|------|
| Critical | 2 | 모델 전파 다이어그램 Sonnet↔Opus 불일치, signal-helper wait running 미지원 |
| High | 4 | acceptance criteria 잔존, fullstack/E2E 불일치, CLAUDE.md 미갱신 (스크립트+테스트) |
| Medium | 3 | agent-pool 경로, config JSON 플레이스홀더, 머지 충돌 처리 불일치 |
| Low | 2 | fullstack 테스트 안내 누락, plugin.json skills 필드 |
