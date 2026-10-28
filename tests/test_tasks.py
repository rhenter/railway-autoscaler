from unittest.mock import Mock, patch

from railway_autoscaler.autoscaling.reconciliation import ReconciliationResult
from railway_autoscaler.tasks import reconcile


def test_reconcile_processes_each_enabled_target():
    targets = [Mock(pk=1), Mock(pk=2)]
    results = [
        ReconciliationResult(1, "run-1", 1, 1, "unchanged", "unchanged"),
        ReconciliationResult(2, "run-2", 1, 2, "high", "preview"),
    ]
    queryset = Mock()
    queryset.select_related.return_value = targets

    with (
        patch(
            "railway_autoscaler.tasks.AutoscalingTarget.objects.filter",
            return_value=queryset,
        ) as query,
        patch("railway_autoscaler.tasks.CredentialService"),
        patch("railway_autoscaler.tasks._reconcile_target", side_effect=results) as run_target,
    ):
        assert reconcile.run() == [result.__dict__ for result in results]

    query.assert_called_once_with(enabled=True)
    queryset.select_related.assert_called_once_with("credential", "policy")
    assert run_target.call_args_list[0].args[0] is targets[0]
    assert run_target.call_args_list[1].args[0] is targets[1]
