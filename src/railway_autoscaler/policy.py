"""A pure, single-sample policy. No I/O and no production control loop."""

from railway_autoscaler.models import Decision, Policy, Sample, finite_number, replica_count


def evaluate(
    policy: Policy,
    sample: Sample,
    current_replicas: int,
    last_scaled_at: float | None = None,
) -> Decision:
    replica_count("current_replicas", current_replicas)
    if not policy.min_replicas <= current_replicas <= policy.max_replicas:
        raise ValueError("current_replicas must be within policy bounds")
    if last_scaled_at is not None:
        finite_number("last_scaled_at", last_scaled_at)
        if not 0 <= last_scaled_at <= sample.at_seconds:
            raise ValueError("last_scaled_at must be between zero and the sample time")
    if sample.utilization is None:
        return Decision(current_replicas, current_replicas, "missing_metric")
    if last_scaled_at is not None and sample.at_seconds - last_scaled_at < policy.cooldown_seconds:
        return Decision(current_replicas, current_replicas, "cooldown")
    if sample.utilization >= policy.upper_threshold:
        desired = min(current_replicas + 1, policy.max_replicas)
        reason = "scale_up" if desired != current_replicas else "at_maximum"
    elif sample.utilization <= policy.lower_threshold:
        desired = max(current_replicas - 1, policy.min_replicas)
        reason = "scale_down" if desired != current_replicas else "at_minimum"
    else:
        desired, reason = current_replicas, "within_thresholds"
    return Decision(current_replicas, desired, reason)
