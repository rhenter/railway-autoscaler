"""Snippet for an existing Django settings module."""

from railway_autoscaler.offline.config import load_policy

RAILWAY_AUTOSCALER_POLICY = load_policy()
RAILWAY_AUTOSCALER_DRY_RUN = True
RAILWAY_AUTOSCALER_API_TIMEOUT = 20
RAILWAY_AUTOSCALER_METRIC_WINDOW_SECONDS = 60
RAILWAY_AUTOSCALER_LEASE_SECONDS = 120
RAILWAY_AUTOSCALER_METRIC_MAX_AGE_SECONDS = 300

CELERY_TASK_ROUTES = {"railway_autoscaler.reconcile": {"queue": "autoscaling"}}

CELERY_BEAT_SCHEDULE = {
    "evaluate-railway-autoscaling": {
        "task": "railway_autoscaler.reconcile",
        "schedule": 60.0,
        "options": {"queue": "autoscaling", "expires": 55},
    }
}
