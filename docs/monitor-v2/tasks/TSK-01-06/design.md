# TSK-01-06: `render_dashboard` 재조립 + sticky header + 드로어 골격 - 설계

## 요구사항 확인

- `render_dashboard(model)`을 v2 섹션 구성으로 재조립한다. 순서: `sticky_header → kpi → [.page col-left: wp_cards → features] + [col-right: live_activity → phase_timeline → team → subagents]`. 각 `<section>`에 `data-section="{key}"` 속성을 부여해 WP-02의 JS 부분 교체 식별자로 사용한다.
- `<aside class="drawer" role="dialog" aria-modal="true">` + `<div class="drawer-backdrop">` 골격 1쌍을 `</body>` 직전에 주입하고, v1의 `<meta http-equiv="refresh">` 태그를 제거한다 (JS 폴링은 WP-02에서 연결).
- 기존 앵커 링크(`#wbs`, `#features`, `#team`, `#subagents`, `#phases`)를 유지하여 상단 nav와 외부 링크 호환성을 보존한다 — 이를 위해 신규 섹션 id를 기존 앵커와 맞추거나 `<a id="...">` 랜딩 패드를 병행 제공한다.

## 타겟 앱

- **경로**: N/A (단일 앱 — `scripts/monitor-server.py` 인라인 렌더 레이어)
- **근거**: dev-plugin은 단일 Python 파일(`scripts/monitor-server.py`, 1871줄) BaseHTTPRequestHandler 구조로, 모든 렌더 함수가 한 파일 안에 직접 정의된다. 모노레포 타겟 앱 분기 없음.

## 구현 방향

- `render_dashboard(model)`의 sections 리스트를 v2 구성 6블록으로 교체한다: `_section_sticky_header`(TSK-01-02) → `_section_kpi`(TSK-01-02) → `.page` 2컬럼 wrapper(좌=`_section_wp_cards`+`_section_features`, 우=`_section_live_activity`+`_section_phase_timeline`+`_section_team`+`_section_subagents`) → `_section_phase_history`(footer로 유지, `#phases` 앵커 보존).
- 신규 헬퍼 `_drawer_skeleton() -> str`를 추가하여 빈 드로어 골격(`.drawer-backdrop` + `<aside class="drawer">`)을 단일 문자열로 반환. `render_dashboard`에서 `</body>` 직전에 한 번만 삽입.
- v1 `_section_wbs`는 TSK-01-03이 `_section_wp_cards`로 **대체** 구현한다는 전제(해당 design.md에 "`_section_wbs` → `_section_wp_cards` 호출 교체를 이 Task에서 함께 수행"으로 명시)이므로, 이 Task는 `render_dashboard`의 호출 레이어 배선만 담당한다. 기존 함수 정의의 제거는 dev-build 단계에서 함수 정의 충돌이 없도록 상태를 확인한 뒤 진행.
- `<meta http-equiv="refresh">` 한 줄 삭제 + 빈 `<script></script>` 태그(placeholder) 추가로 `</body>` 직전 삽입 위치만 확보한다 (실제 JS 문자열은 WP-02에서 채움). placeholder는 `id="dashboard-js"` 속성을 가진 빈 `<script>` 태그로 렌더한다.
- 각 `<section>`에 `data-section="{key}"` 속성을 부여하기 위해 `_section_wrap(anchor, heading, body)`를 확장하거나 신규 `_section_wrap_v2(anchor, heading, body, data_key)` 도입을 검토하되, 이번 Task는 **`render_dashboard` 본체의 외부 래퍼(조립 단계) 한 곳에서 속성을 주입**하여 기존 섹션 함수 본문을 건드리지 않는다(회귀 위험 최소화).
- `.page` 그리드(2컬럼 데스크톱 / 1컬럼 모바일) 스타일은 `DASHBOARD_CSS`에 최소 규칙 2줄(`.page`, `@media`)을 추가한다. 좌/우 컬럼 개별 클래스는 `.page-col-left`, `.page-col-right`. CSS 본체 확장은 TSK-01-01 담당이지만 이 Task의 그리드 컨테이너 규칙은 조립 동작에 필수이므로 포함한다 (CSS 충돌 시 TSK-01-01 산출물로 통합).
- `<meta http-equiv="refresh">` 제거로 테스트 환경(JS 미연결 상태)에서 자동 갱신이 동작하지 않는다. 이는 note에 명시된 의도(`JS 없이도 서버 사이드 렌더로 전 레이아웃 검증 가능`)이며 수동 새로고침으로 검증한다.

