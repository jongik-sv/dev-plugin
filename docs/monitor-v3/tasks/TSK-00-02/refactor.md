# TSK-00-02: 리팩토링 내역

## 변경 사항

| 파일 | 변경 내용 (요약) | 적용 기법 |
|------|-----------------|-----------|
| `scripts/monitor-server.py` | `_filter_panes_by_project` 루프 내 `root + os.sep` 반복 계산을 루프 전 `root_sep` 변수로 추출 | Extract Variable (Introduce Explaining Variable) |
| `scripts/test_monitor_filter_helpers.py` | `import os`를 test 메서드 내부에서 파일 상단 import 섹션으로 이동 | Move Import |

## 테스트 확인
- 결과: PASS
- 실행 명령: `/usr/bin/python3 -m pytest -q scripts/test_monitor_filter_helpers.py`
- 24/24 통과 (전과 동일)

## 비고
- 케이스 분류 (SKILL.md 단계 3 참조): A (성공 — 리팩토링 적용 후 테스트 통과)
- `_filter_panes_by_project`의 `root + os.sep`은 루프 순회마다 동일한 값을 재계산하고 있었음. 입력 리스트가 작을 때는 성능 차이가 미미하지만, Extract Variable로 의도를 명확히 하는 효과도 있음.
- `import os`의 메서드 내 위치는 기능상 문제없으나, PEP 8 권장("파일 상단에 모아 둔다")에 어긋나 lint 경고 대상이 될 수 있어 이동함.
- `_filter_signals_by_project`는 이미 `prefix = project_name + "-"` 변수 추출이 된 상태로 추가 개선 불필요.
