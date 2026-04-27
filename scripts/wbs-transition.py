#!/usr/bin/env python3
"""wbs-transition.py — Apply a state machine transition to a Task (WBS or Feature).

Loads the DFA from references/state-machine.json and applies the transition
based on the current status and event. Unlike a strict DFA, this transition
engine is **permissive**: undefined transitions (typically *.fail events) are
treated as no-ops that leave ``status`` unchanged while still being recorded
in ``phase_history`` and ``last``.

State is stored in a sidecar ``state.json`` file:

  WBS mode:  docs/tasks/{TSK-ID}/state.json
  Feat mode: docs/features/{name}/state.json

``state.json`` schema:
  {
    "status": "[im]",
    "started_at": "2026-04-11T15:00:00Z",
    "last": { "event": "test.fail", "at": "2026-04-11T15:30:00Z" },
    "phase_history": [ { "event": "...", "from": "[ ]", "to": "[dd]", "at": "...", "elapsed_seconds": 120 }, ... ],
    "updated": "2026-04-11T15:30:00Z",
    "completed_at": "2026-04-11T16:00:00Z",   // set when [xx]
    "elapsed_seconds": 3600                     // total, set when [xx]
  }

For WBS mode, the task block's ``- status: [xxx]`` line in wbs.md is kept
in sync with the state.json status (state.json is the source of truth).

Two sources supported (same DFA, different storage):

  WBS mode (default):
    wbs-transition.py <wbs-path> <TSK-ID> <event>

  Feature mode:
    wbs-transition.py --feat <feat-dir> <event>

  event: design.ok | build.ok | build.fail
       | test.ok   | test.fail   | refactor.ok | refactor.fail
       | bypass

Examples:
  wbs-transition.py docs/wbs.md TSK-01-02 design.ok
  wbs-transition.py --feat docs/features/login-2fa build.fail

Output (JSON):
  Success: {"source": "wbs", "id": "TSK-01-02", "previous": "[ ]", "current": "[dd]", "event": "design.ok", "ok": true, "no_change": false}
  No-op:   {"source": "wbs", "id": "TSK-01-02", "previous": "[im]", "current": "[im]", "event": "test.fail", "ok": true, "no_change": true}
  Bypass:  {"source": "wbs", "id": "TSK-01-02", "previous": "[im]", "current": "[im]", "event": "bypass", "ok": true, "no_change": true, "bypassed": true}
  Failure: {"source": "feat", "id": "login-2fa", "error": "...", "ok": false}
"""
import sys
import os
import re
import json
from datetime import datetime, timezone


# ------------------------------ DFA loader ------------------------------


def load_state_machine():
    """Load the state machine definition from references/state-machine.json."""
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not plugin_root:
        plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sm_path = os.path.join(plugin_root, "references", "state-machine.json")
    if not os.path.isfile(sm_path):
        return None, f"state-machine.json not found at {sm_path}"
    try:
        with open(sm_path, "r", encoding="utf-8") as f:
            return json.load(f), None
    except (OSError, json.JSONDecodeError) as e:
        return None, f"failed to load state-machine.json: {e}"


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _calc_elapsed(prev_iso, curr_iso):
    """Calculate elapsed seconds between two ISO timestamps."""
    try:
        prev_dt = datetime.fromisoformat(prev_iso.replace("Z", "+00:00"))
        curr_dt = datetime.fromisoformat(curr_iso.replace("Z", "+00:00"))
        return round((curr_dt - prev_dt).total_seconds())
    except (ValueError, TypeError, AttributeError):
        return None


# ------------------------------ state.json (shared) ------------------------------


def _default_state():
    return {
        "status": "[ ]",
        "started_at": None,
        "last": None,
        "phase_history": [],
        "updated": now_iso(),
    }


def load_state_json(state_path):
    """Load state.json. Returns (data, err). Missing file returns a default state."""
    if not os.path.isfile(state_path):
        return _default_state(), None
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return None, f"failed to load state.json: {e}"

    # Normalize: ensure required keys exist
    data.setdefault("status", "[ ]")
    data.setdefault("last", None)
    data.setdefault("phase_history", [])
    data.setdefault("started_at", None)
    data.setdefault("updated", now_iso())
    return data, None


def save_state_json(state_path, data):
    try:
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
    except OSError as e:
        return f"failed to create state dir: {e}"
    try:
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return None
    except OSError as e:
        return f"failed to write state.json: {e}"