## 파일 계획

**경로 기준:** 모든 파일 경로는 **프로젝트 루트 기준**으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `render_dashboard(model)` 본체 재작성 (sections 리스트 v2 구성으로 교체, `<meta http-equiv="refresh">` 삭제, `.page` 2컬럼 wrapper 조립, `data-section` 속성 주입, `_drawer_skeleton()` 호출, 빈 `<script id="dashboard-js">` placeholder 삽입). `_drawer_skeleton() -> str` 신규 함수 정의. `_SECTION_ANCHORS` 상수에서 앵커 목록 유지(기존 호환) — 신규 섹션 id가 기존 앵커와 다른 경우 `<a id="wbs">` 랜딩 패드 병행 삽입. `DASHBOARD_CSS`에 `.page`/`.page-col-left`/`.page-col-right`/`.drawer-backdrop`/`.drawer` 기본 그리드 규칙 추가 (풀 스타일은 TSK-01-01 범위). | 수정 |
| `scripts/monitor-server.py` | `_section_header` 내부 nav 링크는 기존 `_SECTION_ANCHORS` 기반으로 유지되므로 직접 수정하지 않는다. 단 TSK-01-03이 `wbs` → `wp-cards`로 앵커를 교체한 경우 이 Task에서 `_SECTION_ANCHORS`를 v2 키(`hdr`, `kpi`, `wp-cards`, `features`, `activity`, `phases`, `team`, `subagents`)로 맞춘다. | 수정 |

> 이 Task는 단일 Python 파일 내 함수 재작성이므로 라우터 분리 파일 없음. `render_dashboard`가 곧 `/` 엔드포인트의 HTML 조립 진입점이다. 메뉴·네비게이션은 `_section_header` 내부 nav로 통합되어 있으며 `_SECTION_ANCHORS` 상수 업데이트가 곧 메뉴 업데이트다.

## 진입점 (Entry Points)

- **사용자 진입 경로**: 브라우저에서 `http://localhost:7321/` 접속 → 페이지 전체 로드 시 sticky header 상단 고정 + KPI 5장 + 2컬럼 바디(좌: WP 카드/Features, 우: Live Activity/Phase Timeline/Team/Subagents) + Phase History 푸터 + 빈 드로어(`display:none`)가 서버 렌더로 단일 응답에 조립되어 표시된다. 상단 nav의 "Wbs / Features / Team / Subagents / Phases" 앵커 링크 클릭 시 해당 섹션으로 스크롤 이동한다.
- **URL / 라우트**: `/` (GET, v1과 동일 — 신규 라우트 없음)
- **수정할 라우터 파일**: `scripts/monitor-server.py`의 `render_dashboard(model)` 함수 (현재 1080~1126 라인). 이 함수가 `/` GET 핸들러가 최종 호출하는 HTML 조립 단일 진입점이다. 수정 위치: ① sections 리스트(1103~1110 라인) 재구성, ② `<meta http-equiv="refresh">` 삭제(1118 라인), ③ `.page` wrapper HTML 삽입, ④ `_drawer_skeleton()` 호출 추가(`</body>` 직전), ⑤ `<script id="dashboard-js"></script>` placeholder 삽입(드로어 직후, `</body>` 직전).
- **수정할 메뉴·네비게이션 파일**: `scripts/monitor-server.py`의 `_SECTION_ANCHORS` 상수 (646 라인) — `_section_header`가 이 튜플을 읽어 nav 링크를 생성한다. v2 섹션 키 반영 필요 시 여기서 갱신. 상단 nav가 곧 페이지 내 섹션 메뉴.
- **연결 확인 방법**: E2E에서 `http://localhost:7321/` GET → 상단 nav 링크 중 "Wbs" 또는 "Wp-cards"를 클릭 → URL 해시가 `#wbs` 또는 `#wp-cards`로 변경되며 해당 섹션으로 스크롤 → 페이지 전체가 sticky header·KPI·2컬럼 바디·빈 드로어(`.drawer[style*="display:none"]` 또는 `aria-hidden="true"`) 순서로 존재함을 확인. `<meta http-equiv="refresh">` 미존재 검증은 응답 HTML 문자열 검색으로 수행. URL 직접 해시 입력(`page.goto('/#wbs')`) 금지.

