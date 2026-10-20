from __future__ import annotations

import hashlib
import json
import os

import pytest
from conftest import git

from milestone_inspector.core import GitRepository, InspectionError, to_json, to_markdown


def test_inspect_has_fixed_shas_and_changes(repo):
    path, base, head = repo
    data = GitRepository(path).inspect(base[:12], "HEAD", require_ancestor=True)
    assert data["base_sha"] == base
    assert data["head_sha"] == head
    assert data["commit_count"] == 1
    assert data["changes_by_type"] == {"A": 2, "M": 1}
    assert {c["path"] for c in data["changed_files"]} == {
        "LICENSE",
        "sample.txt",
        "tests/test_example.py",
    }
    assert data["head_repository_signals"]["tests"] is True
    assert data["head_repository_signals"]["license"] is True
    assert data["head_repository_signals"]["ci_config"] is False


def test_snapshot_hashes_are_blob_hashes(repo):
    path, _, head = repo
    manifest = GitRepository(path).snapshot(head)
    doc = next(x for x in manifest["files"] if x["path"] == "sample.txt")
    assert doc["sha256"] == hashlib.sha256(b"after\n").hexdigest()
    assert doc["byte_size"] == 6
    assert manifest["total_blob_bytes"] > 0


def test_snapshot_independent_of_dirty_working_tree(repo):
    path, _, head = repo
    original = GitRepository(path).snapshot(head)
    (path / "sample.txt").write_text("local changes not committed")
    assert GitRepository(path).snapshot(head) == original


def test_rename_detected(repo):
    path, _, head = repo
    git(path, "mv", "sample.txt", "renamed.txt")
    git(path, "commit", "-qm", "rename file")
    data = GitRepository(path).inspect(head, "HEAD")
    assert any(
        f["old_path"] == "sample.txt" and f["path"] == "renamed.txt" and f["status"].startswith("R")
        for f in data["changed_files"]
    )


def test_spaces_and_tabs_in_filename(repo):
    path, _, head = repo
    # Windows forbids tabs in filenames; POSIX exercises the stricter NUL parser case.
    name = "name with spaces.txt" if os.name == "nt" else "a\tname with spaces.txt"
    (path / name).write_text("OK", encoding="utf-8")
    git(path, "add", ".")
    git(path, "commit", "-qm", "unusual filename")
    report = GitRepository(path).inspect(head, "HEAD")
    assert report["changed_files"][0]["path"] == name
    assert GitRepository(path).snapshot("HEAD")["file_count"] == 5


def test_invalid_revision_rejected(repo):
    path, _, _ = repo
    for val in ("", "--help", "missing-branch", "HEAD\n--help"):
        with pytest.raises(InspectionError):
            GitRepository(path).resolve_commit(val)


def test_limits_rejected(repo):
    path, _, head = repo
    with pytest.raises(InspectionError, match="limit"):
        GitRepository(path).snapshot(head, max_blob_bytes=2)
    with pytest.raises(InspectionError, match="limit"):
        GitRepository(path).snapshot(head, max_total_bytes=5)
    with pytest.raises(InspectionError, match="file-count"):
        GitRepository(path).snapshot(head, max_files=2)


def test_output_serializes_and_renders(repo):
    path, base, head = repo
    info = GitRepository(path).inspect(base, head)
    assert json.loads(to_json(info))["schema_version"] == 1
    rendered = to_markdown(info)
    assert "## Changed files" in rendered
    assert "base" in rendered.lower()


def test_empty_range_is_reported_without_changes(repo):
    path, _, head = repo
    info = GitRepository(path).inspect(head, head, require_ancestor=True)
    assert info["commit_count"] == 0
    assert info["changes_by_type"] == {}
    assert info["changed_files"] == []


def test_submodule_gitlink_is_not_followed(repo):
    path, _, head = repo
    git(path, "update-index", "--add", "--cacheinfo", f"160000,{head},linked-module")
    git(path, "commit", "-qm", "record external gitlink")
    report = GitRepository(path).snapshot("HEAD")
    linked = next(item for item in report["files"] if item["path"] == "linked-module")
    assert linked["sha256"] is None
    assert linked["git_oid"] == head
    assert "Submodule content is not inspected: linked-module" in report["warnings"]


def test_lfs_pointer_is_identified(repo):
    path, _, _ = repo
    pointer = (
        "version https://git-lfs.github.com/spec/v1\n" + "oid sha256:" + "a" * 64 + "\nsize 123\n"
    )
    (path / "large.bin").write_text(pointer)
    git(path, "add", "large.bin")
    git(path, "commit", "-qm", "add Git LFS pointer")
    manifest = GitRepository(path).snapshot("HEAD")
    assert "Git LFS pointer, not downloaded file content: large.bin" in manifest["warnings"]


def test_unknown_directory():
    with pytest.raises(InspectionError):
        GitRepository("/path/that/does/not/exist")


def test_divergent_history_require_ancestor(repo):
    path, base, head = repo
    git(path, "checkout", "-qb", "parallel", base)
    (path / "parallel.txt").write_text("parallel branch")
    git(path, "add", ".")
    git(path, "commit", "-qm", "parallel")
    with pytest.raises(InspectionError, match="ancestor"):
        GitRepository(path).inspect(head, "HEAD", require_ancestor=True)
    assert GitRepository(path).inspect(head, "HEAD")["base_is_ancestor"] is False
