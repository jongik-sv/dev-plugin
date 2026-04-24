# monitor-port-per-project - 설계

## 요구사항 확인
- `monitor-launcher.py`의 PID 파일 키를 포트 기준(`dev-monitor-{port}.pid`)에서 **프로젝트 기준** 키(`dev-monitor-{project_hash}.pid`)로 전환하여, 같은 프로젝트에서는 기존 포트 재사용(idempotent)하고 다른 프로젝트에서는 자동으로 다른 포트를 할당해 동시 실행을 허용한다.
- `--stop`/`--status`는 포트를 모르더라도 `project_root` 기준으로 현재 프로젝트의 서버를 타겟해야 한다.
- 기존 포트 기준 PID 파일과의 하위 호환성을 유지하고, 기존 파일은 마이그레이션 또는 좀비 처리한다.

## 타겟 앱
- **경로**: N/A (단일 앱 — Python 스크립트 레이어, scripts/monitor-launcher.py)
- **근거**: 이 Feature는 UI 없는 백엔드/인프라 변경으로 플러그인 내 단일 Python 스크립트만 수정한다.

## 구현 방향

현재 `pid_file_path(port)` 함수가 반환하는 `dev-monitor-{port}.pid` 경로를 **프로젝트 해시 기반** `dev-monitor-{project_hash}.pid` 로 교체한다. PID 파일에는 `pid`와 `port` 두 값을 JSON 형식으로 함께 저장하여, `--stop`/`--status`가 포트 없이도 동작하게 한다.

포트 자동 할당 전략: `--port`를 명시하지 않으면 기본 포트 7321부터 시작해 `test_port()` 로 사용 가능한 포트를 탐색한다 (7321→7322→...→7399 범위). 찾지 못하면 오류를 반환한다.

기존 포트 기준 PID 파일(`dev-monitor-{port}.pid`)은 레거시 파일 탐지 로직으로 마이그레이션 없이 방치하되, 신규 기동 전 좀비 여부를 확인해 정리한다.

`monitor-server.py`의 `pid_file_path(port)` 함수는 launcher가 기록한 파일과 독립적으로 자체 PID 기록을 담당하므로 **수정하지 않는다** (server는 여전히 포트 기준 PID 파일 사용, 그러나 launcher 파일이 source of truth).

## 파일 계획

