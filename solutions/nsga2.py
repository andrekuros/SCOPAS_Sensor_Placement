"""
NSGA-II solution runner.
run(config) -> (population, results).
"""

import sys
from pathlib import Path

# Ensure src is on path when running as script or from run_framework
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
if str(_root / "src") not in sys.path:
    sys.path.insert(0, str(_root / "src"))

from scopas_core import load_config, load_environment_from_config, evaluate_solution
from genetic_algorithm import SensorNetworkGAGeoJSON
from deap_base import setup_multi_objective_creator


def run(config: dict, config_path: str = None, base_dir: Path = None) -> tuple:
    """
    Run NSGA-II and return (population, results).
    population: list of solutions (each = list of {"type", "x", "y", "z"}).
    results: list of {"coverage", "redundancy", "cost", "num_sensors"}.
    When config.optimization.objectives is "coop_only" or "noncoop_only",
    optimizes (M_wp_*, cost) only (2 objectives). Default is dual_layer (3 objectives).
    """
    if base_dir is None:
        base_dir = Path.cwd()
    if config_path is None:
        config_path = ""
    # Set DEAP creator for 2 objectives (single-layer + cost) or 3 (coop, noncoop, cost)
    objective_mode = config.get("optimization", {}).get("objectives", "dual_layer")
    if objective_mode in {"coop_only", "noncoop_only"}:
        setup_multi_objective_creator((1.0, -1.0), force=True)  # maximize M_wp_* , minimize cost
    else:
        setup_multi_objective_creator((1.0, 1.0, -1.0), force=False)
    env = load_environment_from_config(config, base_dir=base_dir)
    ga_config = config.get("pareto_search", {})
    population_size = ga_config.get("n_samples", 100)
    generations = ga_config.get("generations", 50)
    min_sensors = ga_config.get("min_sensors", 3)
    max_sensors = ga_config.get("max_sensors", 15)
    n_cores = ga_config.get("n_cores", 1)

    ga = SensorNetworkGAGeoJSON(
        environment=env,
        max_sensors=max_sensors,
        min_sensors=min_sensors,
        weights=(1.0, 1.0, 0.001),
        n_cores=n_cores,
        config=config,
    )
    ck = config.get("checkpoint", {}) or {}
    checkpoint_dir = None
    checkpoint_frequency = 1
    resume = False
    checkpoint_prefix = config.get("experiment_name", "exp").replace(" ", "_")
    if ck.get("enabled") and ck.get("dir"):
        p = Path(ck["dir"])
        base = Path.cwd() if base_dir is None else Path(base_dir)
        checkpoint_dir = str(p) if p.is_absolute() else str(base / p)
        checkpoint_frequency = max(1, int(ck.get("frequency", 2)))
        resume = bool(ck.get("resume", False))
        checkpoint_prefix = ck.get("prefix", checkpoint_prefix)
    ga_result = ga.run_evolution(
        population_size=population_size,
        generations=generations,
        verbose=True,
        show_progress=True,
        checkpoint_dir=checkpoint_dir,
        checkpoint_prefix=checkpoint_prefix,
        checkpoint_frequency=checkpoint_frequency,
        resume=resume,
        algorithm="nsga2",
    )
    pareto_front = ga_result.get("pareto_front", [])
    sensor_types_config = config.get("sensors", {}).get("types", {})

    population = [ga.individual_to_sensor_list(ind) for ind in pareto_front]
    results = []
    for sol in population:
        res = evaluate_solution(env, sol, sensor_types_config, config=config)
        results.append(res)
    logbook = ga_result.get("logbook", [])
    return population, results, logbook
