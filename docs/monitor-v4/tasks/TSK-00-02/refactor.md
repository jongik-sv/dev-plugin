# TSK-00-02: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 (콤마 구분) |
|------|-----------------|----------------------|
| `scripts/monitor-server.py` | `_serialize_phase_history_tail_for_graph`: `getattr(entry, field, None)` 방어 코드 → 직접 속성 접근 (`entry.event`, `entry.from_status` 등) + loop-append → list comprehension | Simplify Conditional, Remove Duplication |
| `scripts/monitor-server.py` | `_build_graph_payload`: `getattr(task, "phase_history_tail", None)` → `task.phase_history_tail` (WorkItem dataclass 필드 직접 접근) | Simplify Conditional |
| `scripts/monitor-server.py` | `_build_graph_payload`: `bottleneck_ids` (list) → `bottleneck_set` (set) 으로 루프 진입 전 한 번 변환, `task.id in bottleneck_ids` O(N) lookup → O(1) set membership | Replace Magic Number → Introduce Variable, Performance |

## 변경 상세

### 1. `_serialize_phase_history_tail_for_graph` — `getattr` 제거

**변경 전:**
```python
result = []
for entry in tail:
    result.append({
        "event": getattr(entry, "event", None),
        "from": getattr(entry, "from_status", None),
        "to": getattr(entry, "to_status", None),
        "at": getattr(entry, "at", None),
        "elapsed_seconds": getattr(entry, "elapsed_seconds", None),
    })
return result
```

**변경 후:**
```python
return [
    {
        "event": entry.event,
        "from": entry.from_status,
        "to": entry.to_status,
        "at": entry.at,
        "elapsed_seconds": entry.elapsed_seconds,
    }
    for entry in tail
]
```

**근거:** `PhaseEntry`는 `@dataclass(frozen=True)`이며 모든 5개 필드(`event`, `from_status`, `to_status`, `at`, `elapsed_seconds`)가 명시적으로 정의되어 있다. `getattr(entry, "event", None)` fallback은 타입 오타(예: `"evnt"`)를 침묵 버그로 숨긴다 — 직접 접근(`entry.event`)이 오류를 즉시 `AttributeError`로 드러낸다. 또한 list comprehension으로 코드 라인 수 감소.

### 2. `_build_graph_payload` — `getattr` 제거

**변경 전:**
```python
"phase_history_tail": _serialize_phase_history_tail_for_graph(
    getattr(task, "phase_history_tail", None)
),
```

**변경 후:**
```python
"phase_history_tail": _serialize_phase_history_tail_for_graph(
    task.phase_history_tail
),
```

**근거:** `WorkItem.phase_history_tail`은 dataclass 필드(`field(default_factory=list)`)로 항상 존재한다. `getattr` fallback 불필요.

### 3. `_build_graph_payload` — `bottleneck_ids` set 변환

**변경 전:**
```python
bottleneck_ids: list = graph_stats.get("bottleneck_ids", [])
# ...루프 안에서:
"is_bottleneck": task.id in bottleneck_ids,  # O(N) per task
```

**변경 후:**
```python
bottleneck_ids: list = graph_stats.get("bottleneck_ids", [])
bottleneck_set: set = set(bottleneck_ids)
# ...루프 안에서:
"is_bottleneck": task.id in bottleneck_set,  # O(1)
```

**근거:** `bottleneck_ids`는 list이므로 `in` 연산이 O(N). 노드 수 T × bottleneck 수 B = O(T·B). 루프 진입 전 set으로 한 번 변환하면 O(T+B). `cp_node_set`이 이미 같은 패턴으로 처리되어 있어 일관성 확보. `bottleneck_count` 통계 산출은 원본 `bottleneck_ids` list의 `len()`을 그대로 사용하므로 동작 변경 없음.

## 테스트 확인
- 결과: **PASS**
- 실행 명령: `PYTHONPATH=/tmp/pytest-deps python3 -m pytest scripts/test_monitor_graph_api.py -q`
- 결과: **55 passed in 0.06s**
- 정적 검증: `python3 -m py_compile scripts/monitor-server.py scripts/dep-analysis.py` — 통과

## 비고
- 케이스 분류: **A (성공)** — 리팩토링 변경 적용 후 단위 테스트 전부 통과.
- `_derive_node_status` 내 `{sig.kind for sig in signals if sig.task_id == task.id}` set comprehension은 O(N×M)이나, 시그니처를 바꾸면 16개 기존 테스트가 영향받아 리팩토링 범위를 초과한다. 차기 반복에서 pre-computed `failed_ids_set`을 `_build_graph_payload`에서 주입하는 방식으로 개선 가능.
