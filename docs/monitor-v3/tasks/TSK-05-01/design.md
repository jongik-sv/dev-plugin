# TSK-05-01: Fold 영속성 JS + patchSection 훅 확장 - 설계

## 요구사항 확인

- `<details data-wp="{WP-ID}" open>` 서버 렌더 이후 클라이언트 JS가 localStorage 기반으로 fold 상태를 덮어써, 5초 auto-refresh 및 하드 리로드(F5) 후에도 사용자가 접은 WP 카드가 접힌 상태를 유지한다.
- 헬퍼 4종(`readFold`, `writeFold`, `applyFoldStates`, `bindFoldListeners`)을 `_DASHBOARD_JS` 문자열 안에 추가하고, `init()` 함수 내 `startMainPoll()` 직전과 `patchSection('wp-cards')` 교체 직후 두 곳에 훅을 삽입한다.
- quota/disabled localStorage 예외는 try/catch로 무성 처리하고, `__foldBound` 플래그로 중복 listener 바인딩을 방지한다.

## 타겟 앱

- **경로**: N/A (단일 앱)
- **근거**: `scripts/monitor-server.py` 하나의 모놀리식 파일이 SSR HTML + inline JS를 모두 포함하는 단일 앱 구조.

## 구현 방향

- `scripts/monitor-server.py` 내부 `_DASHBOARD_JS` Python 문자열에 fold 헬퍼 4종을 삽입한다.
- `init()` 함수에서 `startMainPoll()` 직전 `applyFoldStates(document); bindFoldListeners(document);` 호출 2줄 추가.
- `patchSection()` 함수의 `'wp-cards'` 분기에서 `current.innerHTML = newHtml` 교체 직후 `applyFoldStates(current); bindFoldListeners(current);` 호출 2줄 추가.
- 서버 측 `_section_wp_cards`의 `<details ... open>` 기본값은 변경하지 않는다 (JS 비활성화/첫 방문자 호환 계약 유지).
- 신규 테스트 파일 `scripts/test_monitor_fold.py` 생성 — 브라우저 비의존 방식으로 JS 코드 존재 및 호출 패턴을 정규식 검증.

## 파일 계획

**경로 기준:** 프로젝트 루트 기준.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | `_DASHBOARD_JS` 문자열에 fold 헬퍼 4종 추가, `init()` 및 `patchSection()` 훅 삽입 | 수정 |
| `scripts/test_monitor_fold.py` | fold JS 코드 존재 검증, patchSection 훅 삽입 검증, `__foldBound` 중복 방지 패턴 검증 | 신규 |

## 진입점 (Entry Points)

- **사용자 진입 경로**: 브라우저에서 대시보드 페이지(`http://localhost:7321`) 접근 → WP 카드 `<details>` 요소의 `<summary>` 클릭으로 접기/펼치기 → 5초 대기 또는 F5 새로고침
- **URL / 라우트**: `http://localhost:7321/` (GET 루트, 기존 라우트 변경 없음)
- **수정할 라우터 파일**: 없음 — 기존 라우트 그대로. `_DASHBOARD_JS` Python 문자열 수정으로 inline script만 변경됨.
- **수정할 메뉴·네비게이션 파일**: 없음 — 기존 네비게이션 변경 없음.

> 이 Task는 신규 라우트·메뉴 없이 기존 대시보드 JS 코드만 확장하는 클라이언트 JS 전용 작업이다. 라우터/메뉴 파일 수정이 없으므로 해당 항목은 N/A.

## 주요 구조

- **`FOLD_KEY_PREFIX`** (`var FOLD_KEY_PREFIX = 'dev-monitor:fold:';`): localStorage 키 접두사 상수.
- **`readFold(wpId)`**: localStorage에서 `dev-monitor:fold:{wpId}` 값(`"open"|"closed"`)을 읽어 반환. try/catch → `null` 반환.
- **`writeFold(wpId, open)`**: `open` 불리언으로 `"open"|"closed"` 값 저장. try/catch 무성 처리.
- **`applyFoldStates(root)`**: `root.querySelectorAll('details[data-wp]')` 순회 → `readFold` 결과로 `open` attribute 추가/제거.
- **`bindFoldListeners(root)`**: `root.querySelectorAll('details[data-wp]')` 순회 → `el.__foldBound` 미설정 시만 `toggle` listener 등록 후 `__foldBound=true` 플래그 셋.

## 데이터 흐름

```
사용자 toggle → details.toggle 이벤트 → writeFold(wpId, el.open) → localStorage['dev-monitor:fold:{WP-ID}'] = 'open'|'closed'
5초 poll/F5 → 서버 HTML(details open) → patchSection innerHTML 교체 → applyFoldStates(current) → localStorage 값으로 open attr 덮어씀 → 상태 복원
```

