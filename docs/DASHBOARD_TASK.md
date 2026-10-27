# Follow-up task: add a Django autoscaling status dashboard

Status: **not implemented**. Depends on the controller, database status and event
models described in [IMPLEMENTATION_TASK.md](IMPLEMENTATION_TASK.md).

## Goal

Let authorized operators inspect what the autoscaler last observed, decided and
applied, using persisted data rather than making Railway calls for every page view.

## Initial scope

- Add a Django view and template with a small JSON endpoint for periodic refresh.
  Start with simple polling, for example every five seconds. No WebSocket service,
  frontend framework or separate telemetry database is needed for the first version.
- Show the target, observed/desired replicas, active limits and mode, latest CPU and
  memory, decision reason, cooldown, pending operation, last attempt/success and
  collector/worker health. Distinguish preview, pending, confirmed and failed states.
- Display recent scaling events with time, previous and confirmed counts, reason,
  result and run ID. Use indexed, bounded queries and paginate history.
- Enforce Django authentication and an explicit view permission. Keep the dashboard
  read-only initially; no manual scaling buttons or arbitrary task execution.
- Hide credentials and raw provider errors. Validate all filters against permitted
  targets and apply the same authorization to the JSON endpoint as to the page.
- Read the database only. Do not run collection or scaling from request handlers.

## Freshness

UI polling frequency is separate from the Beat collection interval. A five-second
refresh cannot produce newer metrics than a sixty-second collection cycle. Display
sample time and last successful collection, flag stale data, and do not present a
stored replica count as a continuously verified live value.

## Acceptance criteria

- An authorized operator sees a confirmed scale change after the next refresh.
- Unauthorized users cannot read status, events, target identifiers or error details.
- Missing, stale, preview and pending data render clearly without claiming success.
- Refreshing the page does not issue Railway mutations, metric requests or Celery tasks.
- History is bounded and paginated; database query count stays controlled.
- Tests cover access control, stale data, pending/failed events and response content.

A read-only Django admin status/history view can precede this dashboard. Push updates
can be considered later if polling proves inadequate for the actual requirements.
