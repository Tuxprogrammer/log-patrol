# Changelog

All notable changes to this project are documented here by change date.

## 2026-05-02

### Added
- Initial log-patrol service implementation with Loki polling, GitLab issue management, SQLite state tracking, smoke tests, and Docker runtime assets.
- Per-fingerprint issue targeting, structured issue titles, rendered sample log blocks, and metadata sections in patrol-created issues.
- LLM gating for classified errors after deterministic filtering.
- Template-first classification using Drain3 clustering with rarity and anomaly scoring for ambiguous logs.
- Project governance and onboarding docs including `LICENSE`, `CONTRIBUTING.md`, `CHANGELOG.md`, `README.md`, and `INSTALLING.md`.

### Changed
- Reworked classification from batch LLM processing to a deterministic-first pipeline with single-item LLM gate calls only where needed.
- Switched GitLab issue creation to the project issues API and added the `gitlab.project` configuration path required for reliable issue creation.
- Raised the default runtime log level to INFO and expanded patrol runtime summaries around classification and template mining.
- Updated the patrol schedule to run every 4 hours and run directly in the service loop instead of relying on `crond`.
- Hardened CI to run `pydocstyle` with the Google convention, `pylint`, and strict `mypy` in a dedicated lint stage before a pytest-only test stage, and publish pytest JUnit plus Cobertura coverage artifacts to GitLab before image builds.
- Aligned the container runtime with Python 3.12 so the image matches local tooling and CI.
- Aligned docs with the actual deployment model, including the distinction between local development and the parent `prometheus-stack` production deployment.

### Fixed
- Hardened Loki query pagination and patrol loop behavior.
- Corrected the Ollama hostname used by the service.
- Repaired batch prompt assembly and output parsing during the transition away from batch classification.
- Stripped ANSI escape bytes from issue text before persistence and issue updates.
- Excluded log-patrol's own logs from patrol queries to prevent a feedback loop.
- Avoided a string-formatting failure in the main workflow caused by a backslash in an f-string expression.
- Suppressed noisy Drain3 template miner output.
- Reduced classifier progress log spam so long patrol runs now emit coarse milestone progress instead of one line per analyzed entry.
