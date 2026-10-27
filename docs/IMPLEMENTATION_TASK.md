# Pending task: implement Django autoscaling with Celery and Celery Beat

Status: **not implemented**. The repository provides configuration loading, an
offline simulator and API research. Django models, tasks and integrations are
intentionally left for the Taiga Code Behaviors implementation.

## Problem

A stateless Django HTTP service needs additional Railway replicas during sustained
load and should return gradually to its baseline afterward. Single spikes,
repeated task delivery, overlapping execution, restarts and ambiguous API responses
must not lead to duplicate or destructive changes. Operators need persisted status
and history that can later power a dashboard.

Implement a reusable Django app. Keep the core policy independent of Django where
practical, but support Django only in this task. Do not build a generic framework
integration system or introduce FastAPI support.

## Deliverable

Implement one bounded reconciliation cycle, invoked by the registered Celery task
`railway_autoscaler.reconcile`, scheduled by **Celery Beat**. Support one explicitly
configured Railway HTTP service/environment/region per invocation. Preserve the
existing offline `simulate` command and keep external access behind adapters.

### Django settings and environment

- Use `RAILWAY_AUTOSCALER_POLICY` in Django settings, backed by `load_policy()`.
  `RAILWAY_AUTOSCALER_MIN_REPLICAS` and `RAILWAY_AUTOSCALER_MAX_REPLICAS` both
  default to `1`. Enforce positive integers and minimum no greater than maximum.
- Configure target identifiers, CPU/memory thresholds, consecutive-sample windows,
  interval, cooldown, freshness and dry-run/apply behavior explicitly through
  Django settings backed by environment variables. Do not put secrets in task args.
- Default to dry-run. Scheduled real mutations require explicit configuration.
  Active environment limits remain authoritative; database values are snapshots
  for audit, not an editable competing configuration source.
- If observed capacity is outside active limits or state unexpectedly disappears,
  pause and report the condition rather than silently forcing capacity to a limit.
- Reuse the host project's database and Celery app. Add Django/Celery runtime
  dependencies with verified Python 3.14 compatibility, packaging and migrations.

### Celery worker and Beat

- Implement a reusable task without importing a private host project. Document task
  registration and Django `INSTALLED_APPS` setup. Ensure the task is discovered.
- Supply a documented `CELERY_BEAT_SCHEDULE` entry for the `autoscaling` queue.
  Exactly one Beat scheduler owns it. Run Beat separately from HTTP and worker
  processes; do not use embedded Beat in each worker or schedule from `AppConfig.ready()`.
- Use bounded task execution and expiry appropriate to the evaluation interval.
  Expiry cannot stop an already running task; overlapping executions and task
  redelivery must be handled by database concurrency controls and idempotency.
- Keep polling, task delivery and Railway mutation retry behavior separate. Do not
  blindly retry the whole task after a possibly accepted mutation.
- Reuse the host's broker, which may be RabbitMQ or Redis. A Celery result backend
  is not the autoscaler's authoritative state store. No Redis dependency is
  required solely to persist autoscaling state.

### Railway adapters and sustained-load policy

- Recheck current Railway API capabilities before implementing integrations.
  Resolve the instance-update versus environment-patch path and verify safe
  scoping, staged/apply semantics and running replica convergence.
- Collect CPU and memory using documented units and normalize against effective
  capacity, accounting for aggregation across replicas. Do not assume percentages.
- Require sustained high CPU OR memory before adding one replica. Require a longer
  sustained period of low CPU AND memory before removing one replica. Respect
  minimum, maximum, cooldown and at most one change per confirmed cycle.
- Missing, stale or invalid metrics block downscaling and reset sample counters.
  Duplicate sample timestamps must not count twice. Make cadence and averaging
  semantics explicit. Optional application metrics can remain future work.
- Preserve unrelated regional settings, reject unsupported layouts, and avoid
  committing unrelated staged changes. Read before write; skip if converged.

### Database status, history and concurrency

- Use Django ORM models and migrations in the host's PostgreSQL database as the
  source of truth. Do not require an additional database service just for the app.
- Store one uniquely identified status row per service/environment/region, with
  observed and desired replicas, effective limit snapshots, CPU/memory values and
  sample time, consecutive-sample counters, last confirmed change, cooldown end,
  pending operation, run ID, last attempt/success, health/error status and version.
