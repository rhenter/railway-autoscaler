"""Snippet for an existing Django settings module.

Policy loading works today. The Celery task below is planned, NOT implemented.
Do not enable this Beat entry until the pending controller and task exist.
Merge the entry into the host project's existing CELERY_BEAT_SCHEDULE.
"""

from railway_autoscaler.config import load_policy

RAILWAY_AUTOSCALER_POLICY = load_policy()

# Planned configuration for a Celery app configured with namespace="CELERY".
CELERY_BEAT_SCHEDULE = {
    "evaluate-railway-autoscaling": {
        "task": "railway_autoscaler.reconcile",
        "schedule": 60.0,
        "options": {"queue": "autoscaling", "expires": 55},
    }
}