## 주요 구조

| 함수 | 책임 |
|------|------|
| `render_dashboard(model: dict) -> str` | (재작성) v2 섹션 순서로 조립. 반환은 완전한 `<!DOCTYPE html>` 문자열. `<meta http-equiv="refresh">` 제거, `.page` 2컬럼 wrapper 삽입, `</body>` 직전 `_drawer_skeleton()` + `<script id="dashboard-js"></script>` placeholder 삽입. 입력 모델 방어(`model`이 dict 아니면 `{}`)는 v1 그대로 유지. `data-section` 속성은 외부 wrapper에서 주입. |
| `_drawer_skeleton() -> str` | (신규) 빈 드로어 골격 문자열 반환. 구조: `<div class="drawer-backdrop" aria-hidden="true"></div><aside class="drawer" role="dialog" aria-modal="true" aria-hidden="true" data-drawer><div class="drawer-header" data-drawer-header></div><div class="drawer-body" data-drawer-body></div></aside>`. 초기 상태 CSS로 숨김(`display:none` 또는 `.drawer:not(.open)`). |
| `_assemble_page_body(sections: dict) -> str` | (신규·내부 헬퍼, `render_dashboard` 내부 정의 가능) sections 딕셔너리(`{"sticky_header": html, "kpi": html, "wp_cards": html, "features": html, "live_activity": html, "phase_timeline": html, "team": html, "subagents": html, "phase_history": html}`)를 받아 `.page` 2컬럼 wrapper HTML로 조립. `data-section` 속성은 각 섹션 HTML의 최상위 `<section>`/`<header>` 태그에 주입(또는 wrapper `<div data-section="...">`로 감싸 주입). |
| `_wrap_with_data_section(section_html: str, key: str) -> str` | (신규·내부 헬퍼) 섹션 함수 반환 HTML의 최상위 태그에 `data-section="{key}"`을 주입한다. 정규표현식 기반 in-place 삽입(최상위 `<section` 또는 `<header` 한 곳만) — 실패 시 `<div data-section="{key}">...</div>`로 감싸는 폴백. 이 헬퍼는 기존 섹션 함수 내부를 건드리지 않기 위한 우회 장치. |

### `render_dashboard` v2 본체 구조 (의사코드)

