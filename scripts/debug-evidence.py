#!/usr/bin/env python3
"""debug-evidence.py — systematic-debugging 4단계 evidence 수집기

dev-test 실패 시 escalation/bypass 진입 전 4단계 evidence를 강제로 수집해
state.json의 phase_history 항목에 ``debug_evidence`` 필드로 합성한다.

4단계:
  1. Errors        — 에러 메시지·스택 트레이스 raw 텍스트 (입력)
  2. Reproduce     — 재현 가능성 (always|conditional|once)
  3. Recent changes — phase 시작 이후 git diff 요약 (자동 수집)
  4. Components    — 다중 컴포넌트 시 경계별 로깅 (입력, 선택)

서브커맨드:
  collect   evidence를 수집해 JSON 출력 (state.json/--debug-evidence로 합성)
  bypass-reason  evidence를 짧은 사람 읽기용 텍스트로 요약 (bypassed_reason 후보)

사용:
  debug-evidence.py collect \\
    --phase test \\
    --target docs/tasks/TSK-04-02 \\
    --error-file /tmp/test-stdout.txt \\
    --reproduce always \\
    --component "auth-api:401 from /login" \\
    --component "db:no row updated"

  debug-evidence.py bypass-reason --evidence /tmp/evidence.json

Python stdlib only.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ALLOWED_PHASES = ("build", "test", "refactor")
ALLOWED_REPRODUCE = ("always", "conditional", "once")


def _utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Step 1: errors
# ---------------------------------------------------------------------------


def _read_error_text(error_file: str | None, error_text: str | None) -> str:
    if error_text is not None:
        return error_text
    if error_file:
        try:
            return Path(error_file).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
    return ""


def _summarize_errors(text: str, max_chars: int = 4000) -> dict:
    """에러 텍스트에서 핵심 라인을 추출."""
    if not text:
        return {"raw_chars": 0, "lines_total": 0, "tail": ""}
    lines = text.splitlines()
    # tail 60 lines + truncate by char limit
    tail = "\n".join(lines[-60:])
    if len(tail) > max_chars:
        tail = tail[-max_chars:]
    error_pattern = re.compile(
        r"(?i)(error|exception|fail|assert|traceback|fatal)"
    )
    error_lines = [ln for ln in lines if error_pattern.search(ln)][-20:]
    return {
        "raw_chars": len(text),
        "lines_total": len(lines),
        "error_line_count": len(error_lines),
        "error_lines_tail": error_lines,
        "tail": tail,
    }


# ---------------------------------------------------------------------------
# Step 3: recent changes
# ---------------------------------------------------------------------------


def _phase_start_iso(target: Path, phase: str) -> str | None:
    """state.json.phase_history에서 현재 phase 시작 시각을 추론.

    가장 최근 ``{prev_phase}.ok`` 이벤트 시각을 phase 시작으로 본다.
    예: phase=test → build.ok의 ``at`` 시각을 반환.
    phase=design은 started_at을 반환.
    """
    sp = target / "state.json"
    if not sp.is_file():
        return None
    try:
        data = json.loads(sp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    prev_map = {"build": "design.ok", "test": "build.ok", "refactor": "test.ok"}
    prev_event = prev_map.get(phase)
    if not prev_event:
        return data.get("started_at")

    history = data.get("phase_history", [])
    for h in reversed(history):
        if h.get("event") == prev_event:
            return h.get("at")
    return data.get("started_at")


def _git_diff_stat_since(target: Path, since_iso: str | None, repo: Path | None = None) -> dict:
    """phase 시작 이후 git diff 요약."""
    if repo is None:
        repo = target
    if not since_iso:
        return {"available": False, "reason": "phase start time unknown"}

    try:
        # Find commits since phase start
        log_proc = subprocess.run(
            ["git", "log", "--since", since_iso, "--pretty=format:%H"],
            capture_output=True, text=True, cwd=str(repo),
        )
        if log_proc.returncode != 0:
            return {"available": False, "reason": "git log failed", "stderr": log_proc.stderr.strip()}
        commits = [c for c in log_proc.stdout.split("\n") if c.strip()]

        # diff stat for working tree vs HEAD~N or vs since
        stat_proc = subprocess.run(
            ["git", "diff", "--stat", f"@{{{since_iso}}}", "HEAD"],
            capture_output=True, text=True, cwd=str(repo),
        )
        # Fallback: just compare HEAD vs HEAD if @{ts} fails
        if stat_proc.returncode != 0:
            stat_proc = subprocess.run(
                ["git", "diff", "--stat", "HEAD"],
                capture_output=True, text=True, cwd=str(repo),
            )

        names_proc = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, cwd=str(repo),
        )
        files_changed = [f for f in names_proc.stdout.split("\n") if f.strip()]

        return {
            "available": True,
            "since_iso": since_iso,
            "commits_since": len(commits),
            "commit_shas": commits[:10],
            "files_changed": files_changed[:50],
            "stat_summary": stat_proc.stdout.strip().splitlines()[-1] if stat_proc.stdout else "",
        }
    except (OSError, FileNotFoundError) as e:
        return {"available": False, "reason": f"git not available: {e}"}


# ---------------------------------------------------------------------------
# Step 4: components
# ---------------------------------------------------------------------------


def _parse_component_arg(arg: str) -> dict:
    """``NAME:LOG_MESSAGE`` → dict."""
    if ":" not in arg:
        raise ValueError(f"invalid --component format: {arg!r} (expected NAME:LOG)")
    name, log = arg.split(":", 1)
    return {"name": name.strip(), "boundary_log": log.strip()}


# ---------------------------------------------------------------------------
# Compose
# ---------------------------------------------------------------------------


def collect_evidence(
    phase: str,
    target: Path,
    error_text: str,
    reproduce: str,
    components: list[dict],
    repo: Path | None = None,
    skip_git: bool = False,
) -> dict:
    if phase not in ALLOWED_PHASES:
        raise ValueError(f"phase '{phase}' not in {ALLOWED_PHASES}")
    if reproduce not in ALLOWED_REPRODUCE:
        raise ValueError(f"reproduce '{reproduce}' not in {ALLOWED_REPRODUCE}")

    errors = _summarize_errors(error_text)
    if skip_git:
        recent = {"available": False, "reason": "skipped via --skip-git"}
    else:
        since = _phase_start_iso(target, phase)
        recent = _git_diff_stat_since(target, since, repo=repo)

    return {
        "phase": phase,
        "captured_at": _utc_iso(),
        "errors": errors,
        "reproduce": reproduce,
        "recent_changes": recent,
        "components": components,
    }


def evidence_to_bypass_reason(evidence: dict, max_len: int = 280) -> str:
    """evidence dict를 한 줄 bypass_reason으로 요약."""
    phase = evidence.get("phase", "?")
    repro = evidence.get("reproduce", "?")
    errors = evidence.get("errors", {})
    err_count = errors.get("error_line_count", 0)
    last_err = ""
    if errors.get("error_lines_tail"):
        last_err = errors["error_lines_tail"][-1]
        last_err = last_err.strip()[:120]
    rc = evidence.get("recent_changes", {})
    files_n = len(rc.get("files_changed", []))
    components = evidence.get("components", [])
    comp_summary = f"{len(components)} component(s) instrumented" if components else "no components"

    msg = (
        f"{phase}.fail ({repro}) — {err_count} error line(s); "
        f"recent: {files_n} file(s) changed; {comp_summary}"
    )
    if last_err:
        msg += f"; last: {last_err}"
    if len(msg) > max_len:
        msg = msg[: max_len - 1] + "…"
    return msg


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="debug-evidence.py",
        description="systematic-debugging 4단계 evidence 수집기",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    cl = sub.add_parser("collect", help="evidence 수집 → JSON")
    cl.add_argument("--phase", required=True, choices=ALLOWED_PHASES)
    cl.add_argument("--target", required=True, help="task/feature 디렉터리")
    cl.add_argument("--error-text", default=None, help="에러 raw 텍스트 (직접)")
    cl.add_argument("--error-file", default=None, help="에러 텍스트 파일 경로")
    cl.add_argument("--reproduce", required=True, choices=ALLOWED_REPRODUCE)
    cl.add_argument("--component", action="append", default=[], help="NAME:LOG (repeatable)")
    cl.add_argument("--repo", default=None, help="git 저장소 경로 (기본: target)")
    cl.add_argument("--skip-git", action="store_true", help="git diff 수집 생략")

    br = sub.add_parser("bypass-reason", help="evidence를 한 줄 사유로 요약")
    br.add_argument("--evidence", required=True, help="collect가 생성한 JSON 파일")
    br.add_argument("--max-len", type=int, default=280)

    args = parser.parse_args(argv)

    if args.cmd == "collect":
        target = Path(args.target)
        if not target.is_dir():
            print(json.dumps({"error": f"target not a directory: {target}"}), file=sys.stderr)
            return 2
        text = _read_error_text(args.error_file, args.error_text)
        try:
            components = [_parse_component_arg(c) for c in args.component]
        except ValueError as e:
            print(json.dumps({"error": str(e)}), file=sys.stderr)
            return 2
        repo = Path(args.repo) if args.repo else None
        try:
            evidence = collect_evidence(
                phase=args.phase, target=target,
                error_text=text, reproduce=args.reproduce,
                components=components, repo=repo, skip_git=args.skip_git,
            )
        except ValueError as e:
            print(json.dumps({"error": str(e)}), file=sys.stderr)
            return 2
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "bypass-reason":
        try:
            evidence = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"failed to load evidence: {e}", file=sys.stderr)
            return 2
        print(evidence_to_bypass_reason(evidence, max_len=args.max_len))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