**경로 기준:** 프로젝트 루트 기준 (단일 앱이므로 접두어 없음).

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-launcher.py` | 프로젝트 해시 기반 PID 파일 네이밍 + JSON 포맷 PID 파일 + 자동 포트 탐색 + --stop/--status 프로젝트 기반 동작 | 수정 |
| `scripts/test_monitor_launcher.py` | launcher 단위 테스트 — 새 시나리오(프로젝트 해시, 자동 포트 탐색, JSON PID, 레거시 파일 정리) 추가 | 수정 |
| `skills/dev-monitor/SKILL.md` | `--stop`/`--status` 설명에서 "포트 기준" 문구를 "현재 프로젝트 기준" 으로 업데이트 | 수정 |

## 진입점 (Entry Points)

N/A — 백엔드/인프라 Feature로 UI 진입점 없음.

## 주요 구조

### `project_key(project_root: str) -> str`
`hashlib.sha256(abs_project_root.encode()).hexdigest()[:12]` 를 반환하는 순수 함수. 동일 경로 → 동일 해시, 다른 경로 → 충돌 가능성 < 1/4096². 프로젝트 루트는 `os.path.realpath(project_root)` 로 정규화한다.

### `pid_file_path(project_root: str) -> pathlib.Path`
기존 포트 기반 서명 대신 `_TEMP_DIR / f"dev-monitor-{project_key(project_root)}.pid"` 를 반환. launcher 내부에서만 사용한다. (monitor-server.py의 동명 함수와는 별개 역할 — server 측은 그대로 포트 기반 유지)

### `log_file_path(project_root: str) -> pathlib.Path`
`_TEMP_DIR / f"dev-monitor-{project_key(project_root)}.log"` 를 반환. 기존 `log_file_path(port)` 대체.

### `read_pid_record(pid_path: pathlib.Path) -> Optional[dict]`
PID 파일을 JSON으로 파싱하여 `{"pid": int, "port": int}` dict 반환. 레거시(정수만 기록된) 파일은 `{"pid": int, "port": None}` 으로 반환 (port는 알 수 없음). 파싱 실패 시 None.

### `find_free_port(start: int = 7321, end: int = 7399) -> Optional[int]`
`start`~`end` 범위에서 `test_port()` 로 첫 번째 사용 가능한 포트를 반환. 없으면 None.

### `main()` 변경 사항
- 기동 경로: `pid_file_path(project_root)` 로 프로젝트 PID 파일 확인 → 존재+생존 시 idempotent 재사용(기존 포트 재출력) → `--port` 미지정이면 `find_free_port()` 로 포트 자동 탐색 → 기동 후 JSON PID 파일 기록.
- `--stop`/`--status`: `--port` 지정 시 기존 동작 유지, 미지정 시 프로젝트 PID 파일에서 port를 읽어 동작.

## 데이터 흐름

입력(`project_root`) → `project_key()` 해시 → `pid_file_path(project_root)` 경로 → JSON PID 파일 `{pid, port}` 읽기/쓰기 → `is_alive(pid)` 확인 → 포트 재사용 또는 `find_free_port()` 탐색 → `start_server(port, ...)` 기동.

## 설계 결정 (대안이 있는 경우만)

### PID 파일 포맷
- **결정**: JSON `{"pid": N, "port": N}` 포맷으로 변경
- **대안**: 두 줄 텍스트(`pid\nport`), 또는 두 파일(`*.pid` + `*.port`)
- **근거**: JSON은 파싱 안전성이 높고 필드 추가가 용이하며, 레거시(정수 텍스트) 폴백도 단일 함수에서 처리 가능

### 포트 자동 탐색 범위
- **결정**: 7321~7399 (79개 슬롯)
- **대안**: OS에 맡기는 랜덤 포트(`port=0` bind)
- **근거**: 예측 가능한 범위가 방화벽/프록시 설정에 편리하고, 사용자가 URL을 예측하기 쉬움. 79개 프로젝트 동시 실행은 실용 범위를 초과하므로 충분하다

### monitor-server.py 미수정
- **결정**: server의 `pid_file_path(port)` 는 그대로 유지
- **대안**: server 측도 프로젝트 해시 기반으로 통합
- **근거**: server는 SIGTERM 핸들러에서 자체 PID 파일을 정리하는 역할이며, launcher의 project PID 파일과 역할이 다름. 수정 범위를 최소화해 회귀를 줄인다

### 레거시 PID 파일 처리
- **결정**: 마이그레이션 없이 방치, 신규 기동 시 좀비 여부만 확인
- **대안**: 기존 `dev-monitor-{port}.pid` 파일을 마이그레이션하여 프로젝트 해시 파일로 전환
- **근거**: 구 파일에서 project_root 정보를 역추적할 방법이 없으므로 마이그레이션 불가. 좀비 파일은 기동 시 자동 정리되므로 사용자 영향 없음

## 선행 조건
- 없음 (Python stdlib `hashlib` 만 추가 사용, 외부 의존성 없음)

## 리스크

- **LOW**: `os.path.realpath()`가 심볼릭 링크를 해소하므로, 동일 물리 경로를 다른 symlink 경로로 접근하면 동일 해시가 산출된다. 이는 의도된 동작이다.
- **LOW**: 7321~7399 범위가 모두 점유된 경우(79개 프로젝트 동시 실행) 기동 실패. 실용적으로 발생 가능성 없으며, 오류 메시지에서 `--port` 명시 사용을 안내하면 충분하다.
- **MEDIUM**: 기존 `test_monitor_launcher.py` 가 `pid_file_path(port)` 시그니처에 의존하는 테스트가 있을 경우 시그니처 변경으로 인해 테스트 수정 필요. Build 단계에서 기존 테스트 보존 및 신규 테스트 추가를 병행한다.
- **LOW**: Windows에서 `os.path.realpath()` 가 UNC 경로(`\\server\share`)를 반환할 수 있으나, 해시 입력은 문자열이므로 동작에는 영향 없다.

## QA 체크리스트

- [ ] 같은 `project_root`로 두 번 기동 시 두 번째 호출은 idempotent(새 프로세스 생성 안 함)하며 기존 포트의 URL을 출력한다.
- [ ] 다른 `project_root`로 기동 시 다른 포트(≠ 7321)가 자동 할당되어 두 서버가 동시 실행된다.
- [ ] `--stop` (포트 미지정)이 현재 프로젝트의 서버만 종료하고 다른 프로젝트 서버에는 영향을 주지 않는다.
- [ ] `--status` (포트 미지정)가 현재 프로젝트의 실행 여부 및 포트를 출력한다.
- [ ] `--port N` 명시 시 기존 동작(포트 고정)이 유지된다.
- [ ] `project_key()` 함수가 동일 경로(realpath 정규화 포함)에 대해 동일 해시를 반환한다.
- [ ] JSON PID 파일 `{"pid": N, "port": N}` 이 정상 기록되고 파싱된다.
- [ ] 레거시 정수 PID 파일이 존재할 때 `read_pid_record()` 가 `{"pid": int, "port": None}` 을 반환하고 기동 플로우를 차단하지 않는다.
- [ ] 좀비 PID 파일(파일 존재 + 프로세스 종료) 정리 후 새 서버가 정상 기동된다.
- [ ] 7321~7399 범위가 모두 점유된 경우 오류 메시지와 함께 종료된다.
- [ ] `--stop --port N` 명시 시 기존 포트 기준 종료 동작이 유지된다.
- [ ] `--status --port N` 명시 시 기존 포트 기준 상태 조회 동작이 유지된다.
