# Contributing

## Workflow

1. Create a branch from `main`.
2. Keep changes focused and easy to review.
3. Run lint and tests locally before opening a merge request.
4. Open a merge request with context, risk notes, and verification steps.

## Local Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pydocstyle --convention=google src smoke_test.py
pylint src tests smoke_test.py
mypy --config-file mypy.ini
pytest -q
```

If you touch deployment docs or config examples, check them against both:

- `log-patrol/docker-compose.yml` for local development
- `/opt/prometheus-stack/docker-compose.yml` for production deployment

## Code Style

- Follow existing project layout under `src/` and `tests/`.
- Prefer clear, deterministic behavior over hidden magic.
- Add tests for bug fixes and new behavior.
- Use Google-style docstrings for public source modules, classes, and functions.
- Keep the codebase clean under strict mypy (`mypy.ini`).

## Commit Guidelines

- Use concise, descriptive commit subjects.
- Include the reasoning for non-obvious changes in the commit body.

## Reporting Issues

Include:
- Expected behavior
- Observed behavior
- Steps to reproduce
- Relevant logs or stack traces
