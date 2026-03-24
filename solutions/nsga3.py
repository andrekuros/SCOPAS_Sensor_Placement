"""
NSGA-III solution runner.
run(config) -> (population, results).
"""

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
if str(_root / "src") not in sys.path:
    sys.path.insert(0, str(_root / "src"))

from muscat_core import load_config, load_environment_from_config, evaluate_solution
from genetic_algorithm import SensorNetworkGAGeoJSON


def run(config: dict, config_path: str = None, base_dir: Path = None) -> tuple:
    """
    Run NSGA-III and return (population, results).
    population: list of solutions (each = list of {"type", "x", "y", "z"}).
    results: list of {"coverage", "redundancy", "cost", "num_sensors"}.
    """
    if base_dir is None:
        base_dir = Path.cwd()
    ga_config = config.get("pareto_search", {})
    env = load_environment_from_config(config, base_dir=base_dir)
    population_size = ga_config.get("n_samples", 100)
    generations = ga_config.get("generations", 50)
    min_sensors = ga_config.get("min_sensors", 3)
    max_sensors = ga_config.get("max_sensors", 15)
    n_cores = ga_config.get("n_cores", 1)
    nsga3_ref_p = ga_config.get("nsga3_ref_p", 6)

    ga = SensorNetworkGAGeoJSON(
        environment=env,
        max_sensors=max_sensors,
        min_sensors=min_sensors,
        weights=(1.0, 1.0, 0.001),
        n_cores=n_cores,
        config=config,
    )
    ga_result = ga.run_evolution(
        population_size=population_size,
        generations=generations,
        verbose=True,
        show_progress=True,
        checkpoint_dir=None,
        algorithm="nsga3",
        nsga3_ref_p=nsga3_ref_p,
    )
    pareto_front = ga_result.get("pareto_front", [])
    sensor_types_config = config.get("sensors", {}).get("types", {})

    population = [ga.individual_to_sensor_list(ind) for ind in pareto_front]
    results = []
    for sol in population:
        res = evaluate_solution(env, sol, sensor_types_config)
        results.append(res)
    return population, results
