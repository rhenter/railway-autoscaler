"""Immutable data-transfer objects returned by provider clients."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectTokenScope:
    project_id: str
    environment_id: str


@dataclass(frozen=True)
class RailwayService:
    id: str
    name: str
    environment_id: str
    environment_name: str


@dataclass(frozen=True)
class RailwayEnvironment:
    id: str
    name: str


@dataclass(frozen=True)
class RailwayProject:
    id: str
    name: str
    environments: tuple[RailwayEnvironment, ...]
    services: tuple[RailwayService, ...]


@dataclass(frozen=True)
class DeploymentSummary:
    id: str
    status: str | None
    created_at: str | None
    instances: tuple[DeploymentInstanceSummary, ...] = ()


@dataclass(frozen=True)
class DeploymentInstanceSummary:
    id: str
    status: str


@dataclass(frozen=True)
class ServiceInstance:
    instance_id: str
    service_id: str
    environment_id: str
    service_name: str | None
    replicas: int | None
    configured_replicas: int | None
    region: str | None
    start_command: str | None
    build_command: str | None
    root_directory: str | None
    healthcheck_path: str | None
    healthcheck_timeout: int | None
    restart_policy_type: str | None
    restart_policy_max_retries: int | None
    latest_deployment: DeploymentSummary | None
    active_deployments: tuple[DeploymentSummary, ...] = ()


@dataclass(frozen=True)
class MetricPoint:
    timestamp: float
    value: float


@dataclass(frozen=True)
class ResourceUtilization:
    timestamp: float
    cpu: float | None
    memory: float | None
