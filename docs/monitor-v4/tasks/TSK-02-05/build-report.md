# TSK-02-05: TDD 구현 결과

## 결과: PASS

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `scripts/monitor-server.py` | `WorkItem.model` 필드 추가, `_load_wbs_title_map` model 파싱 확장, `scan_tasks` model 후처리 추가, `_MAX_ESCALATION()` / `_test_phase_model()` / `_phase_models_for()` / `_DDTR_PHASE_MODELS` 헬퍼 추가, `_build_state_summary_json` 4개 필드(model/retry_count/phase_models/escalated) 확장, `_render_task_row_v2` 모델 칩 + ⚡ 플래그 삽입, CSS `.model-chip`/`.escalation-flag` 추가, JS `renderPhaseModels` 함수 및 툴팁 렌더러 확장 | 수정 |
| `scripts/test_monitor_task_row.py` | `_render_task_row_v2` 모델 칩/⚡/phase_models/escalated 단위 테스트 (47개) | 신규 |
| `scripts/test_monitor_phase_models.py` | `_test_phase_model`/`_phase_models_for`/`_MAX_ESCALATION` 순수 함수 단위 테스트 (26개) | 신규 |
| `scripts/test_monitor_e2e.py` | TSK-02-05 E2E 테스트 클래스 `TaskModelChipE2ETests` (8개 케이스) 추가 | 수정 |

## 테스트 결과

| 구분 | 통과 | 실패 | 합계 |
|------|------|------|------|
| 신규 단위 테스트 (TSK-02-05) | 73 | 0 | 73 |
| 전체 단위 테스트 (회귀 포함) | 1383 | 0 | 1383 |

(skipped: 15 — E2E 서버 미기동 조건부 skip, 정상)

## E2E 테스트 (작성만 — 실행은 dev-test)

| 파일 경로 | 검증 대상 |
|-----------|-----------|
| `scripts/test_monitor_e2e.py` | `TaskModelChipE2ETests`: GET / HTML에 .model-chip 존재, data-model 유효 값, data-state-summary.phase_models 4키, CSS .model-chip/.escalation-flag, JS renderPhaseModels 함수, phase-models dl 클래스 |

## 커버리지 (Dev Config에 coverage 정의 시)

N/A — Dev Config에 `quality_commands.coverage` 미정의. `typecheck` 명령(`python3 -m py_compile`) 통과.

## 비고

- `WorkItem` 데이터클래스에 `model: Optional[str] = None` 필드를 추가하여 하위 호환성 유지 (기존 WorkItem 생성자 호출 무변경).
- `_load_wbs_title_map` 반환 타입이 3-tuple → 4-tuple로 변경됨. `_scan_dir`/`scan_features`는 3-tuple lookup 사용 유지, `scan_tasks`만 4번째 요소(model)를 후처리로 채움.
- `MAX_ESCALATION` 환경변수: 매 호출마다 재읽기 방식 → pytest `monkeypatch.setenv` 없이 os.environ 직접 변경으로 테스트 가능.
- JS `renderTooltipHtml` 반환 타입을 `dl` → `DocumentFragment`로 변경하여 phase_models `<dl>` 을 동일 tooltip 컨테이너에 append.
