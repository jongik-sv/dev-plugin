# Phase Verification Protocol

DDTR 사이클의 각 phase가 ``.ok`` DFA 전이를 시도하기 직전에 통과해야 하는 verification 게이트 정의. ``"should pass"`` / ``"looks good"`` / ``"Done!"`` 같은 무근거 종료 선언을 차단하고, phase 종료 시점의 산출물 상태를 ``state.json.phase_history``에 footer로 기록해 사후 감사를 가능케 한다.

## 호출 흐름

```
[phase end of dev-design / dev-build / dev-test / dev-refactor]
   │
   ├─ 1) (dynamic) 테스트·lint·typecheck 명령 실행 (기존 흐름)
   │
   ├─ 2) verify-phase.py 호출
   │      python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verify-phase.py \
   │        --phase {design|build|test|refactor} \
   │        --target {DOCS_DIR}/tasks/{TSK-ID}     # WBS
   │        # or --target {FEAT_DIR}                # Feature
   │        --check unit_test:ok:exit=0,pass=42,fail=0 \
   │        --check e2e_test:ok:exit=0,pass=8,fail=0 \
   │        --check lint:ok:exit=0
   │      → JSON footer to stdout, exit 0 (ok) or 1 (fail)
   │
   ├─ 3) ok=false 시: 전이 차단, phase에 머무름. footer.checks의 실패 항목 수정 후 재시도.
   │
   └─ 4) ok=true 시: footer를 임시 파일에 저장 후 wbs-transition.py에 --verification 전달
          python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-transition.py \
            {DOCS_DIR}/wbs.md TSK-04-02 build.ok \
            --verification /tmp/verify-build-04-02.json
          → state.json의 새 phase_history entry에 verification 필드 합성
```

## 구조 검사 (Phase별)

verify-phase.py가 자동으로 수행하는 결정적 검사. 외부 명령 실행 없이 산출물의 존재·형식만 확인한다.

| Phase | Structural checks |
|---|---|
| design | `design.md` 존재 / `## Implementation Steps` 섹션 존재 / 체크박스 (`- [ ]` 또는 `- [x]`) ≥ 1 |
| build | `design.md` 존재 / 실행된 체크박스 (`- [x]`) ≥ 1 (build phase에서 최소 한 개 step 완료) |
| test | `design.md` 존재 / `test-report.md` 존재 / `test-report.md` 체크박스 ≥ 1 |
| refactor | `test-report.md` 존재 / `refactor.md` 존재 / `refactor.md` 체크박스 ≥ 1 |

## 동적 검사 (`--check` 플래그)

SKILL.md가 외부에서 실행한 명령 결과를 ``--check NAME:ok|fail[:KEY=VAL,...]`` 형식으로 verify-phase.py에 합성 입력한다.

### 권장 동적 체크 (Phase별)

| Phase | 권장 동적 체크 (있으면) |
|---|---|
| design | (없음 — 정적 산출물만) |
| build | `red_green:ok:steps=N` (TDD red-green 단계 수) |
| test | `unit_test:ok:exit=0,pass=N,fail=0` / `e2e_test:ok:exit=0,pass=N,fail=0` |
| refactor | `unit_test:ok:exit=0,pass=N,fail=0` (regression 확인) / `lint:ok:exit=0` / `typecheck:ok:exit=0` |

### Meta key 규약

| Key | 의미 |
|---|---|
| `exit` | 명령 종료 코드 |
| `pass` | 통과 테스트 수 |
| `fail` | 실패 테스트 수 |
| `command` | 실행한 명령 문자열 (따옴표로 감싸 콤마 보존 가능) |
| `duration_seconds` | 실행 시간 (선택) |
| `steps` | red-green 사이클 횟수 등 phase-specific 메트릭 |

## Footer 스키마

verify-phase.py 표준 출력. ``state.json.phase_history``의 latest entry에 그대로 합성된다.

```json
{
  "ok": true,
  "phase": "test",
  "verified_at": "2026-04-28T12:34:56Z",
  "checks": [
    {"name": "design.md_exists", "kind": "structural", "ok": true, "path": "..."},
    {"name": "test-report.md_exists", "kind": "structural", "ok": true, "path": "..."},
    {"name": "test-report.md_checkbox_min_1", "kind": "structural", "ok": true, "count": 5, "required": 1},
    {"name": "unit_test", "kind": "dynamic", "ok": true, "exit": 0, "pass": 42, "fail": 0, "command": "pytest -q"},
    {"name": "e2e_test", "kind": "dynamic", "ok": true, "exit": 0, "pass": 8, "fail": 0}
  ]
}
```

## state.json 통합 후 모습

```json
{
  "status": "[ts]",
  "phase_history": [
    { "event": "design.ok", "from": "[ ]", "to": "[dd]", "at": "...", "verification": { "ok": true, ... } },
    { "event": "build.ok",  "from": "[dd]", "to": "[im]", "at": "...", "verification": { "ok": true, ... } },
    { "event": "test.ok",   "from": "[im]", "to": "[ts]", "at": "...", "verification": { "ok": true, ... } }
  ]
}
```

## 차단 규칙

- ``verify-phase.py`` exit 1 (ok=false) 시 SKILL.md는 ``wbs-transition.py``의 ``.ok`` 이벤트를 호출하지 않는다.
- 대신 footer.checks의 실패 항목을 수정하고 phase를 재실행한다.
- 실패 footer 자체는 ``wbs-transition.py {phase}.fail --verification``로 전달해 ``phase_history``에 기록할 수 있다 (의존성 분석에 영향 없음).

## 합리화 거부 항목

다음 사고 패턴은 verification 게이트 우회의 신호다:
- "should pass" / "probably works" / "looks correct"
- 이전 실행 결과로 현재 통과 단정
- "agent reported success" — 실제 산출물·종료 코드 확인 없이 신뢰
- "just this once" — 일회성 면제

게이트가 차단되면 **수정 후 재실행**이 유일한 정답이다.
