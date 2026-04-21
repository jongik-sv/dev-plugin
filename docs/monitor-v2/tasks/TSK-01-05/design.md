# TSK-01-05: `_section_team` 수정 — inline preview + expand 버튼 - 설계

## 요구사항 확인
- `_section_team()` 렌더 함수를 수정하여 각 pane row에 마지막 3줄 텍스트 preview(`<pre class="pane-preview">`)와 `[expand ↗]` 버튼(`data-pane-expand="{pane_id}"` 속성)을 추가한다.
- pane 수가 20개 이상이면 preview를 생략하고 `<pre class="pane-preview empty">no preview (too many panes)</pre>`를 렌더한다.
- agent-pool 섹션(`_section_subagents`)은 변경하지 않는다 (PRD §4.5.7: preview·드로어 대상 아님).

## 타겟 앱
- **경로**: N/A (단일 앱)
- **근거**: Python stdlib 단일 파일 서버(`scripts/monitor-server.py`)로 구성된 단일 앱 프로젝트

## 구현 방향
- `scripts/monitor-server.py`의 `_render_pane_row()` 함수에 `preview_lines: Optional[str]` 파라미터를 추가하여 preview `<pre>` 블록과 `[expand ↗]` 버튼을 렌더한다.
- 신규 헬퍼 함수 `_pane_last_n_lines(pane_id, n=3) -> str`를 추가한다. `capture_pane()`을 호출하고 결과의 마지막 n줄(공백-only 줄 제외)을 반환한다.
- `_section_team()`에서 전체 pane 수가 ≥ 20이면 모든 row에 대해 `preview_lines=None`(too-many 메시지)을 전달한다.
- pane_id는 `_esc()`로 HTML escape된다. `html.escape`는 `%`를 변환하지 않으므로 `%2` 등은 그대로 유지된다.
- `DASHBOARD_CSS`에 `.pane-preview` 클래스 스타일(`max-height: 4.5em`, `overflow: hidden`)을 추가한다.

## 파일 계획

**경로 기준:** 모든 파일 경로는 프로젝트 루트 기준으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `_pane_last_n_lines()` 신규 함수, `_render_pane_row()` 수정 (expand 버튼 + preview), `_section_team()` 수정 (pane ≥ 20 분기), `DASHBOARD_CSS`에 `.pane-preview` CSS 추가 | 수정 |
| `scripts/tests/test_monitor_server.py` | TSK-01-05 단위 테스트 추가 | 수정 |

## 진입점 (Entry Points)

- **사용자 진입 경로**: 브라우저에서 dev-monitor 대시보드 메인 페이지(`/`) 접속 → "Team Agents (tmux)" 섹션 확인 → 각 pane row에 `[expand ↗]` 버튼이 렌더됨
- **URL / 라우트**: `/` (메인 대시보드, 기존 라우트 그대로)
- **수정할 라우터 파일**: `scripts/monitor-server.py` — `render_dashboard()` → `_section_team()` → `_render_pane_row()` 호출 체인만 수정. `do_GET` 라우터 등록 변경 없음.
- **수정할 메뉴·네비게이션 파일**: `scripts/monitor-server.py`의 `DASHBOARD_CSS` 문자열 — `.pane-preview` 클래스 규칙 추가. HTML nav/menu 구조 변경 없음.
- **연결 확인 방법**: 브라우저에서 `/` 로드 후 "Team Agents (tmux)" 섹션 내 각 `<div class="pane-row">` 하위에 `<button data-pane-expand="...">` 요소가 1개, `<pre class="pane-preview">` 요소가 1개 존재함을 확인

## 주요 구조

- `_pane_last_n_lines(pane_id: str, n: int = 3) -> str`: `capture_pane(pane_id)` 호출 → 줄 단위 분리 → 뒤쪽 공백-only 줄 제거 → 마지막 n줄 `"\n".join()` 반환. capture 실패/빈 결과 시 빈 문자열 반환.
- `_render_pane_row(pane, preview_lines: Optional[str] = None) -> str`: 기존 메타라인 + `<button data-pane-expand="{pane_id_esc}">[expand ↗]</button>` + `<pre class="pane-preview">{preview_esc}</pre>` 또는 `<pre class="pane-preview empty">no preview (too many panes)</pre>` (`preview_lines is None`이면 too-many 메시지).
- `_section_team(panes) -> str`: `panes`를 list로 변환 → `total = len(all_panes)` → `too_many = total >= 20` → 각 row 렌더 시 `too_many`이면 `preview_lines=None`, 아니면 `_pane_last_n_lines(pane_id)` 결과 전달.
- `DASHBOARD_CSS` 추가: `.pane-preview { max-height: 4.5em; overflow: hidden; margin: 0.25rem 0 0; padding: 0.25rem 0.5rem; background: var(--bg); border: 1px solid var(--border); border-radius: 4px; font-family: "SFMono-Regular", Consolas, monospace; font-size: 0.8rem; color: var(--muted); white-space: pre-wrap; word-break: break-all; }` `.pane-preview.empty { font-style: italic; }`

