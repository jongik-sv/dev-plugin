#!/usr/bin/env python3
"""Unit tests for init-git-rerere.py

test_init_git_rerere_sets_drivers  — fresh git repo: all 6 keys are set
test_init_git_rerere_idempotent    — 2nd run: all items are [no-op], exit 0
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import pathlib

import pytest

# Path to the script under test
SCRIPTS_DIR = pathlib.Path(__file__).parent
INIT_RERERE = SCRIPTS_DIR / "init-git-rerere.py"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _init_git_repo(path: pathlib.Path) -> None:
    """Create a minimal git repo at path."""
    subprocess.run(["git", "init", str(path)], check=True,
                   capture_output=True, text=True)
    # Configure user so commits work (needed to satisfy git's new init checks)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@test.com"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"],
                   check=True, capture_output=True)


def _git_config_get(worktree: pathlib.Path, key: str) -> str | None:
    """Return local git config value or None if not set."""
    r = subprocess.run(
        ["git", "-C", str(worktree), "config", "--local", "--get", key],
        capture_output=True, text=True,
    )
    return r.stdout.strip() if r.returncode == 0 else None


def _run_script(worktree: pathlib.Path, plugin_root: pathlib.Path,
                extra_env: dict | None = None) -> subprocess.CompletedProcess:
    """Run init-git-rerere.py against worktree with controlled environment."""
    env = {**os.environ}
    env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    # Isolate HOME so global ~/.gitconfig is not written
    env["HOME"] = str(worktree / "_fake_home")
    (worktree / "_fake_home").mkdir(exist_ok=True)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(INIT_RERERE), "--worktree", str(worktree)],
        capture_output=True, text=True, env=env,
    )


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def git_repo(tmp_path):
    """Yield a fresh git repo path."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    return repo


@pytest.fixture()
def fake_plugin_root(tmp_path):
    """Yield a fake plugin root that has a scripts/ subdirectory."""
    root = tmp_path / "plugin"
    (root / "scripts").mkdir(parents=True)
    # Create placeholder driver scripts so path resolution is verifiable
    (root / "scripts" / "merge-state-json.py").write_text("# placeholder\n")
    (root / "scripts" / "merge-wbs-status.py").write_text("# placeholder\n")
    return root


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

class TestInitGitRerereSetDrivers:
    """test_init_git_rerere_sets_drivers — all 6 git config keys are written."""

    def test_exit_zero(self, git_repo, fake_plugin_root):
        result = _run_script(git_repo, fake_plugin_root)
        assert result.returncode == 0, f"stderr: {result.stderr}"

    def test_rerere_enabled(self, git_repo, fake_plugin_root):
        _run_script(git_repo, fake_plugin_root)
        assert _git_config_get(git_repo, "rerere.enabled") == "true"

    def test_rerere_autoupdate(self, git_repo, fake_plugin_root):
        _run_script(git_repo, fake_plugin_root)
        assert _git_config_get(git_repo, "rerere.autoupdate") == "true"

    def test_state_json_driver_key(self, git_repo, fake_plugin_root):
        _run_script(git_repo, fake_plugin_root)
        val = _git_config_get(git_repo, "merge.state-json-smart.driver")
        assert val is not None, "merge.state-json-smart.driver not set"
        assert "merge-state-json.py" in val

    def test_state_json_driver_name(self, git_repo, fake_plugin_root):
        _run_script(git_repo, fake_plugin_root)
        val = _git_config_get(git_repo, "merge.state-json-smart.name")
        assert val is not None, "merge.state-json-smart.name not set"

    def test_wbs_status_driver_key(self, git_repo, fake_plugin_root):
        _run_script(git_repo, fake_plugin_root)
        val = _git_config_get(git_repo, "merge.wbs-status-smart.driver")
        assert val is not None, "merge.wbs-status-smart.driver not set"
        assert "merge-wbs-status.py" in val

    def test_wbs_status_driver_name(self, git_repo, fake_plugin_root):
        _run_script(git_repo, fake_plugin_root)
        val = _git_config_get(git_repo, "merge.wbs-status-smart.name")
        assert val is not None, "merge.wbs-status-smart.name not set"

    def test_driver_path_uses_plugin_root(self, git_repo, fake_plugin_root):
        """Driver value must contain plugin_root path (not just filename)."""
        _run_script(git_repo, fake_plugin_root)
        val = _git_config_get(git_repo, "merge.state-json-smart.driver")
        assert str(fake_plugin_root) in val, (
            f"Expected plugin_root path in driver value. Got: {val}"
        )

    def test_only_local_config_modified(self, git_repo, fake_plugin_root, tmp_path):
        """Global git config must NOT be written."""
        fake_home = git_repo / "_fake_home"
        global_gitconfig = fake_home / ".gitconfig"
        _run_script(git_repo, fake_plugin_root)
        if global_gitconfig.exists():
            content = global_gitconfig.read_text()
            assert "rerere" not in content, "rerere written to global config"
            assert "state-json-smart" not in content
            assert "wbs-status-smart" not in content