- Store append-only scaling events with intent, previous/desired/confirmed counts,
  reason, outcome, timestamps and correlation/run IDs. Include pending and failed
  outcomes so an ambiguous operation can be reconstructed. Record non-changing
  cycles in current status; define retention rather than appending unbounded noise.
- Use atomic transactions and explicit concurrency control for state transitions.
  Acquire ownership before making a decision, persist intent before external I/O,
  and prevent a competing or redelivered task from issuing another scale request.
  Avoid holding a database transaction open across Railway network calls.
- Document ownership expiry, crash recovery and how an expired owner is prevented
  from later overwriting newer state or issuing a stale request. Fail closed when
  ownership is uncertain. A task ID alone does not provide mutual exclusion.
- After a write, confirm remote state before recording a successful change and
  starting cooldown. Persist ambiguous outcomes and reread before another mutation.
  Pending-but-not-converged capacity must not become a new scaling opportunity.
- Keep database access scoped and efficient for a future dashboard. A read-only
  Django admin view of current status and events is sufficient for this task.
  Do not let admin edits bypass the policy or trigger arbitrary scaling.

### Operations and validation

- Add bounded HTTP timeouts, GraphQL error handling, safe read retries with backoff
  and rate-limit awareness. Do not blindly retry mutations. Redact credentials,
  broker URLs and raw response bodies in logs, database errors and admin views.
- Document who owns replica configuration so IaC cannot undo dynamic scaling.
  Cover worker/Beat startup, schedule registration, recovery, rollback, database
  migrations, least-required access, and retention of status/event data.
- Reuse or evolve the existing metric/API Protocols; no need for extra plugin layers.

## Acceptance criteria

- Default minimum and maximum are both one; explicit environment limits are honored
  in worker decisions after configuration reload/restart and remain authoritative.
- Celery Beat publishes the registered task to the intended queue at the documented
  interval, and a Celery worker executes it without an HTTP startup hook.
- Sustained-load windows, replica bounds, cooldown and freshness behave as specified.
- PostgreSQL status and event history survive worker/Beat restarts, including pending
  writes and cooldown. No state depends on process memory or a local file.
- Duplicate samples, overlapping tasks and redelivery cannot advance counters twice
  or produce conflicting writes. Cover crash and ownership expiry behavior.
- Tests cover auth rejection, HTTP 200 with GraphQL errors, 429/Retry-After, transient
  read errors, timeouts, accepted writes with delayed convergence and ambiguous writes.
- Dry-run records an explicitly labeled preview without mutating Railway or advancing
  apply-mode counters, cooldown or pending operations. It must not interfere with
  an active apply-mode run.
- Unsupported layouts, configuration drift and storage/ownership failures fail closed
  with actionable messages. Tokens and other credentials never reach persisted output.
- Read-only admin status/history are permission-protected; stored timestamps make
  data freshness visible. Dashboard implementation remains a separate follow-up.
- Tests require no real Railway account. Use adapter fakes, PostgreSQL for transaction/
  concurrency tests, and an isolated worker/Beat/broker smoke test for task wiring.
  Eager task execution alone does not prove scheduler or broker integration.
- Existing simulation and configuration tests pass; documentation explains exactly
  which offline, database, broker and live checks were performed.

## Validation boundary

Offline tests do not establish actual Railway scaling. If an isolated test service
is available, provide an opt-in smoke test: record original replicas, apply a bounded
change, confirm convergence and restore the original count. Exclude it from default
tests. Do not use a production service. Report live access limitations explicitly.

## Out of scope

FastAPI integration, live dashboard UI, WebSockets, queue-based autoscaling,
Celery worker autoscaling, database provisioning, multi-region scaling, plan/resource
limit changes, production deployment and load-capacity guarantees. Celery and Beat
are the required execution model; an additional scheduler or daemon is unnecessary.

## Suggested evaluation prompt

> Implement docs/IMPLEMENTATION_TASK.md as a reusable Django app using Celery and
> Celery Beat, with PostgreSQL status/history and environment replica limits that
> both default to one. Inspect the scaffold and recheck Railway API capabilities
> first. Preserve the offline simulator, implement safe reconciliation, and run
> reproducible tests. Keep the dashboard as the follow-up in docs/DASHBOARD_TASK.md.
> Do not access private applications or production services.
