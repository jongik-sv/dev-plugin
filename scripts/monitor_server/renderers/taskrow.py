"""monitor_server.renderers.taskrow — phase/task-row 공용 헬퍼.

TSK-02-01:
- 커밋 1 시점 (선-shim): monitor-server.py의 함수를 _util 경유로 재-export.
  wp.py / depgraph.py 가 커밋 1~5 기간 동안 이 모듈에서 import할 수 있도록 선행 생성.
- 커밋 6 시점 (본문 이전): 함수 본문을 monitor-server.py에서 복사하고
  monitor-server.py의 원본은 shim 라인으로 대체.

현재 상태: 선-shim (커밋 1).
"""

from __future__ import annotations

from ._util import _mod as _entry  # type: ignore[attr-defined]

# 선-shim: monitor-server.py의 원본 함수를 그대로 재-export
_phase_label = _entry._phase_label
_phase_data_attr = _entry._phase_data_attr
_trow_data_status = _entry._trow_data_status
_render_task_row_v2 = _entry._render_task_row_v2
