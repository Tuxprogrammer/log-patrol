# Log Patrol

Log Patrol watches Loki, spots likely incidents, and keeps a single GitLab issue
per recurring problem instead of flooding your queue.

## Features

- Scans recent Loki logs on a repeating patrol loop
- Catches explicit error-level events fast with deterministic rules
- Mines message templates with Drain3 to surface rare, suspicious patterns
- Runs an Ollama-backed LLM sentiment gate before opening or updating issues
- Deduplicates findings by fingerprint across patrol runs
- Persists patrol state in SQLite
- Closes stale patrol issues automatically

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config-example.yml config.yml
export GITLAB_TOKEN="your-token"
docker compose up -d --build
```

Run a one-off patrol:

```bash
docker compose run --rm log-patrol python -m src.main
```

## Configuration

Start from `config-example.yml` and set:

- `loki.url` plus one or more `loki.queries`
- `gitlab.url`, `gitlab.group`, `gitlab.project`, and `gitlab.patrol_label`
- `llm.base_url` and `llm.model` for the Ollama sentiment gate
- `state.db_path` for persisted SQLite state
- `exclude_patterns` for noisy log lines you want dropped early

## Verification

Local checks:

```bash
pydocstyle --convention=google src tests smoke_test.py
pylint src tests smoke_test.py
mypy --config-file mypy.ini
pytest -q
```

Live smoke test:

```bash
python smoke_test.py
```

## More Details

See `INSTALLING.md` for deployment, configuration, runtime behavior,
operations, and CI details.
