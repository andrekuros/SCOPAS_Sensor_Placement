"""
Random Pareto search: sample random sensor deployments, evaluate, return Pareto front.
run(config) -> (population, results).
"""

import random
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
if str(_root / "src") not in sys.path:
    sys.path.insert(0, str(_root / "src"))

from scopas_core import load_environment_from_config, evaluate_solution


def _dominates(a: Dict, b: Dict) -> bool:
    """True if a dominates b (max coverage, max redundancy, min cost)."""
    better = (
        a["coverage"] >= b["coverage"]
        and a["redundancy"] >= b["redundancy"]
        and a["cost"] <= b["cost"]
    )
    strictly = (
        a["coverage"] > b["coverage"]
        or a["redundancy"] > b["redundancy"]
        or a["cost"] < b["cost"]
    )
    return better and strictly


def _pareto_front_indices(results: List[Dict]) -> List[int]:
    """Indices of results that are on the Pareto front."""
    n = len(results)
    is_pareto = [True] * n
    for i in range(n):
        for j in range(n):
            if i != j and _dominates(results[j], results[i]):
                is_pareto[i] = False
                break
    return [i for i in range(n) if is_pareto[i]]


def run(config: dict, config_path: str = None, base_dir: Path = None) -> Tuple[List[List[Dict]], List[Dict]]:
    """
    Random Pareto search: generate n_samples random deployments, evaluate, return Pareto set.
    Returns (population, results) where population/results are only Pareto solutions.
    """
    if base_dir is None:
        base_dir = Path.cwd()
    env = load_environment_from_config(config, base_dir=base_dir)
    sensor_types = list(config.get("sensors", {}).get("types", {}).keys())
    if not sensor_types:
        sensor_types = ["Radar", "RF", "EO", "Acoustic"]
    locations = env.get_sensor_locations()
    if not locations:
        return [], []
    ga_config = config.get("pareto_search", {})
    n_samples = ga_config.get("n_samples", 100)
    min_sensors = ga_config.get("min_sensors", 3)
    max_sensors = min(ga_config.get("max_sensors", 20), len(locations))
    sensor_types_config = config.get("sensors", {}).get("types", {})

    population = []
    results = []
    for _ in range(n_samples):
        n_sensors = random.randint(min_sensors, max_sensors)
        indices = random.sample(range(len(locations)), n_sensors)
        sol = []
        for idx in indices:
            loc = locations[idx]
            stype = random.choice(sensor_types)
            sol.append({"type": stype, "x": loc[0], "y": loc[1], "z": loc[2]})
        population.append(sol)
        res = evaluate_solution(env, sol, sensor_types_config)
        results.append(res)

    front_idx = _pareto_front_indices(results)
    population = [population[i] for i in front_idx]
    results = [results[i] for i in front_idx]
    return population, results
