from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model

from railway_autoscaler.autoscaling.ports import ResourceSample
from railway_autoscaler.autoscaling.reconciliation import ReconciliationService
from railway_autoscaler.models import (
    AutoscalingPolicy,
    AutoscalingStatus,
    AutoscalingTarget,
    ScalingEvent,
)
from railway_autoscaler.services import CredentialService


class FakeRailwayClient:
    def __init__(self, replicas=1):
        self.replicas = replicas
        self.set_calls = []

    def get_replicas(self, service_id, environment_id):
        return self.replicas

    def set_replicas(self, service_id, environment_id, replicas):
        self.set_calls.append((service_id, environment_id, replicas))
        self.replicas = replicas
        return True


@pytest.fixture
def target(settings):
    settings.RAILWAY_AUTOSCALER_CREDENTIAL_KEY = Fernet.generate_key().decode()
    owner = get_user_model().objects.create_user(username="operator")
    credential = CredentialService().create(
        owner=owner,
        name="production",
        token="railway-token",
        token_type="project",
    )
    target = AutoscalingTarget.objects.create(
        credential=credential,
        name="production api",
        project_id="project-id",
        environment_id="environment-id",
        service_id="service-id",
        service_name="api",
        agent_type=AutoscalingTarget.AgentType.HTTP,
        enabled=True,
    )
    AutoscalingPolicy.objects.create(
        target=target,
        max_replicas=3,
        high_samples=1,
        low_samples=1,
    )
    return target


@pytest.mark.django_db
def test_dry_run_records_preview_without_mutating_railway(target):
    client = FakeRailwayClient()
    result = ReconciliationService(dry_run=True).run(
        target,
        client,
        ResourceSample(timestamp=100, cpu=0.9, memory=0.2),
    )

    assert result.desired_replicas == 2
    assert result.outcome == ScalingEvent.Outcome.PREVIEW
    assert client.set_calls == []
    assert ScalingEvent.objects.get().outcome == ScalingEvent.Outcome.PREVIEW


@pytest.mark.django_db
def test_apply_mode_confirms_after_rereading_railway(target):
    now = datetime.now(UTC)
    client = FakeRailwayClient()
    result = ReconciliationService(now=now, dry_run=False).run(
        target,
        client,
        ResourceSample(timestamp=100, cpu=0.9, memory=0.2),
    )

    assert result.outcome == ScalingEvent.Outcome.CONFIRMED
    assert client.set_calls == [("service-id", "environment-id", 2)]
    event = ScalingEvent.objects.get()
    assert event.confirmed_replicas == 2
    status = target.status
    assert status.last_success_at == now
    assert status.cooldown_until == now + timedelta(seconds=60)


@pytest.mark.django_db
def test_active_lease_skips_remote_reads_and_mutations(target):
    now = datetime.now(UTC)
    AutoscalingStatus.objects.create(
        target=target,
        lease_owner="another-cycle",
        lease_expires_at=now + timedelta(seconds=30),
    )
    client = FakeRailwayClient()

    result = ReconciliationService(now=now, dry_run=False).run(
        target,
        client,
        ResourceSample(timestamp=101, cpu=0.9, memory=0.2),
    )

    assert result.reason == "lease_active"
    assert client.set_calls == []
    assert client.replicas == 1


@pytest.mark.django_db
def test_pending_change_blocks_new_decision_until_convergence(target):
    now = datetime.now(UTC)
    AutoscalingStatus.objects.create(target=target, pending_replicas=2)
    client = FakeRailwayClient(replicas=1)

    result = ReconciliationService(now=now, dry_run=False).run(
        target,
        client,
        ResourceSample(timestamp=101, cpu=0.9, memory=0.2),
    )

    status = AutoscalingStatus.objects.get(target=target)
    assert result.outcome == ScalingEvent.Outcome.REQUESTED
    assert result.reason == "pending_replica_change"
    assert status.pending_replicas == 2
    assert client.set_calls == []
    assert ScalingEvent.objects.get().outcome == ScalingEvent.Outcome.REQUESTED


@pytest.mark.django_db
def test_pending_change_convergence_confirms_without_mutating_again(target):
    now = datetime.now(UTC)
    AutoscalingStatus.objects.create(target=target, pending_replicas=2)
    client = FakeRailwayClient(replicas=2)

    result = ReconciliationService(now=now, dry_run=False).run(
        target,
        client,
        ResourceSample(timestamp=101, cpu=0.9, memory=0.2),
    )

    status = AutoscalingStatus.objects.get(target=target)
    assert result.outcome == ScalingEvent.Outcome.CONFIRMED
    assert status.pending_replicas is None
    assert status.last_success_at == now
    assert client.set_calls == []


@pytest.mark.django_db
def test_invalid_metrics_pause_and_reset_sample_counters(target):
    status = AutoscalingStatus.objects.create(
        target=target,
        consecutive_high_samples=2,
        consecutive_low_samples=1,
    )
    client = FakeRailwayClient()

    result = ReconciliationService(dry_run=False).run(
        target,
        client,
        ResourceSample(timestamp=101, cpu=None, memory=None),
    )

    status.refresh_from_db()
    assert result.outcome == ScalingEvent.Outcome.PAUSED
    assert result.reason == "invalid_or_stale_metrics"
    assert status.consecutive_high_samples == 0
    assert status.consecutive_low_samples == 0
    assert client.set_calls == []


@pytest.mark.django_db
def test_dry_run_does_not_advance_apply_state(target):
    AutoscalingStatus.objects.create(
        target=target,
        consecutive_high_samples=2,
        consecutive_low_samples=1,
        cooldown_until=datetime.now(UTC) + timedelta(minutes=5),
    )
    client = FakeRailwayClient()

    result = ReconciliationService(dry_run=True).run(
        target,
        client,
        ResourceSample(timestamp=101, cpu=0.9, memory=0.2),
    )

    status = AutoscalingStatus.objects.get(target=target)
    assert result.outcome == ScalingEvent.Outcome.PREVIEW
    assert status.consecutive_high_samples == 2
    assert status.consecutive_low_samples == 1
    assert status.pending_replicas is None
    assert status.cooldown_until is not None
    assert client.set_calls == []


@pytest.mark.django_db
def test_stale_metrics_reset_counters_and_block_scaling(target, settings):
    settings.RAILWAY_AUTOSCALER_METRIC_MAX_AGE_SECONDS = 10
    AutoscalingStatus.objects.create(target=target, consecutive_high_samples=2)
    client = FakeRailwayClient()
    now = datetime.now(UTC)

    result = ReconciliationService(now=now, dry_run=False).run(
        target,
        client,
        ResourceSample(timestamp=now.timestamp() - 100, cpu=0.9, memory=0.2),
    )

    status = AutoscalingStatus.objects.get(target=target)
    assert result.reason == "invalid_or_stale_metrics"
    assert status.consecutive_high_samples == 0
    assert status.pending_replicas is None
    assert client.set_calls == []
