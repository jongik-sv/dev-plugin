import importlib.util
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_MONITOR_PATH = _THIS_DIR / "monitor-server.py"
_spec = importlib.util.spec_from_file_location("monitor_server", _MONITOR_PATH)
monitor_server = importlib.util.module_from_spec(_spec)
sys.modules["monitor_server"] = monitor_server
_spec.loader.exec_module(monitor_server)

from test_monitor_render import _make_task

task = _make_task(tsk_id="TSK-01-01", status="[im]")
html = monitor_server._render_task_row_v2(task, {"TSK-01-01"}, set())
print("HTML:")
print(html)
print()
print("Contains data-running:", "data-running" in html)
print("Contains spinner:", 'class="spinner"' in html)
print("Contains data-phase:", "data-phase" in html)
