# Contributing to brick-bacnet-mcp

Thanks for considering a contribution. This document covers the conventions for issues, pull requests, and the v0.1 scope boundary.

## Scope boundary (v0.1)

The v0.1 surface is intentionally narrow: read-only BACnet/IP, Brick + Haystack semantic tagging, MCP server output. The following are explicitly out of v0.1:

- WriteProperty / write paths of any kind
- BACnet/SC (Secure Connect)
- COV subscription (use polling)
- 223P full schema parity
- Niagara station read (Fox protocol)
- FDD / analytics logic
- Web UI / dashboard
- Multi-site federation
- Authentication / authorization layer

If you have a PR for any of the above, open an issue first to discuss whether and how it fits the project's roadmap. We would rather have the conversation early than ask you to rework a large PR.

## Welcome PR shapes

- Additions to the default rule library (`src/brick_bacnet_mcp/rules/`) with test fixtures
- Improved documentation, especially worked examples in `examples/`
- Bug fixes with a reproduction case in the test suite
- Performance improvements with before/after measurements
- Test coverage improvements
- Support for additional BACnet object types within v0.1 scope (Schedule, Calendar, Notification Class, Loop)

## Setup

```bash
git clone https://github.com/[YOUR_HANDLE]/brick-bacnet-mcp
cd brick-bacnet-mcp
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
pytest
```

## Style

- Python 3.11+
- Format with `black`
- Sort imports with `isort`
- Lint with `ruff`
- Type hints on public functions; `mypy` strict for new code
- Run `pre-commit run --all-files` before opening a PR

## Tests

- All PRs must pass `pytest` locally and in CI
- Add tests for new rule patterns in `tests/test_tagger.py`
- Add tests for new modules with module-named test files (e.g., `tests/test_<module>.py`)
- Simulator-based integration tests in `tests/test_integration.py`

## Issues

- Bug reports: include Python version, OS, bacpypes3 version, full error trace, and minimum reproduction steps
- Feature requests: describe the use case before the proposed solution
- Questions: feel free to open a discussion thread instead of an issue if you are not sure whether something is a bug

## Commit messages

Plain English. Imperative mood. Reference the issue number if applicable.

```
Add Brick rule for VAV terminal box discharge temp

Closes #42
```

## License

By contributing, you agree your contributions are licensed under the project's MIT license.
