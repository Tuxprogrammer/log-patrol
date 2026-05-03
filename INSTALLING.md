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
| `exclude_patterns` | Optional regex patterns to drop noisy logs before template mining |

All other values have sensible defaults. See `README.md` → *Configuration reference*
for a full field list.

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

---

## 8. Confirm the patrol loop cadence

Log Patrol no longer relies on `crond`. The container entrypoint runs one patrol
immediately, then sleeps for 4 hours between runs inside `/app/run.sh`.
Confirm the container is still running and inspect the patrol logs:

```bash
docker compose ps log-patrol
docker compose logs --tail=50 log-patrol
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
