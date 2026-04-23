#!/usr/bin/env python3
"""merge-state-json.py — Git custom merge driver for state.json sidecars.

Driver signature (per git documentation):
    merge-state-json.py %O %A %B [%L]
where:
    %O  base version (ancestor)
    %A  ours (current branch; result must be written here on success)
    %B  theirs (incoming)
    %L  conflict marker size (ignored)

Algorithm (TRD §3.12.5):
    1. Load 3 files as JSON. Any parse error → exit 1 (fall back to default
       3-way conflict markers; OURS is not modified).
    2. phase_history: union, dedup by (event, from, to, at), sort by `at`
       ascending (ISO-8601 lexicographic).
    3. status: priority order [xx] > [ts] > [im] > [dd] > [ ]; tie → ours.
    4. bypassed: ours OR theirs (any truthy wins). bypassed_reason preserved
       from whichever side has bypassed=True (ours wins ties).
    5. started_at: earliest non-null value.
    6. updated: max(ours.updated, theirs.updated) by ISO-8601 lexicographic.
    7. last: recomputed from sorted phase_history's final entry.
    8. completed_at / elapsed_seconds: preserved only when merged status=[xx];
       taken from whichever side has the more recent `updated`.
    9. Any other unknown keys are preserved with ours-wins, theirs-fallback.
   10. Result written atomically (tmp in same dir + os.replace) to OURS.

Exit codes:
    0  success — OURS overwritten with merged content
    1  fallback — OURS untouched, git applies standard 3-way markers
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
from typing import Any


STATUS_PRIORITY = {
    "[ ]": 0,
    "[dd]": 1,
    "[im]": 2,
    "[ts]": 3,
    "[xx]": 4,
}


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def _load_json(path: pathlib.Path) -> tuple[Any, str | None]:
    """Return (data, err). data is None on error."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        return None, f"read error: {e}"
    try:
        return json.loads(raw), None
    except (ValueError, json.JSONDecodeError) as e:
        return None, f"json parse error: {e}"


def _atomic_write_json(path: pathlib.Path, data: dict) -> None:
    """Write data as JSON to path atomically (tmp in same dir + os.replace)."""
    dirp = path.parent
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=str(dirp),
        delete=False,
        suffix=".tmp",
        encoding="utf-8",
        newline="\n",
    ) as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
        tmp_path = fh.name
    os.replace(tmp_path, str(path))


# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------

def _status_max(a: str, b: str) -> str:
    """Return the higher-priority status; ties favour `a` (ours)."""
    pa = STATUS_PRIORITY.get(a, -1)
    pb = STATUS_PRIORITY.get(b, -1)
    return a if pa >= pb else b