```
def render_dashboard(model):
    if not isinstance(model, dict):
        model = {}

    refresh   = _refresh_seconds(model)        # 여전히 사용 (auto-refresh 라벨용, sticky_header가 소비)
    shared    = model.get("shared_signals") or []
    running   = _signal_set(shared, "running")
    failed    = _signal_set(shared, "failed")
    tasks     = model.get("wbs_tasks") or []
    features  = model.get("features") or []
    panes     = model.get("tmux_panes")
    ap_sigs   = model.get("agent_pool_signals") or []

    # 섹션별 HTML 빌드 (각 함수는 다른 Task가 구현)
    s = {
        "sticky_header": _section_sticky_header(model),                # TSK-01-02
        "kpi":           _section_kpi(model),                          # TSK-01-02
        "wp_cards":      _section_wp_cards(tasks, running, failed),    # TSK-01-03
        "features":      _section_features(features, running, failed), # TSK-01-03
        "live_activity": _section_live_activity(model),                # TSK-01-04
        "phase_timeline": _section_phase_timeline(tasks, features),    # TSK-01-04
        "team":          _section_team(panes),                         # TSK-01-05
        "subagents":     _section_subagents(ap_sigs),                  # v1 그대로
        "phase_history": _section_phase_history(tasks, features),      # v1 그대로 (#phases)
    }

    # data-section 속성 주입
    for key, html in list(s.items()):
        s[key] = _wrap_with_data_section(html, key.replace("_", "-"))

    body = (
        s["sticky_header"] + "\n"
        + s["kpi"] + "\n"
        + '<div class="page">\n'
        + '  <div class="page-col-left">\n'
        + s["wp_cards"] + "\n"
        + s["features"] + "\n"
        + '  </div>\n'
        + '  <div class="page-col-right">\n'
        + s["live_activity"] + "\n"
        + s["phase_timeline"] + "\n"
        + s["team"] + "\n"
        + s["subagents"] + "\n"
        + '  </div>\n'
        + '</div>\n'
        + s["phase_history"] + "\n"     # 전폭 풋터 (#phases 앵커 유지)
    )

    return (
        '<!DOCTYPE html>\n'
        '<html lang="en">\n'
        '<head>\n'
        '  <meta charset="utf-8">\n'
        '  <title>dev-plugin Monitor</title>\n'
        f'  <style>{DASHBOARD_CSS}</style>\n'
        '</head>\n'
        '<body>\n'
        f'{body}\n'
        f'{_drawer_skeleton()}\n'
        '<script id="dashboard-js"></script>\n'
        '</body>\n'
        '</html>\n'
    )
```

### `_drawer_skeleton` 반환 문자열 (정확한 모양)

```html
<div class="drawer-backdrop" aria-hidden="true" data-drawer-backdrop></div>
<aside class="drawer" role="dialog" aria-modal="true" aria-hidden="true" data-drawer>
  <div class="drawer-header" data-drawer-header></div>
  <div class="drawer-body" data-drawer-body></div>
</aside>
```

### `DASHBOARD_CSS` 최소 추가 규칙 (이 Task 범위)

```
.page { display: grid; grid-template-columns: 2fr 1fr; gap: 1rem; align-items: start; }
.page-col-left, .page-col-right { display: flex; flex-direction: column; gap: 1rem; }
@media (max-width: 960px) { .page { grid-template-columns: 1fr; } }
.drawer-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: none; z-index: 20; }
.drawer-backdrop.open { display: block; }
.drawer { position: fixed; top: 0; right: 0; width: min(520px, 90vw); height: 100vh; background: var(--panel); border-left: 1px solid var(--border); transform: translateX(100%); transition: transform 0.2s ease; z-index: 21; overflow-y: auto; }
.drawer.open { transform: translateX(0); }
```

## 데이터 흐름

입력: `model dict`(`wbs_tasks`, `features`, `shared_signals`, `tmux_panes`, `agent_pool_signals`, `project_root`, `refresh_seconds`, `generated_at`) → 처리: 섹션 함수 9개(TSK-01-02~05 구현)에 모델·시그널 집합 분기 전달 → `_wrap_with_data_section`으로 각 섹션 최상위 태그에 `data-section="{key}"` 주입 → `.page` 2컬럼 wrapper 조립 → `_drawer_skeleton()` + `<script id="dashboard-js">` placeholder 말미 삽입 → 출력: 완전한 `<!DOCTYPE html>` 문자열 (UTF-8 인코딩은 `MonitorHandler`가 담당).

## 설계 결정 (대안이 있는 경우만)

- **결정**: `data-section` 속성 주입을 `_wrap_with_data_section` 헬퍼로 조립 단계에서 후처리
- **대안**: 각 `_section_*` 함수 내부를 수정하여 첫 태그에 `data-section` 직접 추가
- **근거**: TSK-01-02·03·04·05가 이 Task와 병렬로 진행되며, 각 섹션 함수의 반환 구조가 확정되지 않은 상태에서 "`data-section` 주입 규약"을 각 Task에 강제하면 다중 병합 충돌 위험이 크다. 조립자(`render_dashboard`)가 단일 지점에서 후처리하면 상류 Task의 변경 없이 `data-section`을 일관되게 적용할 수 있다. 정규표현식 폴백(감싸기) 덕에 상류가 최상위 태그를 바꿔도 안전.

