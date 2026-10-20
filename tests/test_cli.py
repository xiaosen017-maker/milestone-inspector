import json
import subprocess
import sys


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "milestone_inspector.cli", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def test_cli_inspect(repo, tmp_path):
    path, base, head = repo
    output = tmp_path / "report.json"
    markdown = tmp_path / "report.md"
    result = run_cli(
        "inspect",
        "--repo",
        str(path),
        "--base",
        base,
        "--head",
        head,
        "--json",
        str(output),
        "--markdown",
        str(markdown),
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text())["commit_count"] == 1
    assert "Changed files" in markdown.read_text()


def test_cli_snapshot(repo):
    path, _, _ = repo
    result = run_cli("snapshot", "--repo", str(path), "--ref", "HEAD")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["file_count"] == 4


def test_cli_failure_code(repo):
    path, _, _ = repo
    result = run_cli("snapshot", "--repo", str(path), "--ref", "HEAD", "--max-blob-bytes", "-1")
    assert result.returncode == 2
    assert "must be positive" in result.stderr


def test_cli_file_count_limit(repo):
    path, _, _ = repo
    result = run_cli("snapshot", "--repo", str(path), "--ref", "HEAD", "--max-files", "2")
    assert result.returncode == 2
    assert "file-count limit" in result.stderr
