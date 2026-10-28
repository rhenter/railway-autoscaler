import json
from pathlib import Path

import pytest

from railway_autoscaler.core.policy_types import Policy, Sample
from railway_autoscaler.core.simulation import simulate
from railway_autoscaler.offline.cli import main

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_example_replay_matches_reviewable_expected_output(capsys):
    assert main(["simulate", str(EXAMPLES / "scenario.json")]) == 0

    actual = json.loads(capsys.readouterr().out)
    expected = json.loads((EXAMPLES / "expected-output.json").read_text())
    assert actual == expected
    assert [row["desired_replicas"] for row in actual] == [2, 2, 3, 3, 3, 3, 2, 2, 1, 1]


def test_holds_do_not_extend_cooldown():
    result = simulate(
        Policy(max_replicas=5), 1, [Sample(0, 0.9), Sample(30, None), Sample(60, 0.9)]
    )

    assert [row["desired_replicas"] for row in result] == [2, 2, 3]


def test_each_replay_starts_with_fresh_state():
    samples = [Sample(0, 0.9), Sample(60, 0.1)]

    assert simulate(Policy(max_replicas=5), 1, samples) == simulate(
        Policy(max_replicas=5), 1, samples
    )


@pytest.mark.parametrize("times", [[10, 5], [10, 10]])
def test_unordered_or_duplicate_timestamps_are_rejected(times):
    with pytest.raises(ValueError, match="strictly increasing"):
        simulate(Policy(max_replicas=5), 1, [Sample(time, 0.5) for time in times])


def test_empty_input_returns_no_decisions():
    assert simulate(Policy(max_replicas=5), 1, []) == []


def test_invalid_initial_count_is_rejected_even_without_samples():
    with pytest.raises(ValueError):
        simulate(Policy(max_replicas=5), 6, [])


@pytest.mark.parametrize("document", ["{", "[]", "null", '{"policy": {}}'])
def test_bad_scenario_returns_cli_error(tmp_path, capsys, document):
    scenario = tmp_path / "invalid.json"
    scenario.write_text(document)

    with pytest.raises(SystemExit) as error:
        main(["simulate", str(scenario)])

    assert error.value.code == 2
    assert "invalid scenario" in capsys.readouterr().err


def test_missing_file_returns_cli_error(tmp_path):
    with pytest.raises(SystemExit) as error:
        main(["simulate", str(tmp_path / "missing.json")])

    assert error.value.code == 2
