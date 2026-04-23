#!/usr/bin/env python3
"""Unit tests for args-parse.py — --sequential / --seq / --one-wp-at-a-time flags.

Tests:
  test_sequential_flag           — --sequential sets options.sequential=True
  test_seq_alias                 — --seq is equivalent to --sequential
  test_one_wp_at_a_time_alias    — --one-wp-at-a-time is equivalent to --sequential
  test_no_sequential_flag        — absence of flag: options.sequential=False
  test_sequential_with_wp_ids    — --sequential combined with WP-IDs works
  test_sequential_with_team_size — --sequential combined with --team-size works
  test_sequential_with_on_fail   — --sequential combined with --on-fail works
  test_sequential_not_for_dev    — --sequential flag ignored on non-dev-team skill (no error)
"""
from __future__ import annotations

import json
import subprocess
import sys
import pathlib

import pytest

SCRIPTS_DIR = pathlib.Path(__file__).parent
ARGS_PARSE = SCRIPTS_DIR / "args-parse.py"


def run_args_parse(skill: str, *args: str) -> tuple[dict, int]:
    """Run args-parse.py and return (parsed_json, returncode)."""
    r = subprocess.run(
        [sys.executable, str(ARGS_PARSE), skill, *args],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        return json.loads(r.stdout), r.returncode
    # On error, return stderr info wrapped in dict for easier inspection
    try:
        err = json.loads(r.stderr)
    except Exception:
        err = {"error": r.stderr.strip()}
    return err, r.returncode


# ---------------------------------------------------------------------------
# Core flag parsing tests
# ---------------------------------------------------------------------------

def test_sequential_flag():
    """--sequential must set options.sequential=True."""
    result, rc = run_args_parse("dev-team", "--sequential", "WP-01")
    assert rc == 0, f"Unexpected exit code: {rc}, result: {result}"
    assert result["options"]["sequential"] is True


def test_seq_alias():
    """--seq alias must set options.sequential=True."""
    result, rc = run_args_parse("dev-team", "--seq", "WP-01")
    assert rc == 0, f"Unexpected exit code: {rc}, result: {result}"
    assert result["options"]["sequential"] is True


def test_one_wp_at_a_time_alias():
    """--one-wp-at-a-time alias must set options.sequential=True."""
    result, rc = run_args_parse("dev-team", "--one-wp-at-a-time", "WP-01")
    assert rc == 0, f"Unexpected exit code: {rc}, result: {result}"
    assert result["options"]["sequential"] is True


def test_no_sequential_flag():
    """Absence of --sequential flag: options.sequential must be False."""
    result, rc = run_args_parse("dev-team", "WP-01")
    assert rc == 0, f"Unexpected exit code: {rc}, result: {result}"
    assert result["options"]["sequential"] is False


def test_sequential_no_wp():
    """--sequential without WP-ID is valid (auto-select mode)."""
    result, rc = run_args_parse("dev-team", "--sequential")
    assert rc == 0, f"Unexpected exit code: {rc}, result: {result}"
    assert result["options"]["sequential"] is True
    assert result["wp_ids"] == []


# ---------------------------------------------------------------------------
# Combination tests
# ---------------------------------------------------------------------------

def test_sequential_with_wp_ids():
    """--sequential combined with multiple WP-IDs must parse all IDs."""
    result, rc = run_args_parse("dev-team", "--sequential", "WP-01", "WP-02", "WP-03")
    assert rc == 0, f"Unexpected exit code: {rc}, result: {result}"
    assert result["options"]["sequential"] is True
    assert result["wp_ids"] == ["WP-01", "WP-02", "WP-03"]


def test_sequential_with_team_size():
    """--sequential with --team-size must parse both options correctly."""
    result, rc = run_args_parse("dev-team", "--sequential", "--team-size", "5", "WP-01")
    assert rc == 0, f"Unexpected exit code: {rc}, result: {result}"
    assert result["options"]["sequential"] is True
    assert result["options"]["team_size"] == 5
    assert result["wp_ids"] == ["WP-01"]


def test_sequential_with_on_fail():
    """--sequential with --on-fail must parse both options correctly."""
    result, rc = run_args_parse("dev-team", "--sequential", "--on-fail", "strict", "WP-01")
    assert rc == 0, f"Unexpected exit code: {rc}, result: {result}"
    assert result["options"]["sequential"] is True
    assert result["options"]["on_fail"] == "strict"


def test_sequential_flag_order_independent():
    """--sequential can appear after WP-ID tokens."""
    result, rc = run_args_parse("dev-team", "WP-01", "--sequential")
    assert rc == 0, f"Unexpected exit code: {rc}, result: {result}"
    assert result["options"]["sequential"] is True
    assert "WP-01" in result["wp_ids"]


# ---------------------------------------------------------------------------
# Backward compatibility / non-regression
# ---------------------------------------------------------------------------

def test_dev_team_no_flags_unchanged():
    """Existing dev-team behavior (no --sequential): must still work identically."""
    result, rc = run_args_parse("dev-team", "WP-04", "--team-size", "5")
    assert rc == 0, f"Unexpected exit code: {rc}, result: {result}"
    assert result["options"]["sequential"] is False
    assert result["options"]["team_size"] == 5
    assert "WP-04" in result["wp_ids"]


def test_dev_seq_team_size_still_rejected():
    """dev-seq still rejects --team-size (no regression)."""
    _, rc = run_args_parse("dev-seq", "--team-size", "3", "WP-01")
    assert rc != 0, "dev-seq should still reject --team-size"


def test_dev_skill_no_sequential_field():
    """Non-dev-team skills also include sequential field in options (default False)."""
    result, rc = run_args_parse("dev", "TSK-01-01")
    assert rc == 0
    # sequential field should be present (or at minimum, not error out)
    # After implementation, sequential field is always present in options
    assert "sequential" in result["options"]
    assert result["options"]["sequential"] is False


# ---------------------------------------------------------------------------
# NL keyword aliases (Korean natural language)
# ---------------------------------------------------------------------------

def test_nl_keyword_sunchasilhaeng():
    """'순차실행' bare token activates sequential for dev-team."""
    result, rc = run_args_parse("dev-team", "monitor-v4", "순차실행", "해")
    assert rc == 0, f"Unexpected exit code: {rc}, result: {result}"
    assert result["options"]["sequential"] is True


def test_nl_keyword_suncha():
    """'순차' bare token activates sequential for dev-team."""
    result, rc = run_args_parse("dev-team", "WP-01", "순차")
    assert rc == 0
    assert result["options"]["sequential"] is True
    assert "WP-01" in result["wp_ids"]


def test_nl_keyword_suncha_mode():
    """'순차모드로' bare token activates sequential for dev-team."""
    result, rc = run_args_parse("dev-team", "순차모드로", "WP-01")
    assert rc == 0
    assert result["options"]["sequential"] is True


def test_nl_keyword_sequential_english():
    """Bare 'sequential' token (no dashes, case-insensitive) activates sequential."""
    result, rc = run_args_parse("dev-team", "WP-01", "SEQUENTIAL")
    assert rc == 0
    assert result["options"]["sequential"] is True


def test_nl_keyword_ignored_for_dev_seq():
    """NL keywords do not activate sequential on dev-seq (dev-team only)."""
    result, rc = run_args_parse("dev-seq", "WP-01", "순차")
    assert rc == 0
    # dev-seq already implies sequential by design; NL match intentionally not forwarded here
    # to avoid conflating "already sequential" with "force sequential flag on dev-team".
    assert result["options"]["sequential"] is False


def test_nl_keyword_ignored_for_dev():
    """NL keywords on /dev skill do not set sequential (scope: dev-team only)."""
    result, rc = run_args_parse("dev", "TSK-01-01", "순차")
    assert rc == 0
    assert result["options"]["sequential"] is False
