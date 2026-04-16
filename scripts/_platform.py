"""Cross-platform utilities for dev-plugin scripts."""
import functools
import re
import sys
import tempfile
import pathlib

TEMP_DIR = pathlib.Path(tempfile.gettempdir())
IS_WINDOWS = sys.platform == "win32"
MAX_SIGNAL_LINES = 50

# Pattern: /c/Users/... or /d/project/... (MSYS/Git-Bash drive prefix)
_MSYS_DRIVE_RE = re.compile(r'^/([a-zA-Z])/')


@functools.lru_cache(maxsize=64)
def normalize_path(p: str) -> str:
    """Convert MSYS-style paths to Windows-native on win32.

    MSYS bash (Git Bash) expresses ``C:\\Users\\...`` as ``/c/Users/...``.
    Python's ``pathlib`` / ``os.path`` on Windows interpret the leading ``/``
    as the *current drive root*, turning ``/c/Users`` into ``C:\\c\\Users``
    instead of the intended ``C:\\Users``.

    This function detects the MSYS ``/x/`` prefix and rewrites it to ``X:/``
    so that ``pathlib.Path`` resolves the correct Windows path.  On non-Windows
    platforms (or when the path does not match the MSYS pattern) the input is
    returned unchanged.
    """
    if not IS_WINDOWS:
        return p
    m = _MSYS_DRIVE_RE.match(p)
    if m:
        drive = m.group(1).upper()
        return f"{drive}:/{p[3:]}"
    return p


def json_escape(s: str) -> str:
    """Escape a string for safe embedding in JSON."""
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\n", "\\n")
    s = s.replace("\t", "\\t")
    return s
