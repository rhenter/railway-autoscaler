import pytest

from railway_autoscaler.models import Policy, Sample
from railway_autoscaler.policy import evaluate


@pytest.mark.parametrize(
    ("utilization", "current", "desired", "reason"),
    [
        (0.9, 2, 3, "scale_up"),
        (0.8, 2, 3, "scale_up"),
        (0.2, 2, 1, "scale_down"),
        (0.3, 2, 1, "scale_down"),
        (0.5, 2, 2, "within_thresholds"),
        (1.0, 5, 5, "at_maximum"),
        (0.0, 1, 1, "at_minimum"),
        (None, 2, 2, "missing_metric"),
    ],
)
def test_single_sample_decisions(utilization, current, desired, reason):
    decision = evaluate(Policy(max_replicas=5), Sample(100, utilization), current)

    assert decision.current_replicas == current
    assert decision.desired_replicas == desired
    assert decision.reason == reason


@pytest.mark.parametrize("utilization", [0.1, 0.9])
def test_cooldown_blocks_both_directions(utilization):
    decision = evaluate(Policy(max_replicas=5), Sample(59, utilization), 2, last_scaled_at=0)

    assert decision.desired_replicas == 2
    assert decision.reason == "cooldown"


def test_change_allowed_at_exact_cooldown_boundary():
    decision = evaluate(Policy(max_replicas=5), Sample(60, 0.9), 2, last_scaled_at=0)

    assert decision.desired_replicas == 3


def test_zero_cooldown_allows_immediate_change():
    decision = evaluate(
        Policy(max_replicas=5, cooldown_seconds=0), Sample(0, 0.9), 2, last_scaled_at=0
    )

    assert decision.desired_replicas == 3


@pytest.mark.parametrize("current", [0, -1, 6, True, 1.5])
def test_invalid_observed_replica_count_is_rejected(current):
    with pytest.raises(ValueError):
        evaluate(Policy(max_replicas=5), Sample(0, 0.9), current)


@pytest.mark.parametrize("last_scaled_at", [-1, 101, float("nan"), True])
def test_invalid_last_change_is_rejected(last_scaled_at):
    with pytest.raises(ValueError):
        evaluate(Policy(max_replicas=5), Sample(100, 0.9), 2, last_scaled_at)


@pytest.mark.parametrize(
    "overrides",
    [
        {"min_replicas": 0},
        {"min_replicas": True},
        {"max_replicas": 1.5},
        {"min_replicas": 6},
        {"lower_threshold": 0.8},
        {"lower_threshold": -0.1},
        {"upper_threshold": 1.1},
        {"upper_threshold": float("nan")},
        {"lower_threshold": False},
        {"cooldown_seconds": -1},
        {"cooldown_seconds": float("inf")},
        {"cooldown_seconds": "60"},
    ],
)
def test_invalid_policy_is_rejected(overrides):
    with pytest.raises(ValueError):
        Policy(**overrides)


@pytest.mark.parametrize("utilization", [-0.1, 1.1, float("nan"), float("inf"), True, "0.8"])
def test_invalid_utilization_is_rejected(utilization):
    with pytest.raises(ValueError):
        Sample(0, utilization)


@pytest.mark.parametrize("time", [-1, float("nan"), float("inf"), True])
def test_invalid_sample_time_is_rejected(time):
    with pytest.raises(ValueError):
        Sample(time, 0.5)
