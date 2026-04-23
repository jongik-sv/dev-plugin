#!/usr/bin/env python3
"""Unit tests for wp-setup.py sequential_mode support.

Tests:
  test_sequential_skips_worktree_creation  — sequential_mode=true: no .claude/worktrees/ created
  test_sequential_uses_repo_root           — sequential_mode=true: wt_path is repo root (.)
  test_sequential_prompt_dir_in_temp       — sequential_mode=true: prompt files in TEMP_DIR/seq-prompts/
  test_parallel_mode_creates_worktree      — sequential_mode=false (default): worktree is created
  test_mode_notice_substitution_sequential — {MODE_NOTICE} gets branch-name content in sequential
  test_mode_notice_empty_parallel          — {MODE_NOTICE} is empty string in parallel mode
  test_sequential_signal_restore_from_wbs  — sequential_mode: .done signals restored from wbs.md [xx]

All tests use a temp git repo with minimal wbs.md fixture.
No real tmux session is started (mux detection returns (None, None) in tests).
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import textwrap
import time

import pytest

SCRIPTS_DIR = pathlib.Path(__file__).parent
WP_SETUP = SCRIPTS_DIR / "wp-setup.py"
WBS_PARSE = SCRIPTS_DIR / "wbs-parse.py"

# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

MINIMAL_WBS = textwrap.dedent("""\
    # WBS

    ## Dev Config
    - unit_test: python3 -m pytest scripts/

    ## WP-01: 기능 개발

    ### TSK-01-01: 기본 구현
    - category: backend
    - domain: backend
    - status: [ ]
    - depends: -

    ### TSK-01-02: 추가 구현
    - category: backend
    - domain: backend
    - status: [xx]
    - depends: TSK-01-01
""")

MINIMAL_WBS_WITH_DONE = textwrap.dedent("""\
    # WBS

    ## Dev Config
    - unit_test: python3 -m pytest scripts/

    ## WP-01: 기능 개발

    ### TSK-01-01: 기본 구현
    - category: backend
    - domain: backend
    - status: [xx]
    - depends: -

    ### TSK-01-02: 추가 구현
    - category: backend
    - domain: backend
    - status: [dd]
    - depends: TSK-01-01
