# TSK-00-03: 서브프로젝트 탐지 & 필터 헬퍼 - 설계

## 요구사항 확인

- `discover_subprojects(docs_dir)`: `docs_dir` 하위에서 `wbs.md`를 포함하는 child 디렉터리 이름을 정렬된 리스트로 반환. `wbs.md` 없는 디렉터리(`tasks/`, `features/` 등)는 제외.
- `_filter_by_subproject(state, sp, project_name)`: pane은 `window_name`의 suffix/포함 또는 `pane_current_path`의 경로 포함으로 필터, signal은 `scope` 접두어로 필터.
- `is_multi_mode = len(discover_subprojects(docs_dir)) > 0` 로직을 이 Task가 제공하는 헬퍼로 수행.

## 타겟 앱

- **경로**: N/A (단일 앱)
- **근거**: dev-plugin은 단일 Python stdlib 패키지 구조. `scripts/monitor-server.py`에 직접 추가.

## 구현 방향

- `monitor-server.py`의 `# --- end scan functions ---` 섹션 바로 위(스캔 함수 그룹 말미)에 헬퍼 두 함수를 추가한다.
- `discover_subprojects`는 `pathlib.Path`의 `iterdir()` + `is_dir()` + `Path.__truediv__` + `is_file()`만 사용 (stdlib 전용, TRD §3.1 구현 그대로).
- `_filter_by_subproject`는 `state` dict를 in-place 수정하여 반환. `tmux_panes`가 `None`이면 `None` 유지, 빈 리스트면 빈 리스트 유지.
- 단위 테스트 `scripts/test_monitor_subproject.py` 신규 작성. 5개 테스트케이스 모두 커버.

## 파일 계획

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `discover_subprojects` + `_filter_by_subproject` 함수 추가 (스캔 함수 섹션 말미) | 수정 |
| `scripts/test_monitor_subproject.py` | 5개 테스트케이스 전용 파일 | 신규 |

## 진입점 (Entry Points)

N/A — domain=infrastructure(backend) Task. UI 없음.

## 주요 구조

- **`discover_subprojects(docs_dir: Path) -> List[str]`**: TRD §3.1 명세 그대로. `docs_dir.is_dir()` guard → `sorted(docs_dir.iterdir())` 반복 → `child.is_dir() and (child / "wbs.md").is_file()` 조건 통과 시 `child.name` 수집.
- **`_filter_by_subproject(state: dict, sp: str, project_name: str) -> dict`**: TRD §3.4 명세 그대로. pane 필터 조건 3가지(`endswith(f"-{sp}")`, `f"-{sp}-" in wn`, `f"/{sp}/" in cwd`), signal 필터는 `scope == prefix or scope.startswith(prefix + "-")` (`prefix = f"{project_name}-{sp}"`). `state["tmux_panes"]`가 `None`이면 `None` 보존.
- **`test_discover_subprojects_multi`**: `docs/p1/wbs.md` + `docs/p2/wbs.md` 존재 → `["p1", "p2"]` 반환 검증.
- **`test_discover_subprojects_legacy`**: `docs/wbs.md`만 있고 child에 `wbs.md` 없음 → `[]` 검증.
- **`test_discover_subprojects_ignores_dirs_without_wbs`**: `docs/tasks/`, `docs/features/` 디렉터리는 `wbs.md` 없으므로 결과에 포함되지 않음 검증.
- **`test_filter_by_subproject_signals`**: scope `proj-a-billing` 통과, `proj-a-reporting` 제외 검증.
- **`test_filter_by_subproject_panes_by_window`**: `window_name="WP-01-billing"` 통과 (`-billing` suffix), `window_name="WP-01-reporting"` 제외 검증.

## 데이터 흐름

입력: `docs_dir: Path` (또는 `state dict + sp + project_name`) → 처리: `pathlib.Path` 파일시스템 탐색 / dict 필드 필터링 → 출력: `List[str]` (서브프로젝트 이름 목록) / 필터된 `state dict`

## 설계 결정 (대안이 있는 경우만)

- **결정**: `_filter_by_subproject`가 `state` dict를 in-place 수정하여 반환
- **대안**: 새 dict 복사본 반환 (deep copy)
- **근거**: TRD §3.4 명세가 in-place 수정을 보여주며, 호출 지점에서 이미 on-demand 스캔 결과이므로 원본 보존 필요 없음. 복사 오버헤드 불필요.

## 선행 조건

- 없음 (TSK-00-03은 depends 없음, stdlib `pathlib` 전용)

## 리스크

- LOW: `state["tmux_panes"]`가 `None`인 경우(tmux 미설치) 처리 — TRD §3.4 명세에 `None` 보존 조건이 명시되어 있으므로 `is not None` guard 필수. 테스트에서 커버.
- LOW: `docs_dir`가 존재하지 않는 경로일 때 `discover_subprojects`가 `[]` 반환해야 함 — `is_dir()` guard로 처리.
- LOW: `iterdir()` 결과 순서는 플랫폼 의존 — `sorted()` 감싸서 결정론적 정렬 보장. TRD §3.1 명세에도 `sorted(docs_dir.iterdir())` 명시됨.

## QA 체크리스트

- [ ] `discover_subprojects`에 `docs/p1/wbs.md` + `docs/p2/wbs.md` 존재 시 `["p1", "p2"]` 반환 (test_discover_subprojects_multi)
- [ ] `docs/wbs.md`만 있고 child에 `wbs.md` 없을 때 `discover_subprojects` → `[]` 반환 (test_discover_subprojects_legacy)
- [ ] `docs/tasks/`, `docs/features/` 같이 `wbs.md` 없는 디렉터리는 `discover_subprojects` 결과에서 제외 (test_discover_subprojects_ignores_dirs_without_wbs)
- [ ] `_filter_by_subproject`에서 scope=`proj-a-billing`은 통과, scope=`proj-a-reporting`은 제외 (test_filter_by_subproject_signals)
- [ ] `window_name="WP-01-billing"` pane은 sp=`billing`에서 통과, `window_name="WP-01-reporting"`은 제외 (test_filter_by_subproject_panes_by_window)
- [ ] `tmux_panes=None`일 때 `_filter_by_subproject` 호출 후 `state["tmux_panes"]`가 `None` 유지 (None guard 엣지 케이스)
- [ ] `docs_dir`가 존재하지 않는 경로일 때 `discover_subprojects` → `[]` 반환 (엣지 케이스)
- [ ] `is_multi_mode = len(discover_subprojects(docs_dir)) > 0` 로직이 멀티 모드에서 `True`, 레거시에서 `False` 반환 (통합 케이스)
- [ ] `-{sp}-` 포함 window_name(예: `WP-01-billing-extra`)도 통과 (window 필터 포함 조건 엣지 케이스)
- [ ] `pane_current_path`에 `/{sp}/` 포함 시 통과 (경로 기반 pane 필터 케이스)
- [ ] scope=`proj-a-billing-sub` (`{prefix}-` 접두어 시작)도 통과 (signal prefix 매칭 엣지 케이스)
