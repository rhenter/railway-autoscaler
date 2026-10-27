"""Offline CLI. The only supported operation is simulate."""

import argparse
import json
from pathlib import Path

from railway_autoscaler.models import Policy, Sample
from railway_autoscaler.simulation import simulate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline Railway autoscaling policy simulator")
    commands = parser.add_subparsers(dest="command", required=True)
    simulation = commands.add_parser(
        "simulate", help="Replay synthetic metrics without network access"
    )
    simulation.add_argument("scenario", type=Path)
    args = parser.parse_args(argv)
    try:
        scenario = json.loads(args.scenario.read_text(encoding="utf-8"))
        policy = Policy(**scenario["policy"])
        samples = [Sample(**sample) for sample in scenario["samples"]]
        results = simulate(policy, scenario["initial_replicas"], samples)
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.error(f"invalid scenario: {error}")
    print(json.dumps(results, indent=2, allow_nan=False))
    return 0
