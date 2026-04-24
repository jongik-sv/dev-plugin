"""monitor_server — dev-monitor v5 패키지.

TSK-01-01: 패키지 스캐폴드 초기 생성.
TSK-02-01: renderers 패키지 포함.
TSK-02-02: api 모듈 포함. /api/* 엔드포인트 핸들러 재수출.

엔트리 파일: scripts/monitor-server.py (하이픈).
패키지 이름: monitor_server (언더스코어).

sys.path.insert(0, Path(__file__).parent.parent) 후 import가 가능하다.
"""

__version__ = "0.5.0"

from .api import (  # noqa: F401  TSK-02-02
    handle_state,
    handle_graph,
    handle_task_detail,
    handle_merge_status,
)
