"""Contracts separating policy decisions from provider clients."""

from dataclasses import dataclass
from typing import Protocol


class TargetReference(Protocol):
    service_id: str
    environment_id: str


@dataclass(frozen=True)
class ResourceSample:
    timestamp: float
    cpu: float | None
    memory: float | None

    @property
    def utilization(self) -> float | None:
        values = [value for value in (self.cpu, self.memory) if value is not None]
        return max(values) if values else None


class MetricsProvider(Protocol):
    def read_sample(self, target: TargetReference) -> ResourceSample:
        """Return one normalized resource sample for a target."""
        ...


class RailwayAPI(Protocol):
    def get_replicas(self, *, service_id: str, environment_id: str) -> int:
        """Read observed replica count; fail if the service layout is unsupported."""
        ...

    def set_replicas(self, *, service_id: str, environment_id: str, replicas: int) -> bool:
        """Request a replica count; acceptance alone does not imply convergence.

        The future adapter must preserve unrelated regional configuration.
        """
        ...
