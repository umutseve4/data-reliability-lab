# Contributing

1. Create a focused branch from `main`.
2. Keep runtime dependencies at zero unless an ADR justifies the addition.
3. Run `ruff check .`, `ruff format --check .` and `python -m unittest discover -s tests -v`.
4. Add a regression test for every behavior change.
5. Describe the failure mode, evidence and known limitation in the pull request.

A change is not verified until the GitHub Actions checks pass on the pull request.
