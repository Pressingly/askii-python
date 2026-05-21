# Contributing

Thanks for taking time to contribute. This client is consumed by production
services, so we keep the bar high.

## Local development

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev,redis]"
pre-commit install
```

## The expected loop

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict src/askii
uv run pytest --cov=askii --cov-fail-under=90 -v
```

All four must pass before opening a PR.

## Style

- Python ≥ 3.10. Use `from __future__ import annotations` when it materially
  improves readability.
- `ruff` rules `E, F, I, UP, B`; line length 120; double quotes.
- Google-style docstrings on public classes and methods.
- Public API additions need: a Pydantic request/response pair, resource method
  (sync + async), unit test coverage, and a `CHANGELOG.md` entry under
  `## [Unreleased]`.

## Tests

- Default suite runs against `httpx.MockTransport` — no network.
- Mark tests that need a live backend with `@pytest.mark.integration`; they're
  skipped in the default run.
- New code must keep total coverage at or above 90%.

## Releases

Tag `vX.Y.Z` on `main` once `CHANGELOG.md`'s `Unreleased` section is moved into
a versioned heading. Hatch-vcs derives `askii.__version__` from the tag.

## Reporting issues

Open an issue at https://github.com/Pressingly/askii-python/issues. For security
reports, follow `SECURITY.md` instead.