- **결정**: v1 `<meta http-equiv="refresh">` 제거와 함께 빈 `<script id="dashboard-js"></script>` placeholder를 삽입
- **대안**: 빈 `<script>` 없이 깔끔히 제거만 수행
- **근거**: WP-02가 JS 폴링을 삽입할 때 정확한 위치를 쉽게 찾기 위한 앵커. placeholder id로 JS 조립 코드가 `re.sub` 또는 `str.replace`로 간단히 치환 가능. 빈 태그는 브라우저 동작에 영향 없음(0바이트).

- **결정**: Phase History(`#phases`)는 2컬럼 우측이 아닌 전폭 풋터로 배치
- **대안**: 우측 컬럼 끝에 포함
- **근거**: PRD의 섹션 순서 명세는 "right-col: live_activity → phase_timeline → team → subagents"로 끝난다(phase_history 미포함). Phase History는 v1의 긴 리스트(최근 10건)이며 2컬럼에 끼우면 가독성이 나쁘다. 기존 `#phases` 앵커 유지(constraints)를 위해 전폭 풋터로 유지 — constraints는 "페이지에 존재"하면 충족.

- **결정**: `_SECTION_ANCHORS`에서 기존 5개 키(`wbs`, `features`, `team`, `subagents`, `phases`)를 v2 키셋으로 **교체**하되 v1 앵커와의 호환성을 위해 nav 링크는 v1 표시명을 유지하거나, TSK-01-03의 `wp-cards` 앵커를 `<a id="wbs">` 빈 앵커로 **병행** 배치
- **대안**: `_SECTION_ANCHORS`에 v1·v2 앵커를 모두 포함시켜 중복 nav 링크 렌더
- **근거**: constraints는 "기존 링크 유지"만 요구한다. 가장 간단한 해석은 "앵커 id가 페이지에 존재하면 만족". TSK-01-03 design.md가 `id="wp-cards"` 섹션으로 교체한다고 명시했으므로, 이 Task에서 `_section_wp_cards` 앞에 `<a id="wbs"></a>` 빈 랜딩 패드를 추가하여 외부 링크(`/#wbs`)도 여전히 해당 위치로 스크롤되도록 한다. Features/Team/Subagents/Phases는 기존 섹션 함수가 그대로 재사용되므로 id 변경 없음.

## 선행 조건

- **TSK-01-02** (dd 완료, 설계 확정): `_section_sticky_header(model) -> str`, `_section_kpi(model) -> str`. 이 Task는 두 함수를 조립자로서 호출만 한다.
- **TSK-01-03** (dd 완료, 설계 확정): `_section_wp_cards(tasks, running_ids, failed_ids) -> str`, `_section_features(...)` v2 변형. TSK-01-03 design.md가 "`render_dashboard` 내 호출 교체는 이 Task에서 함께 수행"이라 명시하고 있어 이 Task와 호출-교체 작업이 중복될 수 있음. 구현 단계(dev-build)에서 선행 머지된 쪽의 배선을 존중하고 나머지는 no-op.
- **TSK-01-04** (dd 미완, 설계 진행 중): `_section_live_activity(model)`, `_section_phase_timeline(tasks, features)`. 이 Task는 함수 존재를 전제하고 호출만 수행. 미구현 시 `NameError` 발생하므로 dev-build 단계에서 TSK-01-04 dd/im 완료 대기 후 병합.
- **TSK-01-05** (dd 미완, 설계 진행 중): `_section_team(panes)`의 v2 수정 버전. 함수 시그너처 유지(인자 1개).
- **TSK-01-01**: `DASHBOARD_CSS`의 v2 스타일 확장. 이 Task가 추가하는 `.page`/`.drawer` 최소 그리드 규칙은 TSK-01-01이 본체 스타일을 정할 때 흡수/병합한다. 중복 정의가 발생해도 CSS 우선순위는 동일 선택자 뒤 선언이 이기므로 기능은 유지.
- Python 3.8+ stdlib only (정규표현식 `re` 모듈 사용).

