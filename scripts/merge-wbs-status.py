#!/usr/bin/env python3
"""merge-wbs-status.py — Git custom merge driver for wbs.md files.

Driver signature:
    merge-wbs-status.py %O %A %B [%L]

Algorithm (TRD §3.12.6):
    1. Parse `- status: [xxx]` lines in each file, keyed by the enclosing
       `### TSK-XX-XX:` task header.
    2. For each task where ours/theirs differ, pick the status with the
       highest priority ([xx] > [ts] > [im] > [dd] > [ ]); tie → ours.
    3. Normalise every status line in all three inputs to a placeholder
       token, then run an RCS-style 3-way line merge on the non-status
       content. If any non-status conflict remains, bail out (exit 1,
       OURS untouched) so git can emit standard conflict markers.
    4. Reapply the priority-merged status back into the merged body.
    5. Write the merged text atomically to OURS.
"""
from __future__ import annotations

import os
import pathlib
import re
import sys
import tempfile


STATUS_PRIORITY = {
    "[ ]": 0,
    "[dd]": 1,
    "[im]": 2,
    "[ts]": 3,
    "[xx]": 4,
}

STATUS_TOKEN = "__WBS_STATUS_PLACEHOLDER__"
TASK_HEADER_RE = re.compile(r"^###\s+(TSK-\d+-\d+):")
STATUS_LINE_RE = re.compile(
    r"^(?P<indent>\s*)-\s*status:\s*(?P<status>\[(?:\s|dd|im|ts|xx)\])\s*$"
)


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def _read_text(path: pathlib.Path) -> tuple[str | None, str | None]:
    try:
        return path.read_text(encoding="utf-8"), None
    except OSError as e:
        return None, str(e)


def _atomic_write_text(path: pathlib.Path, text: str) -> None:
    dirp = path.parent
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=str(dirp),
        delete=False,
        suffix=".tmp",
        encoding="utf-8",
        newline="",  # preserve existing line endings in `text`
    ) as fh:
        fh.write(text)
        tmp = fh.name
    os.replace(tmp, str(path))


# ---------------------------------------------------------------------------
# Status parsing / rewriting
# ---------------------------------------------------------------------------

def parse_status_lines(text: str) -> dict[str, str]:
    """Map task_id → status from a wbs.md text body.

    Scans each task block (from `### TSK-XX-XX:` to the next `### ` line)
    for the first `- status: [xxx]` line. Duplicate task_ids keep the first.
    """
    out: dict[str, str] = {}
    current_task: str | None = None
    for line in text.splitlines():
        m = TASK_HEADER_RE.match(line)
        if m:
            current_task = m.group(1)
            continue
        # Any other `### ` heading closes the current task block.
        if line.startswith("### "):
            current_task = None
            continue
        if current_task is None:
            continue
        sm = STATUS_LINE_RE.match(line)
        if sm and current_task not in out:
            out[current_task] = sm.group("status")
    return out


def _status_token_replace(text: str) -> str:
    """Replace every `- status: [xxx]` value with a placeholder token.

    The `- status:` prefix is kept intact so the replaced line still looks
    like a status line (one per task block). Only the bracketed value is
    swapped. This makes ours/theirs/base compare equally on the status line
    as long as the surrounding structure is preserved.
    """
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    for line in lines:
        # Preserve the line ending (\n, \r\n, or bare).
        ending = ""
        stripped = line
        for e in ("\r\n", "\n", "\r"):
            if stripped.endswith(e):
                ending = e
                stripped = stripped[: -len(e)]
                break
        m = STATUS_LINE_RE.match(stripped)
        if m:
            rebuilt = f"{m.group('indent')}- status: {STATUS_TOKEN}"
            out.append(rebuilt + ending)
        else:
            out.append(line)
    return "".join(out)


def _reapply_statuses(text: str, statuses: dict[str, str]) -> str:
    """Walk `text`, replace each STATUS_TOKEN with the resolved status.

    Tasks are matched by scanning for `### TSK-...:` headers and then the
    first status-token line inside that block.
    """
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    current_task: str | None = None
    applied: set[str] = set()
    for line in lines:
        header_match = TASK_HEADER_RE.match(line.rstrip("\r\n"))
        if header_match:
            current_task = header_match.group(1)
            out.append(line)
            continue
        if line.startswith("### "):
            current_task = None
            out.append(line)
            continue
        if STATUS_TOKEN in line and current_task is not None and current_task not in applied:
            resolved = statuses.get(current_task, "[ ]")
            out.append(line.replace(STATUS_TOKEN, resolved, 1))
            applied.add(current_task)
            continue
        # Orphan placeholder (no matching task or already applied) — leave as [ ]
        if STATUS_TOKEN in line:
            out.append(line.replace(STATUS_TOKEN, "[ ]", 1))
            continue
        out.append(line)
    return "".join(out)


