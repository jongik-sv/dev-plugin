# TSK-01-07: Feature 섹션 스캔·렌더 (DEFECT-1 후속) - 설계

## 요구사항 확인

- `docs/features/*/state.json`을 스캔하여 대시보드 Feature 섹션에 렌더링하는 기능이 TSK-01-02/04 구현 당시 코드 레벨에서 이미 완성되어 있다. TSK-03-02 QA(WP-03 워크트리)는 WP-01 머지 이전 코드를 기준으로 테스트하여 DEFECT-1을 보고했으나, 현재 `main` 브랜치 코드에는 `scan_features`, `_section_features`, `_build_state_snapshot.features`, `/api/state features` 배열이 모두 구현되어 있다.
- 따라서 본 Task는 **신규 구현 없이**, 기존 구현의 정확성을 검증하는 **전용 단위/E2E 테스트 강화**가 핵심이다. E2E 테스트(`test_monitor_e2e.py`)에 Feature 섹션 렌더링 시나리오가 누락되어 있으며, 단위 테스트(`test_monitor_scan.py`)에도 엣지 케이스가 보강될 수 있다.
- 수락 기준 3개(fixture 존재 시 렌더 행 존재, 없으면 "no features" 문구, `/api/state` `features` 배열 포함)를 E2E와 단위 테스트로 완전 커버한다.

## 타겟 앱

- **경로**: N/A (단일 앱 — `scripts/monitor-server.py` 단일 파일 프로젝트)
- **근거**: CLAUDE.md 규약 및 PRD §2.1 — "python3 외 추가 설치 0건", 단일 파일 서버

## 구현 방향

- `monitor-server.py`의 `scan_features` / `_section_features` / `_build_state_snapshot` 기능은 이미 완성되어 있으므로 **코드 수정 없음**.
- `test_monitor_scan.py`에 `ScanFeaturesEdgeCaseTests` 클래스를 추가하여 `spec.md` 없는 feature(title=None), 복수 feature 동시 스캔을 검증한다.
- `test_monitor_e2e.py`에 `FeatureSectionE2ETests` 클래스를 추가하여 live 서버의 `GET /`와 `GET /api/state` 응답에서 Feature 섹션을 검증한다. E2E 테스트는 이미 실행 중인 서버의 `--docs` 경로를 그대로 사용하여 실제 상태(feature 있음/없음)를 검증한다.

## 파일 계획

**경로 기준:** 모든 파일 경로는 프로젝트 루트 기준으로 작성한다.

| 파일 경로 | 역할 | 신규/수정 |
|-----------|------|-----------|
| `scripts/monitor-server.py` | Feature 스캔·렌더 본체 (기존 구현 완료) | 수정 없음 |
| `scripts/test_monitor_scan.py` | 단위 테스트 — `ScanFeaturesEdgeCaseTests` 추가 (spec.md 없는 경우, 복수 feature) | 수정 |
| `scripts/test_monitor_e2e.py` | E2E 테스트 — `FeatureSectionE2ETests` 클래스 추가 | 수정 |

## 진입점 (Entry Points)

본 Task는 HTTP 대시보드 서버(`scripts/monitor-server.py`)에 이미 배선된 Feature 섹션을 검증하는 작업이다. 라우터 파일·메뉴/네비게이션 파일은 TSK-01-04에서 이미 배선 완료되어 있다.

- **사용자 진입 경로**: 브라우저에서 `http://localhost:7321` 접속 → 상단 네비바의 `Features` 앵커 클릭 → `#features` 섹션으로 스크롤
- **URL / 라우트**: `GET /` (대시보드 HTML), `GET /api/state` (JSON 스냅샷)
- **수정할 라우터 파일**: `scripts/monitor-server.py` — `MonitorHandler.do_GET()` 내 `_route_root()` 경로 (이미 `scan_features` 호출 완료, 수정 불필요)
- **수정할 메뉴·네비게이션 파일**: `scripts/monitor-server.py` — `_SECTION_ANCHORS` 상수 및 `_section_header()` 함수 (이미 `"features"` 항목 포함, 수정 불필요)
- **연결 확인 방법**: E2E 테스트에서 `GET /` 응답 HTML에 `href="#features"` 앵커와 `id="features"` 섹션이 함께 존재하는지 검증하고, Feature fixture가 있을 때 해당 섹션에 feature ID가 출력되는지 확인한다

## 주요 구조

