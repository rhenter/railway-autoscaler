# Reviewer handoff

## Project description

railway-autoscaler is an independent Python 3.14 starting repository for a real
horizontal autoscaling problem on Railway. The baseline includes a deterministic
local policy simulator, typed metric/API interfaces, pytest coverage, a uv project
and lockfile, synthetic examples, and dated API capability evidence. The actual
network adapters and operational reconciliation controller remain deliberately
unimplemented for the Taiga Code Behaviors task.

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

`actual.json` is a disposable verification file. Checks require no Railway account
or credentials. Dependency installation may download Python and packages; tests
and simulation themselves run offline. The optional schema check is documented
separately and intentionally uses the network.

## Baseline versus pending work

| Included and working | Left for the evaluation |
| --- | --- |
| Single-sample thresholds, hysteresis, replica bounds | Sustained CPU/memory windows and metric normalization |
| In-memory cooldown and deterministic replay | Durable state, distributed lease and restart recovery |
| MetricsProvider and RailwayAPI Protocols | Railway metrics/configuration/mutation adapters |
| Offline CLI and example results | Dry-run/apply reconciliation command |
| Baseline tests and live schema excerpt | Failure, concurrency and integration tests |

The pending task and acceptance criteria are in
[IMPLEMENTATION_TASK.md](IMPLEMENTATION_TASK.md). They describe product engineering
work, not agent configuration. No agent instructions, skills, or agent workflows
are included in this repository.

## Packaging boundary

The delivered ZIP contains source, documentation, examples, tests, license and
lockfile. It excludes `.git`, virtual environments, installed dependencies, caches,
credentials, private application code and editor files. The lockfile records
public package resolution metadata; it does not contain vendored dependencies.

An MIT license allows public reuse. No Taiga platform policy or evaluation outcome
is asserted: the referenced conversation did not expose the attached assessment
images. Follow the assessment's own submission requirements in its interface.
