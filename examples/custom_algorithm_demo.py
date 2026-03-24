"""
Minimal example: custom optimizer calling SCOPAS as an objective function.

This script shows how an external algorithm can:
- load a config and environment,
- generate candidate sensor networks (here: simple random search),
- call scopas_core.evaluate_solution to get coverage / redundancy / cost,
- keep the best solution according to a custom criterion.

Run from the project root:

    python examples/custom_algorithm_demo.py --config configs/pareto_city_10x10_final.json
"""

import argparse
import sys
from pathlib import Path
from typing import List, Dict, Any
import random

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from scopas_core import load_config, load_environment_from_config, evaluate_solution  # type: ignore


def build_random_solution(
    env,
    sensor_types: List[str],
    min_sensors: int,
    max_sensors: int,
) -> List[Dict[str, Any]]:
    """Sample a random sensor network using environment sensor locations."""
    locations = env.get_sensor_locations()
    if not locations:
        return []
    n_sensors = random.randint(min_sensors, min(max_sensors, len(locations)))
    indices = random.sample(range(len(locations)), n_sensors)
    solution: List[Dict[str, Any]] = []
    for idx in indices:
        x, y, z = locations[idx]
        stype = random.choice(sensor_types)
        solution.append({"type": stype, "x": x, "y": y, "z": z})
    return solution


def main() -> None:
    parser = argparse.ArgumentParser(description="Custom algorithm demo using SCOPAS objective function")
    parser.add_argument("--config", required=True, help="Path to SCOPAS JSON config")
    parser.add_argument("--iterations", type=int, default=50, help="Number of random solutions to try")
    args = parser.parse_args()

    base_dir = ROOT
    config_path = Path(args.config)

    config = load_config(str(config_path))
    env = load_environment_from_config(config, base_dir=base_dir)
    sensor_types_config = config.get("sensors", {}).get("types", {})
    sensor_type_names = list(sensor_types_config.keys())
    if not sensor_type_names:
        sensor_type_names = ["Radar", "RF", "EO", "Acoustic"]

    search_cfg = config.get("pareto_search", {})
    min_sensors = int(search_cfg.get("min_sensors", 3))
    max_sensors = int(search_cfg.get("max_sensors", 15))

    best_sol: List[Dict[str, Any]] = []
    best_res: Dict[str, Any] = {}

    for i in range(args.iterations):
        sol = build_random_solution(env, sensor_type_names, min_sensors, max_sensors)
        if not sol:
            continue
        res = evaluate_solution(env, sol, sensor_types_config, config=config)
        # Example: maximize coverage, then minimize cost
        if not best_res:
            best_sol, best_res = sol, res
        else:
            better_coverage = res["coverage"] > best_res["coverage"]
            equal_coverage = abs(res["coverage"] - best_res["coverage"]) < 1e-6
            cheaper = res["cost"] < best_res["cost"]
            if better_coverage or (equal_coverage and cheaper):
                best_sol, best_res = sol, res
        print(f"[{i+1}/{args.iterations}] cov={res['coverage']:.3f} red={res['redundancy']:.3f} cost={res['cost']:.1f}")

    if best_res:
        print("\nBest solution found (custom criterion):")
        print(f"  coverage   = {best_res['coverage']:.3f}")
        print(f"  redundancy = {best_res['redundancy']:.3f}")
        print(f"  cost       = {best_res['cost']:.1f}")
        print(f"  num_sensors= {best_res['num_sensors']}")
    else:
        print("No valid solutions were evaluated.")


if __name__ == "__main__":
    main()

