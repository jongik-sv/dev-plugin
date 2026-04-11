#!/usr/bin/env python3
"""feat-init.py — Initialize a feature directory under {DOCS_DIR}/features/{name}/.

Creates:
  - spec.md    — user requirement (from description or placeholder)
  - state.json — state tracker ({"name", "status": "[ ]", "last": null, "phase_history": [], "updated"})

Legacy: earlier versions created ``status.json`` with a ``state`` field.
This script auto-renames ``status.json`` → ``state.json`` on resume for
backward compatibility.

Idempotent: if the directory already exists, reports resume mode and leaves files intact.

Auto-naming: if `name` is empty or `-`, the script auto-generates a kebab-case name by
slugifying the description. If the slug is too short or invalid, it falls back to a
timestamp-based name (e.g., `feat-20260411-083512`).

Usage:
  feat-init.py <docs-dir> <name> [description...]
  feat-init.py <docs-dir> - <description...>     # auto-name from description

Output: JSON
  {"source": "feat", "feat_name": "...", "feat_dir": "...",
   "spec_path": "...", "state_path": "...",
   "mode": "created"|"resume", "auto_generated": true|false,
   "fallback_used": true|false, "ok": true}

Schema alignment:
  - `source` and `feat_name` keys mirror args-parse.py output so callers can
    consume both scripts with one consistent vocabulary (audit issue 4-7).
  - `feat_dir`/`mode`/`auto_generated`/`fallback_used`/`spec_path`/`state_path`
    are post-IO artifacts that args-parse.py cannot pre-compute.

Examples:
  feat-init.py docs login-2fa "Add 2FA to the login flow"
  feat-init.py docs - "로그인에 2FA 추가"              # auto → feat-YYYYMMDD-HHMMSS
  feat-init.py docs - "add rate limiter middleware"   # auto → add-rate-limiter-middleware
"""
import sys
import os
import re
import json
from datetime import datetime, timezone


FEAT_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
SLUG_MAX_LEN = 40
SLUG_MIN_LEN = 2


def _now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _timestamp_slug():
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _slugify(text: str) -> str:
    """Lowercase ASCII kebab-case from free-form text. Non-ASCII (e.g., Korean) is dropped."""
    s = text.lower()
    s = re.sub(r"[\s_/]+", "-", s)
    s = re.sub(r"[^a-z0-9-]", "", s)
    s = re.sub(r"-+", "-", s)
    s = s.strip("-")
    if len(s) > SLUG_MAX_LEN:
        s = s[:SLUG_MAX_LEN].rstrip("-")
    return s


