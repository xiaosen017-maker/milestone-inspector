"""Command line entry point for milestone-inspector."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from milestone_inspector.core import GitRepository, InspectionError, to_json, to_markdown


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Reproducible, offline Git milestone inspection")
    commands = p.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="Compare two commit snapshots")
    inspect.add_argument("--repo", default=".", help="Local Git working tree")
    inspect.add_argument("--base", required=True, help="Base Git ref (tag, branch or SHA)")
    inspect.add_argument("--head", required=True, help="Head Git ref (tag, branch or SHA)")
    inspect.add_argument("--require-ancestor", action="store_true", help="Fail if history diverges")
    inspect.add_argument("--json", dest="json_file", help="Write JSON to file instead of stdout")
    inspect.add_argument("--markdown", help="Also write a Markdown summary")
    snapshot = commands.add_parser("snapshot", help="Hash file blobs for a fixed snapshot")
    snapshot.add_argument("--repo", default=".")
    snapshot.add_argument("--ref", required=True)
    snapshot.add_argument("--json", dest="json_file")
    snapshot.add_argument("--max-blob-bytes", type=int, default=8_000_000)
    snapshot.add_argument("--max-total-bytes", type=int, default=128_000_000)
    snapshot.add_argument("--max-files", type=int, default=20_000)
    return p


def _write(path: str | None, content: str) -> None:
    if path is None:
        print(content, end="")
        return
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        repo = GitRepository(args.repo)
        if args.command == "inspect":
            report = repo.inspect(args.base, args.head, require_ancestor=args.require_ancestor)
            _write(args.json_file, to_json(report))
            if args.markdown:
                _write(args.markdown, to_markdown(report))
        else:
            if args.max_blob_bytes <= 0 or args.max_total_bytes <= 0 or args.max_files <= 0:
                raise InspectionError("Blob, snapshot byte and file-count limits must be positive")
            report = repo.snapshot(
                args.ref,
                max_blob_bytes=args.max_blob_bytes,
                max_total_bytes=args.max_total_bytes,
                max_files=args.max_files,
            )
            _write(args.json_file, to_json(report))
    except (InspectionError, OSError) as exc:
        print(f"milestone-inspector: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
