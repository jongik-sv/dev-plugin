# TSK-03-02: /api/graph 엔드포인트 - 테스트 보고

## 실행 요약

| 구분        | 통과 | 실패 | 합계 |
|-------------|------|------|------|
| 단위 테스트 | 58   | 0    | 58   |
| E2E 테스트  | 0    | 0    | 0    |

**결과**: ✅ **통과**

---

## 단위 테스트 결과

### 테스트 환경
- 테스트 프레임워크: pytest 8.4.2
- Python 버전: 3.9.6
- 실행 시간: ~0.11초
- 타임아웃: 300초 (run-test.py 래핑)

### 테스트 파일

#### 1. `test_monitor_graph_api.py` (42 테스트)
**목적**: `/api/graph` 엔드포인트 핸들러 + 상태 도출 로직 검증

##### `TestIsApiGraphPath` (8 테스트)
- ✅ 경로 패턴 매칭 (`/api/graph` exact)
- ✅ 쿼리 파라미터 포함 시 매칭 (`/api/graph?subproject=p1`)
- ✅ 유사 경로 구분 (`/api/pane`, `/`, `/api/state` 등 제외)

**결과**: 8/8 PASSED

##### `TestDeriveNodeStatus` (16 테스트)
**목적**: `_derive_node_status()` 상태 판정 로직 (우선순위: bypassed > failed > done > running > pending)

- ✅ `status == "[xx]"` → `"done"`
- ✅ `.running` 신호 존재 → `"running"`
- ✅ `status in {"[dd]", "[im]", "[ts]"}` + 신호 없음 → `"running"`
- ✅ `.failed` 신호 존재 → `"failed"`
- ✅ `last.event == "fail"` (design/build/test/refactor) → `"failed"`
- ✅ `bypassed == true` → `"bypassed"` (최우선)
- ✅ 상태 우선순위: bypassed > failed > done > running > pending
- ✅ 다른 task의 신호는 무시

**결과**: 16/16 PASSED

##### `TestBuildGraphPayload` (7 테스트)
**목적**: 응답 JSON 조립 로직

- ✅ 필드 존재성: `nodes`, `edges`, `stats`, `critical_path`, `subproject`, `docs_dir`, `generated_at`
- ✅ 각 노드: `id`, `label`, `status`, `wp_id`, `is_critical`, `is_bottleneck`, `fan_in`, `fan_out`, `bypassed`
- ✅ 엣지: `source`, `target`
- ✅ stats: `total`, `done`, `running`, `pending`, `failed`, `bypassed`, `max_chain_depth`
- ✅ `stats.total == len(nodes)`
- ✅ `stats.done + stats.running + stats.pending + stats.failed + stats.bypassed == stats.total`
- ✅ `critical_path.nodes` 최장 경로 계산

**결과**: 7/7 PASSED

##### `TestHandleGraphApi` (9 테스트)
**목적**: `/api/graph` 핸들러 전체 흐름 (scan_tasks → dep-analysis subprocess → 응답 조립)

- ✅ **AC-10**: 응답 `nodes`/`edges`가 wbs.md Task와 depends 정확히 반영
- ✅ **AC-11**: status 5종(done/running/pending/failed/bypassed) 올바르게 파생
- ✅ **AC-15**: `?subproject=p1` 필터링 — `docs/p1/`의 Task만 포함
- ✅ **AC-16**: state.json 변경 → 다음 호출에서 즉시 반영 (캐시 없음)
- ✅ 빈 tasks 시 상태 200, nodes=[], stats 0
- ✅ subprocess 타임아웃 → 500 JSON 응답
- ✅ subprocess 에러 → 500 JSON 응답
- ✅ `?subproject=all` (기본값) → `docs/` 루트의 모든 Task
- ✅ `.running` 신호 존재 시 상태 덮어씀

**결과**: 9/9 PASSED

##### `TestMonitorHandlerGraphRoute` (2 테스트)
**목적**: 라우팅 등록 확인

- ✅ `MonitorHandler.do_GET` 메서드 존재
- ✅ `/api/graph` 라우트 등록

**결과**: 2/2 PASSED

#### 2. `test_dep_analysis_graph_stats.py` (16 테스트)
**목적**: `dep-analysis.py --graph-stats` 확장 검증

##### 그래프 계산 (12 테스트)
- ✅ **linear 경로**: T1 → T2 → T3, critical_path = [T1, T2, T3]
- ✅ **diamond 구조**: 가지 1 (T1→T2→T4) vs 가지 2 (T1→T3→T4), 더 긴 경로 우선
- ✅ **fan_out 계산**: 각 노드의 직접 의존 역방향 수
- ✅ **fan_out=0 검증**: 피의존 노드가 없으면 0
- ✅ **bottleneck_ids**: `fan_in >= 3` 또는 `fan_out >= 3`인 Task 추출
- ✅ **CLI 모드**: `--graph-stats` 플래그 + JSON stdin 입력 → stdout에 확장된 graph_stats 출력
- ✅ **빈 그래프**: nodes=[] → stats 0, critical_path=[], bottleneck_ids=[]
- ✅ **단일 노드**: nodes=[T1] → critical_path=[T1], fan_in/fan_out 모두 0
- ✅ **순환 감지**: 순환 존재 시 예외 발생
- ✅ **결정론성**: 동일 입력 → 동일 출력

**결과**: 12/12 PASSED

##### 호환성 (4 테스트)
- ✅ 기존 필드(`nodes`, `edges`, `stats.total/done/running/pending/failed/max_chain_depth`) 유지
- ✅ 신규 필드(`fan_out_map`, `critical_path`, `bottleneck_ids`) 추가

**결과**: 4/4 PASSED

---

## QA 체크리스트

### 설계 요구사항 (8/8)

