# Pending task: implement a safe Railway autoscaling reconciliation cycle

Status: **not implemented**. The simulator is only the starting baseline.

## Problem

Stateless HTTP services need extra replicas during sustained traffic peaks and
should return gradually to a baseline afterward. A single CPU spike must not
trigger repeated changes. Restarts, concurrent runs, missing metrics, and a lost
API response must not cause duplicate or destructive scaling.

Implement this in the independent Python package. Do not depend on any private
application or assume the example thresholds establish real capacity.

## Deliverable

Implement a bounded, one-shot `reconcile` command, suitable for invocation by an
external scheduler. Support one explicitly configured service/environment/region
per invocation. Reuse or evolve `MetricsProvider` and `RailwayAPI` where needed;
keep the existing offline `simulate` command working.

1. **Verify and implement Railway adapters.** Recheck the live schema first.
   Collect CPU and memory data and read observed replicas. Define sample windows,
   units and normalization against effective capacity, considering aggregation
   across replicas. Confirm the usable mutation, staged-change/apply semantics,
   and how desired versus running replicas can be distinguished. Preserve other
   regions and settings; reject unsupported layouts rather than silently changing
   them. Schema presence alone is not proof of runtime behavior.
2. **Implement sustained-load decisions.** Configure separate CPU/memory thresholds,
   upper and lower consecutive-sample counts, minimum, maximum, cooldown and data
   freshness. Require multiple high samples to scale up (CPU OR memory), and a
   longer run of low samples to scale down (CPU AND memory). Missing, stale or
   invalid data must block downscaling and reset the consecutive-sample counters.
   Increase or decrease by at most one replica per successful cycle. Repeated
   timestamps must not count as new samples. Document how window aggregation and
   sample cadence interact. Optional application metrics can remain future work.
3. **Persist and reconcile state.** Use Redis with an explicit dependency and a
   documented isolated local setup. Store service/environment/region, observed
   and desired counts, last processed timestamp, counters, last successful
   change, cooldown, pending operation and run ID. Use a bounded distributed
   lease and atomic state updates so concurrent invocations cannot issue a
   second write. Document lease renewal/expiry behavior. Do not rely on in-memory
   state or a local file for production correctness.
4. **Handle uncertainty safely.** Read before writing, skip when already converged,
   and verify after acceptance. Record intent before a mutation. If the outcome
   is ambiguous after a timeout, preserve it as pending and reread remote state
   before allowing another mutation. Cooldown must survive restarts and begin
   after a confirmed change. A second cycle must not treat accepted-but-not-yet-
   converged replicas as a new scaling opportunity. Fail closed on lock/storage
   failures or unexplained replica drift; explain manual recovery.
5. **Provide an operational entry point.** Default to dry-run; real mutations
   require an explicit `--apply` flag. Dry-run may read metrics, configuration and
   remote state, but must not mutate Railway or advance persistent scaling state.
   Use environment-only credentials, correct token headers, bounded HTTP timeouts,
   GraphQL error handling, rate-limit-aware backoff for safe reads, and no blind
   mutation retries. Log decisions as structured JSON without credentials or raw
   response bodies. Document who owns dynamic replica settings so infrastructure
   configuration does not overwrite them.

Choose simple components and make behavior explicit. No need for a web UI,
framework, daemon, generic plugin system or orchestration platform.

## Acceptance criteria

- CPU or memory sustained above configured thresholds raises capacity by one;
  a short spike does not. Low CPU and memory must persist longer before lowering.
- Minimum, maximum, freshness, cooldown and one-change-per-cycle rules hold.
- Duplicate samples and reruns cannot advance counters twice or repeat a mutation.
- A restarted process resumes cooldown and pending-operation reconciliation.
- Two competing invocations produce at most one replica write; lease expiry and
  storage failures do not enable conflicting writes.
- Tests cover HTTP 200 with GraphQL errors, auth rejection, 429/Retry-After,
  transient read errors, timeouts, ambiguous writes and delayed convergence.
- Tests verify normalized values from representative CPU/memory fixtures rather
  than assuming that Railway returns percentages.
- Dry-run emits a proposed decision and never invokes the mutation boundary.
- Unsupported regional layouts and unexpected replica drift fail with actionable
  messages, without overwriting configuration.
- Automated tests run without real Railway credentials; use fakes at I/O boundaries
  and a documented isolated Redis fixture for persistence/concurrency checks.
- Document API evidence, configuration, scheduling, recovery and rollback.
- Existing simulation examples and baseline checks continue to pass.

## Validation boundary

Offline fixtures prove controller logic, not actual Railway scaling. If an isolated
Railway service is available, add an opt-in smoke test that records observed state,
applies one bounded change, confirms convergence and restores the original count.
Keep it excluded from default tests. Never use an existing production service to
satisfy the task. If live access is unavailable, report that limitation explicitly.

## Out of scope

Queue-based scaling, Celery/RabbitMQ, database provisioning, multi-region scaling,
changing plans or resource limits, production deployment, load-testing private
applications, and guarantees for any particular number of users. An external
scheduler is enough; no scheduling service needs to be built in this task.

## Suggested evaluation prompt

> Implement the pending reconciliation task in docs/IMPLEMENTATION_TASK.md. Start
> by inspecting the scaffold and API evidence, then verify current API capabilities.
> Preserve the offline simulator, keep external access behind adapters, and leave
> validation reproducible. Run the documented checks and explain any integration
> behavior that remains unverified. Do not access private applications or production.
