# Domain별 테스트 명령

테스트 명령은 프로젝트의 wbs.md `## Dev Config` 섹션에서 정의된다.

## 설정 로드

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wbs-parse.py {DOCS_DIR}/wbs.md - --dev-config
```

JSON 출력에 `error` 키가 있으면 에러 메시지를 사용자에게 그대로 출력하고 종료한다.

## 단위 테스트

- `domains[{domain}].unit_test`가 null이 아니면: 해당 명령을 실행
- `domains[{domain}].unit_test`가 null이면: "N/A — {domain} domain"으로 기록
- domain이 `fullstack`이면: `fullstack_domains` 목록의 각 domain에 대해 unit_test를 순차 실행 (fail-fast: 첫 domain 실패 시 중단)

## E2E 테스트

- `domains[{domain}].e2e_test`가 null이 아니면: 해당 명령을 실행. 실행 실패(명령 없음, 스크립트 없음 등)는 N/A가 아니라 실패로 기록
- `domains[{domain}].e2e_test`가 null이면: "N/A — {domain} domain"으로 기록
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
- 출력은 마지막 200줄만 캡처된다 (tail -200 불필요).

## 출력 제한

`run-test.py`가 마지막 200줄만 출력하므로 별도 `tail` 불필요.
전체 통과 시에는 요약 줄(통과/실패 수)만 보고한다.
