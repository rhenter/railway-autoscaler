import pytest

from railway_autoscaler.client.exceptions import RailwayTransportError
from railway_autoscaler.client.railway import RailwayGraphQLClient, RailwayGraphQLError


class FakeResponse:
    def __init__(self, payload, status_code=200, headers=None):
        self.payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def post(self, *args, **kwargs):
        self.requests.append((args, kwargs))
        return self.response


class SequenceSession(FakeSession):
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def post(self, *args, **kwargs):
        self.requests.append((args, kwargs))
        return next(self.responses)


def test_project_token_scope_uses_project_header():
    session = FakeSession(
        FakeResponse({"data": {"projectToken": {"projectId": "p", "environmentId": "e"}}})
    )

    scope = RailwayGraphQLClient("token", session=session).get_project_token_scope()

    assert scope.project_id == "p"
    assert session.requests[0][1]["headers"]["Project-Access-Token"] == "token"


def test_graphql_errors_include_code_and_trace_id():
    session = FakeSession(
        FakeResponse(
            {
                "errors": [
                    {
                        "message": "Not Authorized",
                        "extensions": {"code": "DENIED", "traceId": "t"},
                    }
                ]
            }
        )
    )

    with pytest.raises(RailwayGraphQLError) as error:
        RailwayGraphQLClient("token", session=session).get_project_token_scope()

    assert str(error.value) == "Not Authorized"
    assert error.value.code == "DENIED"
    assert error.value.trace_id == "t"


def test_safe_reads_retry_rate_limits_using_retry_after(monkeypatch):
    session = SequenceSession(
        [
            FakeResponse({}, status_code=429, headers={"Retry-After": "0"}),
            FakeResponse({"data": {"projectToken": {"projectId": "p", "environmentId": "e"}}}),
        ]
    )
    delays = []
    monkeypatch.setattr("railway_autoscaler.client.railway.sleep", delays.append)

    scope = RailwayGraphQLClient(
        "token", session=session, retry_backoff_seconds=1
    ).get_project_token_scope()

    assert scope.project_id == "p"
    assert len(session.requests) == 2
    assert delays == [0.0]


def test_mutations_are_not_retried_after_rate_limit():
    session = FakeSession(FakeResponse({}, status_code=429, headers={"Retry-After": "0"}))

    with pytest.raises(RailwayTransportError) as error:
        RailwayGraphQLClient("token", session=session).set_replicas("service", "environment", 2)

    assert error.value.status_code == 429
    assert len(session.requests) == 1


def test_workspace_token_uses_bearer_header():
    session = FakeSession(
        FakeResponse({"data": {"projectToken": {"projectId": "p", "environmentId": "e"}}})
    )

    client = RailwayGraphQLClient("token", use_project_token=False, session=session)
    client.get_project_token_scope()

    assert session.requests[0][1]["headers"]["Authorization"] == "Bearer token"


def test_project_services_include_selected_environment():
    session = FakeSession(
        FakeResponse(
            {
                "data": {
                    "project": {
                        "id": "p",
                        "name": "Project",
                        "environments": {"edges": [{"node": {"id": "e", "name": "production"}}]},
                        "services": {"edges": [{"node": {"id": "s", "name": "api"}}]},
                    }
                }
            }
        )
    )

    project = RailwayGraphQLClient("token", session=session).get_project("p", environment_id="e")

    assert project.services[0].environment_id == "e"
    assert project.services[0].environment_name == "production"


def test_service_instance_returns_configuration_and_deployment():
    session = FakeSession(
        FakeResponse(
            {
                "data": {
                    "serviceInstance": {
                        "id": "instance",
                        "serviceId": "service",
                        "environmentId": "environment",
                        "serviceName": "api",
                        "numReplicas": 2,
                        "region": "us-east4-eqdc4a",
                        "startCommand": "gunicorn app.wsgi",
                        "buildCommand": "uv sync",
                        "rootDirectory": "/app",
                        "healthcheckPath": "/health",
                        "healthcheckTimeout": 30,
                        "restartPolicyType": "ON_FAILURE",
                        "restartPolicyMaxRetries": 3,
                        "latestDeployment": {
                            "id": "deployment",
                            "status": "SUCCESS",
                            "createdAt": "2026-10-27T12:00:00Z",
                            "instances": [{"id": "instance", "status": "RUNNING"}],
                        },
                        "activeDeployments": [
                            {
                                "id": "deployment",
                                "status": "SUCCESS",
                                "createdAt": "2026-10-27T12:00:00Z",
                                "instances": [{"id": "instance", "status": "RUNNING"}],
                            }
                        ],
                    }
                }
            }
        )
    )

    instance = RailwayGraphQLClient("token", session=session).get_service_instance(
        "service", "environment"
    )

    assert instance.instance_id == "instance"
    assert instance.service_name == "api"
    assert instance.replicas == 2
    assert instance.configured_replicas == 2
    assert instance.start_command == "gunicorn app.wsgi"
    assert instance.latest_deployment.status == "SUCCESS"
    assert instance.latest_deployment.instances[0].status == "RUNNING"


def test_service_instance_counts_running_instances_when_configured_replicas_is_null():
    session = FakeSession(
        FakeResponse(
            {
                "data": {
                    "serviceInstance": {
                        "id": "instance",
                        "serviceId": "service",
                        "environmentId": "environment",
                        "numReplicas": None,
                        "activeDeployments": [
                            {
                                "id": "deployment",
                                "status": "SUCCESS",
                                "createdAt": None,
                                "instances": [
                                    {"id": "running", "status": "RUNNING"},
                                    {"id": "removed", "status": "REMOVED"},
                                ],
                            }
                        ],
                    }
                }
            }
        )
    )

    instance = RailwayGraphQLClient("token", session=session).get_service_instance(
        "service", "environment"
    )

    assert instance.configured_replicas is None
    assert instance.replicas == 1


def test_get_replicas_returns_observed_count():
    session = FakeSession(
        FakeResponse(
            {
                "data": {
                    "serviceInstance": {
                        "id": "instance",
                        "serviceId": "service",
                        "environmentId": "environment",
                        "numReplicas": 3,
                        "activeDeployments": [],
                    }
                }
            }
        )
    )

    replicas = RailwayGraphQLClient("token", session=session).get_replicas("service", "environment")

    assert replicas == 3