## 데이터 흐름

`_section_team(panes)` → panes를 list 변환 → 전체 수 카운트 → (≥20이면 too_many=True) → window별 그룹 순회 → 각 pane에 대해 `_pane_last_n_lines(pane_id)` 호출(too_many이면 스킵, None 전달) → `_render_pane_row(pane, preview_lines)` → HTML 조립 → `_section_wrap()` 반환

## 설계 결정 (대안이 있는 경우만)

- **결정**: `_render_pane_row(pane, preview_lines: Optional[str] = None)` — `None`을 "too many panes" 신호, `str`(빈 문자열 포함)을 "capture 결과"로 구분
- **대안**: `_render_pane_row()` 내부에서 직접 `capture_pane()` 호출 또는 sentinel 문자열 사용
- **근거**: 렌더 함수 내 외부 프로세스 호출 방지, 단위 테스트 용이성 확보. None/str 구분이 sentinel보다 타입 명확.

- **결정**: pane 수 카운트를 그룹화 전 `len(list(panes))` 으로 단순 계산
- **대안**: 그룹화 후 `sum(len(g) for g in groups.values())` 계산
- **근거**: list 변환 1회로 iterable 소진 없이 len을 얻고 이후 그룹화에 재사용.

## 선행 조건

- TSK-01-01: `_section_team()` 뼈대 + `_render_pane_row()` 기본 구현 완료 필요 (depends: TSK-01-01)
- `capture_pane()` 함수는 v1 그대로 사용 (수정 없음)

## 리스크

- **MEDIUM**: pane 수가 1~19개 구간에서 `_pane_last_n_lines()`가 pane 수만큼 subprocess 호출을 발생시킨다. 19개 시 최대 19번 subprocess. 렌더 지연 가능성 있으나 현재 요구사항 범위 내.
- **MEDIUM**: `capture_pane()` 결과 후행 빈 줄이 많으면 tail n줄이 의미 없는 빈 줄로 채워질 수 있다. 공백-only 줄 제거 후 tail 취하는 로직 주의.
- **LOW**: `pane_id`의 `%` 문자 — `html.escape`는 `%`를 변환하지 않으므로 `%2`, `%20` 등 `data-pane-expand` 속성 값에 그대로 유지됨. 별도 처리 불필요.

## QA 체크리스트

- [ ] (정상 케이스) pane 수 1~19개일 때, 각 pane row HTML에 `data-pane-expand="{pane_id}"` 속성을 가진 버튼이 정확히 1개 존재한다.
- [ ] (정상 케이스) pane 수 1~19개일 때, 각 pane row에 `<pre class="pane-preview">` 요소가 존재하고 내용이 3줄 이하 텍스트를 포함한다.
- [ ] (엣지 케이스) pane 수 정확히 20개일 때, 모든 pane row에 `<pre class="pane-preview empty">no preview (too many panes)</pre>`가 렌더된다.
- [ ] (엣지 케이스) pane 수 21개 이상일 때, 모든 pane row에 too-many preview 메시지가 렌더된다.
- [ ] (엣지 케이스) `capture_pane()` 결과가 빈 문자열일 때, `_pane_last_n_lines()`는 빈 문자열을 반환하고 preview는 빈 `<pre class="pane-preview">` 태그로 렌더된다.
- [ ] (엣지 케이스) pane 0개일 때, "no tmux panes running" empty-state가 렌더된다.
- [ ] (에러 케이스) tmux 미설치(panes=None)일 때, "tmux not available" empty-state가 렌더된다 (v1과 동일).
- [ ] (에러 케이스) pane_id가 `%2`, `%20` 등 `%` 포함 형태일 때 `data-pane-expand` 속성 값에 `%`가 그대로 유지된다 (이중 인코딩 없음).
- [ ] (통합 케이스) agent-pool 섹션(`_section_subagents`) HTML에 `data-pane-expand` 속성과 `pane-preview` 클래스가 존재하지 않는다.
- [ ] (클릭 경로) 브라우저에서 메인 대시보드(`/`) 로드 후 "Team Agents (tmux)" 섹션을 확인하면 각 pane row에 `[expand ↗]` 버튼이 표시된다.
- [ ] (화면 렌더링) `[expand ↗]` 버튼이 브라우저에서 실제 표시되고 기본 상호작용이 동작한다.
