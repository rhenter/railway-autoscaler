# railway-autoscaler

Open source starting point for a **Django** Railway horizontal autoscaler using
**Celery workers, Celery Beat, and database-backed status/history**.

This Python 3.14 release provides the reusable Django app, encrypted Railway
credentials, autoscaling targets and policies, database-backed status/history,
the Railway resource client, and a Celery reconciliation task. The task defaults
to dry-run. See [CELERY.md](docs/CELERY.md) for host-project wiring.

## Configuration

The future Django app will expose its policy through `settings.py`, backed by
environment variables. Replica bounds already load with the helper below:

```python
from railway_autoscaler.offline.config import load_policy

RAILWAY_AUTOSCALER_POLICY = load_policy()
```

| Environment variable | Default | Meaning |
| --- | --- | --- |
| `RAILWAY_AUTOSCALER_MIN_REPLICAS` | `1` | Minimum allowed service replicas |
| `RAILWAY_AUTOSCALER_MAX_REPLICAS` | `1` | Maximum allowed service replicas |

Both values must be positive integers, with minimum no greater than maximum.
With the defaults, the policy remains at one replica. Raise the maximum explicitly
to permit scale-up. These are Railway service instances, not Celery concurrency
or web worker counts. Invalid configuration fails instead of guessing a limit.

[.env.example](.env.example) has no credentials. The helper reads the process
environment; it does not automatically load `.env` files. A Django project can
use its existing environment loader before calling it. The future Celery worker
must receive the same active limits. Environment settings remain authoritative;
stored state must never silently replace them.

## Planned runtime

```text
Django settings + environment limits
                 |
one Celery Beat scheduler -> broker -> Celery worker task
                                            |
                                    Django database: status, history, ownership
                                            |
                                      Railway API
```

Beat schedules a bounded reconciliation task; a worker performs the evaluation.
The broker may be RabbitMQ or Redis. The host Django database is the source of
truth for autoscaling state and history; the Celery result backend is separate.
The controller does not run in HTTP workers or start from Django application
initialization.

The Django models record observed/desired counts, pending operations, cooldown,
sample counters, leases and scaling events. Reconciliation uses PostgreSQL
transactions and explicit ownership to handle overlapping tasks and redelivery.
Exactly one Beat scheduler owns this schedule. Redis is optional as a broker/cache,
not a second authoritative state store. A Celery result backend does not replace
these models.

Persisted status enables a future read-only dashboard showing capacity, decisions,
metrics and event history. Start with periodic refresh and display collection
timestamps so data freshness is clear. See [DASHBOARD_TASK.md](docs/DASHBOARD_TASK.md).

The [Django settings example](examples/django_settings.py) includes the Beat entry
and the safe dry-run defaults. The default offline simulator still requires no
Railway account, broker or credentials; Django and Celery are needed only for the
integrated task.

## Run the scaffold locally

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```sh
uv python install 3.14
uv sync --locked --group dev
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked railway-autoscaler simulate examples/scenario.json
```

`uv.lock` records development dependencies. Current runtime uses only the Python
standard library. Simulation and tests require no Railway, Django, Celery, Redis,
credentials or network access. Initial dependency installation downloads packages.

## Simulator behavior

Samples contain synthetic `utilization` between 0 and 1 and `at_seconds` measured
from a simulated time origin. This is **not raw Railway CPU usage**.

- At or above the upper threshold: add one replica, respecting the maximum.
- At or below the lower threshold: remove one replica, respecting the minimum.
- Between thresholds: hold the current count (hysteresis).
- During cooldown or with a missing metric (`null`): hold the count.
- The first sample may change capacity immediately. Only changes reset cooldown.
- Sample times must strictly increase; counts outside policy bounds are rejected.

The CLI uses the explicit policy in the JSON scenario, independently of the host
environment. Its example sets maximum to three to demonstrate scaling. This does
not change the default maximum of one in `Policy()` and `load_policy()`.
Ten samples produce counts `2, 2, 3, 3, 3, 3, 2, 2, 1, 1`; the complete
[expected output](examples/expected-output.json) is checked in.

Replay assumes successful, instantaneous in-memory changes. Sustained-load windows,
freshness checks, database persistence, task execution, concurrency and real Railway
operations are not implemented. No production readiness or load capacity is claimed.

## Structure

```text
railway_autoscaler/
  autoscaling/   # provider contracts and reconciliation service
  core/           # pure policy types, decisions and simulation
  offline/        # simulator CLI and environment configuration
  models.py       # Django models for the autoscaler application
  client/          # Railway and broker clients
  services.py      # encrypted credential service
examples/         # synthetic replay and planned Django/Beat settings
tests/           # configuration, policy, replay and CLI validation
docs/            # API evidence, pending implementation task and reviewer guide
```

## Railway API evidence and evaluation

Read-only introspection on 2026-10-27 confirmed metric/configuration operations
and replica-related inputs. [RAILWAY_API.md](docs/RAILWAY_API.md) records the
schema excerpt and remaining uncertainties. No authenticated resource query or
mutation was executed. The task must recheck the API before implementing writes.

Use this repository as the starting state for the task, not as a finished
integration. [REVIEWER.md](docs/REVIEWER.md) contains verification commands and
scope. No private application code, identifiers or infrastructure are required.

MIT licensed. Not affiliated with Railway or Taiga.
