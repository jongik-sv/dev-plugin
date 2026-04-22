# TSK-00-02: 프로젝트 레벨 pane/signal 필터 헬퍼 - 설계

## 요구사항 확인
- `scripts/monitor-server.py`에 두 개의 pure 헬퍼 함수를 추가한다.
- `_filter_panes_by_project(panes, project_root, project_name)`: `pane_current_path`가 project_root 하위이거나 `window_name`이 `WP-*-{project_name}` 패턴이면 통과시킨다.
- `_filter_signals_by_project(signals, project_name)`: `scope`가 `project_name` 또는 `project_name-*` prefix인 signal만 통과시키며, 다른 프로젝트의 signal은 제외한다.

## 타겟 앱
- **경로**: N/A (단일 앱 — `scripts/monitor-server.py` 단일 파일)
- **근거**: dev-plugin은 모노레포가 아닌 단일 앱 구조이며, 모든 서버 로직이 `scripts/monitor-server.py`에 집중되어 있다.

## 구현 방향
- TRD §3.2에 명시된 두 함수를 기존 `_classify_signal_scopes` 헬퍼 근처(스캔/필터 헬퍼 섹션)에 순수 함수로 추가한다.
- `_filter_panes_by_project`: `panes is None` 이면 `None` 반환(tmux 미설치 신호 보존). `os.sep`으로 경로 비교하여 크로스플랫폼 호환성 확보. `project_root.rstrip(os.sep)`으로 trailing separator 정규화.
- `_filter_signals_by_project`: `scope == project_name` 또는 `scope.startswith(project_name + "-")` 조건으로 prefix 매칭. `agent-pool:*` scope는 현재 `_filter_panes_by_project` 대상이 아니므로 이 함수는 shared signal 영역에만 적용된다.
- Python 3 stdlib만 사용. 외부 의존성 없음.

## 파일 계획

**경로 기준:** 모든 파일 경로는 **프로젝트 루트 기준**으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `_filter_panes_by_project`, `_filter_signals_by_project` pure 헬퍼 함수 추가. `_classify_signal_scopes` 직후 삽입. | 수정 |

## 진입점 (Entry Points)
N/A — 이 Task는 `domain=backend`인 non-UI Task로, 라우터/메뉴 수정 불필요.

## 주요 구조

```python
def _filter_panes_by_project(
    panes: Optional[List[PaneInfo]],
    project_root: str,
    project_name: str,
) -> Optional[List[PaneInfo]]:
    """pane_current_path 또는 window_name 기준으로 현재 프로젝트 pane만 통과."""
    ...

def _filter_signals_by_project(
    signals: List[SignalEntry],
    project_name: str,
) -> List[SignalEntry]:
    """scope가 project_name 또는 project_name-* prefix인 signal만 통과."""
    ...
```

- `_filter_panes_by_project`: `panes is None` → `None` 반환(tmux 미설치 보존). `project_root.rstrip(os.sep)`으로 정규화. 각 pane에 대해 `cwd == root or cwd.startswith(root + os.sep)` 또는 `wname.startswith("WP-") and f"-{project_name}" in wname` 이면 통과.
- `_filter_signals_by_project`: 각 signal의 `scope` 필드에 대해 `scope == project_name or scope.startswith(project_name + "-")` 이면 통과.

## 데이터 흐름

입력(`panes` 또는 `signals` 전체 리스트 + `project_root`/`project_name`) → 각 항목에 대해 project 귀속 여부 판정 → 귀속 항목만 담은 신규 리스트 반환 (원본 불변).

## 설계 결정 (대안이 있는 경우만)

- **결정**: `panes is None` 입력 시 `None` 반환 (빈 리스트 반환 대신)
- **대안**: 빈 리스트 `[]` 반환
- **근거**: `list_tmux_panes()` 의 `None` 반환값은 "tmux 미설치" 신호이며, 현재 `_build_render_state` 및 HTML 렌더러가 `panes is None`으로 tmux 미설치를 구분한다. 빈 리스트로 변환하면 "tmux 설치됨, pane 없음"으로 오인된다.

