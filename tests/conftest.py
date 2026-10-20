from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def git(path: Path, *args: str) -> str:
    p = subprocess.run(
        ["git", "-C", str(path), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return p.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path):
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "tester@example.invalid")
    git(tmp_path, "config", "user.name", "Test User")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "sample.txt").write_text("before\n", encoding="utf-8")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "initial")
    base = git(tmp_path, "rev-parse", "HEAD")
    (tmp_path / "sample.txt").write_text("after\n", encoding="utf-8")
    (tmp_path / "LICENSE").write_text("Example license\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_example.py").write_text("assert True\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "add validation")
    head = git(tmp_path, "rev-parse", "HEAD")
    return tmp_path, base, head
