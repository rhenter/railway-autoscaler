"""Values shared by the policy, simulator, and future adapters."""

from dataclasses import dataclass
from math import isfinite


def finite_number(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{name} must be a finite number")


def replica_count(name: str, value: int) -> None:
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")


@dataclass(frozen=True)
class Policy:
    min_replicas: int = 1
    max_replicas: int = 5
    lower_threshold: float = 0.3
    upper_threshold: float = 0.8
    cooldown_seconds: float = 60

    def __post_init__(self) -> None:
        replica_count("min_replicas", self.min_replicas)
        replica_count("max_replicas", self.max_replicas)
        if self.min_replicas > self.max_replicas:
            raise ValueError("min_replicas must not exceed max_replicas")
        finite_number("lower_threshold", self.lower_threshold)
        finite_number("upper_threshold", self.upper_threshold)
        if not 0 <= self.lower_threshold < self.upper_threshold <= 1:
            raise ValueError("thresholds must satisfy 0 <= lower < upper <= 1")
        finite_number("cooldown_seconds", self.cooldown_seconds)
        if self.cooldown_seconds < 0:
            raise ValueError("cooldown_seconds must be nonnegative")


@dataclass(frozen=True)
class Sample:
    """Synthetic normalized utilization, not a raw Railway CPU measurement."""

    at_seconds: float
    utilization: float | None

    def __post_init__(self) -> None:
        finite_number("at_seconds", self.at_seconds)
        if self.at_seconds < 0:
            raise ValueError("at_seconds must be nonnegative")
        if self.utilization is not None:
            finite_number("utilization", self.utilization)
            if not 0 <= self.utilization <= 1:
                raise ValueError("utilization must be between 0 and 1")


@dataclass(frozen=True)
class Decision:
    current_replicas: int
    desired_replicas: int
    reason: str
