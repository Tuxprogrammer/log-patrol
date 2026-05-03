# Log Patrol

Log Patrol is a containerized service that runs one patrol immediately on start, then repeats every 4 hours. It scans Loki logs, mines message templates, detects rare error-like patterns, and opens or updates GitLab project issues with deduplication.

## Features

- Loki query over the last N minutes (default 30 minutes in `config.yml`)
- Deterministic pass for explicit error levels
- Template-first classification with Drain3 clustering
- Rare/anomalous template selection for unknown-level logs
- Fingerprint-based deduplication across patrol runs
- SQLite state persistence for patrol counts and issue mapping
- Stale issue cleanup for unresolved inactive items
- Per-fingerprint issue targeting with markdown run sections

## Deployment Modes

This repo is used in two different ways:

1. Local development in this directory with `log-patrol/docker-compose.yml`
2. Production deployment from the top-level stack in `<stack-root>/docker-compose.yml`

Production currently runs this image from the internal registry:

```text
registry.example.com/example/log-patrol:latest
```

The top-level stack mounts:

- `./log-patrol/config.yml` -> `/app/config.yml`
- `./log-patrol/data` -> `/data`

That means the persisted patrol state lives on the host at:

```text
<stack-root>/log-patrol/data/state.db
```

## Prerequisites

- Docker Engine and Docker Compose plugin
- GitLab token with group issue permissions
- Python 3.12 for local lint/test runs

## Local Development Setup

1. Enter the project directory.

```bash
cd /path/to/log-patrol
```

2. Set your token in the shell (or environment file loaded by Compose).

```bash
export GITLAB_TOKEN="your-token"
```

3. Build and start the local development stack.

```bash
docker compose up -d --build
```

4. For local lint, typecheck, and tests:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pydocstyle --convention=google src tests smoke_test.py
pylint src tests smoke_test.py
mypy --config-file mypy.ini
pytest -q
```

## Production Deployment

The production stack is driven from `<stack-root>/docker-compose.yml`, not
from this subdirectory.

Builds are published by GitLab CI on push, then the main stack pulls the new image.

Relevant production service:

- `log-patrol`

Typical production refresh from `<stack-root>`:

```bash
docker compose pull log-patrol
docker compose up -d log-patrol
```

## Manual run

```bash
docker compose run --rm log-patrol python -m src.main
```

To run against the already-running production stack instead:

```bash
cd <stack-root>
docker compose exec log-patrol python -m src.main
```

## Trigger Immediate Patrol

```bash
docker compose run --rm log-patrol python -m src.main
```

## View logs

```bash
docker compose logs -f log-patrol
```

For the production stack:

```bash
cd <stack-root>
docker compose logs -f log-patrol
```

## Smoke test

Run live connectivity checks and a create/close issue probe:

```bash
source .venv/bin/activate
python smoke_test.py
```

`smoke_test.py` validates the configured Loki, Ollama, and GitLab endpoints.
Runtime patrol classification still uses the configured LLM gate after the
deterministic-first classifier.

## Resetting State

If you want log-patrol to reseed issue state from scratch, delete the SQLite
state database before restarting the service.

Production reset:

```bash
cd <stack-root>
rm -f log-patrol/data/state.db
docker compose up -d log-patrol
```

Local reset:

```bash
cd /path/to/log-patrol
rm -f data/state.db
docker compose up -d log-patrol
```

## Configuration reference

Configuration file: `config.yml`

- loki.url: Loki base URL
- loki.lookback_minutes: Query window for each patrol
- loki.queries: LogQL selectors queried each run
- gitlab.url: GitLab base URL
- gitlab.token: API token (supports env interpolation)
- gitlab.group: Group path for issues
- gitlab.project: Project path where log-patrol creates/updates issues
- gitlab.patrol_label: Label applied to all patrol issues
- gitlab.stale_days: Close patrol issues not updated for this many days
- state.db_path: SQLite file path
- exclude_patterns: Optional list of regex patterns dropped before template mining

### Template-Mining Behavior

For entries without explicit `level=error` style labels, the classifier now:

- Mines templates with Drain3 in-memory for the current patrol run.
- Computes per-template counts.
- Keeps only templates that are both:
	- error-like (keyword/HTTP 5xx hints), and
	- rare or low-frequency outliers.

This reduces issue floods from repetitive non-actionable messages while still
capturing novel failures.

## Performance Tuning

Template-first behavior is mostly deterministic. The main tuning controls are:

- `loki.lookback_minutes`: Keep this low to reduce noisy backfill.
- `exclude_patterns`: Add repetitive known-noise patterns early.
- Query scope in `loki.queries`: narrower selectors improve precision.

## CI/CD


`.gitlab-ci.yml` currently runs:

- `pydocstyle --convention=google src tests smoke_test.py`
- `pylint src tests smoke_test.py`
- `mypy --config-file mypy.ini`
- `pytest -q --junitxml=reports/junit.xml --cov=src --cov-report=term-missing:skip-covered --cov-report=xml:coverage/cobertura.xml`
- `buildah` image build and push to your configured registry image (for example `registry.example.com/example/log-patrol`)

GitLab registers the pytest JUnit report from `reports/junit.xml` and the
coverage report from `coverage/cobertura.xml`.

## Patrol issue behavior

- Every created issue includes an embedded fingerprint marker in the description.
- Existing issues get their seen-Nx label replaced with the latest patrol count.
- Stale issues are closed automatically after stale_days.