## 리스크

- **HIGH**: 이 Task는 TSK-01-02/03/04/05 산출 함수를 모두 호출한다. dev-team 병렬 실행 시 개별 Task의 dd/im이 아직 완료되지 않으면 `NameError`/`AttributeError`가 발생한다. 완화책: dev-build 단계에서 `depends: TSK-01-02, 03, 04, 05` 시그널을 `wait`로 대기 후 진행(dev-plugin 표준). 또한 호출 자리에 `try/except NameError`로 placeholder 빈 문자열 대체 로직을 두면 상류 미구현 상태에서도 페이지는 렌더된다(디그레이디드 UX).
- **HIGH**: TSK-01-03 design.md의 "`render_dashboard` 호출 교체를 이 Task에서 함께 수행" 문장과 본 Task의 재조립 작업이 충돌한다. 두 Task가 `render_dashboard` 본체를 각자 수정하면 머지 충돌 필연. 완화책: dev-team 단계에서 TSK-01-03이 먼저 머지되면 이 Task는 `_section_wbs→_section_wp_cards` 교체 상태에서 출발. 머지 순서가 반대이면 이 Task가 v1 상태를 v2로 바꾼 뒤 TSK-01-03이 재배선 no-op. 두 Task 모두 "상대가 이미 배선했을 수 있음"을 전제로 `sections` 리스트를 **덮어쓰기 기준**으로 재작성해야 한다.
- **MEDIUM**: `_wrap_with_data_section`의 정규표현식이 중첩/여러 최상위 태그를 가진 섹션에서 첫 번째 태그만 잡거나 실패할 수 있다. 완화책: "첫 번째 `<section` 또는 `<header` 출현 1회만 치환 + 성공 여부 반환" 구조로 작성하고 실패 시 `<div data-section="{key}">{html}</div>` 래핑 폴백. 테스트에서 각 섹션에 정확히 1개의 `data-section="{key}"`가 출현함을 검증.
- **MEDIUM**: 200KB 바이트 크기 상한 (acceptance). v1 이미 Pane preview/phase_history를 포함해 수만 바이트 수준. TSK-01-04(phase_timeline SVG)·TSK-01-05(pane preview)가 크기를 크게 늘릴 수 있다. 30 Task 기준 측정은 dev-test에서 실데이터 + 경계 모델로 확인. 초과 시 phase_timeline 렌더 상한(>50 tasks → "+N more")이 이미 TSK-01-04 acceptance에 포함되어 있음.
- **MEDIUM**: `_SECTION_ANCHORS` 상수 변경이 `_section_header`의 nav 링크 렌더에 즉시 반영된다. v2 앵커로 교체하면 v1 링크 문구("Wbs")가 사라져 기존 북마크/외부 링크 혼란 가능. 완화책: 이 Task는 상수를 건드리지 않고 v1 그대로 두되, 페이지 내 `<a id="wbs">` 빈 랜딩 패드만 추가. `_SECTION_ANCHORS` 변경은 후속 Task로 분리.
- **LOW**: 빈 드로어(`display:none` 또는 `aria-hidden="true"`)가 스크린리더에 노출될 가능성 — `aria-hidden="true"` 명시로 해결.
- **LOW**: `_refresh_seconds(model)` 변수가 조립자에서 즉시 사용되지 않는다(`<meta http-equiv="refresh">` 삭제로). 값은 여전히 `_section_sticky_header`로 전달되어 "⟳ Ns" 라벨 생성에 쓰이므로 model 패스스루만 유지. dev-build에서 unused variable 경고 방지 위해 조립자에서는 호출만 남기고 중간 변수는 인라인화.
- **LOW**: `<script id="dashboard-js"></script>` 빈 태그가 `py_compile` 외 HTML 린터에서 `empty script` 경고를 낼 수 있으나, 프로젝트 quality_commands에 HTML 린트 없음(`python3 -m py_compile scripts/monitor-server.py`). 무시 가능.