| 항목 | 상태 | 비고 |
|------|------|------|
| AC-10: 응답 nodes/edges가 WBS Task와 depends 정확히 반영 | ✅ | test_api_graph_returns_nodes_and_edges |
| AC-11: status 5종 올바르게 파생 | ✅ | test_api_graph_derives_status_done_running_pending_failed_bypassed |
| AC-15: ?subproject=p1 필터링 | ✅ | test_api_graph_respects_subproject_filter |
| AC-16: state.json 변경 → 즉시 반영 (캐시 없음) | ✅ | test_api_graph_no_cache_ac16 |
| `_derive_node_status` 우선순위 (bypassed > failed > done > running > pending) | ✅ | TestDeriveNodeStatus 16 테스트 |
| `_build_graph_payload` stats 항등식 | ✅ | test_stats_sum_equals_total |
| subprocess 에러 처리 (timeout/crash → 500) | ✅ | test_api_graph_subprocess_error_returns_500, timeout |
| critical_path, fan_out, bottleneck_ids 계산 | ✅ | test_dep_analysis_critical_path_*, fan_out, bottleneck |

---

## 기술 검증

### 1. 엔드포인트 라우팅
- ✅ `/api/graph` 경로 정확히 매칭 (쿼리 파라미터 포함)
- ✅ 유사 경로(`/api/state`, `/api/pane`) 구분

### 2. 상태 판정 (5종)
| 상태 | 조건 | 우선순위 | 검증 |
|------|------|---------|------|
| `done` | `status == "[xx]"` | 3 | ✅ test_done_status_xx |
| `running` | `.running` 신호 \| status ∈ {`[dd]`, `[im]`, `[ts]`} | 4 | ✅ 3 테스트 |
| `pending` | 기타 | 5 | ✅ test_pending_* |
| `failed` | `.failed` 신호 \| `last.event == "fail"` | 2 | ✅ 3 테스트 |
| `bypassed` | `bypassed == true` | 1 (최우선) | ✅ test_bypassed_* |

### 3. 서브프로젝트 필터링
- ✅ `?subproject=p1` → `docs/p1/` 스캔
- ✅ `?subproject=all` (기본값) → `docs/` 루트 스캔

### 4. subprocess 통신
- ✅ `dep-analysis.py --graph-stats`를 subprocess로 호출
- ✅ tasks JSON stdin으로 전달
- ✅ graph_stats JSON stdout에서 수신
- ✅ 타임아웃(3초) 적용
- ✅ 에러/timeout → 500 응답

### 5. 그래프 계산 확장 (dep-analysis.py)
- ✅ **fan_out_map**: {task_id: count} — 각 노드의 직접 피의존 수
- ✅ **critical_path**: longest-path DP — 동점 시 alphabetical 순
- ✅ **bottleneck_ids**: `fan_in >= 3` 또는 `fan_out >= 3`인 Task 목록

### 6. 응답 스키마
```json
{
  "subproject": "all|<sp>",
  "docs_dir": "/path/to/docs",
  "generated_at": "2026-04-22T...",
  "stats": {
    "total": N,
    "done": D,
    "running": R,
    "pending": P,
    "failed": F,
    "bypassed": B,
    "max_chain_depth": MC,
    "critical_path_length": CP,
    "bottleneck_count": BC
  },
  "critical_path": {"nodes": [...], "edges": [...]},
  "nodes": [
    {
      "id": "TSK-XX-XX",
      "label": "...",
      "status": "done|running|pending|failed|bypassed",
      "wp_id": "WP-XX",
      "is_critical": bool,
      "is_bottleneck": bool,
      "fan_in": int,
      "fan_out": int,
      "bypassed": bool
    }
  ],
  "edges": [{"source": "TSK-XX-XX", "target": "TSK-XX-XX"}]
}
```
✅ 모든 필드 검증 완료

---

## 컴파일 검증

```bash
python3 -m py_compile scripts/monitor-server.py scripts/dep-analysis.py
```
✅ **통과** — 문법 에러 없음

---

## E2E 테스트

**상태**: N/A

**근거**: domain=backend (API 핸들러이며 UI 없음). Dev Config에 `domains.backend.e2e_test = null`.

---

## 성능 검증

- ✅ subprocess 타임아웃: 3초 설정 (설계: `<50ms` 목표, 2초 폴링 허용)
- ✅ 테스트 실행 시간: 0.11초 (체계적 검증)

---

## 결론

### 통과 조건

| 조건 | 상태 |
|------|------|
| 모든 설계 테스트 통과 | ✅ 58/58 |
| AC 요구사항 충족 (AC-10, 11, 15, 16) | ✅ 모두 검증됨 |
| 상태 도출 5종 올바름 | ✅ 우선순위 + 각 케이스 검증 |
| 그래프 계산 정확성 | ✅ critical_path, fan_out, bottleneck |
| 컴파일 성공 | ✅ |
| subprocess 통신 동작 | ✅ stdin/stdout JSON 파이핑 |

### 최종 판정

✅ **모든 테스트 통과** — TSK-03-02 테스트 페이즈 성공

이 Task는 다음 단계(Refactor)로 진행할 준비가 완료되었습니다.

---

## 실행 환경 메타데이터

- **테스트 일시**: 2026-04-22 (현재)
- **테스트 대상**: 
  - `scripts/monitor-server.py` (`_derive_node_status`, `_handle_graph_api`, `_is_api_graph_path`)
  - `scripts/dep-analysis.py` (`compute_graph_stats` 확장)
- **테스트 실행**: `python3 /path/to/run-test.py 300 -- python3 -m pytest scripts/test_monitor_graph_api.py scripts/test_dep_analysis_graph_stats.py -v`
- **결과 요약**: 58 passed, 0 failed, 0 skipped, 0 errors