# ---------------------------------------------------------------------------
# Priority-merge of statuses
# ---------------------------------------------------------------------------

def merge_status_dicts(
    ours: dict[str, str], theirs: dict[str, str]
) -> dict[str, str]:
    """Merge status dictionaries by priority. Tie → ours."""
    merged: dict[str, str] = {}
    for k, v in theirs.items():
        merged[k] = v
    for k, v in ours.items():
        if k in merged:
            pa = STATUS_PRIORITY.get(v, -1)
            pb = STATUS_PRIORITY.get(merged[k], -1)
            merged[k] = v if pa >= pb else merged[k]
        else:
            merged[k] = v
    return merged


# ---------------------------------------------------------------------------
# RCS-style 3-way line merge (stdlib only)
# ---------------------------------------------------------------------------

def _lcs_matrix(a: list[str], b: list[str]) -> list[list[int]]:
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m - 1, -1, -1):
        for j in range(n - 1, -1, -1):
            if a[i] == b[j]:
                dp[i][j] = dp[i + 1][j + 1] + 1
            else:
                dp[i][j] = max(dp[i + 1][j], dp[i][j + 1])
    return dp


def _align(a: list[str], b: list[str]) -> list[tuple[int | None, int | None]]:
    """Return pairs of indices (i,j) representing the alignment of `a` to `b`.

    (i, j)  — matched line (a[i] == b[j])
    (i, None) — line from a deleted in b
    (None, j) — line from b inserted vs a
    """
    dp = _lcs_matrix(a, b)
    i, j = 0, 0
    result: list[tuple[int | None, int | None]] = []
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            result.append((i, j))
            i += 1
            j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            result.append((i, None))
            i += 1
        else:
            result.append((None, j))
            j += 1
    while i < len(a):
        result.append((i, None))
        i += 1
    while j < len(b):
        result.append((None, j))
        j += 1
    return result