def _auto_name(description: str, features_root: str):
    """Generate a kebab-case name. Falls back to timestamp if slugify fails or name collides."""
    fallback = False

    slug = _slugify(description) if description else ""
    if len(slug) < SLUG_MIN_LEN or not FEAT_NAME_RE.match(slug):
        slug = f"feat-{_timestamp_slug()}"
        fallback = True

    # Resolve collision: append a short timestamp suffix
    candidate = slug
    if os.path.isdir(os.path.join(features_root, candidate)):
        suffix = _timestamp_slug()
        candidate = f"{slug}-{suffix}"
        # Cap the final length
        if len(candidate) > SLUG_MAX_LEN + len(suffix) + 1:
            candidate = candidate[: SLUG_MAX_LEN + len(suffix) + 1]

    return candidate, fallback


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    docs_dir = sys.argv[1]
    name_arg = sys.argv[2] if len(sys.argv) > 2 else ""
    description = " ".join(sys.argv[3:]).strip() if len(sys.argv) > 3 else ""

    # Treat "-" or empty as "auto-name requested"
    name = name_arg if name_arg and name_arg != "-" else ""

    if not os.path.isdir(docs_dir):
        print(json.dumps({
            "error": f"docs dir not found: {docs_dir}",
            "ok": False,
        }, ensure_ascii=False))
        sys.exit(1)

    features_root = os.path.join(docs_dir, "features")
    os.makedirs(features_root, exist_ok=True)

    auto_generated = False
    fallback_used = False

    if not name:
        if not description:
            print(json.dumps({
                "error": "이름과 설명이 모두 비어 있습니다. 최소한 하나는 필요합니다. 예: /feat rate-limiter 또는 /feat \"add rate limiter\"",
                "ok": False,
            }, ensure_ascii=False))
            sys.exit(1)
        name, fallback_used = _auto_name(description, features_root)
        auto_generated = True

    # Validate (explicit names and auto-generated both must match the pattern)
    if not FEAT_NAME_RE.match(name):
        print(json.dumps({
            "error": f"invalid feature name: '{name}' — kebab-case required (lowercase, digits, hyphens)",
            "ok": False,
        }, ensure_ascii=False))
        sys.exit(1)

    feat_dir = os.path.join(features_root, name)
    spec_path = os.path.join(feat_dir, "spec.md")
    state_path = os.path.join(feat_dir, "state.json")
    legacy_status_path = os.path.join(feat_dir, "status.json")

    # Legacy migration: if status.json exists and state.json does not, rename.
    legacy_migrated = False
    if os.path.isdir(feat_dir) and not os.path.isfile(state_path) and os.path.isfile(legacy_status_path):
        try:
            os.rename(legacy_status_path, state_path)
            _normalize_state_file(state_path)
            legacy_migrated = True
        except OSError:
            pass

    # Resume mode: directory already exists
    if os.path.isdir(feat_dir):
        if not os.path.isfile(state_path):
            _write_state(state_path, name)
        result = {
            "source": "feat",
            "feat_name": name,
            "feat_dir": feat_dir,
            "spec_path": spec_path,
            "state_path": state_path,
            "mode": "resume",
            "auto_generated": auto_generated,
            "fallback_used": fallback_used,
            "ok": True,
        }
        if legacy_migrated:
            result["legacy_migrated"] = True
        print(json.dumps(result, ensure_ascii=False))
        return

    # Create mode
    os.makedirs(feat_dir, exist_ok=True)

    if not os.path.isfile(spec_path):
        spec_body = _spec_template(name, description, auto_generated)
        with open(spec_path, "w", encoding="utf-8") as f:
            f.write(spec_body)

    _write_state(state_path, name)

    print(json.dumps({
        "source": "feat",
        "feat_name": name,
        "feat_dir": feat_dir,
        "spec_path": spec_path,
        "state_path": state_path,
        "mode": "created",
        "auto_generated": auto_generated,
        "fallback_used": fallback_used,
        "ok": True,
    }, ensure_ascii=False))


def _write_state(state_path, name):
    data = {
        "name": name,
        "status": "[ ]",
        "last": None,
        "phase_history": [],
        "updated": _now_utc(),
    }
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _normalize_state_file(state_path):
    """Normalize a migrated state file: rename legacy ``state`` field → ``status``,
    ensure ``last`` field exists."""
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return
    if "state" in data and "status" not in data:
        data["status"] = data.pop("state")
    data.setdefault("last", None)
    data.setdefault("phase_history", [])
    data.setdefault("updated", _now_utc())
    try:
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def _spec_template(name, description, auto_generated):
    header = f"# Feature: {name}"
    if auto_generated:
        header += "  (이름 자동 생성 — 필요 시 변경하세요)"
    body = [
        header,
        "",
        "## 요구사항",
        "",
    ]
    if description:
        body.append(description)
    else:
        body.append("(여기에 기능 요구사항을 작성하세요. dev-design Phase가 이 파일을 읽어 설계를 수행합니다.)")
    body += [
        "",
        "## 배경 / 맥락",
        "",
        "(선택: 이 기능이 필요한 이유, 관련 이슈, 영향 범위 등)",
        "",
        "## 도메인",
        "",
        "(backend | frontend | fullstack | database — Dev Config의 domains 중 하나. 비워두면 dev-design이 판단)",
        "",
        "## 비고",
        "",
        "(선택: 제약사항, 의존성, 주의사항 등)",
        "",
    ]
    return "\n".join(body)


if __name__ == "__main__":
    main()
