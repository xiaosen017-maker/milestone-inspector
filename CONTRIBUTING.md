# Contributing

Thanks for contributing. Open an issue describing the bug or proposed feature, with a reproducible command and the expected behavior. Do not publish credentials or private repository contents.

1. Fork the repository and create a descriptive branch.
2. Install Python 3.10+ and Git: `python -m pip install -e '.[dev]'`.
3. Add regression tests for behavior changes. Use temporary Git fixtures, not someone else's private repository.
4. Run `python -m pytest -q`, `python -m ruff check src tests`, and `python -m ruff format --check src tests`.
5. Open a PR describing the change, known limitations, and the commands you ran.

This is a small project: avoid introducing network dependencies for core commands without a clear justification.