## 설계 결정 (대안이 있는 경우만)

- **결정**: `patchSection` 내부에 직접 fold 훅 코드 삽입 (name==='wp-cards' 분기 안)
- **대안**: `fetchAndPatch`에서 `patchSection` 호출 후 별도 `applyFoldStates` 호출
- **근거**: TRD §3.11.4 명세 그대로이며, `hdr` 섹션의 chip/toggle 상태 복원 패턴(line 3693-3714)과 일관된 단일 책임 위치. 섹션별 특화 복원 로직을 `patchSection` 내부에 두는 기존 패턴을 따름.

- **결정**: `__foldBound` 플래그를 DOM element 프로퍼티로 직접 셋
- **대안**: WeakMap으로 bound 요소 추적
- **근거**: 모놀리식 inline IIFE 환경에서 WeakMap은 IE 호환성 이슈가 있고 코드 볼륨이 증가. DOM element 프로퍼티 직접 셋은 기존 코드 스타일과 동일하며 garbage collection 문제도 없음.

## 선행 조건

- 없음 (`depends: -`, 서버 계약 변경 없음)

## 리스크

- **MEDIUM**: `_DASHBOARD_JS`는 5,644줄 모놀리스 파일 내부의 Python multiline 문자열임. 삽입 위치를 잘못 잡으면 문법 오류가 발생하나 `python3 -m py_compile` 타입체크로 사전 감지 가능.
- **MEDIUM**: `patchSection`에서 `name==='wp-cards'` 분기가 없는 경우 — 현재 코드(line 3686-3717)를 확인하면 `'wp-cards'`는 `hdr`/`dep-graph`와 달리 별도 분기 없이 `current.innerHTML!==newHtml` 기본 경로를 탄다. 따라서 해당 분기를 신설(`if(name==='wp-cards')`)하거나 기본 경로 내에서 조건부로 호출해야 함.
- **LOW**: localStorage quota/disabled 환경(Safari 비공개 모드 등)에서 try/catch 무성 처리로 fold 상태가 초기화될 뿐, 기능 중단은 없음.

## QA 체크리스트

dev-test 단계에서 검증할 항목.

- [ ] `test_fold_localstorage_write` (정상): `_DASHBOARD_JS` 문자열에 `writeFold` 함수 정의와 `localStorage.setItem` 호출이 존재한다.
- [ ] `test_fold_restore_on_patch` (정상): `patchSection` 함수 내에 `applyFoldStates` 및 `bindFoldListeners` 호출이 존재하며, `wp-cards` 관련 분기 내에 위치한다.
- [ ] `test_fold_bind_idempotent` (정상): `bindFoldListeners` 함수 정의에 `__foldBound` 플래그 확인 패턴(`el.__foldBound`)이 존재한다.
- [ ] `test_fold_key_prefix` (정상): `FOLD_KEY_PREFIX`가 `'dev-monitor:fold:'` 값으로 정의된다.
- [ ] `test_fold_apply_states` (정상): `applyFoldStates` 함수가 `details[data-wp]`를 쿼리하고 `removeAttribute('open')` 또는 `setAttribute('open','')` 호출을 포함한다.
- [ ] `test_fold_init_hook` (정상): `init()` 함수 내 `startMainPoll()` 직전에 `applyFoldStates` 호출이 존재한다.
- [ ] `test_fold_try_catch` (에러): `readFold`와 `writeFold` 각각에 `try{...}catch` 블록이 존재한다 — quota/disabled localStorage 대응.
- [ ] `test_fold_server_default_open` (서버 계약): 서버 `_section_wp_cards` Python 함수가 `details` 요소를 `open` attribute와 함께 렌더링한다 (서버 계약 변경 없음 확인).
- [ ] (통합): 5초 auto-refresh 후 접힌 WP 카드가 다시 펼쳐지지 않는다 (AC-23 — 수동 브라우저 관찰 기반, test 파일에 skip 마커 포함).
- [ ] (통합): 하드 리로드(F5) 후 접힌 상태가 유지된다 (AC-24 — 수동 브라우저 관찰 기반, test 파일에 skip 마커 포함).

**fullstack/frontend Task 필수 항목 (E2E 테스트에서 검증 — dev-test reachability gate):**
- [ ] (클릭 경로) 대시보드 접근 후 WP 카드 `<summary>` 클릭으로 WP 카드를 접는다 (URL 직접 입력 금지)
- [ ] (화면 렌더링) 핵심 UI 요소인 `<details data-wp>` 요소가 브라우저에서 실제 표시되고 기본 토글 상호작용이 동작한다
