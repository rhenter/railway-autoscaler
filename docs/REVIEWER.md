# Reviewer handoff

## Project description

railway-autoscaler is an independent, MIT-licensed Python 3.14 starting repository
for a Django autoscaler on Railway. The target design uses Celery workers, a single
Celery Beat scheduler, and the host Django PostgreSQL database for status, ownership
and scaling history. That stored data can later power a read-only status dashboard.

The baseline implements validated environment replica limits (minimum=1 and
maximum=1 by default), a deterministic local policy simulator, metric/API Protocols,
pytest coverage, a uv project/lockfile, credential-free examples and dated API
capability evidence. Django integration, database models, Celery tasks, scheduling
and Railway adapters remain the substantial Taiga Code Behaviors task. The dashboard
is a separate follow-up rather than part of the initial controller implementation.

## Reproduce baseline checks

Extract the archive, enter `railway-autoscaler/`, and run:

```sh
uv python install 3.14
uv sync --locked --group dev
uv run --locked python --version
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked railway-autoscaler simulate examples/scenario.json > actual.json
uv run --locked python -c 'import json,pathlib; assert json.loads(pathlib.Path("actual.json").read_text()) == json.loads(pathlib.Path("examples/expected-output.json").read_text())'
```

`actual.json` is disposable. These checks require no Django server, broker, database,
Railway account or credentials. Dependency installation downloads public packages;
tests and simulation themselves run offline. Optional live schema introspection
uses the network and is documented separately in `RAILWAY_API.md`.

## Verify environment limits

```sh
uv run --locked python -c 'from railway_autoscaler.config import load_policy; p = load_policy({}); assert (p.min_replicas, p.max_replicas) == (1, 1)'
RAILWAY_AUTOSCALER_MIN_REPLICAS=1 RAILWAY_AUTOSCALER_MAX_REPLICAS=4 uv run --locked python -c 'from railway_autoscaler.config import load_policy; print(load_policy())'
```

The helper reads the environment, not `.env` files automatically. The JSON simulator
uses its explicit scenario bounds instead; ambient settings do not alter replay.
The Django example contains a **planned** Beat entry referencing a task that does
not exist yet. Do not enable that schedule before implementing the task.

## Baseline versus pending work

| Included and working | Left for the evaluation |
| --- | --- |
| Environment limits, defaulting to one; Django settings snippet | Installable Django app and integration wiring |
| Single-sample thresholds, hysteresis and bounds | Sustained CPU/memory decisions and normalization |
| In-memory cooldown and deterministic replay | Database status, ownership, history and restart recovery |
| MetricsProvider and RailwayAPI Protocols | Railway adapters and safe reconciliation |
| Planned Beat configuration example | Registered Celery task, Beat schedule and worker smoke tests |
| Offline tests and API evidence | PostgreSQL concurrency, broker and opt-in live tests |

See [IMPLEMENTATION_TASK.md](IMPLEMENTATION_TASK.md) for the main task,
[DJANGO_DESIGN.md](DJANGO_DESIGN.md) for architecture and configuration, and
[DASHBOARD_TASK.md](DASHBOARD_TASK.md) for the later read-only dashboard.

## Packaging boundary

All filenames, descriptions, documentation and tasks are in English. The ZIP
contains source, docs, tests, examples, license and lockfile. It excludes `.git`,
virtual environments, installed dependencies, caches, credentials, private code and
editor files. No AGENTS.md, skills or agent workflows are shipped. The lockfile
contains public dependency metadata, not vendored packages.

No Taiga policy or evaluation outcome is asserted. Follow the assessment's own
submission requirements in its interface.
