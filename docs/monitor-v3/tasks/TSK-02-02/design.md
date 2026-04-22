# TSK-02-02: i18n 프레임워크 + 언어 토글 UI - 설계

## 요구사항 확인
- `scripts/monitor-server.py` 모듈 상단에 `_I18N` 상수(ko/en 딕셔너리)와 `_t(lang, key)` 헬퍼를 추가하고, 섹션 h2 heading에만 적용한다. eyebrow·테이블 컬럼·코드 블록·에러 메시지는 번역 대상에서 제외한다.
- `render_dashboard(model, lang="ko")` 서명을 확장하고, `_section_*` 함수의 heading 인자를 `_t(lang, key)` 결과로 교체하여 전파한다.
- 헤더 우측에 `<nav class="lang-toggle">` SSR 렌더를 추가하고, 링크는 현재 `subproject` 쿼리를 보존한다. `?lang=` 쿼리가 없으면 기본값 `ko`.

## 타겟 앱
- **경로**: N/A (단일 앱 — `scripts/monitor-server.py` 단일 Python 파일이 SSR 서버)
- **근거**: dev-monitor는 `scripts/monitor-server.py` 한 파일이 HTTP 서버 + HTML 렌더러를 겸한다. 프레임워크·모노레포 없음.

## 구현 방향
- `monitor-server.py` 상단 Constants 섹션에 `_I18N` 딕셔너리 상수와 `_t` 헬퍼 함수를 추가한다. `_t`는 순수 함수로 구현하여 단위 테스트가 용이하게 한다.
- `render_dashboard(model, lang="ko")` 서명에 `lang` 파라미터를 추가하고, 내부에서 호출하는 각 `_section_*` 함수에 heading 문자열 인자로 `_t(lang, key)` 결과를 전달한다. `_section_*` 함수 자체의 시그니처는 변경하지 않는다 — heading은 이미 문자열 인자로 넘기고 있으므로 값만 교체하면 된다.
- `_section_header(model, lang, subproject)` 함수 시그니처를 확장하여 헤더 우측에 `<nav class="lang-toggle">` 블록을 삽입한다.
- `_route_root()`에서 `?lang=` 쿼리 파라미터를 읽어 `render_dashboard`로 전달한다. `lang` 값이 없거나 ko/en 이외이면 `"ko"` 기본값으로 처리한다.
- 단위 테스트는 `scripts/test_monitor_render.py`에 `test_section_titles_korean_default`, `test_section_titles_english_with_lang_en` 두 케이스를 추가한다.

## 파일 계획

**경로 기준:** 모든 파일 경로는 프로젝트 루트 기준으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `_I18N` 상수·`_t` 헬퍼 추가; `render_dashboard` + `_section_header` 시그니처 확장; `?lang=` 쿼리 파싱; nav.lang-toggle SSR 렌더 | 수정 |
| `scripts/test_monitor_render.py` | `test_section_titles_korean_default`, `test_section_titles_english_with_lang_en` 테스트 케이스 추가 | 수정 |

> **진입점 체크 (fullstack)**
> - 헤더 내 `<nav class="lang-toggle">` 가 라우터 역할을 겸한다. 신규 URL 라우트는 없고 기존 `GET /` 라우트에 쿼리 파라미터가 추가되는 구조이다.
> - 별도 라우터 파일 없음 — 단일 파일(`monitor-server.py`)에 `do_GET` → `_route_root`가 라우터 역할을 한다.
> - 메뉴/네비게이션은 `_section_header` 함수 내 `<nav class="lang-toggle">` HTML이 nav 역할을 한다.

## 진입점 (Entry Points)

