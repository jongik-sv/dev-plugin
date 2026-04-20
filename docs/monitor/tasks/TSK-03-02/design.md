# TSK-03-02: 통합 시나리오 QA + Windows(psmux) 검증 - 설계

## 요구사항 확인

PRD §7 P4 / TRD §10.2, §10.3에서 정의한 5종 수동 QA 시나리오를 실행하고 결과를 `docs/monitor/qa-report.md`에 기록한다. macOS는 현 개발 환경에서 직접 검증하고, Linux/WSL2/Windows(psmux)는 접근 가능한 환경에서 검증하되 없으면 "미검증" 명시한다. QA 중 소스 파일(state.json, wbs.md, signal 파일)을 수정하지 않는 Read-Only 보장도 함께 확인한다. 또한 PRD §8 T1/T2(refresh 간격·pane 캡처 라인 수 기본값)를 확정하여 코드에 반영한다.

## 타겟 앱

- **경로**: N/A (단일 앱 — 플러그인 루트 기준 단일 Python 파일 스크립트)
- **근거**: QA/검증 Task이므로 별도 앱 경로 없음. 검증 대상은 `scripts/monitor-server.py`, `skills/dev-monitor/SKILL.md`이며 결과물은 `docs/monitor/qa-report.md`.

## 구현 방향

TSK-03-02의 "구현"은 코드 작성이 아니라 **QA 절차 실행 + 결과 기록**이다.

1. **QA 환경 준비**: 테스트 픽스처(빈 docs 트리, 손상 state.json, 실행 중인 dev-team 시뮬레이션)를 스크립트로 만들어 재현 가능하게 한다.
2. **5종 시나리오 순차 실행**: 각 시나리오마다 기동 → curl/브라우저 확인 → 서버 종료 흐름을 따른다.
3. **플랫폼 매트릭스 문서화**: macOS에서 모든 시나리오를 실행 후 결과를 기록하고, 나머지 플랫폼은 접근 가능성에 따라 Pass 또는 "미검증"으로 표기한다.
4. **PRD §8 T1/T2 결정**: QA 실행 중 refresh 간격(3s vs 5s)과 pane 라인 수(500 vs 1000)를 실제 사용성으로 판단하고 기본값을 확정하여 코드에 반영한다.
5. **결함 분리**: 발견된 결함은 qa-report.md에 기록하고 별도 WBS Task 또는 이슈로 분리한다.
6. **FD 누수 확인**: `lsof -p {pid}`로 장시간 실행 중 FD 증가 여부를 확인한다.

## 파일 계획

**경로 기준:** 모든 파일 경로는 **프로젝트 루트 기준**으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `docs/monitor/qa-report.md` | QA 시나리오 5종 실행 결과, 플랫폼 매트릭스, T1/T2 결정, 발견 결함 목록 | 신규 |
| `scripts/test_qa_fixtures.py` | QA 픽스처 생성/정리 헬퍼 (빈 docs 트리, 손상 state.json, 임시 신호 파일 등) — 재현 가능한 테스트 환경 제공 | 신규 |
| `scripts/monitor-server.py` | PRD §8 T1(refresh 기본값 3초), T2(pane 라인 수 기본값 500) 확정 후 argparse 기본값 반영 | 수정 |

> 비-UI Task이므로 라우터/메뉴 파일 항목 없음.

## 진입점 (Entry Points)

N/A — domain이 `infra`인 비-UI Task.

## 주요 구조

- **`test_qa_fixtures.py`**: QA 픽스처 생성/정리 클래스. `EmptyProjectFixture`, `CorruptedStateFixture`, `PortConflictFixture` 등 컨텍스트 매니저로 제공. QA 실행자가 임시 디렉터리에 독립된 테스트 환경을 구성할 수 있게 함.
- **QA 실행 절차 (qa-report.md)**: 시나리오별 실행 명령, 기대 결과, 실제 결과, Pass/Fail 판정을 표 형태로 기록.
- **T1/T2 결정 섹션 (qa-report.md)**: 3s/5s 비교 관찰 결과 + 500/1000 라인 비교 결과를 기술하고 결정값을 명시.
- **플랫폼 매트릭스 표 (qa-report.md)**: macOS/Linux/WSL2/Windows(psmux) × 시나리오 5종의 결과 행렬.
- **결함 목록 (qa-report.md)**: 발견 결함 ID, 설명, 심각도, 재현 방법, 권장 조치를 기술.

## 데이터 흐름

QA 실행자 → `test_qa_fixtures.py`로 픽스처 생성 → monitor-server.py 기동 → curl/브라우저로 응답 확인 → 결과를 `qa-report.md`에 기록 → 서버 종료 및 픽스처 정리.

## 설계 결정 (대안이 있는 경우만)

- **결정**: QA 픽스처를 별도 `test_qa_fixtures.py` 스크립트로 분리
- **대안**: qa-report.md에 수동 명령어만 기술하고 픽스처 자동화 없음
- **근거**: 재현 가능성과 Read-Only 보장 검증(chmod 0o444 테스트)을 위해 픽스처 스크립트가 필요하며, 단위 테스트 패턴(`test_monitor*.py`)과 일관성 유지.