## QA 체크리스트

dev-test 단계에서 검증할 항목. 각 항목은 pass/fail로 판정 가능해야 한다.

- [ ] `render_dashboard({})` — 빈 모델에서 예외 없이 `<!DOCTYPE html>`로 시작하는 문자열 반환, 문자열 내 `<aside class="drawer"` 정확히 1회 출현
- [ ] `render_dashboard(None)` — dict 아닌 입력에서도 빈 `{}`로 처리되어 크래시 없이 HTML 반환
- [ ] `render_dashboard(valid_model)` — 30 Task + 5 Feature 기준 출력 `len(html.encode("utf-8"))` < 204_800 (200KB)
- [ ] 출력 HTML에 `<meta http-equiv="refresh"` 문자열이 **미존재** (v1 태그 제거 확인)
- [ ] 출력 HTML에 `<aside class="drawer"` 정확히 1회, `<div class="drawer-backdrop"` 정확히 1회 출현 (중복 방지)
- [ ] 드로어 요소에 `role="dialog"`, `aria-modal="true"`, `aria-hidden="true"` 세 속성 모두 존재
- [ ] 출력 HTML에 `<script id="dashboard-js">` 태그가 `</body>` 직전에 정확히 1회 존재 (빈 내용 허용)
- [ ] 출력 HTML에 `<div class="page">` 정확히 1회, `<div class="page-col-left">`와 `<div class="page-col-right">` 각 1회 존재
- [ ] 섹션 순서 검증: 문자열 내 `data-section="sticky-header"` 위치 < `data-section="kpi"` < `data-section="wp-cards"` < `data-section="features"` < `data-section="live-activity"` < `data-section="phase-timeline"` < `data-section="team"` < `data-section="subagents"` < `data-section="phase-history"` (정수 index 비교)
- [ ] 각 `data-section="{key}"` 속성이 페이지에 정확히 1회 출현 (중복 주입 방지)
- [ ] 기존 앵커 호환: 출력 HTML에 `id="wbs"`, `id="features"`, `id="team"`, `id="subagents"`, `id="phases"` 중 `constraints` 명시된 5개 모두가 최소 1회 출현(섹션 id 또는 `<a id="...">` 랜딩 패드 형태)
- [ ] `_drawer_skeleton()` 단독 호출 시 `<aside class="drawer"`, `<div class="drawer-backdrop"`, `data-drawer`, `data-drawer-header`, `data-drawer-body` 키워드 모두 포함
- [ ] 모델에 `wbs_tasks=None`, `features=None`, `tmux_panes=None`, `agent_pool_signals=None` 하나라도 있어도 각 섹션 함수로 안전 전달되어 크래시 없이 렌더
- [ ] `_wrap_with_data_section("<section id='x'><h2>T</h2></section>", "x")` 반환값에 `data-section="x"` 정확히 1회 포함, 원본 id/h2 보존
- [ ] `_wrap_with_data_section("no-outer-tag", "x")` 폴백 동작: `<div data-section="x">no-outer-tag</div>` 형태 감싸기
- [ ] `render_dashboard` 반환 HTML의 `</body>` 바로 앞에 드로어 골격 + dashboard-js placeholder가 위치함 (string index로 검증)

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**
- [ ] (클릭 경로) 브라우저에서 `http://localhost:7321/` 접속 → 상단 nav의 기존 앵커 링크(예: "Wbs" 또는 v2 키) 클릭 → URL 해시가 `#wbs` 등으로 변경되며 해당 위치로 스크롤
- [ ] (화면 렌더링) 페이지 로드 시 sticky header가 상단 고정, KPI 5카드 1줄, 그 아래 2컬럼(좌·우) 레이아웃(데스크톱 너비) 또는 1컬럼(모바일 너비 ≤ 960px) 레이아웃이 브라우저에서 실제 표시되고, 빈 드로어가 `aria-hidden="true"` 상태로 DOM에 존재(화면에 노출되지 않음)함을 확인