def apply_transition(sm, state_data, event, bypass_reason="", verification=None, debug_evidence=None):
    """Apply an event to state_data in-place.

    Returns (previous_status, next_status, no_change).
    Undefined transitions are treated as no-ops.
    The special ``bypass`` event marks the task as bypassed without changing status.

    Timing fields (added automatically):
      - started_at: set on first event (top-level)
      - elapsed_seconds: per phase_history entry (delta from previous event)
      - completed_at: set when status reaches [xx] (top-level)
      - elapsed_seconds: total from started_at to completed_at (top-level)

    If ``verification`` (dict) is provided, it is merged into the new
    phase_history entry as a ``verification`` field. See
    references/verification-protocol.md for footer schema.

    If ``debug_evidence`` (dict) is provided, it is merged into the new
    phase_history entry as a ``debug_evidence`` field (systematic-debugging
    4-phase output). See scripts/debug-evidence.py.
    """
    current = state_data.get("status", "[ ]")
    ts = now_iso()

    # Set started_at on first event
    if not state_data.get("started_at"):
        state_data["started_at"] = ts

    # Calculate elapsed from previous event (or started_at)
    prev_at = (state_data["phase_history"][-1]["at"]
               if state_data["phase_history"]
               else state_data.get("started_at"))
    phase_elapsed = _calc_elapsed(prev_at, ts) if prev_at else None

    # bypass is a special meta-event: status unchanged, bypassed flag set
    if event == "bypass":
        entry = {"event": "bypass", "from": current, "to": current, "at": ts}
        if phase_elapsed is not None:
            entry["elapsed_seconds"] = phase_elapsed
        if verification is not None:
            entry["verification"] = verification
        if debug_evidence is not None:
            entry["debug_evidence"] = debug_evidence
        state_data["phase_history"].append(entry)
        state_data["last"] = {"event": "bypass", "at": ts}
        state_data["bypassed"] = True
        state_data["bypassed_reason"] = bypass_reason or "escalation retries exhausted"
        state_data["updated"] = ts
        return current, current, True

    transitions = sm.get("transitions", {}).get(current, {})
    # Filter out meta keys like _comment
    next_status = transitions.get(event) if not event.startswith("_") else None

    no_change = False
    if next_status is None:
        # Undefined transition — permissive no-op
        next_status = current
        no_change = True
    elif next_status == current:
        no_change = True

    entry = {"event": event, "from": current, "to": next_status, "at": ts}
    if phase_elapsed is not None:
        entry["elapsed_seconds"] = phase_elapsed
    if verification is not None:
        entry["verification"] = verification
    if debug_evidence is not None:
        entry["debug_evidence"] = debug_evidence
    state_data["phase_history"].append(entry)
    state_data["last"] = {"event": event, "at": ts}
    state_data["status"] = next_status
    state_data["updated"] = ts

    # Track completion
    if next_status == "[xx]":
        state_data["completed_at"] = ts
        started = state_data.get("started_at")
        if started:
            total = _calc_elapsed(started, ts)
            if total is not None:
                state_data["elapsed_seconds"] = total

    return current, next_status, no_change


# ------------------------------ WBS backend ------------------------------


def wbs_state_path(wbs_path, tsk_id):
    """Derive state.json path from wbs.md path and task id.

    wbs.md is expected at {DOCS_DIR}/wbs.md; state.json lives at
    {DOCS_DIR}/tasks/{TSK-ID}/state.json.
    """
    docs_dir = os.path.dirname(os.path.abspath(wbs_path))
    return os.path.join(docs_dir, "tasks", tsk_id, "state.json")