- **사용자 진입 경로**: 대시보드(`http://localhost:{PORT}/`) 접속 → 헤더 우측 `[ 한 | EN ]` 토글에서 `EN` 클릭 → URL에 `?lang=en` 추가되어 페이지 재로드 → 영문 섹션 heading 표시. `한` 클릭 시 `?lang=ko`로 한국어 복귀.
- **URL / 라우트**: `GET /?lang=ko` (기본), `GET /?lang=en`; 서브프로젝트 병행 시 `GET /?lang=en&subproject=billing`
- **수정할 라우터 파일**: `scripts/monitor-server.py`의 `_route_root()` 메서드 — `urlsplit(self.path).query`에서 `parse_qs`로 `lang` 파라미터를 추출하여 `render_dashboard(model, lang=lang)`으로 전달. (이 파일은 위 "파일 계획" 표에 포함됨)
- **수정할 메뉴·네비게이션 파일**: `scripts/monitor-server.py`의 `_section_header()` 함수 — 헤더 `<div class="actions">` 직전 또는 직후에 `<nav class="lang-toggle">` 블록 삽입. (이 파일은 위 "파일 계획" 표에 포함됨)
- **연결 확인 방법**: 대시보드 홈에서 `[ 한 | EN ]` 토글의 `EN` 링크를 클릭 → URL이 `?lang=en`을 포함하도록 변경됨 → `<h2>Work Packages</h2>` 등 영문 heading 렌더 확인

## 주요 구조

- **`_I18N` (dict, 모듈 상수)**: ko/en 두 언어의 섹션 heading 문자열을 저장하는 중첩 딕셔너리. 키: `work_packages`, `features`, `team_agents`, `subagents`, `live_activity`, `phase_timeline`.
- **`_t(lang: str, key: str) -> str`**: `_I18N[lang][key]` 조회 헬퍼. 미지원 lang은 `"ko"` fallback, 미지원 key는 key 자체 반환. 순수 함수.
- **`render_dashboard(model: dict, lang: str = "ko") -> str`**: 기존 함수에 `lang` 파라미터 추가. `_section_*` 호출 시 heading 인자를 `_t(lang, key)`로 교체.
- **`_section_header(model: dict, lang: str = "ko", subproject: str = "") -> str`**: 기존 함수에 `lang`, `subproject` 파라미터 추가. 헤더 HTML에 `<nav class="lang-toggle">` 블록 삽입. subproject 쿼리를 lang 링크에 보존.
- **`_route_root()`의 쿼리 파싱**: `parse_qs(urlsplit(self.path).query)`로 `lang` 추출, `ko`/`en` 외 값은 `ko`로 정규화. `subproject`도 동시에 파싱하여 header에 전달.

## 데이터 흐름

입력: `GET /?lang=en[&subproject=billing]` HTTP 요청  
처리: `_route_root` → `parse_qs`로 `lang="en"` 추출 → `render_dashboard(model, lang="en")` → 각 `_section_*` 호출 시 `_t("en", "work_packages")` → `"Work Packages"` 등 영문 heading → `_section_header` 에서 lang-toggle nav 렌더  
출력: 섹션 h2가 영문인 완성 HTML 문서 (200 응답)

## 설계 결정 (대안이 있는 경우만)

- **결정**: `lang` 파라미터를 `render_dashboard`에서 각 `_section_*` 함수로 명시적 인자 전달 (not model dict 경유)
- **대안**: `model` 딕셔너리에 `lang` 키를 추가하여 암묵적으로 전달
- **근거**: 명시적 인자가 함수 시그니처에서 의도를 드러내며, `_section_*` 함수를 순수 함수로 유지해 테스트 용이성을 보장한다. model dict는 스냅샷 데이터 전용 관례를 유지.

- **결정**: `_section_header`에 `lang`과 `subproject`를 함께 전달하여 lang-toggle nav를 SSR
- **대안**: `render_dashboard` 에서 nav HTML을 직접 생성하여 header HTML에 문자열 연접
- **근거**: nav 생성 로직이 header와 밀접하고, subproject 쿼리 보존 로직을 한 함수에서 관리하는 것이 응집도 높음.

## 선행 조건

- TSK-02-01 (서브프로젝트 탭 + subproject 쿼리 파싱 기반)이 있으면 `subproject` 쿼리가 이미 파싱되어 있을 수 있으나, TSK-02-02는 독립 구현 가능. `depends: -` 로 명시됨.
- `urllib.parse.parse_qs`는 stdlib — 추가 의존성 없음. `from urllib.parse import urlsplit, parse_qs`로 import 확장 필요.

