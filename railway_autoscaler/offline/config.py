"""Environment configuration shared by Django settings and the policy core. No external access."""

import os
from collections.abc import Mapping

from railway_autoscaler.core.policy_types import Policy


def load_policy(environ: Mapping[str, str] | None = None) -> Policy:
    """Read replica bounds from an environment mapping or the process environment.

    Both bounds default to one. Other policy values retain the simulator defaults.
    This function does not load .env files or connect to Redis, Celery, or Railway.
    """
    source = os.environ if environ is None else environ
    counts = {}
    for field in ("min_replicas", "max_replicas"):
        name = f"RAILWAY_AUTOSCALER_{field.upper()}"
        try:
            counts[field] = int(source.get(name, "1"))
        except ValueError:
            raise ValueError(f"{name} must be a positive integer") from None
        if counts[field] < 1:
            raise ValueError(f"{name} must be a positive integer")
    return Policy(**counts)
