# Domain별 테스트 명령

테스트 명령은 프로젝트의 Dev Config에서 정의된다. **SOURCE에 따라 로드 경로가 다르다.**

## 설정 로드

**SOURCE=wbs** (WBS 모드):
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md - --dev-config
```
JSON 출력에 `error` 키가 있으면 에러 메시지를 사용자에게 그대로 출력하고 종료한다 (WBS 모드는 반드시 wbs.md에 Dev Config가 있어야 한다).

**SOURCE=feat** (Feature 모드 — fallback chain):
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py --feat {FEAT_DIR} --dev-config {DOCS_DIR}
```
우선순위:
1. `{FEAT_DIR}/dev-config.md` — Feature별 로컬 오버라이드
2. `{DOCS_DIR}/wbs.md`의 `## Dev Config` 섹션
3. `${CLAUDE_PLUGIN_ROOT}/references/default-dev-config.md` — 전역 기본값

`source` 필드(`feat-local`/`wbs`/`default`)로 적용된 설정을 확인할 수 있다. Feature 모드는 fallback chain에 의해 `error`가 거의 발생하지 않는다 (플러그인 설치가 손상된 경우만 예외).

## 단위 테스트

- `domains[{domain}].unit_test`가 null이 아니면: 해당 명령을 실행
- `domains[{domain}].unit_test`가 null이면: "N/A — {domain} domain"으로 기록
- domain이 `fullstack`이면: `fullstack_domains` 목록의 각 domain에 대해 unit_test를 순차 실행 (fail-fast: 첫 domain 실패 시 중단)

## E2E 테스트

- `domains[{domain}].e2e_test`가 null이 아니면: 해당 명령을 실행. 실행 실패(명령 없음, 스크립트 없음 등)는 N/A가 아니라 실패로 기록
- `domains[{domain}].e2e_test`가 null이면 **도메인에 따라 처리가 달라진다** (v1.4.1부터, lect 사고 대응):
  - **frontend / fullstack 도메인**: 설정 공백으로 간주하여 **`test.fail`**. UI 도메인은 E2E 명령 누락을 silent skip으로 처리하지 않는다. 이 차단은 `skills/dev-test/SKILL.md` **단계 1-5 (UI E2E 정합성 게이트)**에서 서브에이전트 스폰 전에 수행된다
  - **그 외 도메인** (backend, default 등): "N/A — {domain} domain"으로 기록하고 계속 진행
- **명시적 skip (권장 X)**: UI 도메인에서도 고의로 E2E를 건너뛰려면 `e2e-test` 칸에 명시적 placeholder 명령을 쓴다:
  - 크로스플랫폼 권장: `python3 -c "pass"`
  - 지양: `/bin/true` (Windows에서 실패, macOS/Linux 전용)
  - 이유: 파일에 흔적이 남아 PR 리뷰에서 "왜 E2E를 skip했나?"를 포착 가능
- **design.md UI 키워드 재분류**: dev-design이 domain을 "default"나 "backend"로 라벨링했어도 design.md 본문에 UI 키워드(button/click/render/form/Playwright/화면/버튼…)가 있으면 dev-test 단계 1-5가 `effective_domain = frontend`로 재라벨링하여 본 규칙을 적용한다. 자세한 키워드 목록과 알고리즘은 `skills/dev-test/SKILL.md` 단계 1-5 참조
- domain이 `fullstack`이면: `fullstack_domains` 목록의 각 domain에 대해 e2e_test를 순차 실행 (fail-fast: 첫 domain 실패 시 중단)

## 실행 래핑

모든 테스트 명령은 `run-test.py`로 감싸서 실행한다:

**단위 테스트**:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/run-test.py 300 -- {단위 테스트 명령}
```

**E2E 테스트**:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/run-test.py 900 -- {E2E 테스트 명령}
```

- 첫 번째 인자: 타임아웃 초. 단위 테스트 300초(5분), E2E 테스트 900초(15분).
- 테스트 프로세스를 새 프로세스 그룹으로 실행하고, 완료/타임아웃/시그널 시 프로세스 그룹 전체를 kill한다.
- exit code 124 = 타임아웃 — 테스트 실패로 기록한다.

## 출력 제한

**단일 소스**: `run-test.py`가 출력 truncation을 **내부에서 확정적으로 처리**한다.

- 구현: `scripts/run-test.py`에서 `deque(maxlen=TAIL_LINES)`(`TAIL_LINES = 200`)로 스트리밍 캡처. 테스트 명령이 10,000줄을 출력해도 메모리에는 항상 마지막 200줄만 남고, 이후 `for line in tail: print(line)` 루프로 stdout에 200줄만 방출된다.
- 결과: 호출자(Claude, 스킬, 서브에이전트)는 `tail -200` 등 추가 truncation을 걸 필요가 **없고 걸어서도 안 된다**. 래퍼 외부의 중복 truncation은 일관성을 깨고 컨텍스트 폭발 방어 지점을 분산시킨다.
- 전체 통과 시에는 요약 줄(통과/실패 수)만 보고한다.

> 본 섹션이 truncation 정책의 **유일한 공식 정의**다. 다른 스킬/문서는 이 섹션만 참조한다.
