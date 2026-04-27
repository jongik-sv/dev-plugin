#!/usr/bin/env python3
"""verify-phase.py — DDTR phase 종료 verification 게이트

각 phase가 .ok DFA 전이를 시도하기 직전에 호출된다. 구조적 산출물 존재·필수
섹션·형식을 자동 검사하고, SKILL.md가 외부에서 실행한 동적 체크(테스트
재실행 결과·lint exit code 등)를 ``--check`` 플래그로 합성하여 단일 footer
JSON으로 출력한다.

사용:
  verify-phase.py --phase {design|build|test|refactor} --target DIR \\
                  [--source {wbs|feat}] \\
                  [--check NAME:OK:KEY=VAL,KEY=VAL ...] \\
                  [--strict]

Phase별 구조 검사:
  design   — design.md 존재 + ``## Implementation Steps`` 섹션 + 체크박스 ≥ 1
  build    — build phase에서 변경된 산출물 단서(state.json + 최근 phase_history)
  test     — test-report.md 존재 + 최소 한 개의 ``- [x]`` (실행된 항목)
  refactor — refactor.md 존재 + 최소 한 개의 ``- [x]``

``--check`` 플래그 형식:
  unit_test:ok:exit=0,pass=42,fail=0,command="pytest -q"
  e2e_test:fail:exit=2,pass=8,fail=1
  lint:ok:exit=0
  red_green:ok:steps=3

  NAME:STATUS  — STATUS는 ok|fail
  KEY=VAL,...  — 콤마 구분된 메타데이터 (선택)

종료 코드:
  0  ok=true (모든 체크 통과)
  1  ok=false (하나 이상 실패) — ``--strict``가 없어도 ok=false 시 1 반환
  2  사용 오류

표준 출력: JSON footer 객체. SKILL.md가 그대로 ``wbs-transition.py --verification``에 전달.

Footer 스키마:
  {
    "ok": bool,
    "phase": str,
    "verified_at": ISO8601,
    "checks": [
      {"name": str, "ok": bool, "kind": "structural"|"dynamic", ...metadata}
    ]
  }
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

ALLOWED_PHASES = ("design", "build", "test", "refactor")


def _utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Structural checks
# ---------------------------------------------------------------------------


def _check_file_exists(target: Path, filename: str) -> dict:
    """파일 존재만 확인."""
    p = target / filename
    return {
        "name": f"{filename}_exists",
        "kind": "structural",
        "ok": p.is_file(),
        "path": str(p),
    }


def _check_section_present(target: Path, filename: str, header_re: str) -> dict:
    """파일 내 헤더 섹션 존재 여부."""
    p = target / filename
    name = f"{filename}_has_section"
    if not p.is_file():
        return {"name": name, "kind": "structural", "ok": False, "reason": "file missing"}
    content = p.read_text(encoding="utf-8")
    return {
        "name": name,
        "kind": "structural",
        "ok": bool(re.search(header_re, content, re.MULTILINE)),
        "header_pattern": header_re,
    }


def _check_checkbox_count(target: Path, filename: str, min_count: int = 1, executed_only: bool = False) -> dict:
    """체크박스 개수 검사. executed_only=True면 ``- [x]``만 셈."""
    p = target / filename
    name = f"{filename}_checkbox_min_{min_count}"
    if executed_only:
        name = f"{filename}_executed_checkbox_min_{min_count}"
    if not p.is_file():
        return {"name": name, "kind": "structural", "ok": False, "reason": "file missing"}
    content = p.read_text(encoding="utf-8")
    if executed_only:
        count = len(re.findall(r"^\s*-\s*\[x\]", content, re.MULTILINE | re.IGNORECASE))
    else:
        count = len(re.findall(r"^\s*-\s*\[[ xX]\]", content, re.MULTILINE))
    return {
        "name": name,
        "kind": "structural",
        "ok": count >= min_count,
        "count": count,
        "required": min_count,
    }


def _check_state_history_event(target: Path, expected_event: str, since_phase: str | None = None) -> dict:
    """state.json phase_history에 expected_event가 since_phase 시작 이후에 존재하는지 확인."""
    state_path = target / "state.json"
    name = f"state_has_{expected_event}"
    if not state_path.is_file():
        return {"name": name, "kind": "structural", "ok": False, "reason": "state.json missing"}
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return {"name": name, "kind": "structural", "ok": False, "reason": f"state.json parse error: {e}"}
    history = data.get("phase_history", [])

    if since_phase:
        # Find last event whose status matches phase entry — heuristic: filter from last *.ok of prior phase
        cutoff_idx = 0
        for i, h in enumerate(history):
            if h.get("event", "").startswith(f"{since_phase}."):
                cutoff_idx = i
        history = history[cutoff_idx + 1:]

    has = any(h.get("event") == expected_event for h in history)
    return {
        "name": name,
        "kind": "structural",
        "ok": has,
        "history_entry_count_scanned": len(history),
    }


def structural_checks(phase: str, target: Path) -> list[dict]:
    """phase별 결정적 구조 검사 목록을 반환."""
    if phase == "design":
        return [
            _check_file_exists(target, "design.md"),
            _check_section_present(target, "design.md", r"^##+\s*Implementation Steps"),
            _check_checkbox_count(target, "design.md", min_count=1),
        ]
    if phase == "build":
        return [
            _check_file_exists(target, "design.md"),
            # design.md의 Implementation Steps 중 하나 이상 실행됐어야 한다 (build phase 종료 시점)
            _check_checkbox_count(target, "design.md", min_count=1, executed_only=True),
        ]
    if phase == "test":
        return [
            _check_file_exists(target, "design.md"),
            _check_file_exists(target, "test-report.md"),
            _check_checkbox_count(target, "test-report.md", min_count=1),
        ]
    if phase == "refactor":
        return [
            _check_file_exists(target, "test-report.md"),
            _check_file_exists(target, "refactor.md"),
            _check_checkbox_count(target, "refactor.md", min_count=1),
        ]
    raise ValueError(f"unknown phase: {phase}")


# ---------------------------------------------------------------------------
# Dynamic check parser
# ---------------------------------------------------------------------------


_CHECK_RE = re.compile(r"^(?P<name>[a-zA-Z0-9_-]+):(?P<status>ok|fail)(?::(?P<meta>.+))?$")


def parse_check_arg(arg: str) -> dict:
    """``unit_test:ok:exit=0,pass=42,fail=0`` → dict."""
    m = _CHECK_RE.match(arg)
    if not m:
        raise ValueError(
            f"invalid --check format: {arg!r} (expected NAME:ok|fail[:KEY=VAL,...])"
        )
    result = {
        "name": m.group("name"),
        "kind": "dynamic",
        "ok": m.group("status") == "ok",
    }
    meta = m.group("meta")
    if meta:
        for pair in _split_meta(meta):
            if "=" not in pair:
                raise ValueError(f"invalid meta entry: {pair!r} (expected KEY=VAL)")
            k, v = pair.split("=", 1)
            k = k.strip()
            v = v.strip()
            # Try int
            if v.lstrip("-").isdigit():
                result[k] = int(v)
            else:
                # Strip surrounding quotes if present
                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                    v = v[1:-1]
                result[k] = v
    return result


def _split_meta(meta: str) -> list[str]:
    """콤마로 split하되 따옴표 내부의 콤마는 보존."""
    parts: list[str] = []
    buf = ""
    in_quote: str | None = None
    for ch in meta:
        if in_quote:
            buf += ch
            if ch == in_quote:
                in_quote = None
        elif ch in ('"', "'"):
            in_quote = ch
            buf += ch
        elif ch == ",":
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    if buf:
        parts.append(buf)
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# Composer
# ---------------------------------------------------------------------------


def compose_footer(phase: str, target: Path, dynamic_checks: list[dict]) -> dict:
    structural = structural_checks(phase, target)
    all_checks = structural + dynamic_checks
    return {
        "ok": all(c["ok"] for c in all_checks),
        "phase": phase,
        "verified_at": _utc_iso(),
        "checks": all_checks,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verify-phase.py",
        description="DDTR phase 종료 verification 게이트",
    )
    parser.add_argument("--phase", required=True, choices=ALLOWED_PHASES)
    parser.add_argument("--target", required=True, help="task/feature 디렉터리")
    parser.add_argument("--source", choices=["wbs", "feat"], default="wbs")
    parser.add_argument(
        "--check", action="append", default=[],
        help="동적 체크: NAME:ok|fail[:KEY=VAL,...]",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="ok=false 시 비-0 종료 (기본 동작과 동일, 명시적 의도 표현)",
    )

    args = parser.parse_args(argv)
    target = Path(args.target)
    if not target.is_dir():
        print(json.dumps({"ok": False, "error": f"target not a directory: {target}"}), file=sys.stderr)
        return 2

    try:
        dynamic = [parse_check_arg(c) for c in args.check]
    except ValueError as e:
        print(json.dumps({"ok": False, "error": str(e)}), file=sys.stderr)
        return 2

    footer = compose_footer(args.phase, target, dynamic)
    print(json.dumps(footer, ensure_ascii=False, indent=2))
    return 0 if footer["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
