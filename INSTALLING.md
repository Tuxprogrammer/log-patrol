# Installing Log Patrol

This guide covers a fresh deployment of Log Patrol into the
`<stack-root>` parent stack. Follow the steps in order.

---

## Prerequisites

Before starting, confirm the following are available on your target host:

- Docker Engine with Compose plugin (`docker compose version`)
- A GitLab personal access token with `api` scope for the target group
- A running Loki instance reachable from Docker (example: `http://loki:3100`)
- Python 3.12+ for local lint and test runs (optional but recommended)

---

## 1. Clone the parent repository

```bash
git clone git@example.com:example/prometheus-stack.git <stack-root>
cd <stack-root>
```

If the repo is already present, pull the latest and update submodules:

```bash
git pull
git submodule update --init --recursive
```

---

## 2. Configure the GitLab token

Log Patrol reads `GITLAB_TOKEN` from the environment. Add it to the parent stack
environment file:

```bash
# <stack-root>/.env
echo "GITLAB_TOKEN=<your-token>" >> .env
```

Alternatively export it in your shell before running `docker compose`.

---

## 3. Review `log-patrol/config.yml`

Open `log-patrol/config.yml` and verify:

| Key | What to set |
|-----|-------------|
| `loki.url` | Base URL of your Loki instance |
| `loki.queries` | LogQL selectors for the log streams you want to patrol |
| `gitlab.url` | Your GitLab base URL |
| `gitlab.group` | GitLab group path where patrol issues should be created |
| `gitlab.project` | Project path where patrol issues are created (e.g. `example-group/example-project`) |
| `gitlab.patrol_label` | Label name applied to all patrol issues |
| `llm.base_url` | Base URL for the Ollama API used by the final sentiment gate |
| `llm.model` | Ollama model name used for the final yes/no actionability check |
| `exclude_patterns` | Optional regex patterns to drop noisy logs before template mining |

All other values have sensible defaults. See the *Configuration Reference*
section below for the full field list.

### Runtime classification flow

Each patrol run:

1. Fetches logs from Loki for the configured lookback window
2. Drops any lines matching `exclude_patterns`
3. Applies deterministic classification, including explicit error-level signals
4. Mines templates with Drain3 to keep rare, error-like unknown-level messages
5. Runs the final Ollama-backed LLM sentiment gate on the classified candidates
6. Groups remaining entries by fingerprint and creates or updates GitLab issues
7. Closes stale patrol issues based on `gitlab.stale_days`

If the LLM call times out or the Ollama endpoint is unavailable, Log Patrol
defaults that candidate to not actionable and leaves it out of issue updates.

`llm.skip_llm_if_level_error` is still present in the config schema for
compatibility, but the current runtime always applies the final LLM gate.

---

## 4. Create the data directory

Log Patrol persists its SQLite state database on the host. Create the data
directory before first start:

```bash
mkdir -p <stack-root>/log-patrol/data
```

---

## 5. Build or pull the Log Patrol image

The GitLab CI pipeline publishes the image automatically on every push to `main`.
The pipeline now runs a separate `lint` stage (`pydocstyle`, `pylint`, `mypy`),
then a `test` stage (`pytest` with JUnit and Cobertura artifacts), before the
container build stage.
Pull the latest published image:

```bash
docker compose pull log-patrol
```

To build locally from source instead:

```bash
cd <stack-root>/log-patrol
docker build -t registry.example.com/example/log-patrol:latest .
```

---

## 6. Start the full stack

```bash
cd <stack-root>
docker compose up -d
```

Confirm `log-patrol` is running:

```bash
docker compose ps log-patrol
```

---

## 7. Trigger a manual patrol run

Verify end-to-end connectivity by running a single patrol cycle:

```bash
docker compose exec log-patrol python -m src.main
```

Check the output for Loki query success, template mining/anomaly detection
summary lines, and GitLab issue creation/update events.

To run locally from the repository checkout instead:

```bash
cd <repo-root>
docker compose run --rm log-patrol python -m src.main
```

---

## 8. Confirm the patrol loop cadence

Log Patrol no longer relies on `crond`. The container entrypoint runs one patrol
immediately, then sleeps for 4 hours between runs inside `/app/run.sh`.
Confirm the container is still running and inspect the patrol logs:

```bash
docker compose ps log-patrol
docker compose logs --tail=50 log-patrol
```

For a local checkout:

```bash
cd <repo-root>
docker compose logs -f log-patrol
```

---

## Optional Tuning

### Lookback window (`loki.lookback_minutes`)

Set this as low as possible while still catching target failures. Lower windows
reduce repeated noise and issue churn.

### Exclusion filters (`exclude_patterns`)

Add high-volume known-noise patterns (firewall pass logs, benign debug spam,
etc.) so they are dropped before template mining.

### Query scope (`loki.queries`)

Use focused selectors per service or namespace instead of broad catch-all
queries when possible; this improves template quality and anomaly precision.

---

## Operations

### Reset persisted state

If you want Log Patrol to reseed issue state from scratch, delete the SQLite
database before restarting the service.

Production reset:

```bash
cd <stack-root>
rm -f log-patrol/data/state.db
docker compose up -d log-patrol
```

Local reset:

```bash
cd <repo-root>
rm -f data/state.db
docker compose up -d log-patrol
```

### Smoke test

Run the live connectivity probe from the repository checkout:

```bash
cd <repo-root>
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python smoke_test.py
```

`smoke_test.py` validates the configured Loki, Ollama, and GitLab endpoints.

---

## Configuration Reference

Configuration file: `config.yml`

- `loki.url`: Loki base URL
- `loki.lookback_minutes`: Query window for each patrol
- `loki.queries`: LogQL selectors queried each run
- `gitlab.url`: GitLab base URL
- `gitlab.token`: API token (supports env interpolation)
- `gitlab.group`: Group path for issue discovery
- `gitlab.project`: Project path where Log Patrol creates or updates issues
- `gitlab.patrol_label`: Label applied to patrol issues
- `gitlab.stale_days`: Close inactive patrol issues after this many days
- `llm.base_url`: Ollama base URL for the final sentiment gate
- `llm.model`: Ollama model name
- `llm.timeout_seconds`: HTTP timeout for Ollama classification calls
- `llm.context_window`: Context window passed to Ollama
- `llm.max_log_chars`: Maximum cleaned log length sent to the LLM
- `llm.temperature`: Reserved config value; current runtime sends a deterministic prompt
- `llm.skip_llm_if_level_error`: Compatibility config key; current runtime still applies the LLM gate
- `state.db_path`: SQLite file path
- `exclude_patterns`: Optional list of regex patterns dropped before template mining

## CI/CD

`.gitlab-ci.yml` currently runs:

- `pydocstyle --convention=google src tests smoke_test.py`
- `pylint src tests smoke_test.py`
- `mypy --config-file mypy.ini`
- `pytest -q --junitxml=reports/junit.xml --cov=src --cov-report=term-missing:skip-covered --cov-report=xml:coverage/cobertura.xml`
- image build and push for the configured registry target
