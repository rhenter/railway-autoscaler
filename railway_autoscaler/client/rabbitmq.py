"""Read-only RabbitMQ Management API client for message-based agents."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .exceptions import RabbitMQClientError


@dataclass(frozen=True)
class QueueMetrics:
    queue_name: str
    ready: int
    unacked: int

    @property
    def total(self) -> int:
        return self.ready + self.unacked


class RabbitMQManagementClient:
    """Fetch queue depth without consuming or acknowledging messages."""

    def __init__(self, management_url: str, username: str, password: str, *, timeout: float = 10.0):
        if not management_url or not username or not password:
            raise ValueError("management_url, username and password are required")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.management_url = management_url.rstrip("/")
        self._username = username
        self._password = password
        self.timeout = timeout

    def get_queue_metrics(self, queue_name: str, *, virtual_host: str = "/") -> QueueMetrics:
        if not queue_name:
            raise ValueError("queue_name must not be empty")
        path = f"/api/queues/{quote(virtual_host, safe='')}/{quote(queue_name, safe='')}"
        credentials = base64.b64encode(f"{self._username}:{self._password}".encode()).decode()
        request = Request(
            f"{self.management_url}{path}",
            headers={"Accept": "application/json", "Authorization": f"Basic {credentials}"},
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read())
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise RabbitMQClientError("RabbitMQ queue metrics could not be collected") from error
        try:
            return QueueMetrics(
                queue_name,
                int(body["messages_ready"]),
                int(body["messages_unacknowledged"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise RabbitMQClientError(
                "RabbitMQ returned an invalid queue metrics response"
            ) from error