def _diff3_hunks(
    base: list[str], ours: list[str], theirs: list[str]
) -> list[dict]:
    """Produce a list of hunks describing ours vs base and theirs vs base.

    Each hunk has keys: `type` (`stable`|`changed`), `base_start/end`,
    `ours_start/end`, `theirs_start/end`. A stable hunk means all three
    sides agree on that span.
    """
    ao = _align(base, ours)
    at = _align(base, theirs)

    # Flatten alignments to per-base-index ours/theirs line sets.
    # For every base index, we collect the ours lines that align to it as
    # a "block" (empty list + the line at that index if matched).

    # Use a simpler approach: reconstruct diff runs against base.

    def runs(alignment: list[tuple[int | None, int | None]], side: list[str]):
        # Produce list of (base_idx, op, side_idx)
        # op is 'match' | 'delete' (from base, missing in side) | 'insert'
        events = []
        for bi, si in alignment:
            if bi is not None and si is not None:
                events.append(("match", bi, si))
            elif bi is not None and si is None:
                events.append(("delete", bi, None))
            elif bi is None and si is not None:
                events.append(("insert", None, si))
        return events

    ours_events = runs(ao, ours)
    theirs_events = runs(at, theirs)

    # Walk base index by index and group contiguous "changed" regions.
    # A base index is "stable" if both sides match it.
    ours_by_base: dict[int, int | str] = {}  # bi → si (int) or 'del'
    for op, bi, si in ours_events:
        if op == "match":
            ours_by_base[bi] = si
        elif op == "delete":
            ours_by_base[bi] = "del"
    theirs_by_base: dict[int, int | str] = {}
    for op, bi, si in theirs_events:
        if op == "match":
            theirs_by_base[bi] = si
        elif op == "delete":
            theirs_by_base[bi] = "del"

    # Insertions from each side at a given base position (before bi).
    def _collect_inserts(
        events: list[tuple[str, int | None, int | None]],
    ) -> dict[int, list[int]]:
        """Map each base insertion position → list of side-line indices."""
        inserts: dict[int, list[int]] = {}
        cur_bi = 0
        pending: list[int] = []
        for op, bi, si in events:
            if op == "insert":
                pending.append(si)  # type: ignore[arg-type]
            else:
                if pending:
                    inserts.setdefault(cur_bi, []).extend(pending)
                    pending = []
                if op in ("match", "delete") and bi is not None:
                    cur_bi = bi + 1
        if pending:
            inserts.setdefault(cur_bi, []).extend(pending)
        return inserts

    ours_inserts = _collect_inserts(ours_events)
    theirs_inserts = _collect_inserts(theirs_events)

    hunks: list[dict] = []
    i = 0
    n = len(base)
    while i <= n:
        # Build a "changed region" if there are insertions at position i,
        # or if base[i] is changed (not matched) by either side.
        has_insert = i in ours_inserts or i in theirs_inserts
        is_changed = False
        if i < n:
            om = ours_by_base.get(i)
            tm = theirs_by_base.get(i)
            if om == "del" or tm == "del":
                is_changed = True
            elif om is None or tm is None:
                # This should not happen since every base index is either
                # matched or deleted per the LCS alignment, but guard anyway.
                is_changed = True

        if not has_insert and not is_changed:
            # Stable region: accumulate as far as possible.
            start = i
            while i < n:
                if i in ours_inserts or i in theirs_inserts:
                    break
                om = ours_by_base.get(i)
                tm = theirs_by_base.get(i)
                if om == "del" or tm == "del" or om is None or tm is None:
                    break
                i += 1
            hunks.append({
                "type": "stable",
                "base_start": start, "base_end": i,
                "ours_start": ours_by_base.get(start) if start < n else None,
                "ours_end": None,  # not used for stable
                "theirs_start": theirs_by_base.get(start) if start < n else None,
                "theirs_end": None,
            })
            if i == n and i not in ours_inserts and i not in theirs_inserts:
                break
            continue

        # Changed region: collect the full changed span (consecutive
        # not-matched base indices + adjacent insert positions).
        base_start = i
        ours_lines: list[int] = []
        theirs_lines: list[int] = []
        # trailing inserts at position i (before the first changed base line)
        ours_lines.extend(ours_inserts.get(i, []))
        theirs_lines.extend(theirs_inserts.get(i, []))
        # Trailing inserts past base end (i >= n): the inserts above are
        # the entire changed region. Without this guard the inner `while
        # i < n` body never advances `i`, and the outer `while i <= n`
        # loops forever appending the same hunk — observed when base is
        # 0-byte and ours/theirs both have content (ours_inserts ==
        # theirs_inserts == {0:[0..k]}), exhausting memory.
        if i >= n:
            hunks.append({
                "type": "changed",
                "base_start": base_start, "base_end": i,
                "ours_lines": ours_lines,
                "theirs_lines": theirs_lines,
            })
            break
        while i < n:
            om = ours_by_base.get(i)
            tm = theirs_by_base.get(i)
            stable_here = (om not in (None, "del")) and (tm not in (None, "del"))
            if stable_here and not (i in ours_inserts or i in theirs_inserts):
                break
            # include base[i] in the "removed" side; the replacement is
            # what either branch had (match → that line, delete → nothing).
            if om != "del" and isinstance(om, int):
                ours_lines.append(om)
            if tm != "del" and isinstance(tm, int):
                theirs_lines.append(tm)
            # inserts between i and i+1:
            ours_lines.extend(ours_inserts.get(i + 1, []))
            theirs_lines.extend(theirs_inserts.get(i + 1, []))
            i += 1
        base_end = i
        hunks.append({
            "type": "changed",
            "base_start": base_start, "base_end": base_end,
            "ours_lines": ours_lines,
            "theirs_lines": theirs_lines,
        })
    return hunks


def _is_preserving(region: list[str], base_region: list[str]) -> bool:
    """Return True iff every base_region line appears in `region` in order.

    (i.e. base_region is a subsequence of region — both sides preserved the
    base content and only inserted new lines around it.)
    """
    if not base_region:
        return True
    i = 0
    for line in region:
        if i < len(base_region) and line == base_region[i]:
            i += 1
    return i == len(base_region)


