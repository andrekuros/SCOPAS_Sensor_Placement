"""
Abstract base for solution runners.
run(config) -> (population, results).
population: list of solutions, each solution = list of {"type", "x", "y", "z"}.
results: list of {"coverage", "redundancy", "cost", "num_sensors"} (one per solution).
"""

from pathlib import Path
from typing import List, Dict, Any, Tuple


def run(config: Dict[str, Any], **kwargs) -> Tuple[List[List[Dict]], List[Dict[str, Any]]]:
    """
    Placeholder base implementation; override in nsga2, nsga3, random_search.
    Returns (population, results) where population is list of sensor deployments,
    results is list of evaluation dicts.
    """
    raise NotImplementedError("Use solutions.nsga2.run, solutions.nsga3.run, or solutions.random_search.run")
