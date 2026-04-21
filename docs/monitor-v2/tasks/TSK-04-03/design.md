# TSK-04-03: 4-플랫폼 Smoke 테스트 (macOS / Linux / WSL2 / Windows psmux) - 설계

## 요구사항 확인
- 각 플랫폼(macOS / Linux / WSL2 / Windows psmux)에서 dev-monitor를 기동하고 대시보드 로드 → 드로어 열기 → pane 출력 2초 폴링을 검증한다.
- tmux 미설치 환경에서 "tmux not available" 안내가 Team 섹션에 정상 표시되는지 확인한다.
- Windows psmux 환경에서 `sys.executable` 사용으로 rc=9009(MS Store App Execution Alias 간섭) 없이 서버가 기동됨을 확인한다.

## 타겟 앱
- **경로**: N/A (단일 앱)
- **근거**: 이 프로젝트는 모노레포 구조가 없으며 단일 Python 패키지이다.

## 구현 방향
- 플랫폼별 smoke 테스트 절차를 정의한 `scripts/test_platform_smoke.py`를 신규 작성한다.
- 테스트는 `monitor-launcher.py`를 통해 서버를 기동하고, `urllib.request`로 HTTP 요청을 보내 응답을 검증한다.
- tmux 미설치 시나리오는 `--no-tmux` 플래그로 시뮬레이션하며, Team 섹션에 "tmux not available" 문자열이 포함되는지 확인한다.
- Windows psmux 경로는 `monitor-launcher.py`의 `start_server()`가 `sys.executable`을 사용하는지 단위 테스트로 검증한다.
- 플랫폼별 결함은 `docs/monitor-v2/tasks/TSK-04-03/qa-report.md`에 기록한다.

## 파일 계획