- `scan_features(docs_dir: Path) -> List[WorkItem]`: `{docs_dir}/features/*/state.json`을 glob 스캔하여 `WorkItem(kind="feat")` 반환. `_scan_dir` 공통 골격에 위임. **이미 구현 완료.**
- `_section_features(features, running_ids, failed_ids) -> str`: `_render_task_row`로 각 Feature를 행 렌더링. 빈 목록이면 `"no features found — docs/features/ is empty"` 메시지. **이미 구현 완료.**
- `_build_state_snapshot(...)`: `features` 필드에 `scan_features(docs_dir)` 결과 포함, `/api/state` JSON에 노출. **이미 구현 완료.**
- `ScanFeaturesEdgeCaseTests` (신규): `test_monitor_scan.py`에 추가. `spec.md` 없는 feature → `title=None`, `raw_error=None`; 복수 feature → 모두 반환 검증.
- `FeatureSectionE2ETests` (신규): `test_monitor_e2e.py`에 추가. live 서버 대상으로 `GET /`에서 `#features` 섹션 존재 및 `GET /api/state`에서 `features` 배열 존재 검증.

## 데이터 흐름

HTTP 요청 → `scan_features(docs_dir)` → `docs/features/*/state.json` on-demand 읽기 → `List[WorkItem(kind="feat")]` → `_section_features(features, running_ids, failed_ids)` → HTML `<section id="features">` 블록 → `render_dashboard(model)` 합성 → 응답 바이트.

`/api/state` 경로: 동일 `_build_state_snapshot()` 호출 → `features` 키에 `List[dict]` 포함 → JSON 직렬화 → 응답.

## 설계 결정 (대안이 있는 경우만)

대안이 없음. 기존 구현 재활용이 유일한 합리적 선택. 중복 구현은 TRD/PRD 및 CLAUDE.md 규약 위반이다.

## 선행 조건

- TSK-01-02: `scan_features` 구현 (완료, `[xx]` 상태)
- TSK-01-04: `_section_features` + `render_dashboard` 구현 (완료, `[xx]` 상태)

## 리스크

- LOW: E2E 테스트는 live 서버를 필요로 하므로 서버가 기동되어 있지 않으면 `@skipUnless` 조건에 의해 자동 스킵된다. 이는 기존 E2E 테스트와 동일한 패턴이며 의도된 동작이다.
- LOW: `FeatureSectionE2ETests`는 서버가 기동된 `--docs` 경로의 실제 feature 유무에 따라 "feature 있음"/"feature 없음" 두 분기를 모두 커버해야 한다. 두 케이스를 단일 테스트 메서드에서 분기 처리하거나 조건부 skipTest로 처리한다.

## QA 체크리스트

- [ ] `scan_features(docs_dir)` — `features/sample/state.json` 존재 시 `len == 1`, `kind == "feat"`, `id == "sample"` (단위)
- [ ] `scan_features(docs_dir)` — `features/` 디렉토리 없으면 `[]` 반환, 예외 없음 (단위, 기확인)
- [ ] `scan_features(docs_dir)` — `spec.md` 없는 feature → `title=None`, `raw_error=None` (단위, 신규)
- [ ] `scan_features(docs_dir)` — 복수 feature(alpha, beta) 존재 시 두 항목 모두 반환 (단위, 신규)
- [ ] `_section_features([], ...)` → HTML에 `"no features"` 문구 포함 (단위, 기확인)
- [ ] `_section_features([item], ...)` → HTML에 해당 feature id가 렌더됨 (단위, 기확인)
- [ ] `GET /` live 응답 — `id="features"` 섹션 존재 및 `href="#features"` 네비 앵커 존재 (E2E, 기확인)
- [ ] `GET /` live 응답 — Feature 있을 때 해당 feature ID가 `#features` 섹션 HTML에 포함됨 (E2E, 신규)
- [ ] `GET /` live 응답 — Feature 없을 때 `#features` 섹션에 `"no features"` 문구 포함 (E2E, 신규)
- [ ] `GET /api/state` live 응답 — `features` 키가 JSON에 존재하고 배열 타입임 (E2E, 신규)
- [ ] (클릭 경로) 상단 네비의 `Features` 앵커 클릭으로 `#features` 섹션에 도달한다 (E2E)
- [ ] (화면 렌더링) Feature 섹션이 브라우저에서 실제 표시되고 feature 행 또는 "no features" 메시지가 렌더된다 (E2E)
