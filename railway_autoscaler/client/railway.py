"""Small, typed client for the Railway GraphQL API.

The client is intentionally unaware of autoscaling policy. It only owns the
provider boundary: authentication, GraphQL errors and service operations.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from time import sleep
from typing import Any

import requests

from .exceptions import RailwayGraphQLError, RailwayTransportError
from .railway_types import (
    DeploymentInstanceSummary,
    DeploymentSummary,
    MetricPoint,
    ProjectTokenScope,
    RailwayEnvironment,
    RailwayProject,
    RailwayService,
    ResourceUtilization,
    ServiceInstance,
)

DEFAULT_ENDPOINT = "https://backboard.railway.com/graphql/v2"


class RailwayGraphQLClient:
    """Authenticated Railway GraphQL client.

    ``use_project_token=True`` uses Railway's ``Project-Access-Token`` header.
    Account and workspace tokens should use ``use_project_token=False`` and the
    ``Authorization: Bearer`` header instead.
    """

    def __init__(
        self,
        token: str,
        *,
        use_project_token: bool = True,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout: float = 20.0,
        session: requests.Session | None = None,
        max_read_retries: int = 2,
        retry_backoff_seconds: float = 0.25,
    ) -> None:
        if not token or not token.strip():
            raise ValueError("token must not be empty")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if max_read_retries < 0:
            raise ValueError("max_read_retries must not be negative")
        if retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds must not be negative")
        self._token = token
        self._use_project_token = use_project_token
        self.endpoint = endpoint
        self.timeout = timeout
        self._session = session or requests.Session()
        self.max_read_retries = max_read_retries
        self.retry_backoff_seconds = retry_backoff_seconds

    def execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
        *,
        retry_safe_read: bool = False,
    ) -> dict[str, Any]:
        """Execute a query and return its data, raising on every API failure."""
        token_header = {"Authorization": f"Bearer {self._token}"}
        if self._use_project_token:
            token_header = {"Project-Access-Token": self._token}

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "railway-autoscaler/0.1",
        }
        headers.update(token_header)

        attempts = self.max_read_retries + 1 if retry_safe_read else 1
        for attempt in range(attempts):
            try:
                response = self._session.post(
                    self.endpoint,
                    json={"query": query, "variables": variables or {}},
                    headers=headers,
                    timeout=self.timeout,
                )
            except requests.Timeout as error:
                if retry_safe_read and attempt + 1 < attempts:
                    self._sleep_before_retry(attempt)
                    continue
                raise RailwayTransportError("Railway HTTP request timed out") from error
            except requests.RequestException as error:
                if retry_safe_read and attempt + 1 < attempts:
                    self._sleep_before_retry(attempt)
                    continue
                status = error.response.status_code if error.response is not None else None
                raise RailwayTransportError(
                    "Railway HTTP request failed"
                    if status is None
                    else f"Railway HTTP request failed with status {status}",
                    status_code=status,
                ) from error

            status = getattr(response, "status_code", None)
            if status in {408, 425, 429, 500, 502, 503, 504}:
                if retry_safe_read and attempt + 1 < attempts:
                    self._sleep_before_retry(attempt, response)
                    continue
                raise RailwayTransportError(
                    f"Railway HTTP request failed with status {status}",
                    status_code=status,
                    retry_after=self._retry_after(response),
                )
            try:
                response.raise_for_status()
            except requests.RequestException as error:
                raise RailwayTransportError(
                    f"Railway HTTP request failed with status {status}",
                    status_code=status,
                ) from error
            break

        try:
            body = response.json()
        except (TypeError, ValueError) as error:
            raise RailwayTransportError(
                f"Railway returned invalid JSON (HTTP {response.status_code})"
            ) from error
        if not isinstance(body, dict):
            raise RailwayTransportError("Railway returned an invalid GraphQL response")

        errors = body.get("errors")
        if errors:
            error = errors[0] if isinstance(errors[0], dict) else {}
            extensions = error.get("extensions", {})
            raise RailwayGraphQLError(
                str(error.get("message", "Railway GraphQL request failed")),
                code=extensions.get("code"),
                trace_id=extensions.get("traceId"),
            )
        data = body.get("data")
        if not isinstance(data, dict):
            raise RailwayTransportError("Railway response did not contain GraphQL data")
        return data

    def _sleep_before_retry(self, attempt: int, response=None):
        retry_after = self._retry_after(response)
        delay = (
            retry_after if retry_after is not None else self.retry_backoff_seconds * (2**attempt)
        )
        sleep(delay)

    @staticmethod
    def _retry_after(response) -> float | None:
        if response is None:
            return None
        headers = getattr(response, "headers", {}) or {}
        value = headers.get("Retry-After")
        if value is None:
            return None
        try:
            return max(0.0, float(value))
        except TypeError, ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
            except TypeError, ValueError, OverflowError:
                return None
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=UTC)
            return max(0.0, (retry_at - datetime.now(UTC)).total_seconds())

    def get_project_token_scope(self) -> ProjectTokenScope:
        data = self.execute(
            "query { projectToken { projectId environmentId } }", retry_safe_read=True
        )
        scope = data["projectToken"]
        return ProjectTokenScope(scope["projectId"], scope["environmentId"])

    def get_project(self, project_id: str, *, environment_id: str | None = None) -> RailwayProject:
        data = self.execute(
            """
            query($id: String!) {
              project(id: $id) {
                id name
                environments { edges { node { id name } } }
                services { edges { node { id name } } }
              }
            }
            """,
            {"id": project_id},
            retry_safe_read=True,
        )
        project = data["project"]
        environments = tuple(
            RailwayEnvironment(node["id"], node["name"])
            for edge in project["environments"]["edges"]
            for node in [edge["node"]]
        )
        if environment_id is None:
            if len(environments) != 1:
                raise ValueError(
                    "environment_id is required when a project has multiple environments"
                )
            selected_environment = environments[0]
        else:
            selected_environment = next(
                (environment for environment in environments if environment.id == environment_id),
                None,
            )
            if selected_environment is None:
                raise ValueError("environment_id does not belong to the project")
        return RailwayProject(
            id=project["id"],
            name=project["name"],
            environments=environments,
            services=tuple(
                RailwayService(
                    node["id"],
                    node["name"],
                    selected_environment.id,
                    selected_environment.name,
                )
                for edge in project["services"]["edges"]
                for node in [edge["node"]]
            ),
        )

    def get_service_instance(self, service_id: str, environment_id: str) -> ServiceInstance:
        data = self.execute(
            """
            query($serviceId: String!, $environmentId: String!) {
              serviceInstance(serviceId: $serviceId, environmentId: $environmentId) {
                id
                serviceId
                environmentId
                serviceName
                numReplicas
                region
                startCommand
                buildCommand
                rootDirectory
                healthcheckPath
                healthcheckTimeout
                restartPolicyType
                restartPolicyMaxRetries
                latestDeployment {
                  id status createdAt
                  instances { id status }
                }
                activeDeployments {
                  id status createdAt
                  instances { id status }
                }
              }
            }
            """,
            {"serviceId": service_id, "environmentId": environment_id},
            retry_safe_read=True,
        )
        instance = data["serviceInstance"]
        deployment = instance.get("latestDeployment")
        active_deployments = tuple(
            DeploymentSummary(
                id=active["id"],
                status=active.get("status"),
                created_at=active.get("createdAt"),
                instances=tuple(
                    DeploymentInstanceSummary(
                        id=deployment_instance["id"],
                        status=deployment_instance["status"],
                    )
                    for deployment_instance in active.get("instances", [])
                ),
            )
            for active in instance.get("activeDeployments", [])
        )
        configured_replicas = instance.get("numReplicas")
        running_replicas = sum(
            deployment_instance.status == "RUNNING"
            for active in active_deployments
            for deployment_instance in active.instances
        )
        latest_instances = (
            tuple(
                DeploymentInstanceSummary(
                    id=deployment_instance["id"],
                    status=deployment_instance["status"],
                )
                for deployment_instance in deployment.get("instances", [])
            )
            if deployment
            else ()
        )
        return ServiceInstance(
            instance_id=instance["id"],
            service_id=instance.get("serviceId", service_id),
            environment_id=instance.get("environmentId", environment_id),
            service_name=instance.get("serviceName"),
            replicas=(configured_replicas if configured_replicas is not None else running_replicas),
            configured_replicas=configured_replicas,
            region=instance.get("region"),
            start_command=instance.get("startCommand"),
            build_command=instance.get("buildCommand"),
            root_directory=instance.get("rootDirectory"),
            healthcheck_path=instance.get("healthcheckPath"),
            healthcheck_timeout=instance.get("healthcheckTimeout"),
            restart_policy_type=instance.get("restartPolicyType"),
            restart_policy_max_retries=instance.get("restartPolicyMaxRetries"),
            latest_deployment=(
                DeploymentSummary(
                    id=deployment["id"],
                    status=deployment.get("status"),
                    created_at=deployment.get("createdAt"),
                    instances=latest_instances,
                )
                if deployment
                else None
            ),
            active_deployments=active_deployments,
        )

    def get_replicas(self, service_id: str, environment_id: str) -> int:
        """Return the observed replica count for a service instance.

        ``numReplicas`` can be null for some Railway layouts. In that case,
        ``get_service_instance`` derives the count from running deployment
        instances. If neither source provides a count, fail closed instead of
        allowing an autoscaler to make a decision from incomplete state.
        """
        instance = self.get_service_instance(service_id, environment_id)
        if instance.replicas is None:
            raise RailwayTransportError(
                "Railway did not return an observable replica count for the service"
            )
        return instance.replicas

    def get_resource_limits(self, service_id: str, environment_id: str) -> Any:
        """Read Railway's resource-limit payload without interpreting its shape."""
        data = self.execute(
            """
            query($serviceId: String!, $environmentId: String!) {
              serviceInstanceLimits(serviceId: $serviceId, environmentId: $environmentId)
            }
            """,
            {"serviceId": service_id, "environmentId": environment_id},
            retry_safe_read=True,
        )
        return data["serviceInstanceLimits"]

    def get_metric_series(
        self,
        *,
        service_id: str,
        environment_id: str,
        measurement: str,
        start_date: datetime,
        end_date: datetime | None = None,
        averaging_window_seconds: int = 60,
    ) -> tuple[MetricPoint, ...]:
        """Read one Railway metric series for a bounded time window."""
        if not measurement.replace("_", "").isalnum() or not measurement.isupper():
            raise ValueError("measurement must be a Railway metric enum name")
        end_date = end_date or datetime.now(UTC)
        if start_date.tzinfo is None or end_date.tzinfo is None:
            raise ValueError("metric dates must be timezone-aware")
        if end_date <= start_date:
            raise ValueError("end_date must be after start_date")
        if averaging_window_seconds < 1:
            raise ValueError("averaging_window_seconds must be positive")
        data = self.execute(
            f"""
            query($serviceId: String!, $environmentId: String!, $startDate: DateTime!,
                  $endDate: DateTime, $averagingWindowSeconds: Int!) {{
              metrics(
                serviceId: $serviceId,
                environmentId: $environmentId,
                startDate: $startDate,
                endDate: $endDate,
                averagingWindowSeconds: $averagingWindowSeconds,
                measurements: [{measurement}]
              ) {{
                ts
                value
              }}
            }}
            """,
            {
                "serviceId": service_id,
                "environmentId": environment_id,
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "averagingWindowSeconds": averaging_window_seconds,
            },
            retry_safe_read=True,
        )
        return tuple(
            MetricPoint(timestamp=float(point["ts"]), value=float(point["value"]))
            for point in data["metrics"]
        )

    def get_resource_utilization(
        self,
        *,
        service_id: str,
        environment_id: str,
        window_seconds: int = 60,
    ) -> ResourceUtilization:
        """Return the latest normalized CPU and memory utilization ratios."""
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(seconds=window_seconds)
        series = {
            measurement: self.get_metric_series(
                service_id=service_id,
                environment_id=environment_id,
                measurement=measurement,
                start_date=start_date,
                end_date=end_date,
                averaging_window_seconds=window_seconds,
            )
            for measurement in (
                "CPU_USAGE",
                "CPU_LIMIT",
                "MEMORY_USAGE_GB",
                "MEMORY_LIMIT_GB",
            )
        }
        latest = {name: points[-1] if points else None for name, points in series.items()}
        timestamps = [point.timestamp for point in latest.values() if point is not None]
        if not timestamps:
            return ResourceUtilization(timestamp=end_date.timestamp(), cpu=None, memory=None)
        cpu = _ratio(latest["CPU_USAGE"], latest["CPU_LIMIT"])
        memory = _ratio(latest["MEMORY_USAGE_GB"], latest["MEMORY_LIMIT_GB"])
        return ResourceUtilization(timestamp=max(timestamps), cpu=cpu, memory=memory)

    def set_replicas(self, service_id: str, environment_id: str, replicas: int) -> bool:
        if type(replicas) is not int or replicas < 1:
            raise ValueError("replicas must be a positive integer")
        data = self.execute(
            """
            mutation($serviceId: String!, $environmentId: String!, $replicas: Int!) {
              serviceInstanceUpdate(
                serviceId: $serviceId,
                environmentId: $environmentId,
                input: { numReplicas: $replicas }
              )
            }
            """,
            {"serviceId": service_id, "environmentId": environment_id, "replicas": replicas},
        )
        return bool(data["serviceInstanceUpdate"])


def _ratio(usage: MetricPoint | None, limit: MetricPoint | None) -> float | None:
    if usage is None or limit is None or limit.value <= 0:
        return None
    return max(0.0, min(1.0, usage.value / limit.value))