---

- **결정**: PRD §8 T1 refresh 기본값 = **3초**, T2 pane 라인 수 = **500**
- **대안**: T1=5초, T2=1000
- **근거**: 3초는 개발 중 빠른 피드백을 제공하고 서버 부하가 무시할 수준. 500라인은 대부분 터미널 세션에서 충분하며 대용량 pane 캡처 시 지연을 줄인다. QA 실행 중 최종 확인 후 이 결정값을 `monitor-server.py` argparse 기본값으로 확정.

## 선행 조건

- TSK-02-01 완료: `skills/dev-monitor/SKILL.md` 본문 + monitor-server.py 기동/PID 관리 구현
- TSK-02-02 완료: `--stop` / `--status` 서브커맨드 구현
- TSK-01-05 완료: `/pane/{id}`, `/api/pane/{id}` 엔드포인트 구현
- TSK-01-06 완료: `/api/state` JSON 스냅샷 엔드포인트 구현
- macOS 개발 환경에 tmux 설치 (시나리오 2의 Team 에이전트 섹션 검증 목적)

## 리스크

- **MEDIUM**: Windows native(psmux) 환경 미접근 — 환경 제약 시 해당 플랫폼 결과를 "미검증"으로 명시. macOS + Linux 통과로 acceptance 조건 충족 가능.
- **MEDIUM**: 시나리오 2(`/dev-team` 실행 중 검증)는 실제 dev-team 실행 상태를 필요로 함 — 실 WBS Task가 없으면 signal 파일·state.json 픽스처로 시뮬레이션. tmux session + 더미 WBS 구조로 재현.
- **LOW**: PRD §8 T1/T2 결정 후 `monitor-server.py` argparse 기본값 변경이 기존 테스트와 충돌할 수 있음 — 단위 테스트에서 `--refresh-seconds`/`--max-pane-lines` 명시 인자로 호출하도록 수정.
- **LOW**: `lsof` 미설치 환경(일부 Linux minimal) — FD 누수 확인에 대한 대체 방법(`/proc/{pid}/fd/` 직접 확인) 병기.

## QA 체크리스트

### 시나리오별 검증 항목

- [ ] **시나리오 1 — 빈 프로젝트**: `docs/tasks/`와 `docs/features/`가 비어 있는 상태에서 `GET /` 응답 HTML에 "no tasks" 또는 "no features" 안내 문구가 포함되고 HTTP 200이 반환된다.
- [ ] **시나리오 2 — dev-team 실행 중**: 실행 중인 state.json + signal 파일 + tmux pane이 있을 때 `/` HTML에 WBS 섹션, Team 에이전트 섹션, Signal 섹션이 모두 채워진 상태로 렌더링된다.
- [ ] **시나리오 3 — feat 실행 중**: `docs/features/{name}/state.json`이 존재할 때 `/` HTML에 Feature 섹션이 표시된다.
- [ ] **시나리오 4 — state.json 손상**: 손상된 state.json이 있는 Task만 ⚠️ 배지로 표시되고 나머지 Task는 정상 렌더링된다.
- [ ] **시나리오 5 — 포트 충돌 재기동**: 이미 기동 중인 포트로 `/dev-monitor` 재실행 시 기존 PID 재사용 안내가 출력되고 새 프로세스가 생성되지 않는다.

### 플랫폼 검증 항목

- [ ] **macOS**: 5종 시나리오 전체 Pass 또는 결함 분리 완료.
- [ ] **Linux(또는 WSL2)**: 시나리오 1~3 최소 Pass 또는 "미검증" 명시. (환경 접근 가능 시)
- [ ] **Windows(psmux)**: `detect_mux()` 실행 결과 psmux 인식 여부 기록, `capture-pane` 동작 확인 또는 "미검증" 명시.

### Read-Only 보장 검증

- [ ] QA 시나리오 전/후 `git diff` 실행 시 QA 결과물(`qa-report.md`) 외 state.json, wbs.md, signal 파일의 수정이 0건이다.
- [ ] `os.chmod 0o444`로 state.json 읽기 전용 설정 후 `GET /` 요청이 해당 Task만 에러 표시하고 서버는 계속 동작한다.

### FD 누수 확인

- [ ] monitor-server.py를 기동하고 연속으로 30회 이상 `GET /` 요청 후 `lsof -p {pid} | wc -l` 값이 초기 대비 유의미하게 증가하지 않는다 (FD 누수 없음).

### PRD §8 T1/T2 결정 검증

- [ ] `monitor-server.py`의 `--refresh-seconds` argparse 기본값이 3으로 설정되어 있고 `<meta http-equiv="refresh" content="3">` 태그가 HTML에 포함된다.
- [ ] `monitor-server.py`의 `--max-pane-lines` argparse 기본값이 500으로 설정되어 있고 pane 캡처 결과에 최대 500라인이 적용된다.

### qa-report.md 완성 검증

- [ ] `docs/monitor/qa-report.md` 파일이 생성되고 5종 시나리오 결과 표, 플랫폼 매트릭스 표, T1/T2 결정 근거, 결함 목록(0건 이상)이 포함된다.
