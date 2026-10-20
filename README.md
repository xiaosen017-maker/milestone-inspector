# Milestone Inspector

**Reproducible Git snapshots and milestone evidence, entirely offline.**

[![CI](https://github.com/xiaosen017-maker/milestone-inspector/actions/workflows/ci.yml/badge.svg)](https://github.com/xiaosen017-maker/milestone-inspector/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

Milestone Inspector turns a **pair of existing Git revisions** into an inspectable JSON/Markdown change report, or builds an integrity manifest for every tracked file at an **immutable commit**. It helps maintainers document what changed during a milestone without making unsupported claims about the repository's software quality.

> **Status:** v0.1.0, initial release candidate. No affiliation with GitHub or any code-collection/qualification platform. Locally verified tests are described below; CI badge will reflect GitHub Actions only after the repository is published.

## Why this exists

`main` changes over time; a Git SHA identifies a stable snapshot. Reviews should link to precise revisions, show changed paths, and distinguish evidence from subjective quality judgments. Milestone Inspector provides a small, auditable implementation of those primitives.

## Features

- Resolve tags, branches and abbreviated commit refs to full **commit SHA** values.
- Compare Git histories with filename-safe, NUL-delimited parsing (including renames).
- Inspect whether a milestone's base commit belongs to head's ancestry.
- Summarize change types, short commit subjects and repository health-file **presence**.
- Build SHA-256 manifests of tracked Git blob bytes; ignore uncommitted local edits.
- Make symlinks, submodules and Git LFS pointers explicit in warnings.
- Work offline, without network access or GitHub tokens; no third-party runtime dependencies.
- Emit machine-readable JSON and human-readable Markdown.

## Quickstart

**Requirements:** Python 3.10+ and Git.

```bash
python -m pip install -e .
# Inspect any existing local Git repository:
milestone-inspector inspect --repo /path/to/repo --base v1.0.0 --head v1.1.0 \
  --require-ancestor --json milestone.json --markdown milestone.md
# A reproducible file hash manifest for a chosen commit:
milestone-inspector snapshot --repo /path/to/repo --ref HEAD --json snapshot.json
# Optional resource ceilings can be tightened for automation:
milestone-inspector snapshot --repo /path/to/repo --ref HEAD --max-files 5000 \
  --max-blob-bytes 2000000 --max-total-bytes 32000000
```

You can also use `python -m milestone_inspector.cli inspect ...` without installing a console-script entrypoint, provided the package is installed (or `PYTHONPATH=src`).

**Important:** use a full `commit_sha` copied from the report for an external evidence record; passing `HEAD` or branch names creates a snapshot of the ref *at inspection time*, not a permanently fixed reference.

## Example output

```json
{
  "base_sha": "<resolved 40-character commit>",
  "head_sha": "<resolved 40-character commit>",
  "base_is_ancestor": true,
  "commit_count": 3,
  "changes_by_type": {"A": 2, "M": 1}
}
```

Illustrative shape only; actual reports include changed file records, commit subjects, snapshot signals and limitations. No example here claims to derive from an external live project.

## Documentation

- [Architecture and trust boundaries](docs/architecture.md)
- [JSON schema and interpretation](docs/report-format.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Changelog](CHANGELOG.md)

## Development

```bash
python -m pip install -e '.[dev]'  # or: pip install pytest ruff
python -m pytest -q
python -m ruff check src tests
python -m ruff format --check src tests
```

The tests create temporary, **synthetic Git histories solely as test fixtures**; they do not purport to be records of real development. No dataset is bundled and no proprietary task material is included.

## Limitations

- Git's recorded file content is hashed; Git LFS large objects are not downloaded. Submodule commits are recorded but external trees are not traversed.
- A repository containing untrusted Git objects is processed via a local Git executable; run in a trusted environment or isolated container when evaluating adversarial repositories.
- Health-file detection checks filenames, not substance; the tool is **not** a code quality, licensing, correctness or security certification.
- Histories with merges are counted with `git rev-list base..head`; the report is not a semantic changelog.
- To keep resource use bounded, snapshots have configurable file size, total size and file-count ceilings.

## Development provenance

This initial project implementation and documentation were prepared **with AI assistance** at the repository owner's request, and were locally exercised with a test suite. Before representing this work as personal engineering experience, the owner should review the code, reproduce the checks and make meaningful contributions. No history of production use, independent third-party review or external adoption is claimed.

## License

MIT License; see [LICENSE](LICENSE). This project does not bundle external repository source code.
