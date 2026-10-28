# Celery and Beat

The Django host application owns the Celery application. The autoscaler only
registers the shared task `railway_autoscaler.reconcile`.

```python
# project/celery.py
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")
app = Celery("project")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

Add the application to `INSTALLED_APPS` and merge this schedule into the host
settings. The default is intentionally safe:

```python
RAILWAY_AUTOSCALER_DRY_RUN = True
RAILWAY_AUTOSCALER_API_TIMEOUT = 20
RAILWAY_AUTOSCALER_METRIC_WINDOW_SECONDS = 60
RAILWAY_AUTOSCALER_LEASE_SECONDS = 120
# Optional: reject samples older than this many seconds (and equally far in the future).
RAILWAY_AUTOSCALER_METRIC_MAX_AGE_SECONDS = 300

CELERY_TASK_ROUTES = {
    "railway_autoscaler.reconcile": {"queue": "autoscaling"},
}
CELERY_BEAT_SCHEDULE = {
    "evaluate-railway-autoscaling": {
        "task": "railway_autoscaler.reconcile",
        "schedule": 60.0,
        "options": {"queue": "autoscaling", "expires": 55},
    },
}
```

Se o projeto usa `django-celery-beat`, não é necessário adicionar essa entrada
ao arquivo de settings. Crie uma `PeriodicTask` no admin do Django com:

- **Name:** `evaluate-railway-autoscaling`
- **Task:** `railway_autoscaler.reconcile`
- **Interval:** o intervalo desejado, por exemplo, 60 segundos
- **Enabled:** habilitado somente depois de criar um target

Nesse caso, mantenha apenas um scheduler Beat ativo. A tarefa periódica do
`django-celery-beat` substitui a entrada equivalente em `CELERY_BEAT_SCHEDULE`;
não configure as duas para evitar avaliações duplicadas.

Se o projeto já possui um `CELERY_BEAT_SCHEDULE`, apenas acrescente a entrada
`evaluate-railway-autoscaling` ao dicionário existente. Não substitua as outras
periodic tasks do projeto.

Run exactly one Beat process and at least one worker consuming the queue:

```sh
celery -A project.celery worker -Q autoscaling --loglevel=INFO
celery -A project.celery beat --loglevel=INFO
```

`DRY_RUN` records previews in `ScalingEvent` and does not call Railway. Set it
to `False` only after the target, policy, token and metric reads have been
validated against an isolated service.

## Ownership and crash recovery

Each target has one `AutoscalingStatus` row. A reconciliation cycle acquires its
short-lived database lease with `select_for_update` before reading or deciding.
The lease owner is a generated run ID and its expiration is persisted in
`lease_expires_at`; a cycle with an active owner exits without contacting Railway.

The intent (`pending_replicas`) is committed before a replica mutation and is
checked on every later cycle. A pending change that has not converged remains
paused and cannot create a new decision. If it has converged, the cycle records
confirmation and starts cooldown without issuing another mutation.

If a worker crashes, a later cycle may recover an expired lease. The old worker
must re-check the owner and expiration before every state transition, so it
cannot overwrite the recovered cycle or issue a stale follow-up mutation.
Unexpired leases without an expiration timestamp are treated as uncertain and
fail closed. Network calls happen outside database transactions; database
failures therefore prevent a mutation from being started.
