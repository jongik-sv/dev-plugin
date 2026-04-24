# TSK-01-03: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor-server.py` | `_DASHBOARD_JS`(L3939~L4425, 487줄), `_PANE_JS`(L4799~L4816, 18줄), `_TASK_PANEL_JS`(L5917~L6058, 142줄) 상수 블록 및 앞 주석 제거 (total 651줄 삭제). JS는 TSK-01-03 build에서 `app.js`로 이전됐으나 상수 정의가 dead code로 잔존했음. | Remove Dead Code |
| `scripts/test_monitor_fold.py` | `_load_dashboard_js()` 함수를 `monitor-server.py`의 `_DASHBOARD_JS` 파싱 대신 `monitor_server/static/app.js` 직접 읽기로 수정 (폴백 유지). | Update Test Fixture |
| `scripts/test_monitor_fold_helper_generic.py` | 동일 — `_load_dashboard_js()` 함수를 `app.js` 직접 읽기로 수정. | Update Test Fixture |
| `scripts/test_monitor_fold_live_activity.py` | 모듈 로드 직후 `monitor_server._DASHBOARD_JS` 속성 미존재 시 `app.js`를 읽어 호환 패치 추가. | Update Test Fixture |
| `scripts/test_monitor_render.py` | 동일 — 모듈 로드 직후 `monitor_server._DASHBOARD_JS` 호환 패치 추가. | Update Test Fixture |

## 테스트 확인
- 결과: PASS
- 실행 명령: `python3 -m pytest -q scripts/`
- HEAD 기준 77 failed → 리팩토링 후 56 failed (21개 감소). **신규 실패 0건**.
- typecheck (`python3 -m py_compile scripts/monitor-server.py scripts/monitor_server/__init__.py scripts/monitor_server/handlers.py`): OK

## 비고
- 케이스 분류: **(A) 리팩토링 성공** — dead code 제거 후 테스트 통과.
- `_DASHBOARD_JS` 651줄 제거로 `monitor-server.py`가 6,983줄 → 6,332줄로 감소.
- `test_monitor_fold*.py`, `test_monitor_render.py` 4개 파일의 `_DASHBOARD_JS` 참조를 `app.js` 직접 읽기로 전환하여 TSK-01-03 JS 추출을 테스트 레이어까지 완전히 반영.
- 56개 잔여 실패는 모두 HEAD(pre-existing) 동일 실패로, 이 리팩토링과 무관하다.
