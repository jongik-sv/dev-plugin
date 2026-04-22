# TSK-00-01: Signal scope 구조 subdir-per-scope 변경 - 설계

## 요구사항 확인
- `scan_signals()`가 `${TMPDIR}/claude-signals/` 하위를 **subdir 단위로 쪼개 스캔**하고 각 `SignalEntry.scope`에 `"shared"` 평탄화 대신 **해당 subdir 이름**을 기록한다 (PRD §2 P0-1 / TRD §3.3).
- `agent-pool:{timestamp}` 버킷은 기존 그대로 유지. 표시 측면(`_classify_signal_scopes` 분류 규칙)도 불변이므로 `agent-pool:` 외 모든 scope는 shared 버킷으로 들어가 대시보드 카운트에 regression이 없어야 한다.
- `scan_signals`의 입력 트리가 `claude-signals/` 바로 아래에 파일만 있는(subdir 없는) 형태여도 기존처럼 동작해야 한다 (하위 호환).

## 타겟 앱
- **경로**: N/A (단일 앱 — dev-plugin 리포지토리의 `scripts/` 하위 단일 모듈).
- **근거**: 대상이 `scripts/monitor-server.py` 한 파일이며 앱 디렉터리 구조(`apps/*`, `packages/*`)가 없는 flat 레이아웃.

## 구현 방향
- `scan_signals()`의 "(A) Shared scope — recursive walk under claude-signals/" 블록을 제거하고, `claude-signals/` 루트의 **직하 엔트리**를 순회한다.
  - 직하 엔트리가 **디렉터리**이면 그 디렉터리 이름을 scope 값으로 삼아 `_walk_signal_entries(subdir, scope=subdir_name)` 호출.
  - 직하 엔트리가 **파일**이면 기존 호환을 위해 `scope="shared"`로 기록 (bare-file fallback; 기존 테스트 `test_done_signal_in_shared_dir` 등이 `shared/dev/*` 같은 nested 구조를 이미 쓰고 있으므로, 실제로는 대부분 subdir 분기를 탄다. root 직하 bare-file 경로는 안전망.)
- agent-pool 블록(B)은 손대지 않는다.
- `_classify_signal_scopes`의 분류 로직은 변경하지 않는다 (이 Task의 핵심 계약: 표시 불변). 단, 기존에 `shared` 문자열 리터럴에 의존하던 분기가 있으면 유지하되 "그 외도 shared 버킷" 규칙으로 자연스럽게 흡수된다.
- SignalEntry dataclass의 `scope: str` 타입/이름은 그대로, **값의 의미만 "flat 문자열 shared"에서 "subdir 이름"으로 확장**된다.

## 파일 계획

**경로 기준:** 프로젝트 루트 기준.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `scan_signals()` 로직을 subdir-per-scope로 변경. `_walk_signal_entries` / `_signal_entry` / `SignalEntry` 시그니처는 그대로 유지 | 수정 |
| `scripts/test_monitor_signal_scan.py` | 기존 `scope=="shared"` 기대 테스트를 subdir-per-scope 계약에 맞게 갱신 + 신규 acceptance 테스트 `test_scan_signals_scope_is_subdir` 추가 | 수정 |

> 이 Task는 순수 백엔드 스캐너 변경이다 (`domain: backend`). UI/라우터/메뉴 파일 변경 없음.

## 진입점 (Entry Points)

N/A (비-UI Task).

## 주요 구조
- `scan_signals() -> List[SignalEntry]`
  - (A) `cs_root = ${TMPDIR}/claude-signals` 존재 확인 → `os.listdir(cs_root)` 를 정렬 순회.
    - 엔트리가 디렉터리면 `_walk_signal_entries(sub_path, scope=sub_name)`.
    - 엔트리가 파일이면 `_signal_entry(full_path, scope="shared")` 결과가 None이 아닐 때 수집 (확장자 필터는 `_signal_entry`가 처리).
  - (B) agent-pool 블록 변경 없음.
- `_walk_signal_entries` / `_signal_entry` / `SignalEntry`: 시그니처 불변 — 단지 호출자(scan_signals)가 전달하는 scope 값 의미가 바뀔 뿐이다.
- `_classify_signal_scopes(signals) -> (shared, agent_pool)`: **수정하지 않는다.** 이미 "agent-pool: prefix면 agent_pool 버킷, 나머지는 shared 버킷"으로 구현되어 있어, scope가 `"shared"`든 `"proj-a"`든 `"dev-team-foo"`든 모두 shared 버킷에 떨어져 대시보드 카운트/렌더가 불변이다.

## 데이터 흐름
`${TMPDIR}/claude-signals/{subdir}/X.done` (입력) → `scan_signals` 가 `subdir`을 scope로 읽어 SignalEntry 생성 → `_classify_signal_scopes` 가 `agent-pool:` 이외 모든 scope를 shared 버킷으로 분류 → 기존 렌더러(`_section_*`)가 동일한 카운트로 표시 (출력).

## 설계 결정

- **결정**: Root 직하가 **파일**인 경우(예: `claude-signals/X.done`)는 기존 호환으로 `scope="shared"`로 기록한다.
  - **대안**: root 직하 파일을 스캔 대상에서 완전히 제외 (subdir만 허용).
  - **근거**: 기존 `test_unknown_extension_ignored` 같은 테스트가 root 직하에 `TSK-Z.done`을 만들어 스캔되기를 기대한다. 하위 호환을 깨지 않으면서도 TRD §3.3의 subdir-per-scope 요구를 만족시키는 가장 작은 변경.