def read_wbs_status_line(wbs_path, tsk_id):
    """Read the '- status: [xxx]' line from the task block in wbs.md.

    Returns (status_string, err). Missing task returns (None, err).
    """
    if not os.path.isfile(wbs_path):
        return None, f"file not found: {wbs_path}"

    with open(wbs_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    in_block = False
    block_level = 0

    for line in lines:
        stripped = line.rstrip("\n")
        hl = 0
        for ch in stripped:
            if ch == "#":
                hl += 1
            else:
                break

        if not in_block and hl >= 3 and f"{tsk_id}:" in stripped:
            in_block = True
            block_level = hl
            continue

        if in_block and 2 <= hl <= block_level and f"{tsk_id}:" not in stripped:
            break

        if in_block:
            m = re.match(r"^- status:\s*(\[.*?\])", stripped)
            if m:
                return m.group(1), None

    return None, f"{tsk_id} not found or status line missing in {wbs_path}"


def write_wbs_status_line(wbs_path, tsk_id, new_status):
    """Sync the '- status: [xxx]' line in wbs.md to match state.json.

    Returns (old_status, err).
    """
    with open(wbs_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    in_block = False
    block_level = 0
    old_status = None
    updated_lines = []
    updated = False

    for line in lines:
        stripped = line.rstrip("\n")
        hl = 0
        for ch in stripped:
            if ch == "#":
                hl += 1
            else:
                break

        if not in_block and hl >= 3 and f"{tsk_id}:" in stripped:
            in_block = True
            block_level = hl
            updated_lines.append(line)
            continue

        if in_block and 2 <= hl <= block_level and f"{tsk_id}:" not in stripped:
            in_block = False

        if in_block and not updated and re.match(r"^- status:\s*\[", stripped):
            m = re.match(r"^(- status:\s*)(\[.*?\])", stripped)
            if m:
                old_status = m.group(2)
                new_line = line.replace(m.group(2), new_status, 1)
                updated_lines.append(new_line)
                updated = True
                continue

        updated_lines.append(line)

    if not updated:
        return None, f"{tsk_id} status line not found in wbs.md"

    with open(wbs_path, "w", encoding="utf-8") as f:
        f.writelines(updated_lines)

    return old_status, None


def wbs_resolve_initial_state(wbs_path, tsk_id, state_path):
    """Resolve initial state for a WBS task.

    Priority: state.json > wbs.md status line > [ ] default.
    Used on first transition when state.json does not yet exist.
    Migrates legacy status markers [dd!]/[im!] to their simplified
    equivalents when seeding state.json from wbs.md.
    """
    data, err = load_state_json(state_path)
    if err:
        return None, err

    if os.path.isfile(state_path):
        return data, None  # state.json exists — use as-is

    wbs_status, err = read_wbs_status_line(wbs_path, tsk_id)
    if err:
        # Task not found in wbs.md — bail
        return None, err

    # Legacy marker migration
    legacy_map = {
        "[dd!]": "[ ]",
        "[im!]": "[im]",  # assume previous build was ok; safest for resume
    }
    migrated = legacy_map.get(wbs_status, wbs_status)

    # Validate migrated status is known
    known_states = {"[ ]", "[dd]", "[im]", "[ts]", "[xx]"}
    if migrated not in known_states:
        return None, f"unknown status in wbs.md: {wbs_status}"

    data["status"] = migrated
    if migrated != wbs_status:
        data["phase_history"].append({
            "event": "_migrate",
            "from": wbs_status,
            "to": migrated,
            "at": now_iso(),
        })
    return data, None


# ------------------------------ Feature backend ------------------------------


def feat_state_path(feat_dir):
    return os.path.join(feat_dir, "state.json")


def feat_legacy_status_path(feat_dir):
    return os.path.join(feat_dir, "status.json")


def feat_migrate_legacy(feat_dir):
    """If status.json exists and state.json does not, rename status.json → state.json.

    Returns (migrated: bool, err).
    """
    legacy = feat_legacy_status_path(feat_dir)
    current = feat_state_path(feat_dir)
    if os.path.isfile(current):
        return False, None
    if not os.path.isfile(legacy):
        return False, None
    try:
        os.rename(legacy, current)
        return True, None
    except OSError as e:
        return False, f"failed to rename status.json → state.json: {e}"


def feat_resolve_initial_state(feat_dir, state_path):
    """Resolve initial state for a feature, handling legacy status.json."""
    _, err = feat_migrate_legacy(feat_dir)
    if err:
        return None, err
    data, err = load_state_json(state_path)
    if err:
        return None, err
    # Legacy schema may have used "state" instead of "status"
    if "state" in data and "status" not in data:
        data["status"] = data.pop("state")
    # Normalize legacy status markers
    legacy_map = {"[dd!]": "[ ]", "[im!]": "[im]"}
    if data.get("status") in legacy_map:
        old = data["status"]
        data["status"] = legacy_map[old]
        data["phase_history"].append({
            "event": "_migrate",
            "from": old,
            "to": data["status"],
            "at": now_iso(),
        })
    return data, None


# ------------------------------ Main ------------------------------


def parse_args(argv):
    """Parse argv into (mode, args_dict).

    Supports an optional ``--verification PATH`` flag (JSON file produced by
    verify-phase.py) anywhere after the positional args. Removed before
    positional parsing so existing callers see no change.
    """
    args = list(argv[1:])
    if not args:
        print(__doc__)
        sys.exit(1)

    # Extract --verification PATH and --debug-evidence PATH if present
    verification_path = None
    debug_evidence_path = None
    out = []
    i = 0
    while i < len(args):
        if args[i] == "--verification":
            if i + 1 >= len(args):
                print("ERROR: --verification requires a path argument", file=sys.stderr)
                sys.exit(1)
            verification_path = args[i + 1]
            i += 2
            continue
        if args[i] == "--debug-evidence":
            if i + 1 >= len(args):
                print("ERROR: --debug-evidence requires a path argument", file=sys.stderr)
                sys.exit(1)
            debug_evidence_path = args[i + 1]
            i += 2
            continue
        out.append(args[i])
        i += 1
    args = out

    if args[0] == "--feat":
        if len(args) < 3:
            print("ERROR: --feat requires <feat-dir> <event>", file=sys.stderr)
            sys.exit(1)
        return "feat", {
            "feat_dir": args[1],
            "event": args[2],
            "reason": args[3] if len(args) > 3 else "",
            "verification_path": verification_path,
            "debug_evidence_path": debug_evidence_path,
        }

    if len(args) < 3:
        print(__doc__)
        sys.exit(1)
    return "wbs", {
        "wbs_path": args[0],
        "tsk_id": args[1],
        "event": args[2],
        "reason": args[3] if len(args) > 3 else "",
        "verification_path": verification_path,
    }


def _load_verification(path):
    if not path:
        return None, None
    if not os.path.isfile(path):
        return None, f"verification file not found: {path}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), None
    except (OSError, json.JSONDecodeError) as e:
        return None, f"failed to load verification JSON: {e}"


def main():
    mode, a = parse_args(sys.argv)

    sm, err = load_state_machine()
    if err:
        print(json.dumps({"error": err, "ok": False}, ensure_ascii=False))
        sys.exit(1)

    event = a["event"]
    reason = a.get("reason", "")
    verification, verr = _load_verification(a.get("verification_path"))
    if verr:
        print(json.dumps({"error": verr, "ok": False}, ensure_ascii=False))
        sys.exit(1)
    debug_evidence, derr = _load_verification(a.get("debug_evidence_path"))
    if derr:
        print(json.dumps({"error": derr.replace("verification", "debug_evidence"), "ok": False}, ensure_ascii=False))
        sys.exit(1)

    # bypass is a special meta-event handled outside the DFA events dict
    if event != "bypass" and event not in sm.get("events", {}):
        known = list(sm.get("events", {}).keys()) + ["bypass"]
        print(json.dumps({
            "error": f"unknown event: {event}",
            "known_events": known,
            "ok": False,
        }, ensure_ascii=False))
        sys.exit(1)

    if mode == "wbs":
        wbs_path = a["wbs_path"]
        tsk_id = a["tsk_id"]
        state_path = wbs_state_path(wbs_path, tsk_id)

        data, err = wbs_resolve_initial_state(wbs_path, tsk_id, state_path)
        if err:
            print(json.dumps({"source": "wbs", "id": tsk_id, "error": err, "ok": False}, ensure_ascii=False))
            sys.exit(1)

        previous, current, no_change = apply_transition(sm, data, event, bypass_reason=reason, verification=verification, debug_evidence=debug_evidence)

        err = save_state_json(state_path, data)
        if err:
            print(json.dumps({"source": "wbs", "id": tsk_id, "error": err, "ok": False}, ensure_ascii=False))
            sys.exit(1)

        # Sync wbs.md status line (bypass keeps same status, but sync ensures consistency)
        _, err = write_wbs_status_line(wbs_path, tsk_id, current)
        if err:
            print(json.dumps({"source": "wbs", "id": tsk_id, "error": err, "ok": False}, ensure_ascii=False))
            sys.exit(1)

        result = {
            "source": "wbs",
            "id": tsk_id,
            "previous": previous,
            "current": current,
            "event": event,
            "last": data["last"],
            "no_change": no_change,
            "ok": True,
        }
        if data.get("bypassed"):
            result["bypassed"] = True
            result["bypassed_reason"] = data.get("bypassed_reason", "")
        print(json.dumps(result, ensure_ascii=False))
        return

    # feat mode
    feat_dir = a["feat_dir"]
    if not os.path.isdir(feat_dir):
        print(json.dumps({"source": "feat", "error": f"feature dir not found: {feat_dir}", "ok": False}, ensure_ascii=False))
        sys.exit(1)

    state_path = feat_state_path(feat_dir)
    data, err = feat_resolve_initial_state(feat_dir, state_path)
    if err:
        print(json.dumps({"source": "feat", "error": err, "ok": False}, ensure_ascii=False))
        sys.exit(1)

    previous, current, no_change = apply_transition(sm, data, event, bypass_reason=reason, verification=verification, debug_evidence=debug_evidence)

    err = save_state_json(state_path, data)
    if err:
        print(json.dumps({"source": "feat", "error": err, "ok": False}, ensure_ascii=False))
        sys.exit(1)

    feat_id = os.path.basename(feat_dir.rstrip("/"))
    result = {
        "source": "feat",
        "id": feat_id,
        "previous": previous,
        "current": current,
        "event": event,
        "last": data["last"],
        "no_change": no_change,
        "ok": True,
    }
    if data.get("bypassed"):
        result["bypassed"] = True
        result["bypassed_reason"] = data.get("bypassed_reason", "")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
