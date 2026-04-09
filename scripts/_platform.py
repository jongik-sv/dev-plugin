"""Cross-platform utilities for dev-plugin scripts."""
import sys
import tempfile
import pathlib

TEMP_DIR = pathlib.Path(tempfile.gettempdir())
IS_WINDOWS = sys.platform == "win32"
MAX_SIGNAL_LINES = 50


def json_escape(s: str) -> str:
    """Escape a string for safe embedding in JSON."""
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\n", "\\n")
    s = s.replace("\t", "\\t")
    return s
