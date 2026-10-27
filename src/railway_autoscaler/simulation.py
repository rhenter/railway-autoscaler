"""Deterministic replay with instantaneous, successful in-memory scaling."""

from collections.abc import Iterable
from dataclasses import asdict

from railway_autoscaler.models import Policy, Sample, replica_count
from railway_autoscaler.policy import evaluate


def simulate(policy: Policy, initial_replicas: int, samples: Iterable[Sample]) -> list[dict]:
    replica_count("initial_replicas", initial_replicas)
    if not policy.min_replicas <= initial_replicas <= policy.max_replicas:
        raise ValueError("initial_replicas must be within policy bounds")
    current = initial_replicas
    last_scaled_at = None
    previous_time = -1
    results = []
    for sample in samples:
        if sample.at_seconds <= previous_time:
            raise ValueError("sample times must be strictly increasing")
        decision = evaluate(policy, sample, current, last_scaled_at)
        results.append({**asdict(sample), **asdict(decision)})
        if decision.desired_replicas != current:
            last_scaled_at = sample.at_seconds
            current = decision.desired_replicas
        previous_time = sample.at_seconds
    return results
