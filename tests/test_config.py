import runpy
from pathlib import Path

import pytest

from railway_autoscaler.core.policy import evaluate
from railway_autoscaler.core.policy_types import Policy, Sample
from railway_autoscaler.offline.config import load_policy

MINIMUM = "RAILWAY_AUTOSCALER_MIN_REPLICAS"
MAXIMUM = "RAILWAY_AUTOSCALER_MAX_REPLICAS"
EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_default_policy_and_environment_limits_are_one():
    assert Policy().min_replicas == Policy().max_replicas == 1
    assert load_policy({}) == Policy()
    assert evaluate(load_policy({}), Sample(0, 1), 1).desired_replicas == 1


def test_explicit_limits_allow_scaling():
    policy = load_policy({MINIMUM: "2", MAXIMUM: "4"})

    assert policy.min_replicas == 2
    assert policy.max_replicas == 4
    assert evaluate(policy, Sample(0, 1), 2).desired_replicas == 3


def test_loads_process_environment(monkeypatch):
    monkeypatch.setenv(MINIMUM, "2")
    monkeypatch.setenv(MAXIMUM, "3")

    assert load_policy().min_replicas == 2
    assert load_policy().max_replicas == 3


def test_explicit_empty_mapping_does_not_read_process_environment(monkeypatch):
    monkeypatch.setenv(MAXIMUM, "10")

    assert load_policy({}).max_replicas == 1


@pytest.mark.parametrize("name", [MINIMUM, MAXIMUM])
@pytest.mark.parametrize("value", ["", "0", "-1", "1.5", "true", "not-a-number"])
def test_invalid_environment_limits_are_rejected(name, value):
    with pytest.raises(ValueError, match=name):
        load_policy({name: value})


def test_minimum_above_maximum_is_rejected():
    with pytest.raises(ValueError, match="min_replicas"):
        load_policy({MINIMUM: "3", MAXIMUM: "2"})


def test_django_settings_example_loads_environment_policy(monkeypatch):
    monkeypatch.setenv(MINIMUM, "1")
    monkeypatch.setenv(MAXIMUM, "4")

    namespace = runpy.run_path(str(EXAMPLES / "django_settings.py"))

    assert namespace["RAILWAY_AUTOSCALER_POLICY"] == load_policy({MINIMUM: "1", MAXIMUM: "4"})
