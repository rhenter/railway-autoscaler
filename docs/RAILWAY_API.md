# Railway API capability check

Checked on **2026-10-27**, before any integration was implemented.

## Evidence and method

Read-only, unauthenticated introspection succeeded against
`https://backboard.railway.com/graphql/v2`. No token was sent; no project, account
or service data was read, and no mutation was executed.

[schema-check.graphql](schema-check.graphql) contains the executed query.
[railway-schema-snapshot.json](railway-schema-snapshot.json) records selected
results, filtered to relevant query/mutation fields and replica settings. Type
references are depth-limited; this is a research excerpt, not a complete schema.
The MetricMeasurement enum is filtered to CPU, memory and network values.

To repeat the read-only check (optional; requires curl and network access):

```sh
uv run --locked python -c 'import json,pathlib; print(json.dumps({"query": pathlib.Path("docs/schema-check.graphql").read_text()}))' \
  | curl --fail-with-body --silent --show-error --max-time 30 \
      https://backboard.railway.com/graphql/v2 \
      --header 'Content-Type: application/json' --data-binary @-
```

This returns a broader schema response than the filtered snapshot. Inspect the
GraphQL `errors` field even when HTTP status is 200. Introspection access can
change and does not establish authorization to manage a real service.

## Confirmed by live schema inspection

| Capability | Observed contract | Practical limit |
| --- | --- | --- |
| Metrics | `Query.metrics`; `startDate` and `measurements` required; service/environment/project filters, sampling and averaging arguments available | No actual metric series or unit normalization tested |
| CPU and memory metric names | `CPU_USAGE`, `CPU_USAGE_2`, `CPU_LIMIT`, `MEMORY_USAGE_GB`, `MEMORY_LIMIT_GB` enum values present | Names alone do not settle units, aggregation or which CPU series to use |
| Configuration read | `Query.serviceInstance(serviceId, environmentId)`; `numReplicas` and `region` fields | Configured count is not evidence of healthy running replicas |
| Instance update | `Mutation.serviceInstanceUpdate`; `ServiceInstanceUpdateInput.numReplicas: Int`, `region: String`, `multiRegionConfig: JSON` | Schema presence does not prove runtime scaling semantics |
| Environment patch | `environmentPatchCommit`, `environmentPatchCommitStaged`, `environmentPatchRestage` | Discover patch shape and service scoping before implementing writes |

The future implementation should inspect additional configuration and deployment
state as needed. Do not assume the nullable `numReplicas` field describes all
regional replica layouts. Do not commit all staged environment changes blindly.

## Documentation cross-check

- [Public API](https://docs.railway.com/integrations/api): GraphQL endpoint,
  authentication, errors and rate limits. Project tokens use
  `Project-Access-Token`; account/workspace tokens use `Authorization: Bearer`.
- [Manage services](https://docs.railway.com/integrations/api/manage-services):
  service instance reads and updates are documented operations.
- [Scaling](https://docs.railway.com/deployments/scaling): vertical autoscaling and
  configurable horizontal replicas are distinct. Dashboard metrics aggregate
  replicas, so raw usage must not be treated as a utilization percentage.
- [CLI scale](https://docs.railway.com/cli/scale): the current CLI uses an environment
  patch flow and commits replica configuration without a separate redeploy.

The older instance-update examples and the current CLI patch flow are both
relevant evidence. This scaffold does not choose an untested mutation strategy.
The pending task must resolve the current supported path and verify it in an
isolated service before claiming actual integration behavior.

## Still unverified

Token-specific permissions and plan restrictions; data freshness and actual units;
regional JSON shape; safe patch merging; mutation effects; staged versus applied
settings; drain/startup timing; running replica convergence; rate-limit responses;
and how infrastructure configuration interacts with dynamic replica ownership.
No claim of load capacity or production readiness is made. The simulator uses
synthetic normalized utilization and never sends GraphQL requests.
