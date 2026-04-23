#!/usr/bin/env python3
"""Agent tool signal emitter — PreToolUse/PostToolUse hook for dev-monitor.

Writes agent-pool-style signal files when Claude Code invokes the ``Agent``
(a.k.a. ``Task``) tool so the dev-monitor dashboard's "서브 에이전트" section
can display in-flight Agent tool dispatches as running/done/failed pills.

Contract:
  - stdin:  Claude Code hook JSON payload.
  - argv:   ``pre`` | ``post`` (default ``pre``).
  - stdout: silent.
  - exit:   always 0 — the hook must never block the tool call.

Signal layout:
  ``{TEMP_DIR}/agent-pool-signals-hooks-{session}/{task_id}.{running,done,failed}``

The ``agent-pool-signals-`` prefix is what ``monitor-server.py:scan_signals``
already globs for (scope ``agent-pool:*``), so no server-side change is
required beyond existing scope-preserving behavior.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

# Import cross-platform helpers (TEMP_DIR).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _platform import TEMP_DIR  # noqa: E402

_AGENT_TOOL_NAMES = {"Agent", "Task"}
_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9_.\-]+")
_MAX_TASK_ID_LEN = 80
_MAX_SESSION_LEN = 40


def _sanitize(raw: str, max_len: int) -> str:
    cleaned = _UNSAFE_CHARS.sub("-", (raw or "").strip()).strip("-")
    return cleaned[:max_len]


def _resolve_task_id(tool_input: dict, tool_use_id: str) -> str:
    description = tool_input.get("description") or ""
    subagent = tool_input.get("subagent_type") or ""
    for candidate in (description, subagent):
        cleaned = _sanitize(candidate, _MAX_TASK_ID_LEN)
        if cleaned:
            return cleaned
    fallback = _sanitize(tool_use_id, _MAX_TASK_ID_LEN)
    return fallback or f"agent-{int(time.time() * 1000)}"


def _resolve_signal_dir(session_id: str) -> Path:
    suffix = _sanitize(session_id, _MAX_SESSION_LEN) or "default"
    path = TEMP_DIR / f"agent-pool-signals-hooks-{suffix}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _atomic_write(path: Path, content: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)
    os.replace(tmp, path)


def _is_error(tool_response) -> bool:
    if isinstance(tool_response, dict):
        if tool_response.get("is_error") is True:
            return True
        status = tool_response.get("status")
        if isinstance(status, str) and status.lower() in {"error", "failed", "failure"}:
            return True
    return False


def _emit(phase: str, payload: dict) -> None:
    tool_name = payload.get("tool_name") or ""
    if tool_name not in _AGENT_TOOL_NAMES:
        return

    tool_input = payload.get("tool_input") or {}
    tool_use_id = payload.get("tool_use_id") or ""
    session_id = payload.get("session_id") or ""

    task_id = _resolve_task_id(tool_input, tool_use_id)
    sig_dir = _resolve_signal_dir(session_id)

    body = json.dumps(
        {
            "tool_use_id": tool_use_id,
            "subagent_type": tool_input.get("subagent_type") or "",
            "description": tool_input.get("description") or "",
            "phase": phase,
            "ts": time.time(),
        },
        ensure_ascii=False,
    )

    if phase == "pre":
        _atomic_write(sig_dir / f"{task_id}.running", body)
        return

    # post-phase — promote .running to .done or .failed
    kind = "failed" if _is_error(payload.get("tool_response")) else "done"
    running = sig_dir / f"{task_id}.running"
    try:
        running.unlink()
    except FileNotFoundError:
        pass
    _atomic_write(sig_dir / f"{task_id}.{kind}", body)


def main() -> int:
    phase = sys.argv[1] if len(sys.argv) > 1 else "pre"
    if phase not in {"pre", "post"}:
        return 0
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError, OSError):
        return 0
    try:
        _emit(phase, payload if isinstance(payload, dict) else {})
    except Exception:
        # Never block the tool call on hook failure.
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