class TestInitGitRerereIdempotent:
    """test_init_git_rerere_idempotent — 2nd run is all [no-op], exit 0."""

    def test_second_run_exit_zero(self, git_repo, fake_plugin_root):
        _run_script(git_repo, fake_plugin_root)
        result2 = _run_script(git_repo, fake_plugin_root)
        assert result2.returncode == 0, f"stderr: {result2.stderr}"

    def test_second_run_all_noop(self, git_repo, fake_plugin_root):
        _run_script(git_repo, fake_plugin_root)
        result2 = _run_script(git_repo, fake_plugin_root)
        output = result2.stdout
        assert "[no-op]" in output, f"Expected [no-op] in 2nd run output: {output!r}"
        # All 6 keys → 6 [no-op] lines
        noop_count = output.count("[no-op]")
        assert noop_count >= 6, f"Expected >=6 [no-op] lines, got {noop_count}. Output:\n{output}"

    def test_values_unchanged_after_second_run(self, git_repo, fake_plugin_root):
        _run_script(git_repo, fake_plugin_root)
        val_before = _git_config_get(git_repo, "rerere.enabled")
        _run_script(git_repo, fake_plugin_root)
        val_after = _git_config_get(git_repo, "rerere.enabled")
        assert val_before == val_after == "true"


class TestInitGitRerereFallback:
    """CLAUDE_PLUGIN_ROOT not set → fallback to __file__-based path."""

    def test_fallback_without_env_var(self, git_repo):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"}
        env["HOME"] = str(git_repo / "_fake_home")
        (git_repo / "_fake_home").mkdir(exist_ok=True)
        result = subprocess.run(
            [sys.executable, str(INIT_RERERE), "--worktree", str(git_repo)],
            capture_output=True, text=True, env=env,
        )
        # Should succeed (fallback to parent of scripts/ dir)
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert _git_config_get(git_repo, "rerere.enabled") == "true"


class TestInitGitRerereGitMissing:
    """No git binary → exit 1 with clear message."""

    def test_no_git_exits_1(self, git_repo, fake_plugin_root, monkeypatch):
        # Override PATH so git cannot be found
        env = {k: v for k, v in os.environ.items()}
        env["PATH"] = str(git_repo / "_empty_bin")  # non-existent → no git
        (git_repo / "_empty_bin").mkdir(exist_ok=True)
        env["CLAUDE_PLUGIN_ROOT"] = str(fake_plugin_root)
        env["HOME"] = str(git_repo / "_fake_home")
        (git_repo / "_fake_home").mkdir(exist_ok=True)
        result = subprocess.run(
            [sys.executable, str(INIT_RERERE), "--worktree", str(git_repo)],
            capture_output=True, text=True, env=env,
        )
        assert result.returncode == 1
        assert "git" in result.stderr.lower() or "git" in result.stdout.lower()
