# TSK-00-01: TDD 구현 결과

## 결과: FAIL

**사유**: `pytest -q scripts/` exit 1 — 41개 실패. acceptance criterion `pytest exit 0` 미충족.

**코드 변경 0 제약**: 이 Task는 측정과 태깅만 수행하는 infra Task로, 테스트 실패를 코드 수정으로 해결하는 것은 범위 밖이다.

**실패 분류**:
- 25개: `test_monitor_filter_bar_e2e.py` — TSK-05-01 v5 새 기능 TDD Red (정상)
- 3개: `test_monitor_graph_filter_e2e.py` — TSK-05-02 v5 새 기능 TDD Red (정상)
- 10개: `test_monitor_e2e.py` — v4 디자인 회귀 (v3 리팩터링 후 테스트 미갱신)
- 3개: `test_monitor_dep_graph_html.py` + `test_monitor_render.py` — v4 기존 회귀

## 생성/수정된 파일

| 파일 경로 | 변경 내용 | 신규/수정 |
|-----------|-----------|-----------|
| `docs/monitor-v5/baseline.md` | v4 기준선 기록 갱신 (전체 41개 실패 분류 상세화) | 수정 |

> 코드 변경 0 제약 — baseline.md 외 어떤 파일도 수정하지 않았다.

## 테스트 결과

### 전체 (`pytest -q scripts/`)

| 구분 | 통과 | 실패 | 스킵 | exit code |
|------|------|------|------|-----------|
| 전체 실행 | 1739 | **41** | 31 | **1** |

### 실패 카테고리별 분류

| 카테고리 | 파일 | 개수 | 처리 방향 |
|----------|------|------|-----------|
| v5 새 기능 TDD Red | `test_monitor_filter_bar_e2e.py` | 25 | v5 Tasks 구현 시 Green 전환 |
| v5 새 기능 TDD Red | `test_monitor_graph_filter_e2e.py` | 3 | v5 Tasks 구현 시 Green 전환 |
| v4 디자인 회귀 | `test_monitor_e2e.py` | 10 | v5 S1 또는 별도 Task에서 수정 |
| v4 기존 회귀 | `test_monitor_dep_graph_html.py` + `test_monitor_render.py` | 3 | v5 S1에서 수정 |

### v4 unit 테스트만 (E2E/v5 파일 제외)

| 구분 | 통과 | 실패 | 스킵 | exit code |
|------|------|------|------|-----------|
| unit only | 1663 | **3** | 25 | **1** |

## E2E 테스트 (작성만 — 실행은 dev-test)

N/A — infra domain (코드 변경 없는 측정/태깅 Task)

## 커버리지

N/A — Dev Config에 coverage 미정의

## 비고

- **git tag 생성 완료**: `monitor-server-pre-v5` → `f1e7e7d7509675e8f579acf8282a4d3eafba4b9e`
- **플러그인 캐시 일치 확인**: `~/.claude/plugins/marketplaces/dev-tools/scripts/monitor-server.py` MD5 = `f360c1fc683e146b6713fc0c57d06940` (프로젝트와 동일)
- **baseline.md 기재 완료**: 커밋 SHA, 태그명, pytest 결과 요약(분류 포함), 플러그인 캐시 확인 결과
- **AC 달성 현황**: 태그 생성 ✅ / baseline.md 기재 ✅ / pytest exit 0 ❌ (v4+v5 테스트 혼재로 달성 불가)
- **v4 기존 회귀 3개**: height:640px 테스트(clamp 미반영) + running 시그널 done 계산 버그 → v5 S1 수정 대상
