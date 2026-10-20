"""Git-backed snapshot and milestone inspection without network access.

Git is invoked with argument arrays (never through a shell), with revision
strings resolved to immutable commit hashes before diffing. The results are
observations and heuristic signals, *not* an authoritative quality rating.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


class InspectionError(Exception):
    """Invalid input, inaccessible repository or unsupported Git object."""


_SHA = re.compile(r"^[0-9a-f]{40,64}$")


@dataclass(frozen=True)
class FileChange:
    status: str
    path: str
    old_path: str | None = None


@dataclass(frozen=True)
class SnapshotFile:
    path: str
    mode: str
    git_oid: str
    byte_size: int | None
    sha256: str | None


class GitRepository:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        if not self.path.is_dir():
            raise InspectionError(f"Repository directory not found: {self.path}")
        if not self._git("rev-parse", "--is-inside-work-tree").strip() == b"true":
            raise InspectionError("Not a Git work tree")

    def _git(self, *args: str, input_data: bytes | None = None) -> bytes:
        try:
            completed = subprocess.run(
                ["git", "-C", str(self.path), "--no-pager", *args],
                input=input_data,
                capture_output=True,
                timeout=35,
                check=False,
                env=None,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise InspectionError(f"Git execution failed: {exc}") from exc
        if completed.returncode:
            details = completed.stderr.decode("utf-8", errors="replace").strip()
            raise InspectionError(f"git {args[0]} failed: {details[:320]}")
        return completed.stdout

    def resolve_commit(self, rev: str) -> str:
        if not rev or rev.startswith("-") or "\x00" in rev or "\n" in rev:
            raise InspectionError("Revision must be a nonempty commit reference")
        # '--end-of-options' prevents user-supplied strings from becoming Git flags.
        raw = self._git("rev-parse", "--verify", "--end-of-options", f"{rev}^{{commit}}")
        sha = raw.decode("ascii").strip()
        if not _SHA.fullmatch(sha):
            raise InspectionError("Unexpected revision output from Git")
        return sha

    def is_ancestor(self, base_sha: str, head_sha: str) -> bool:
        p = subprocess.run(
            ["git", "-C", str(self.path), "merge-base", "--is-ancestor", base_sha, head_sha],
            capture_output=True,
            timeout=35,
            check=False,
        )
        if p.returncode not in (0, 1):
            raise InspectionError(p.stderr.decode(errors="replace") or "merge-base failed")
        return p.returncode == 0

    def changes(self, base_sha: str, head_sha: str) -> list[FileChange]:
        stream = self._git(
            "diff", "--no-ext-diff", "--name-status", "-z", "--find-renames", base_sha, head_sha
        )
        fields = stream.split(b"\x00")
        if fields[-1] != b"":
            raise InspectionError("Git returned an incomplete diff listing")
        result: list[FileChange] = []
        i = 0
        while i < len(fields) - 1:
            status = fields[i].decode("ascii")
            i += 1
            if not status or status[0] not in "ACDMRTUXB":
                raise InspectionError(f"Unknown change status: {status}")
            if status.startswith(("R", "C")):
                if i + 1 >= len(fields) - 1:
                    raise InspectionError("Malformed renamed/copied path")
                old_path = fields[i].decode("utf-8", errors="surrogateescape")
                path = fields[i + 1].decode("utf-8", errors="surrogateescape")
                i += 2
                result.append(FileChange(status=status, path=path, old_path=old_path))
            else:
                if i >= len(fields) - 1:
                    raise InspectionError("Malformed changed path")
                path = fields[i].decode("utf-8", errors="surrogateescape")
                i += 1
                result.append(FileChange(status=status, path=path))
        return result

    def commit_subjects(
        self, base_sha: str, head_sha: str, limit: int = 25
    ) -> list[dict[str, str]]:
        rows = self._git(
            "log", f"--max-count={limit}", "--format=%H%x1f%s%x00", f"{base_sha}..{head_sha}"
        )
        records = []
        for item in rows.strip(b"\n\x00").split(b"\x00"):
            raw = item.strip(b"\n")
            if not raw:
                continue
            values = raw.decode("utf-8", errors="replace").split("\x1f", 1)
            if len(values) == 2:
                records.append({"sha": values[0], "subject": values[1]})
        return records

    def tree(self, sha: str) -> list[tuple[str, str, str, str]]:
        output = self._git("ls-tree", "-r", "-z", sha)
        entries: list[tuple[str, str, str, str]] = []
        for line in output.split(b"\x00"):
            if not line:
                continue
            try:
                left, path = line.split(b"\t", 1)
                mode, typ, oid = left.decode("ascii").split(" ", 2)
            except (ValueError, UnicodeError) as exc:
                raise InspectionError("Malformed tree listing") from exc
            entries.append((mode, typ, oid, path.decode("utf-8", errors="surrogateescape")))
        return entries

    def blob(self, oid: str) -> bytes:
        return self._git("cat-file", "blob", oid)

    def file_signals(self, sha: str) -> dict[str, bool]:
        paths = {p.lower() for _, typ, _, p in self.tree(sha) if typ == "blob"}
        root = {p for p in paths if "/" not in p}
        return {
            "readme": any(p in root for p in ("readme.md", "readme.rst", "readme")),
            "license": any(p in root for p in ("license", "license.md", "license.txt", "copying")),
            "tests": any(
                p.startswith(("tests/", "test/")) or p.endswith("_test.py") for p in paths
            ),
            "ci_config": any(
                p.startswith(".github/workflows/") or p == ".gitlab-ci.yml" for p in paths
            ),
            "contributing": any(p in root for p in ("contributing.md", "contributing.rst")),
        }

    def inspect(self, base: str, head: str, *, require_ancestor: bool = False) -> dict[str, Any]:
        base_sha = self.resolve_commit(base)
        head_sha = self.resolve_commit(head)
        is_ancestor = self.is_ancestor(base_sha, head_sha)
        if require_ancestor and not is_ancestor:
            raise InspectionError("Base commit is not an ancestor of head commit")
        files = self.changes(base_sha, head_sha)
        counts: dict[str, int] = {}
        for change in files:
            k = change.status[0]
            counts[k] = counts.get(k, 0) + 1
        count = int(self._git("rev-list", "--count", f"{base_sha}..{head_sha}").strip())
        return {
            "schema_version": 1,
            "base_sha": base_sha,
            "head_sha": head_sha,
            "base_is_ancestor": is_ancestor,
            "commit_count": count,
            "changes_by_type": dict(sorted(counts.items())),
            "changed_files": [asdict(c) for c in files],
            "recent_commits": self.commit_subjects(base_sha, head_sha),
            "head_repository_signals": self.file_signals(head_sha),
            "limitations": [
                "File presence is not evidence of correctness, security or maintainability.",
                "Commit count describes Git history, not engineering impact.",
                "No remote content is fetched and no code is executed.",
            ],
        }

    def snapshot(
        self,
        ref: str,
        *,
        max_blob_bytes: int = 8_000_000,
        max_total_bytes: int = 128_000_000,
        max_files: int = 20_000,
    ) -> dict[str, Any]:
        sha = self.resolve_commit(ref)
        entries = self.tree(sha)
        if len(entries) > max_files:
            raise InspectionError("Snapshot exceeds file-count limit")
        total = 0
        files: list[SnapshotFile] = []
        warnings: list[str] = []
        for mode, typ, oid, path in entries:
            if typ == "commit":
                warnings.append(f"Submodule content is not inspected: {path}")
                files.append(SnapshotFile(path, mode, oid, None, None))
                continue
            if typ != "blob":
                warnings.append(f"Unsupported tree entry: {path}")
                continue
            byte_size = int(self._git("cat-file", "-s", oid).strip())
            if byte_size > max_blob_bytes or total + byte_size > max_total_bytes:
                raise InspectionError(f"Snapshot exceeds configured byte limit at: {path}")
            total += byte_size
            payload = self.blob(oid)
            if len(payload) != byte_size:
                raise InspectionError("Blob length mismatch")
            if payload.startswith(b"version https://git-lfs.github.com/spec/v1\n"):
                warnings.append(f"Git LFS pointer, not downloaded file content: {path}")
            if mode == "120000":
                warnings.append(f"Symbolic link target hashed as bytes, not followed: {path}")
            files.append(
                SnapshotFile(path, mode, oid, byte_size, hashlib.sha256(payload).hexdigest())
            )
        return {
            "schema_version": 1,
            "commit_sha": sha,
            "files": [asdict(f) for f in files],
            "file_count": len(files),
            "total_blob_bytes": total,
            "warnings": warnings,
            "algorithm": "SHA-256 over raw Git blob bytes; git_oid uses the repository's Git object format",
        }


def to_markdown(report: dict[str, Any]) -> str:
    """Render a human-readable inspection summary. Escape Markdown table cells."""

    def cell(value: object) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")

    out = [
        "# Git Milestone Inspection",
        "",
        f"- Base: `{report['base_sha']}`",
        f"- Head: `{report['head_sha']}`",
        f"- Commits in range: {report['commit_count']}",
        f"- Base is ancestor: {str(report['base_is_ancestor']).lower()}",
        "",
        "## Changed files",
        "",
        "| Status | Path | Previous path |",
        "| --- | --- | --- |",
    ]
    for f in report["changed_files"]:
        out.append(f"| {cell(f['status'])} | {cell(f['path'])} | {cell(f.get('old_path') or '')} |")
    out.extend(["", "## Repository signals at head", ""])
    for name, present in report["head_repository_signals"].items():
        out.append(f"- {name}: {'present' if present else 'not detected'}")
    out.extend(["", "## Interpretation limits", ""])
    out.extend(f"- {note}" for note in report["limitations"])
    return "\n".join(out) + "\n"


def to_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