- **결정**: `_classify_signal_scopes`를 수정하지 않고 "unknown scope → shared 버킷" fallback에 의존한다.
  - **대안**: 명시적으로 `scope == "shared" or not scope.startswith("agent-pool:")` 같은 분기 추가.
  - **근거**: 이미 `_classify_signal_scopes` docstring(§3468)에 "anything else (unknown future scope) → shared (conservative fallback)"이 문서화돼 있고, 이번 subdir 이름도 그 fallback 경로를 그대로 타면 된다. 표시 로직 불변을 가장 깔끔히 보장.

- **결정**: `_walk_signal_entries`는 그대로 두고 단일 subdir 내부는 재귀 스캔을 유지한다.
  - **대안**: subdir 내부도 flat 스캔으로 바꿈.
  - **근거**: 기존 `test_recursive_scan_claude_signals`가 `claude-signals/proj/wp-01/*` 2단계 중첩을 테스트한다. subdir 이름(`proj`)을 scope로 쓰고 그 아래 `wp-01/*`를 재귀로 수집하는 동작이 TRD §3.3 예시 코드(`entries.extend(_walk_signal_entries(sub_path, scope=sub))`)와도 정확히 일치한다.

## 선행 조건
- 없음. `depends: -` (WBS). Python 3 stdlib만 사용.

## 리스크
- **MEDIUM**: 기존 테스트 `ScanSignalsSharedTests.test_*` 4개 중 3개가 `scope == "shared"` 를 직접 검증한다. subdir 구조로 바꾸면 이 assertion을 새 규약(`scope == subdir_name`)으로 갱신해야 하며, 기존 Shared 계약을 참조하는 다른 테스트/모듈이 없는지 grep으로 한 번 더 확인해야 한다. dev-build 단계에서 TDD 순서상 테스트를 먼저 갱신하므로 실패는 조기에 드러난다.
- **LOW**: `_classify_signal_scopes`의 fallback 주석(§3467-3468)에서 "unknown future scope → shared"를 이 Task가 실질적으로 활성화시킨다. 의도된 변경이지만, 주석에 "subdir name도 여기로 들어온다"는 한 줄을 추가해두면 유지보수에 도움이 된다 (선택 사항, 동작에는 영향 없음).
- **LOW**: `/tmp/claude-signals/` 가 공유 디렉터리인 호스트에서 다른 프로젝트가 만든 signal 파일이 이제 `scope="<다른프로젝트 이름>"`으로 노출된다. 표시 불변(shared 버킷 합산)이므로 카운트는 동일하지만, 향후 필터링 UI(TSK-00-03 계열)가 이 값을 그대로 노출할 때 프라이버시 이슈가 될 수 있음 — 이번 Task 범위 밖.

## QA 체크리스트
dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

- [ ] (정상 — acceptance) `/tmp/claude-signals/proj-a/X.done` 생성 시 `scan_signals()` 결과 엔트리의 `scope == "proj-a"` — 즉 `test_scan_signals_scope_is_subdir`가 통과한다.
- [ ] (정상) 여러 subdir이 공존(`proj-a/`, `proj-b/`, `dev-team-foo/`)할 때 각 엔트리의 scope가 해당 subdir 이름과 정확히 일치한다.
- [ ] (정상 — 기존 재귀 호환) `claude-signals/proj/wp-01/X.running` 2단계 중첩에서 scope=="proj"이고 파일은 수집된다 (기존 `test_recursive_scan_claude_signals`를 subdir-per-scope 계약으로 갱신).
- [ ] (엣지 — 디렉터리 부재) `${TMPDIR}/claude-signals/` 자체가 없으면 빈 리스트를 반환하고 예외를 던지지 않는다.
- [ ] (엣지 — bare-file 하위 호환) `claude-signals/TSK-Z.done` (root 직하 파일)도 여전히 수집되며 `scope == "shared"`로 기록된다.
- [ ] (엣지 — 미지원 확장자) subdir 내 `*.log`, `.DS_Store`, `*.tmp` 같은 파일은 scan_signals가 무시한다 (`_signal_entry`의 기존 필터 위임).
- [ ] (통합 — agent-pool 불변) `${TMPDIR}/agent-pool-signals-ts1-1/P.running`는 이전과 동일하게 `scope == "agent-pool:ts1-1"`로 수집된다 (기존 `ScanSignalsAgentPoolTests` 전부 통과).
- [ ] (통합 — 표시 regression 방지) subdir 이름을 가진 signal 여러 개와 agent-pool signal이 섞인 상태에서 `_classify_signal_scopes`가 반환하는 `(shared, agent_pool)` 튜플의 **len 합**이 이전 버전과 동일하며, agent-pool 버킷 크기도 동일하다 (즉, 모든 subdir-scoped entry는 shared 버킷으로 떨어진다).
- [ ] (통합 — dataclass 계약) `asdict(SignalEntry)`의 키 집합은 여전히 `{name, kind, task_id, mtime, scope}` — TRD §5.2 준수 (기존 `SignalEntryShapeTests`가 통과).
