# railway-autoscaler

Python 3.14 scaffold for an independent, public Railway horizontal autoscaler.
The current release is **an offline policy simulator**, with no Railway client,
credentials, background jobs, or changes to remote services.

The practical goal is to scale stateless HTTP services gradually during traffic
peaks. The initial implementation deliberately leaves a meaningful engineering
task open for Taiga Code Behaviors: build and test the actual reconciler and
Railway adapters. See [the pending task](docs/IMPLEMENTATION_TASK.md).

## Run locally

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run from
this directory:

```sh
uv python install 3.14
uv sync --locked --group dev
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked railway-autoscaler simulate examples/scenario.json
```

`uv.lock` records development dependencies. Runtime uses only the Python standard
library. No account, environment variables, or network access is needed by the
simulator or tests. Initial dependency installation requires package downloads.

## Current behavior

A sample contains synthetic `utilization` between 0 and 1 and `at_seconds` measured
from a simulated time origin. This value is **not raw Railway CPU usage**.

- At or above the upper threshold: request one additional replica, up to the maximum.
- At or below the lower threshold: request one fewer replica, down to the minimum.
- Between thresholds: hold the current count (hysteresis).
- During cooldown or with a missing metric (`null`): hold the current count.
- The first sample may change capacity immediately. Cooldown starts at a change.
- Reaching a bound or holding capacity does not reset cooldown.
- Sample times must strictly increase; counts outside policy bounds are rejected.

The simulator assumes every change succeeds instantly in memory. It has no
sustained-load window, fresh-data checks, deployment lifecycle, persistent state,
retry handling, concurrency control, or production readiness claim. Ten example
samples produce replica counts `2, 2, 3, 3, 3, 3, 2, 2, 1, 1`.
The complete expected output is [checked in](examples/expected-output.json).

## Structure

```text
src/railway_autoscaler/
  models.py       # policy, samples and decisions
  policy.py       # pure single-sample decision function
  simulation.py   # deterministic in-memory replay
  cli.py          # simulate command only
  ports.py        # MetricsProvider and RailwayAPI Protocol interfaces
examples/         # synthetic input and expected output; no identifiers or tokens
tests/           # policy boundaries, cooldown, replay and CLI validation
docs/            # API evidence, pending implementation task and reviewer guide
```

## Railway API research

On 2026-10-27, read-only introspection against Railway's public GraphQL endpoint
confirmed `metrics`, `serviceInstance`, and `serviceInstanceUpdate`, including
replica-related inputs. The snapshot and reproducible query are in
[RAILWAY_API.md](docs/RAILWAY_API.md). No authenticated resource query or mutation
was executed, so permissions, units, regional behavior, and actual convergence
remain integration work.

## Evaluation handoff

Use this repository as the **starting state**, not a completed autoscaler.
[IMPLEMENTATION_TASK.md](docs/IMPLEMENTATION_TASK.md) describes the work still to
be performed in Taiga, with acceptance criteria and explicit exclusions.
[REVIEWER.md](docs/REVIEWER.md) contains verification commands and delivery scope.
The project has no dependency on any private SaaS source, IDs, or infrastructure.

MIT licensed. Not affiliated with Railway or Taiga.