def _dedup_phase_history(items: list[dict]) -> list[dict]:
    """Deduplicate by (event, from, to, at) tuple; sort by `at` ascending."""
    seen: set[tuple] = set()
    out: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        key = (
            item.get("event"),
            item.get("from"),
            item.get("to"),
            item.get("at"),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    out.sort(key=lambda e: (e.get("at") or "", e.get("event") or ""))
    return out


def _min_iso(a: str | None, b: str | None) -> str | None:
    if a and b:
        return a if a <= b else b
    return a or b


def _max_iso(a: str | None, b: str | None) -> str | None:
    if a and b:
        return a if a >= b else b
    return a or b


def merge_state(base: dict, ours: dict, theirs: dict) -> dict:
    """Domain merge of two state.json dicts. `base` is retained for future use.

    The result is a brand-new dict; inputs are not mutated.
    """
    # Start with a shallow union: theirs first, then ours overrides, so that
    # unknown keys present only in theirs survive with ours-wins precedence.
    merged: dict = {}
    for k, v in theirs.items():
        merged[k] = v
    for k, v in ours.items():
        merged[k] = v

    # ---- phase_history ----
    ph_ours = ours.get("phase_history") or []
    ph_theirs = theirs.get("phase_history") or []
    if not isinstance(ph_ours, list):
        ph_ours = []
    if not isinstance(ph_theirs, list):
        ph_theirs = []
    merged_history = _dedup_phase_history(list(ph_ours) + list(ph_theirs))
    merged["phase_history"] = merged_history

    # ---- status (priority) ----
    status_o = ours.get("status") or "[ ]"
    status_t = theirs.get("status") or "[ ]"
    merged_status = _status_max(status_o, status_t)
    merged["status"] = merged_status

    # ---- bypassed (OR) + reason ----
    bp_o = bool(ours.get("bypassed"))
    bp_t = bool(theirs.get("bypassed"))
    merged_bp = bp_o or bp_t
    if merged_bp:
        merged["bypassed"] = True
        if bp_o and ours.get("bypassed_reason") is not None:
            merged["bypassed_reason"] = ours.get("bypassed_reason")
        elif bp_t and theirs.get("bypassed_reason") is not None:
            merged["bypassed_reason"] = theirs.get("bypassed_reason")
        else:
            merged.pop("bypassed_reason", None)
    else:
        merged.pop("bypassed", None)
        merged.pop("bypassed_reason", None)

    # ---- started_at (min non-null) ----
    started = _min_iso(ours.get("started_at"), theirs.get("started_at"))
    if started is not None:
        merged["started_at"] = started
    else:
        merged.pop("started_at", None)

    # ---- updated (max) ----
    merged_updated = _max_iso(ours.get("updated"), theirs.get("updated"))
    if merged_updated is not None:
        merged["updated"] = merged_updated
    else:
        merged.pop("updated", None)

    # ---- last (recomputed from sorted phase_history tail) ----
    if merged_history:
        tail = merged_history[-1]
        merged["last"] = {
            "event": tail.get("event"),
            "at": tail.get("at"),
        }
    else:
        merged.pop("last", None)

    # ---- completed_at / elapsed_seconds (only when result status=[xx]) ----
    if merged_status == "[xx]":
        # Take from whichever side has the more recent `updated` and
        # actually has a completed_at value; fall back to the other.
        o_done = ours.get("completed_at")
        t_done = theirs.get("completed_at")
        o_upd = ours.get("updated") or ""
        t_upd = theirs.get("updated") or ""
        pick_ours_first = o_upd >= t_upd
        if pick_ours_first:
            completed = o_done if o_done is not None else t_done
            elapsed = (ours.get("elapsed_seconds")
                       if o_done is not None else theirs.get("elapsed_seconds"))
        else:
            completed = t_done if t_done is not None else o_done
            elapsed = (theirs.get("elapsed_seconds")
                       if t_done is not None else ours.get("elapsed_seconds"))
        if completed is not None:
            merged["completed_at"] = completed
        else:
            merged.pop("completed_at", None)
        if elapsed is not None:
            merged["elapsed_seconds"] = elapsed
        else:
            merged.pop("elapsed_seconds", None)
    else:
        merged.pop("completed_at", None)
        merged.pop("elapsed_seconds", None)

    return merged


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    if len(argv) < 4:
        print(
            "usage: merge-state-json.py BASE OURS THEIRS [MARKER_SIZE]",
            file=sys.stderr,
        )
        return 1

    base_p = pathlib.Path(argv[1])
    ours_p = pathlib.Path(argv[2])
    theirs_p = pathlib.Path(argv[3])

    base_data, err_b = _load_json(base_p)
    ours_data, err_o = _load_json(ours_p)
    theirs_data, err_t = _load_json(theirs_p)

    # `base` may be legitimately absent (file added on both sides). Treat a
    # missing/unparsable base as an empty dict to allow the merge to proceed.
    if err_b is not None:
        base_data = {}
    else:
        if not isinstance(base_data, dict):
            base_data = {}

    if err_o is not None or err_t is not None:
        # Any non-base parse error triggers the fallback: leave OURS intact.
        print(
            f"merge-state-json: parse failure (ours_err={err_o}, theirs_err={err_t})",
            file=sys.stderr,
        )
        return 1

    if not isinstance(ours_data, dict) or not isinstance(theirs_data, dict):
        print("merge-state-json: ours/theirs must be JSON objects", file=sys.stderr)
        return 1

    try:
        merged = merge_state(base_data, ours_data, theirs_data)
    except Exception as e:  # pragma: no cover - defensive
        print(f"merge-state-json: merge error: {e}", file=sys.stderr)
        return 1

    try:
        _atomic_write_json(ours_p, merged)
    except OSError as e:
        print(f"merge-state-json: write error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