## 리스크

- **LOW**: `render_dashboard` 기존 호출부(`_route_root`, 단위 테스트)에서 `lang` 인자를 생략하면 기본값 `"ko"`로 동작 — 하위 호환. 기존 테스트는 영향 없음. 단, 테스트 내에서 명시적 `lang="ko"` 없이 호출하면 기본값이 `"ko"`임을 확인해야 함.
- **LOW**: `_section_header` 시그니처 변경 시 기존 호출부(테스트 내 직접 호출)가 있으면 수정 필요. grep으로 사전 확인 필수.
- **LOW**: subproject 탭 UI(TSK-02-01)가 아직 미구현이면 lang-toggle nav의 `subproject=` 파라미터가 빈 문자열로 렌더될 수 있음. 빈 값이면 `subproject` 파라미터를 링크에서 생략하는 처리 필요.

## QA 체크리스트

dev-test 단계에서 검증할 항목.

- [ ] (정상 케이스) `render_dashboard(model)` 호출 시 기본 `lang="ko"` 적용 — HTML에 `<h2>작업 패키지</h2>`, `<h2>기능</h2>`, `<h2>팀 에이전트 (tmux)</h2>`, `<h2>서브 에이전트 (agent-pool)</h2>`, `<h2>실시간 활동</h2>`, `<h2>단계 타임라인</h2>` 가 모두 포함된다 (`test_section_titles_korean_default`).
- [ ] (정상 케이스) `render_dashboard(model, lang="en")` 호출 시 `<h2>Work Packages</h2>`, `<h2>Features</h2>`, `<h2>Team Agents (tmux)</h2>`, `<h2>Subagents (agent-pool)</h2>`, `<h2>Live Activity</h2>`, `<h2>Phase Timeline</h2>` 가 모두 포함된다 (`test_section_titles_english_with_lang_en`).
- [ ] (엣지 케이스) `_t("ko", "work_packages")` → `"작업 패키지"`, `_t("en", "work_packages")` → `"Work Packages"` 반환.
- [ ] (엣지 케이스) `_t("fr", "work_packages")` — 미지원 lang이면 `"ko"` fallback으로 `"작업 패키지"` 반환.
- [ ] (엣지 케이스) `_t("ko", "unknown_key")` — 미지원 key이면 `"unknown_key"` 자체 반환.
- [ ] (엣지 케이스) `?lang=` 파라미터가 없는 `GET /` 요청 → `lang="ko"` 기본 적용 → 한국어 heading 렌더.
- [ ] (엣지 케이스) `?lang=INVALID` 요청 → 정규화되어 `lang="ko"` 기본 적용.
- [ ] (정상 케이스) `?lang=en&subproject=billing` 요청 시 lang-toggle nav 링크가 `?lang=ko&subproject=billing`, `?lang=en&subproject=billing` 두 href를 포함한다.
- [ ] (정상 케이스) `?lang=ko` 요청 시 lang-toggle nav가 렌더된 HTML에 `<nav class="lang-toggle">` 가 포함된다.
- [ ] (에러 케이스) `_I18N` 키에 없는 섹션 이름이 `_t`에 전달되어도 서버가 500 없이 key 자체를 heading으로 사용한다.
- [ ] (통합 케이스) `render_dashboard` 결과 HTML에서 eyebrow, 테이블 컬럼명 등 비대상 텍스트가 lang과 관계없이 동일하게 유지된다 (번역 스코프 제한 검증).
- [ ] (통합 케이스) 기존 `test_monitor_render.py`의 모든 기존 테스트가 `lang` 파라미터 추가 후에도 regression 없이 통과한다.

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**
- [ ] (클릭 경로) 헤더 우측 `[ 한 | EN ]` 토글의 `EN` 링크를 클릭하여 URL이 `?lang=en`을 포함한 상태로 변경되고 영문 heading이 표시되는 페이지에 도달한다 (URL 직접 입력 금지)
- [ ] (화면 렌더링) 언어 토글 `<nav class="lang-toggle">` 요소가 브라우저에서 실제 표시되고 ko/en 링크 클릭 기본 상호작용이 동작한다
