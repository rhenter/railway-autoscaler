# Provider clients

The first implementation keeps provider access separate from policy and task
execution:

- `railway_autoscaler.client.RailwayGraphQLClient` handles the Railway
  GraphQL endpoint, project-token authentication, typed discovery, read-only
  instance/resource reads, and an explicit `set_replicas` mutation.
- `railway_autoscaler.client.RabbitMQManagementClient` reads queue
  depth through RabbitMQ's Management API. It never consumes or acknowledges a
  message.

## Read-only discovery

```python
import os

from railway_autoscaler.client import RailwayGraphQLClient

railway = RailwayGraphQLClient(os.environ["RAILWAY_API_TOKEN"])
scope = railway.get_project_token_scope()
project = railway.get_project(
    scope.project_id,
    environment_id=scope.environment_id,
)

for service in project.services:
    print(service.id, service.name, service.environment_id, service.environment_name)
```

The token must be a project token and the environment must be the intended
target. Do not put credentials in task arguments, logs, or persisted status.

## Replica mutation

`set_replicas` is intentionally a low-level operation. The future agent must
read the current instance, validate active bounds, acquire database ownership,
write intent, call this method, and reread the instance before recording
convergence. Do not call it from a discovery command or a web request.

## RabbitMQ queue metrics

```python
import os

from railway_autoscaler.client import RabbitMQManagementClient

broker = RabbitMQManagementClient(
    os.environ["RABBITMQ_MANAGEMENT_URL"],
    os.environ["RABBITMQ_DEFAULT_USER"],
    os.environ["RABBITMQ_DEFAULT_PASS"],
)
metrics = broker.get_queue_metrics("celery")
print(metrics.ready, metrics.unacked, metrics.total)
```

The Management API must be enabled and reachable from the autoscaler service.
If the Railway RabbitMQ image does not expose it, the next adapter should use
an AMQP passive queue declaration instead. That adapter must be selected only
after the broker's connection contract is verified.

## Next implementation steps

1. Add a target configuration model/loader requiring explicit service and
   environment IDs; fail closed when no target is selected.
2. Add a message policy based on queue depth per worker, with activation,
   hysteresis, cooldown, and one replica change per cycle.
3. Add a read-only `discover` command that lists project, environment and
   services without mutating Railway.
4. Add Django status/event models and a Celery task that owns one bounded
   reconciliation cycle.
5. Start in dry-run, then run an isolated smoke test that changes and restores
   a non-production service before enabling apply mode.
