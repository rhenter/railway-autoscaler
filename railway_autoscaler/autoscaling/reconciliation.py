"""One bounded, database-backed autoscaling reconciliation cycle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import isfinite
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.utils import timezone as django_timezone

from ..client.railway import RailwayGraphQLClient
from ..core.policy import evaluate
from ..core.policy_types import Policy, Sample
from ..models import AutoscalingPolicy, AutoscalingStatus, AutoscalingTarget, ScalingEvent
from .ports import RailwayAPI, ResourceSample


class RailwayResourceMetricsProvider:
    """Read a normalized CPU/memory sample from Railway."""

    def __init__(self, client: RailwayGraphQLClient, window_seconds: int = 60) -> None:
        self.client = client
        self.window_seconds = window_seconds

    def read_sample(self, target: AutoscalingTarget) -> ResourceSample:
        metrics = self.client.get_resource_utilization(
            service_id=target.service_id,
            environment_id=target.environment_id,
            window_seconds=self.window_seconds,
        )
        return ResourceSample(metrics.timestamp, metrics.cpu, metrics.memory)


@dataclass(frozen=True)
class ReconciliationResult:
    target_id: int
    run_id: str
    current_replicas: int | None
    desired_replicas: int | None
    reason: str
    outcome: str


class LeaseLost(RuntimeError):
    """The cycle no longer owns the target status row."""


class ReconciliationService:
    def __init__(self, *, now=None, dry_run: bool | None = None, lease_seconds: int | None = None):
        self.now = now or django_timezone.now()
        self.dry_run = (
            getattr(settings, "RAILWAY_AUTOSCALER_DRY_RUN", True) if dry_run is None else dry_run
        )
        self.lease_seconds = (
            getattr(settings, "RAILWAY_AUTOSCALER_LEASE_SECONDS", 120)
            if lease_seconds is None
            else lease_seconds
        )
        if self.lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")

    def run(
        self,
        target: AutoscalingTarget,
        client: RailwayAPI,
        sample: ResourceSample,
    ) -> ReconciliationResult:
        run_id = uuid4().hex
        policy = self._policy(target)
        status = self._acquire_lease(target, run_id)
        if status is None:
            return ReconciliationResult(
                target.pk, run_id, None, None, "lease_active", ScalingEvent.Outcome.PAUSED
            )

        current = None
        desired = None
        reason = "reconciliation_failed"
        try:
            if not target.enabled:
                return self._pause(target, status, run_id, None, "disabled")

            current = client.get_replicas(
                service_id=target.service_id,
                environment_id=target.environment_id,
            )
            with transaction.atomic():
                status = self._owned_status(status.pk, run_id)
                if not policy.min_replicas <= current <= policy.max_replicas:
                    return self._pause(
                        target,
                        status,
                        run_id,
                        current,
                        "observed_replicas_outside_policy",
                    )

                pending_result = self._resolve_pending(target, status, run_id, current, policy)
                if pending_result is not None:
                    return pending_result

                if status.sample_at and sample.timestamp <= status.sample_at.timestamp():
                    return self._return(
                        status.pk,
                        run_id,
                        ReconciliationResult(
                            target.pk, run_id, current, current, "duplicate_sample", "ignored"
                        ),
                    )

                if not self._valid_sample(sample):
                    return self._pause(target, status, run_id, current, "invalid_or_stale_metrics")

                utilization = sample.utilization
                sample_value = Sample(sample.timestamp, utilization)
                high = utilization is not None and utilization >= policy.upper_threshold
                low = utilization is not None and utilization <= policy.lower_threshold
                high_count = status.consecutive_high_samples + 1 if high else 0
                low_count = status.consecutive_low_samples + 1 if low else 0
                if high and high_count < policy.high_samples:
                    decision = (current, "high_sample_window")
                elif low and low_count < policy.low_samples:
                    decision = (current, "low_sample_window")
                else:
                    evaluated = evaluate(
                        policy,
                        sample_value,
                        current,
                        status.last_scaled_at.timestamp() if status.last_scaled_at else None,
                    )
                    decision = (evaluated.desired_replicas, evaluated.reason)

                desired, reason = decision
                status.observed_replicas = current
                status.desired_replicas = current if self.dry_run else desired
                status.min_replicas = policy.min_replicas
                status.max_replicas = policy.max_replicas
                status.cpu_utilization = sample.cpu
                status.memory_utilization = sample.memory
                status.sample_at = datetime.fromtimestamp(sample.timestamp, tz=UTC)
                if not self.dry_run:
                    status.consecutive_high_samples = high_count
                    status.consecutive_low_samples = low_count
                status.health = AutoscalingStatus.Health.HEALTHY
                status.error = ""
                self._save_owned(status, run_id)

                if desired == current:
                    return self._return(
                        status.pk,
                        run_id,
                        ReconciliationResult(
                            target.pk, run_id, current, desired, reason, "unchanged"
                        ),
                    )

                if self.dry_run:
                    ScalingEvent.objects.create(
                        target=target,
                        run_id=run_id,
                        reason=reason,
                        previous_replicas=current,
                        desired_replicas=desired,
                        outcome=ScalingEvent.Outcome.PREVIEW,
                    )
                    return self._return(
                        status.pk,
                        run_id,
                        ReconciliationResult(
                            target.pk,
                            run_id,
                            current,
                            desired,
                            reason,
                            ScalingEvent.Outcome.PREVIEW,
                        ),
                    )

                status.pending_replicas = desired
                self._save_owned(status, run_id)

            client.set_replicas(
                service_id=target.service_id,
                environment_id=target.environment_id,
                replicas=desired,
            )
            confirmed = client.get_replicas(
                service_id=target.service_id,
                environment_id=target.environment_id,
            )
        except Exception as error:
            self._record_failure(status.pk, target, run_id, current, desired, reason, error)
            self._release_lease(status.pk, run_id)
            raise

        try:
            with transaction.atomic():
                status = self._owned_status(status.pk, run_id)
                if confirmed != desired:
                    status.health = AutoscalingStatus.Health.PAUSED
                    status.error = "Railway accepted the request but has not converged"
                    self._save_owned(status, run_id)
                    outcome = ScalingEvent.Outcome.REQUESTED
                else:
                    status.observed_replicas = confirmed
                    status.desired_replicas = confirmed
                    status.pending_replicas = None
                    status.last_scaled_at = self.now
                    status.last_success_at = self.now
                    status.cooldown_until = self.now + timedelta(seconds=policy.cooldown_seconds)
                    status.health = AutoscalingStatus.Health.HEALTHY
                    status.error = ""
                    self._save_owned(status, run_id)
                    outcome = ScalingEvent.Outcome.CONFIRMED

                ScalingEvent.objects.create(
                    target=target,
                    run_id=run_id,
                    reason=reason,
                    previous_replicas=current,
                    desired_replicas=desired,
                    confirmed_replicas=confirmed,
                    outcome=outcome,
                )
                result = ReconciliationResult(target.pk, run_id, current, desired, reason, outcome)
        except Exception:
            self._release_lease(status.pk, run_id)
            raise
        target.status = status
        return self._return(status.pk, run_id, result)

    @staticmethod
    def _policy(target: AutoscalingTarget) -> Policy:
        policy = AutoscalingPolicy.objects.get(target=target)
        return Policy(
            min_replicas=policy.min_replicas,
            max_replicas=policy.max_replicas,
            lower_threshold=policy.lower_threshold,
            upper_threshold=policy.upper_threshold,
            cooldown_seconds=policy.cooldown_seconds,
            high_samples=policy.high_samples,
            low_samples=policy.low_samples,
        )

    def _acquire_lease(self, target, run_id):
        with transaction.atomic():
            status, _ = AutoscalingStatus.objects.select_for_update().get_or_create(target=target)
            if status.lease_owner and not status.lease_expires_at:
                raise LeaseLost("target lease has no expiration")
            if status.lease_expires_at and status.lease_expires_at > self.now:
                return None
            status.lease_owner = run_id
            status.lease_expires_at = self.now + timedelta(seconds=self.lease_seconds)
            status.run_id = run_id
            status.last_attempt_at = self.now
            self._save_owned(status, run_id)
            return status

    @staticmethod
    def _owned_status(status_id, run_id):
        status = AutoscalingStatus.objects.select_for_update().get(pk=status_id)
        if status.lease_owner != run_id or not status.lease_expires_at:
            raise LeaseLost("target lease is no longer owned")
        if status.lease_expires_at <= django_timezone.now():
            raise LeaseLost("target lease expired before state transition")
        return status

    def _save_owned(self, status, run_id):
        if status.lease_owner != run_id or not status.lease_expires_at:
            raise LeaseLost("target lease is no longer owned")
        status.state_version += 1
        status.save()

    def _resolve_pending(self, target, status, run_id, current, policy):
        pending = status.pending_replicas
        if pending is None:
            return None
        if current != pending:
            status.observed_replicas = current
            status.desired_replicas = pending
            status.health = AutoscalingStatus.Health.PAUSED
            status.error = "pending_replica_change_not_converged"
            self._save_owned(status, run_id)
            ScalingEvent.objects.create(
                target=target,
                run_id=run_id,
                reason="pending_replica_change",
                previous_replicas=current,
                desired_replicas=pending,
                outcome=ScalingEvent.Outcome.REQUESTED,
            )
            return self._return(
                status.pk,
                run_id,
                ReconciliationResult(
                    target.pk,
                    run_id,
                    current,
                    pending,
                    "pending_replica_change",
                    ScalingEvent.Outcome.REQUESTED,
                ),
            )
        status.observed_replicas = current
        status.desired_replicas = current
        status.pending_replicas = None
        status.last_scaled_at = self.now
        status.last_success_at = self.now
        status.cooldown_until = self.now + timedelta(seconds=policy.cooldown_seconds)
        status.health = AutoscalingStatus.Health.HEALTHY
        status.error = ""
        self._save_owned(status, run_id)
        ScalingEvent.objects.create(
            target=target,
            run_id=run_id,
            reason="pending_replica_change_confirmed",
            previous_replicas=current,
            desired_replicas=current,
            confirmed_replicas=current,
            outcome=ScalingEvent.Outcome.CONFIRMED,
        )
        return self._return(
            status.pk,
            run_id,
            ReconciliationResult(
                target.pk,
                run_id,
                current,
                current,
                "pending_replica_change_confirmed",
                ScalingEvent.Outcome.CONFIRMED,
            ),
        )

    def _record_failure(self, status_id, target, run_id, current, desired, reason, error):
        try:
            with transaction.atomic():
                status = self._owned_status(status_id, run_id)
                status.health = AutoscalingStatus.Health.ERROR
                status.error = error.__class__.__name__
                self._save_owned(status, run_id)
                if desired is not None:
                    ScalingEvent.objects.create(
                        target=target,
                        run_id=run_id,
                        reason=reason,
                        previous_replicas=current,
                        desired_replicas=desired,
                        outcome=ScalingEvent.Outcome.FAILED,
                    )
        except LeaseLost:
            return

    def _valid_sample(self, sample):
        if not isfinite(sample.timestamp) or sample.timestamp <= 0:
            return False
        for value in (sample.cpu, sample.memory):
            if value is not None and (not isfinite(value) or not 0 <= value <= 1):
                return False
        max_age = getattr(settings, "RAILWAY_AUTOSCALER_METRIC_MAX_AGE_SECONDS", None)
        if max_age is not None and (
            self.now.timestamp() - sample.timestamp > max_age
            or sample.timestamp - self.now.timestamp() > max_age
        ):
            return False
        return sample.cpu is not None or sample.memory is not None

    @staticmethod
    def _release_lease(status_id, run_id):
        AutoscalingStatus.objects.filter(pk=status_id, lease_owner=run_id).update(
            lease_owner="", lease_expires_at=None
        )

    def _return(self, status_id, run_id, result):
        self._release_lease(status_id, run_id)
        return result

    def _pause(self, target, status, run_id, current, reason, *, current_override=None):
        if current_override is not None:
            current = current_override
        status.observed_replicas = current
        status.health = AutoscalingStatus.Health.PAUSED
        status.error = reason
        status.run_id = run_id
        status.last_attempt_at = self.now
        status.consecutive_high_samples = 0
        status.consecutive_low_samples = 0
        self._save_owned(status, run_id)
        if current is None:
            return self._return(
                status.pk,
                run_id,
                ReconciliationResult(
                    target.pk, run_id, None, None, reason, ScalingEvent.Outcome.PAUSED
                ),
            )
        ScalingEvent.objects.create(
            target=target,
            run_id=run_id,
            reason=reason,
            previous_replicas=current,
            desired_replicas=current,
            confirmed_replicas=current,
            outcome=ScalingEvent.Outcome.PAUSED,
        )
        return self._return(
            status.pk,
            run_id,
            ReconciliationResult(
                target.pk, run_id, current, current, reason, ScalingEvent.Outcome.PAUSED
            ),
        )
