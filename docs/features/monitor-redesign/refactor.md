# monitor-redesign: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor-server.py` | `DASHBOARD_CSS` 내 `.col` 선택자 중복(line 1213 / 1725) 제거 — 후방 중복 제거 | Remove Duplication |
| `scripts/monitor-server.py` | `.arow` 선택자 두 블록 통합 — 구 v3 정의(구 line 1430-1453) 삭제하고 redesign 정의(line 1742-)에 `:hover`, `data-to` 색상 선택자, `.to font-weight` 추가 | Consolidate Duplicate Fragment |
| `scripts/monitor-server.py` | `_DASHBOARD_CSS_COMPAT` 내 `/* kpi-section: used by _section_kpi */` 주석이 잘못된 정보(v3 redesign 후 해당 클래스 미사용) — 실제 용도(backward-compat assertion test 전용)로 수정 | Fix Misleading Comment |

### 변경 상세

**`.col` 중복 제거**
- 원인: Build 단계에서 `/* ---------- grid columns ---------- */` 블록이 메인 CSS 섹션(§ main 2-col grid) 외부에 중복 삽입됨
- 후방 중복 1줄 + 주석 2줄 제거

**`.arow` 통합**
- 원인: Build 단계에서 `/* ---------- activity row (redesign) ---------- */` 블록이 기존 `/* ---------- 6. Live Activity ---------- */` 내 `.arow` 정의와 병존
- 구 v3 `.arow` 정의는 `grid-template-columns: auto auto 1fr auto`, `padding: 5px 14px`, `border-bottom: 1px dashed transparent` 등 redesign과 다른 값을 가졌음
- redesign 정의가 실제 렌더 결과를 결정(CSS cascade 후방 우선)하므로 구 정의 삭제
- 구 정의에만 있던 `:hover`, `data-to` 상태별 `.to` 색상 선택자를 redesign 블록에 추가 (기능 보존)

**주석 수정**
- `/* kpi-section: used by _section_kpi */` → `/* kpi legacy — v3 redesign replaced with ...*/` 로 변경
- 레거시 `.kpi-card*`, `.kpi-label`, `.kpi-num`, `.kpi-sparkline` 등 CSS는 `test_monitor_kpi.py` 내 assertIn 테스트가 존재하므로 삭제 불가 — 주석으로 의도 명시

### 조사하여 변경하지 않은 항목

- **`.spark` 중복 의혹**: `.kpi .spark` (grid 배치)와 `.spark` (display/width)는 서로 다른 속성을 담당하여 중복이 아님 — 유지
- **`_DASHBOARD_CSS_COMPAT` 레거시 블록 삭제**: 테스트 assertIn으로 보호되어 삭제 불가 — 주석만 수정
- **`_DASHBOARD_JS` 구형 셀렉터**: 전수 grep 결과 `.task-row`, `.activity-row`, `.kpi-card`, `.run-line` 등 구형 셀렉터 참조 없음 — 변경 불필요

## 테스트 확인

- 결과: PASS
- 실행 명령: `python3 -m unittest scripts.test_monitor_render scripts.test_monitor_kpi scripts.test_monitor_signal_scan -v`
- 322개 tests, 0 failures, 0 errors

## 비고

- 케이스 분류: **A** (리팩토링 성공, 테스트 통과)
- 서버 스팟 체크: `curl http://localhost:7322/?subproject=monitor-v3 | head -50` → `<!DOCTYPE html>` 정상 출력, cmdbar 포함 확인