""")


def _init_git_repo(path: pathlib.Path) -> None:
    """Create a minimal git repo with an initial commit."""
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@test.com"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"],
                   check=True, capture_output=True)
    # Create an initial commit so HEAD exists
    readme = path / "README.md"
    readme.write_text("test\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "README.md"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "commit", "-m", "init"],
                   check=True, capture_output=True)


def _make_plugin_stub(plugin_root: pathlib.Path) -> None:
    """Create minimal plugin stubs needed by wp-setup.py."""
    # Create scripts dir (wp-setup.py imports _platform from same dir)
    scripts_dir = plugin_root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    # Copy the real scripts we need
    for script in ("_platform.py", "wbs-parse.py", "init-git-rerere.py", "send-prompt.py"):
        src = SCRIPTS_DIR / script
        if src.exists():
            dst = scripts_dir / script
            dst.write_bytes(src.read_bytes())

    # Create minimal template stubs
    refs_dir = plugin_root / "skills" / "dev-team" / "references"
    refs_dir.mkdir(parents=True, exist_ok=True)

    # Minimal template files with ``` markers
    for fname, content in [
        ("ddtr-prompt-template.md", "```\n{TSK-ID} ddtr prompt {DOCS_DIR}\n```\n"),
        ("ddtr-design-template.md", "```\n{TSK-ID} design prompt\n```\n"),
        ("wp-leader-prompt.md",
         "```\n{WP-ID} leader prompt\n{MODE_NOTICE}\n## path\n- DOCS_DIR = {DOCS_DIR}\n"
         "- WT_NAME = {WT_NAME}\n- MODEL_OVERRIDE = {MODEL_OVERRIDE}\n"
         "- ON_FAIL = {ON_FAIL}\n"
         "[WP 내 모든 Task 블록 — TSK-ID, domain, depends, 요구사항, 기술 스펙 포함]\n"
         "[팀리더가 산출한 레벨별 실행 계획]\n```\n"),
        ("wp-leader-init.md", "```\ninit content\n```\n"),
        ("wp-leader-cleanup.md", "```\ncleanup content\n```\n"),
    ]:
        (refs_dir / fname).write_text(content, encoding="utf-8")


def _make_config(
    repo_root: pathlib.Path,
    plugin_root: pathlib.Path,
    temp_dir: pathlib.Path,
    signal_dir: pathlib.Path,
    sequential_mode: bool = False,
    current_branch: str = "main",
    wps: list | None = None,
) -> pathlib.Path:
    """Write a wp-setup-config.json and return its path."""
    if wps is None:
        wps = [
            {
                "wp_id": "WP-01",
                "team_size": 1,
                "tasks": ["TSK-01-01", "TSK-01-02"],
                "execution_plan": "Level 0: TSK-01-01",
            }
        ]

    config = {
        "project_name": "test-proj",
        "window_suffix": "",
        "temp_dir": str(temp_dir),
        "shared_signal_dir": str(signal_dir),
        "docs_dir": "docs",
        "wbs_path": str(repo_root / "docs" / "wbs.md"),
        "session": "",
        "model_override": "",
        "worker_model": "sonnet",
        "wp_leader_model": "sonnet",
        "plugin_root": str(plugin_root),
        "on_fail": "bypass",
        "sequential_mode": sequential_mode,
        "current_branch": current_branch,
        "wps": wps,
    }
    config_path = temp_dir / "wp-setup-config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return config_path


def _run_wp_setup(repo_root: pathlib.Path, config_path: pathlib.Path,
                  extra_env: dict | None = None) -> subprocess.CompletedProcess:
    """Run wp-setup.py from repo_root directory."""
    env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(repo_root)}
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(WP_SETUP), str(config_path)],
        capture_output=True, text=True,
        cwd=str(repo_root),
        env=env,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSequentialMode:
    """Tests for sequential_mode=True behavior in wp-setup.py."""

    def setup_method(self):
        self._tmpdir = tempfile.mkdtemp(prefix="wp-setup-seq-test-")
        self.repo_root = pathlib.Path(self._tmpdir) / "repo"
        self.repo_root.mkdir()
        _init_git_repo(self.repo_root)

        # Create docs/wbs.md
        docs_dir = self.repo_root / "docs"
        docs_dir.mkdir()
        (docs_dir / "wbs.md").write_text(MINIMAL_WBS, encoding="utf-8")

        # Create plugin stub
        self.plugin_root = pathlib.Path(self._tmpdir) / "plugin"
        self.plugin_root.mkdir()
        _make_plugin_stub(self.plugin_root)

        self.temp_dir = pathlib.Path(self._tmpdir) / "tmp"
        self.temp_dir.mkdir()
        self.signal_dir = pathlib.Path(self._tmpdir) / "signals"
        self.signal_dir.mkdir()

    def test_sequential_skips_worktree_creation(self):
        """sequential_mode=True must NOT create .claude/worktrees/ directory."""
        config_path = _make_config(
            self.repo_root, self.plugin_root,
            self.temp_dir, self.signal_dir,
            sequential_mode=True,
        )
        result = _run_wp_setup(self.repo_root, config_path)
        assert result.returncode == 0, f"wp-setup failed:\n{result.stderr}"

        worktrees_dir = self.repo_root / ".claude" / "worktrees"
        assert not worktrees_dir.exists(), (
            f".claude/worktrees/ should NOT be created in sequential_mode=True. "
            f"Found: {list(worktrees_dir.iterdir()) if worktrees_dir.exists() else 'N/A'}"
        )

    def test_sequential_stdout_indicates_mode(self):
        """wp-setup.py sequential mode should print a message indicating sequential mode."""
        config_path = _make_config(
            self.repo_root, self.plugin_root,
            self.temp_dir, self.signal_dir,
            sequential_mode=True,
        )
        result = _run_wp_setup(self.repo_root, config_path)
        assert result.returncode == 0, f"wp-setup failed:\n{result.stderr}"
        # Should indicate sequential mode in output
        assert "sequential" in result.stdout.lower() or "seq" in result.stdout.lower(), (
            f"Expected 'sequential' or 'seq' in stdout:\n{result.stdout}"
        )

    def test_sequential_prompt_files_in_temp(self):
        """sequential_mode=True: prompt files should be in TEMP_DIR/seq-prompts/ (not .claude/worktrees/)."""
        config_path = _make_config(
            self.repo_root, self.plugin_root,
            self.temp_dir, self.signal_dir,
            sequential_mode=True,
        )
        result = _run_wp_setup(self.repo_root, config_path)
        assert result.returncode == 0, f"wp-setup failed:\n{result.stderr}"

        # Prompt file should exist in temp dir, NOT in .claude/worktrees/
        prompt_in_worktrees = self.repo_root / ".claude" / "worktrees" / "WP-01-prompt.txt"
        assert not prompt_in_worktrees.exists(), (
            f"Prompt file should NOT be in .claude/worktrees/ for sequential_mode=True"
        )

        # seq-prompts dir should be used instead
        seq_prompts_dir = self.temp_dir / "seq-prompts"
        prompt_in_seq = seq_prompts_dir / "WP-01-prompt.txt"
        assert seq_prompts_dir.exists(), (
            f"TEMP_DIR/seq-prompts/ should be created for sequential_mode=True"
        )
        assert prompt_in_seq.exists(), (
            f"Prompt file should exist in TEMP_DIR/seq-prompts/ for sequential_mode=True. "
            f"Contents of seq-prompts: {list(seq_prompts_dir.iterdir())}"
        )

    def test_parallel_mode_creates_worktree(self):
        """sequential_mode=False (default): worktree must be created under .claude/worktrees/."""
        config_path = _make_config(
            self.repo_root, self.plugin_root,
            self.temp_dir, self.signal_dir,
            sequential_mode=False,
        )
        result = _run_wp_setup(self.repo_root, config_path)
        assert result.returncode == 0, f"wp-setup failed:\n{result.stderr}"

        worktree_dir = self.repo_root / ".claude" / "worktrees" / "WP-01"
        assert worktree_dir.exists(), (
            f".claude/worktrees/WP-01/ should be created in parallel mode (sequential_mode=False)"
        )

    def test_mode_notice_sequential_contains_branch(self):
        """sequential_mode=True: wp-leader prompt must contain branch name in MODE_NOTICE area."""
        config_path = _make_config(
            self.repo_root, self.plugin_root,
            self.temp_dir, self.signal_dir,
            sequential_mode=True,
            current_branch="feature-xyz",
        )
        result = _run_wp_setup(self.repo_root, config_path)
        assert result.returncode == 0, f"wp-setup failed:\n{result.stderr}"

        # Read the generated prompt file
        seq_prompts_dir = self.temp_dir / "seq-prompts"
        prompt_file = seq_prompts_dir / "WP-01-prompt.txt"
        assert prompt_file.exists(), "Prompt file should exist"
        content = prompt_file.read_text(encoding="utf-8")

        # The prompt should contain branch name (from MODE_NOTICE)
        assert "feature-xyz" in content, (
            f"Branch name 'feature-xyz' should appear in MODE_NOTICE in prompt. "
            f"Prompt content:\n{content[:500]}"
        )

    def test_mode_notice_parallel_empty(self):
        """sequential_mode=False: MODE_NOTICE should be replaced with empty string."""
        config_path = _make_config(
            self.repo_root, self.plugin_root,
            self.temp_dir, self.signal_dir,
            sequential_mode=False,
        )
        result = _run_wp_setup(self.repo_root, config_path)
        assert result.returncode == 0, f"wp-setup failed:\n{result.stderr}"

        # Read the generated prompt file from .claude/worktrees/
        prompt_file = self.repo_root / ".claude" / "worktrees" / "WP-01-prompt.txt"
        assert prompt_file.exists(), "Prompt file should exist in .claude/worktrees/"
        content = prompt_file.read_text(encoding="utf-8")

        # {MODE_NOTICE} placeholder should be gone (replaced with empty string)
        assert "{MODE_NOTICE}" not in content, (
            "Raw {MODE_NOTICE} placeholder should be substituted (not left as-is)"
        )
        # And it should not say "순차 모드" in the prompt for parallel mode
        assert "순차 모드" not in content, (
            "Parallel mode prompt should not contain sequential mode notice"
        )

    def test_sequential_signal_restore_from_wbs(self):
        """sequential_mode=True: .done signals restored from wbs.md [xx] status lines."""
        # Use wbs with some [xx] tasks
        (self.repo_root / "docs" / "wbs.md").write_text(
            MINIMAL_WBS_WITH_DONE, encoding="utf-8"
        )
        config_path = _make_config(
            self.repo_root, self.plugin_root,
            self.temp_dir, self.signal_dir,
            sequential_mode=True,
        )
        result = _run_wp_setup(self.repo_root, config_path)
        assert result.returncode == 0, f"wp-setup failed:\n{result.stderr}"

        # TSK-01-01 is [xx] in wbs — .done and -design.done should be pre-created
        done_path = self.signal_dir / "TSK-01-01.done"
        design_done_path = self.signal_dir / "TSK-01-01-design.done"
        assert done_path.exists(), (
            f"TSK-01-01.done should be pre-created from wbs.md [xx] status in sequential_mode"
        )
        assert design_done_path.exists(), (
            f"TSK-01-01-design.done should be pre-created from wbs.md [xx] status in sequential_mode"
        )

        # TSK-01-02 is [dd] — only -design.done should be created
        done_path2 = self.signal_dir / "TSK-01-02.done"
        design_done_path2 = self.signal_dir / "TSK-01-02-design.done"
        assert not done_path2.exists(), (
            f"TSK-01-02.done should NOT be pre-created for [dd] status"
        )
        assert design_done_path2.exists(), (
            f"TSK-01-02-design.done should be pre-created for [dd] status in sequential_mode"
        )


class TestParallelModeRegression:
    """Ensure sequential_mode=False doesn't regress existing parallel behavior."""

    def setup_method(self):
        self._tmpdir = tempfile.mkdtemp(prefix="wp-setup-par-test-")
        self.repo_root = pathlib.Path(self._tmpdir) / "repo"
        self.repo_root.mkdir()
        _init_git_repo(self.repo_root)
        docs_dir = self.repo_root / "docs"
        docs_dir.mkdir()
        (docs_dir / "wbs.md").write_text(MINIMAL_WBS, encoding="utf-8")

        self.plugin_root = pathlib.Path(self._tmpdir) / "plugin"
        self.plugin_root.mkdir()
        _make_plugin_stub(self.plugin_root)

        self.temp_dir = pathlib.Path(self._tmpdir) / "tmp"
        self.temp_dir.mkdir()
        self.signal_dir = pathlib.Path(self._tmpdir) / "signals"
        self.signal_dir.mkdir()

    def test_missing_sequential_mode_field_treated_as_false(self):
        """Config without sequential_mode field should default to parallel (False)."""
        config = {
            "project_name": "test-proj",
            "window_suffix": "",
            "temp_dir": str(self.temp_dir),
            "shared_signal_dir": str(self.signal_dir),
            "docs_dir": "docs",
            "wbs_path": str(self.repo_root / "docs" / "wbs.md"),
            "session": "",
            "model_override": "",
            "worker_model": "sonnet",
            "wp_leader_model": "sonnet",
            "plugin_root": str(self.plugin_root),
            "on_fail": "bypass",
            # NOTE: no sequential_mode field
            "wps": [
                {
                    "wp_id": "WP-01",
                    "team_size": 1,
                    "tasks": ["TSK-01-01"],
                    "execution_plan": "Level 0: TSK-01-01",
                }
            ],
        }
        config_path = self.temp_dir / "wp-setup-config.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")

        result = _run_wp_setup(self.repo_root, config_path)
        assert result.returncode == 0, f"wp-setup failed:\n{result.stderr}"

        # Should create worktree (parallel mode)
        worktree_dir = self.repo_root / ".claude" / "worktrees" / "WP-01"
        assert worktree_dir.exists(), (
            ".claude/worktrees/WP-01/ should be created when sequential_mode is absent (parallel mode)"
        )
