"""Contracts only. No HTTP client, credentials, or Railway adapter is implemented."""

from typing import Protocol

from railway_autoscaler.models import Sample


class MetricsProvider(Protocol):
    def read_sample(self, *, service_id: str, environment_id: str) -> Sample:
        """Return normalized utilization; represent missing metrics as None.

        A real adapter must define normalization and preserve sample freshness.
        at_seconds must use the controller's time origin, not raw epoch time.
        """
        ...


class RailwayAPI(Protocol):
    def get_replicas(self, *, service_id: str, environment_id: str) -> int:
        """Read observed replica count; fail if the service layout is unsupported."""
        ...

    def set_replicas(self, *, service_id: str, environment_id: str, replicas: int) -> None:
        """Request a replica count; acceptance alone does not imply convergence.

        The future adapter must preserve unrelated regional configuration.
        """
        ...
