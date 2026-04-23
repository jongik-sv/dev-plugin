"""
merge-preview-scanner.py — TSK-04-02

WP별 merge-preview.json 집계 + 상태 판정 + merge-status.json 원자 쓰기.

Usage:
    python3 scripts/merge-preview-scanner.py --docs docs/monitor-v4
    python3 scripts/merge-preview-scanner.py --docs docs/monitor-v4 --force
    python3 scripts/merge-preview-scanner.py --docs docs/monitor-v4 --daemon 120

stdlib only. No pip dependencies.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import signal
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Constants (TRD §3.12)
# ---------------------------------------------------------------------------

AUTO_MERGE_FILES: frozenset[str] = frozenset({"state.json", "wbs.md", "wbs-merge-log.md"})
STALE_SECONDS: float = 1800.0  # 30 minutes

# Regex: TSK-{two-digit-group}-{digits} → WP-{zero-padded two digit}
_TSK_ID_RE = re.compile(r"^TSK-(\d+)-\d+$")

# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _extract_wp_id(tsk_id: str) -> Optional[str]:
    """Extract WP-ID from TSK-XX-YY pattern.

    Returns 'WP-{int:02d}' or None if pattern doesn't match.
    Examples:
        'TSK-02-03' → 'WP-02'
        'TSK-10-01' → 'WP-10'
        'INVALID'   → None
    """
    m = _TSK_ID_RE.match(tsk_id)
    if not m:
        return None
    return f"WP-{int(m.group(1)):02d}"


def scan_tasks(docs_dir: Path) -> dict[str, list[dict]]:
    """Scan docs_dir/tasks/TSK-*/merge-preview.json and group by WP-ID.

    For each file:
    - Load JSON
    - Extract WP-ID from directory name (TSK-XX-YY pattern)
    - Read _mtime from file stat
    - Read _status from adjacent state.json (None if missing)
    - Inject _mtime, _tsk_id, _status into dict

    WP-ID extraction failure → stderr warning + skip.

    Returns: {wp_id: [preview_dict, ...]}
    """
    groups: dict[str, list[dict]] = {}

    tasks_dir = docs_dir / "tasks"
    if not tasks_dir.exists():
        return groups

    # Use os.scandir for efficiency (avoids double stat)
    try:
        entries = list(os.scandir(str(tasks_dir)))
    except OSError as e:
        sys.stderr.write(f"merge-preview-scanner: cannot scan {tasks_dir}: {e}\n")
        return groups

    for entry in entries:
        if not entry.is_dir():
            continue

        tsk_id = entry.name
        wp_id = _extract_wp_id(tsk_id)
        if wp_id is None:
            sys.stderr.write(
                f"merge-preview-scanner: WP-ID extraction failed for '{tsk_id}', skipping\n"
            )
            continue

        preview_path = Path(entry.path) / "merge-preview.json"
        if not preview_path.exists():
            continue

        try:
            mtime = preview_path.stat().st_mtime
            raw = preview_path.read_text(encoding="utf-8", errors="replace")
            preview = json.loads(raw)
        except (OSError, json.JSONDecodeError) as e:
            sys.stderr.write(
                f"merge-preview-scanner: failed to load {preview_path}: {e}\n"
            )
            continue

        # Read status from adjacent state.json
        status_path = Path(entry.path) / "state.json"
        task_status: Optional[str] = None
        if status_path.exists():
            try:
                state_raw = status_path.read_text(encoding="utf-8", errors="replace")
                state = json.loads(state_raw)
                task_status = state.get("status")
            except (OSError, json.JSONDecodeError):
                pass  # silently treat as None

        # Inject metadata fields
        preview["_mtime"] = mtime
        preview["_tsk_id"] = tsk_id
        preview["_status"] = task_status

        groups.setdefault(wp_id, []).append(preview)

    return groups


def _classify_wp(wp_id: str, previews: list[dict], now: float) -> dict:
    """Classify WP merge readiness from its task previews (TRD §3.12).

    Logic:
    1. stale: any preview._mtime is more than STALE_SECONDS old
    2. incomplete: _status != "[xx]" (including None)
    3. Filter conflicts: keep only files NOT in AUTO_MERGE_FILES
    4. Priority: incomplete > 0 → "waiting"; real_conflicts > 0 → "conflict"; else → "ready"

    Returns dict with schema:
        {wp_id, state, pending_count, conflict_count, conflicts, is_stale, last_scan_at}
    """
    is_stale = any(now - p.get("_mtime", now) > STALE_SECONDS for p in previews)

    pending_count = sum(
        1 for p in previews if p.get("_status") != "[xx]"
    )

    # Collect real (non-auto-merge) conflicts across all tasks
    all_real_conflicts: list[dict] = []
    for p in previews:
        raw_conflicts = p.get("conflicts") or []
        for c in raw_conflicts:
            file_path = c.get("file", "")
            filename = Path(file_path).name
            if filename not in AUTO_MERGE_FILES:
                all_real_conflicts.append(c)

    # State priority: waiting > conflict > ready
    if pending_count > 0:
        state = "waiting"
    elif all_real_conflicts:
        state = "conflict"
    else:
        state = "ready"

    return {
        "wp_id": wp_id,
        "state": state,
        "pending_count": pending_count,
        "conflict_count": len(all_real_conflicts),
        "conflicts": all_real_conflicts,
        "is_stale": is_stale,
        "last_scan_at": _utc_iso(now),
    }


def _utc_iso(ts: float) -> str:
    """Format a Unix timestamp as UTC ISO-8601 string (Z suffix)."""
    return datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_status(wp_id: str, status: dict, out_dir: Path) -> None:
    """Write merge-status.json atomically using tempfile + rename.

    Creates out_dir/wp_id/ if needed.
    Uses NamedTemporaryFile(delete=False) + Path.replace() for atomicity.
    Falls back to shutil.copy2 + unlink on cross-device rename failure.
    """
    target_dir = out_dir / wp_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "merge-status.json"

    body = json.dumps(status, ensure_ascii=False, indent=2)
    tmp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=str(target_dir),
            suffix=".tmp",
            delete=False,
            encoding="utf-8",
            newline="\n",
        ) as tf:
            tf.write(body)
            tmp_path = Path(tf.name)
        try:
            tmp_path.replace(target_file)
        except OSError:
            # Cross-device fallback (e.g. Windows tmpdir on different drive)
            shutil.copy2(str(tmp_path), str(target_file))
            tmp_path.unlink(missing_ok=True)
            tmp_path = None
    except Exception:
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


# ---------------------------------------------------------------------------
# mtime-based skip check
# ---------------------------------------------------------------------------


def _should_skip(wp_id: str, previews: list[dict], out_dir: Path, force: bool) -> bool:
    """Return True if merge-status.json is already up-to-date and --force not set."""
    if force:
        return False
    target = out_dir / wp_id / "merge-status.json"
    if not target.exists():
        return False
    try:
        out_mtime = target.stat().st_mtime
    except OSError:
        return False
    latest_input = max((p.get("_mtime", 0.0) for p in previews), default=0.0)
    return out_mtime >= latest_input


# ---------------------------------------------------------------------------
# Main scan loop
# ---------------------------------------------------------------------------


def _run_once(docs_dir: Path, out_dir: Path, force: bool) -> None:
    """Perform one scan cycle: read previews, classify, write outputs."""
    groups = scan_tasks(docs_dir)
    now = time.time()
    for wp_id, previews in groups.items():
        if _should_skip(wp_id, previews, out_dir, force):
            continue
        status = _classify_wp(wp_id, previews, now)
        write_status(wp_id, status, out_dir)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

_stop = False


def _sigterm_handler(signum, frame):  # noqa: ANN001
    global _stop
    _stop = True


def main() -> None:
    global _stop

    parser = argparse.ArgumentParser(
        description="Scan WP merge-preview.json files and write merge-status.json per WP."
    )
    parser.add_argument(
        "--docs",
        required=True,
        metavar="DIR",
        help="Path to docs directory (e.g. docs/monitor-v4)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore mtime checks and always regenerate output files",
    )
    parser.add_argument(
        "--daemon",
        type=int,
        metavar="N",
        default=0,
        help="Run as daemon, scanning every N seconds (0 = one-shot)",
    )
    args = parser.parse_args()

    docs_dir = Path(args.docs).resolve()
    out_dir = docs_dir / "wp-state"

    if not docs_dir.exists():
        sys.stderr.write(f"merge-preview-scanner: docs dir not found: {docs_dir}\n")
        sys.exit(1)

    if args.daemon > 0:
        signal.signal(signal.SIGTERM, _sigterm_handler)
        try:
            while not _stop:
                _run_once(docs_dir, out_dir, args.force)
                elapsed = 0
                while elapsed < args.daemon and not _stop:
                    time.sleep(1)
                    elapsed += 1
        except KeyboardInterrupt:
            pass
    else:
        _run_once(docs_dir, out_dir, args.force)


if __name__ == "__main__":
    main()