def _additions_relative_to_base(
    region: list[str], base_region: list[str]
) -> list[str] | None:
    """If `region` contains `base_region` as a contiguous ordered subsequence,
    return the list of lines added relative to base, preserving their
    relative order (all additions appear either before or after each base
    line). Returns None if region does not purely preserve base (e.g. lines
    were reordered or deleted)."""
    if not _is_preserving(region, base_region):
        return None
    # Remove base_region lines (match each base line once, greedily) from
    # the region; whatever remains is the addition. This is correct when
    # base_region lines are unique inside `region`; when they duplicate we
    # conservatively fall through.
    additions: list[str] = []
    bi = 0
    for line in region:
        if bi < len(base_region) and line == base_region[bi]:
            bi += 1
            continue
        additions.append(line)
    return additions


def merge3_lines(
    base: list[str], ours: list[str], theirs: list[str]
) -> tuple[list[str], bool]:
    """3-way line merge. Returns (merged_lines, has_conflict)."""
    hunks = _diff3_hunks(base, ours, theirs)
    out: list[str] = []
    conflict = False
    for h in hunks:
        if h["type"] == "stable":
            out.extend(base[h["base_start"]:h["base_end"]])
            continue
        # changed
        bs, be = h["base_start"], h["base_end"]
        ours_region = [ours[i] for i in h["ours_lines"]]
        theirs_region = [theirs[i] for i in h["theirs_lines"]]
        base_region = base[bs:be]
        if ours_region == theirs_region:
            # Same change on both sides
            out.extend(ours_region)
            continue
        if ours_region == base_region:
            # Only theirs changed
            out.extend(theirs_region)
            continue
        if theirs_region == base_region:
            # Only ours changed
            out.extend(ours_region)
            continue

        # Additive-both: both sides preserved base content and only
        # inserted new lines. Combine the two addition sets (ours first,
        # then theirs) around the preserved base.
        ours_add = _additions_relative_to_base(ours_region, base_region)
        theirs_add = _additions_relative_to_base(theirs_region, base_region)
        if ours_add is not None and theirs_add is not None:
            out.extend(ours_add)
            out.extend(base_region)
            out.extend(theirs_add)
            continue

        # True 3-way conflict
        conflict = True
        out.extend(ours_region)  # placeholder; caller must bail anyway
    return out, conflict


# ---------------------------------------------------------------------------
# Top-level merge
# ---------------------------------------------------------------------------

def merge_wbs_text(
    base_text: str, ours_text: str, theirs_text: str
) -> tuple[str | None, bool]:
    """Return (merged_text, success).

    success=False means the caller should exit 1 and leave OURS untouched.
    """
    # 1. Parse statuses.
    ours_statuses = parse_status_lines(ours_text)
    theirs_statuses = parse_status_lines(theirs_text)
    merged_statuses = merge_status_dicts(ours_statuses, theirs_statuses)

    # 2. Normalise statuses to a placeholder and 3-way merge the bodies.
    base_norm = _status_token_replace(base_text)
    ours_norm = _status_token_replace(ours_text)
    theirs_norm = _status_token_replace(theirs_text)

    base_lines = base_norm.splitlines(keepends=True)
    ours_lines = ours_norm.splitlines(keepends=True)
    theirs_lines = theirs_norm.splitlines(keepends=True)

    try:
        merged_lines, conflict = merge3_lines(base_lines, ours_lines, theirs_lines)
    except Exception:
        return None, False
    if conflict:
        return None, False

    merged_norm = "".join(merged_lines)
    # 3. Re-apply resolved statuses.
    final_text = _reapply_statuses(merged_norm, merged_statuses)
    return final_text, True


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    if len(argv) < 4:
        print(
            "usage: merge-wbs-status.py BASE OURS THEIRS [MARKER_SIZE]",
            file=sys.stderr,
        )
        return 1
    base_p = pathlib.Path(argv[1])
    ours_p = pathlib.Path(argv[2])
    theirs_p = pathlib.Path(argv[3])

    base_text, err_b = _read_text(base_p)
    ours_text, err_o = _read_text(ours_p)
    theirs_text, err_t = _read_text(theirs_p)

    if err_b is not None:
        base_text = ""
    if err_o is not None or err_t is not None:
        print(
            f"merge-wbs-status: read failure (ours={err_o}, theirs={err_t})",
            file=sys.stderr,
        )
        return 1

    merged, ok = merge_wbs_text(base_text or "", ours_text or "", theirs_text or "")
    if not ok or merged is None:
        return 1

    try:
        _atomic_write_text(ours_p, merged)
    except OSError as e:
        print(f"merge-wbs-status: write error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