- **결정**: `os.sep` 기반 경로 비교 (`cwd.startswith(root + os.sep)`)
- **대안**: `Path(cwd).is_relative_to(project_root)` (Python 3.9+)
- **근거**: Python 3.8 호환성 유지 + `os.sep` 기반은 Windows(`\`) / macOS·Linux(`/`) 차이를 투명하게 처리한다.

## 선행 조건
- 없음. TSK-00-01과 독립적으로 구현 가능하며, `scope` 값 의존 없음 (`project_name` prefix 매칭만 사용).

## 리스크

- LOW: `pane_current_path`는 셸 cd 상태에 의존하므로 사용자가 pane 내부에서 다른 프로젝트 디렉터리로 cd하면 필터가 어긋날 수 있음. TRD §6에서 "알려진 한계"로 명시됨 — `window_name` fallback으로 일부 완화됨.
- LOW: `project_root`에 trailing separator가 있을 때 `rstrip(os.sep)` 정규화를 빠뜨리면 `root + os.sep`이 이중 separator가 되어 매칭 실패. 구현에서 `rstrip` 명시 필요.
- LOW: Windows 환경에서 `project_root`가 `C:\` 형태이면 `rstrip(os.sep)` 후 `C:` 가 되어 drive root 비교가 잘못될 수 있음. 단, CLAUDE.md 규약상 로컬 temp 경로는 Unix-like 환경이 주 대상이며, Windows는 WSL2 경로(`/mnt/c/...`) 사용이 일반적.

## QA 체크리스트
dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

**_filter_panes_by_project:**
- [ ] (정상: root 하위) `pane_current_path=/proj/a/src`이고 `project_root=/proj/a`이면 해당 pane이 반환 리스트에 포함된다 (`test_filter_panes_by_project_root_startswith`).
- [ ] (정상: root 정확 일치) `pane_current_path=/proj/a`이고 `project_root=/proj/a`이면 해당 pane이 반환 리스트에 포함된다.
- [ ] (정상: window_name 매칭) `pane_current_path`가 project_root 밖이더라도 `window_name=WP-01-myproj`이고 `project_name=myproj`이면 통과한다 (`test_filter_panes_by_project_window_name_match`).
- [ ] (엣지: prefix 오탐 방지) `project_root=/proj/a`이고 `pane_current_path=/proj/alpha/src`이면 해당 pane이 제외된다 (단순 `startswith("/proj/a")` 오탐 방지 — `root + os.sep` 비교 필수).
- [ ] (엣지: panes=None) 입력이 `None`이면 반환값도 `None`이다.
- [ ] (엣지: 빈 리스트) 입력이 빈 리스트 `[]`이면 반환값도 빈 리스트이다.
- [ ] (에러: window_name 미매칭) `window_name=WP-01-otherproj`이고 `project_name=myproj`이면 cwd 무관하게 통과하지 않는다.

**_filter_signals_by_project:**
- [ ] (정상: 동일 scope) `scope=myproj`이고 `project_name=myproj`이면 통과한다 (`test_filter_signals_by_project`).
- [ ] (정상: 서브프로젝트 scope) `scope=myproj-billing`이고 `project_name=myproj`이면 통과한다.
- [ ] (정상: 더 깊은 서브프로젝트) `scope=proj-a-billing-eu`이고 `project_name=proj-a`이면 통과한다.
- [ ] (에러: 다른 프로젝트) `scope=otherproj`이고 `project_name=myproj`이면 제외된다.
- [ ] (에러: prefix 오탐 방지) `scope=myproj2`이고 `project_name=myproj`이면 제외된다 (`startswith(project_name + "-")` 검사로 오탐 방지).
- [ ] (엣지: 빈 scope) `scope=""`이면 제외된다.
- [ ] (엣지: 빈 리스트) 입력이 빈 리스트이면 반환값도 빈 리스트이다.
