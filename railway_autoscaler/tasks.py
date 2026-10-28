"""Celery entry points for the autoscaler."""

from dataclasses import asdict
from typing import Any

from celery import shared_task
from django.conf import settings

from .autoscaling.reconciliation import RailwayResourceMetricsProvider, ReconciliationService
from .client.railway import RailwayGraphQLClient
from .models import AutoscalingTarget
from .services import CredentialService


def _client_for_target(target: AutoscalingTarget, credential_service: CredentialService):
    """Build the Railway client for a target without exposing its token."""
    credential = target.credential
    return RailwayGraphQLClient(
        credential_service.reveal(credential),
        use_project_token=credential.token_type == credential.TokenType.PROJECT,
        timeout=getattr(settings, "RAILWAY_AUTOSCALER_API_TIMEOUT", 20),
    )


def _reconcile_target(
    target: AutoscalingTarget,
    credential_service: CredentialService,
):
    """Collect one sample and run one bounded reconciliation for ``target``."""
    client = _client_for_target(target, credential_service)
    provider = RailwayResourceMetricsProvider(
        client=client,
        window_seconds=getattr(settings, "RAILWAY_AUTOSCALER_METRIC_WINDOW_SECONDS", 60),
    )
    sample = provider.read_sample(target)
    return ReconciliationService().run(target, client, sample)


@shared_task(
    bind=True,
    name="railway_autoscaler.reconcile",
    queue="autoscaling",
    ignore_result=True,
)
def reconcile(self):
    """Run one bounded cycle for every enabled target."""
    credential_service = CredentialService()
    results: list[dict[str, Any]] = []
    targets = AutoscalingTarget.objects.filter(enabled=True).select_related("credential", "policy")
    for target in targets:
        result = _reconcile_target(target, credential_service)
        results.append(asdict(result))
    return results
