# Django integration design

Status: **implemented locally with fakes**, except for PostgreSQL concurrency,
worker/broker smoke testing and isolated-service validation.

## Responsibilities

| Component | Responsibility |
| --- | --- |
| Django settings and environment | Authoritative policy and replica bounds; minimum=1, maximum=1 by default |
| Celery Beat | Publish periodic evaluation tasks; one scheduler owns the schedule |
| Existing message broker | Deliver tasks; RabbitMQ or Redis can be reused |
| Celery workers | Execute bounded, idempotent reconciliation cycles |
| Django PostgreSQL models | Current status, pending operations, ownership, cooldown and scaling events |
| Railway API adapters | Collect service metrics, read configuration, request and confirm replica changes |
| Read-only admin/dashboard | Read persisted status and history, with authentication and permissions |

The target is a stateless HTTP service. Autoscaling Celery workers or Beat itself
is outside the first implementation. Do not launch the control loop from every web
worker or from Django application initialization.

## Configuration

In Django settings, use the working configuration helper:

```python
from railway_autoscaler.offline.config import load_policy

RAILWAY_AUTOSCALER_POLICY = load_policy()
```

`RAILWAY_AUTOSCALER_MIN_REPLICAS` and `RAILWAY_AUTOSCALER_MAX_REPLICAS` are read from
the environment, both defaulting to one. Raising the maximum is explicit. Changing
worker environment configuration requires a worker restart/reload; stored snapshots
do not override active limits. CPU/memory thresholds and task/runtime settings are
configured explicitly by the host. The reconciliation lease defaults to 120 seconds;
metric freshness can be bounded with `RAILWAY_AUTOSCALER_METRIC_MAX_AGE_SECONDS`.

The simulator reads its policy from JSON to keep replay deterministic. Its example
maximum of three is separate from the default configuration.

## Planned task registration and scheduling

[django_settings.py](../examples/django_settings.py) contains the Beat entry.
The reusable app registers the shared task through normal Celery autodiscovery;
the host still owns the Celery application and must include the Django app.

With a host Celery app configured using `namespace="CELERY"`, the schedule belongs
in `CELERY_BEAT_SCHEDULE`. Merge it with the host's existing schedule rather than
replacing unrelated periodic tasks. The `autoscaling` queue must be consumed.
The example interval and expiry are illustrative, not production tuning.

After implementation and host configuration, use separate processes such as:

```sh
celery -A your_project worker --loglevel=INFO --queues=autoscaling
celery -A your_project beat --loglevel=INFO
```

`your_project` is the host Celery app reference, not a module provided by this
repository. Those commands do not work against the current offline scaffold.
Beat schedules; workers execute. Task overlap and redelivery still require
application-level concurrency control. Task expiry does not cancel active work.

## Persistence and future dashboard

Use the host's Django database as the canonical store, with a unique current-status
row and append-only operation events. Persist intent before network access; record
success only after confirmation. Preserve ambiguous outcomes for the next cycle.
Separate short database transactions from Railway network calls, and document crash
recovery and ownership expiry. Database failure must pause mutations.

The current status row persists `lease_owner`, `lease_expires_at` and
`state_version`. A cycle may recover only an expired lease. Before and after a
Railway call it locks and verifies the owner; an expired or replaced owner fails
closed, and conditional lease release prevents an old worker from clearing a new
owner's lease. `pending_replicas` is intent, not confirmation: it remains set
until a later read observes the requested count.

This data can support a read-only Django admin view first, then a dashboard using
small periodic JSON refreshes. Show the sample time and last successful collection.
Dashboard refresh rate is not the metric collection rate. Keep the dashboard as
[its own follow-up task](DASHBOARD_TASK.md), after safe reconciliation works.

## References checked for this design

- [Django application initialization](https://docs.djangoproject.com/en/6.0/ref/applications/):
  initialization also occurs for management commands; keep startup work minimal.
- [Celery periodic tasks](https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html):
  Beat schedules worker tasks; use one scheduler and handle task overlap.
- [Celery with Django](https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html):
  namespaced settings use the `CELERY_` prefix and reusable tasks can be shared.

A database-backed Beat scheduler such as django-celery-beat is optional. It manages
schedules; it does not replace autoscaling status/event models. The first version
can use a static environment-backed schedule without adding a scheduler database UI.