**경로 기준:** 모든 파일 경로는 **프로젝트 루트 기준**으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/test_platform_smoke.py` | 4-플랫폼 Smoke 테스트 — 서버 기동→HTTP 요청→섹션 검증→드로어 API→폴링 확인의 전체 흐름. `unittest.TestCase` 기반 | 신규 |
| `docs/monitor-v2/tasks/TSK-04-03/qa-report.md` | 플랫폼별 Smoke 실행 결과 및 결함 기록 | 신규 |

## 진입점 (Entry Points)
N/A (domain=test, 비-UI Task)

## 주요 구조

- **`SmokeTestBase(unittest.TestCase)`**: 서버 기동/정지 공통 로직 (`setUpClass`/`tearDownClass`). `monitor-launcher.py`를 `sys.executable`로 subprocess 호출하여 포트 7399에 기동. 기동 후 최대 5초 HTTP 헬스체크 폴링.
- **`test_dashboard_loads()`**: `GET /` 응답 200, HTML에 `<section data-section="kpi">` 존재 확인.
- **`test_no_tmux_section()`**: `--no-tmux` 플래그로 기동된 서버에서 `GET /` 응답 Body에 `"tmux not available"` 문자열 포함 확인.
- **`test_drawer_api()`**: `GET /api/state` 응답 JSON 파싱 성공 (200 + `application/json` Content-Type).
- **`test_pane_polling_interval()`**: `GET /` 응답 HTML에 폴링 관련 JS 코드(`setInterval` 또는 `fetch`) 존재 확인. 2초 폴링 최솟값 상수(`minInterval = 2000`) 또는 해당 상수명 존재 확인.
- **`test_sys_executable_used()`**: `monitor-launcher.py` 소스 코드를 읽어 `sys.executable`이 서버 기동 명령에 사용됨을 단위 검증 (소스 grep 방식, 플랫폼 무관 통과).

## 데이터 흐름
`test_platform_smoke.py` → `monitor-launcher.py` subprocess 기동 → `monitor-server.py` HTTP 서버 대기 → `urllib.request` GET 요청 → 응답 Body/헤더 검증 → tearDown에서 `--stop`으로 정지.

## 설계 결정 (대안이 있는 경우만)

- **결정**: 테스트 포트로 7399를 사용 (기본 7321 대신)
- **대안**: 기본 포트 7321 사용
- **근거**: 기존 dev-monitor 인스턴스와 포트 충돌 없이 테스트를 격리하기 위함.

- **결정**: tmux 미설치 시나리오를 `--no-tmux` 플래그로 시뮬레이션
- **대안**: 실제 tmux 바이너리를 PATH에서 제거
- **근거**: PATH 조작은 테스트 환경 오염 위험이 있으며, `--no-tmux` 플래그가 동일한 코드 경로를 실행하므로 충분하다.

- **결정**: `test_sys_executable_used()`를 런타임 subprocess 검증 대신 소스 코드 텍스트 검증으로 구현
- **대안**: Windows 환경에서만 실제 `python3` 하드코딩 유무를 subprocess 결과로 검증
- **근거**: 소스 코드 검증은 모든 플랫폼에서 동일하게 실행되며, Windows psmux 환경 없이도 rc=9009 방지 규약 준수 여부를 확인할 수 있다.

## 선행 조건
- TSK-04-02 (dev-monitor v2 구현 완료): `monitor-server.py`의 `_section_team`, `--no-tmux` 플래그, `/api/state` 엔드포인트, 폴링 JS 코드가 존재해야 한다.
- Python 3.8+ stdlib (`unittest`, `urllib.request`, `subprocess`, `sys`, `time`, `pathlib`)

## 리스크

- **MEDIUM**: Windows psmux 환경은 CI에서 자동화하기 어려워 수동 실행이 필요하다. 테스트는 3+ 플랫폼(macOS + Linux + Windows) 통과를 목표로 하며 WSL2 누락은 허용된다.
- **MEDIUM**: `setUpClass`에서 서버 기동 후 HTTP가 준비될 때까지 폴링하는 대기 로직(최대 5초)이 필요하다. 느린 환경에서 타임아웃이 발생할 수 있으므로 최대 대기 시간을 10초로 설정하는 것을 검토한다.
- **LOW**: 7399 포트가 이미 사용 중인 경우 테스트가 실패한다. `test_port()` 사전 체크를 `setUpClass`에 추가하여 명확한 에러 메시지를 제공한다.
- **LOW**: `_DASHBOARD_JS`에서 폴링 간격 상수명이 변경될 경우 `test_pane_polling_interval()`이 깨질 수 있다. 상수명보다 `"2000"` 리터럴 숫자 또는 `"setInterval"` 존재 여부를 검증하는 것이 더 안정적이다.

## QA 체크리스트

- [ ] **정상 케이스**: `GET /` 응답이 200 OK이며, HTML에 `<section data-section="kpi">` 태그가 존재한다.
- [ ] **정상 케이스**: `GET /api/state` 응답이 200 OK이며, `Content-Type: application/json` 헤더와 파싱 가능한 JSON body를 반환한다.
- [ ] **정상 케이스**: 서버가 `--no-tmux` 플래그 없이 기동될 때 Team 섹션이 정상 렌더링된다 (panes 없으면 "no tmux panes running" 표시).
- [ ] **엣지 케이스**: `--no-tmux` 플래그로 기동된 서버의 대시보드 HTML에 `"tmux not available"` 문자열이 포함된다.
- [ ] **엣지 케이스**: 폴링 간격 최솟값 2초 관련 JS 코드(`2000` 또는 `setInterval`)가 대시보드 HTML에 존재한다.
- [ ] **정상 케이스**: `monitor-launcher.py` 소스에서 서버 subprocess 기동 시 `sys.executable`이 사용되어 있다 (python3 하드코딩 없음).
- [ ] **통합 케이스**: `SmokeTestBase.setUpClass` — 서버가 10초 이내에 HTTP 요청에 응답한다.
- [ ] **통합 케이스**: `SmokeTestBase.tearDownClass` — `--stop` 명령으로 서버가 정상 종료되고 PID 파일이 삭제된다.
- [ ] **에러 케이스**: 포트 7399가 이미 사용 중이면 `setUpClass`에서 명확한 에러 메시지와 함께 테스트를 스킵한다.
