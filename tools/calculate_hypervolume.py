#!/usr/bin/env python3
"""
Calculate hypervolume indicator for Pareto fronts.
Supports:
  - 3 objectives: dual-layer (M_wp_coop, M_wp_noncoop, cost)
  - 2 objectives: single-layer (coop_only or noncoop_only) vs cost
Usage: python tools/calculate_hypervolume.py --results results/exp/run_id/
"""

import sys
from pathlib import Path
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "src"))

import json
import numpy as np
import argparse


def _resolve_results_file(results_arg):
    p = Path(results_arg)
    if p.is_file():
        return p
    for name in ["pareto_results.json", "pareto_front.json"]:
        f = p / name
        if f.exists():
            return f
    raise FileNotFoundError(f"No results in {p}")


def calculate_hypervolume_2d(pareto_front, reference_point):
    """Pareto front: (obj1 maximize, obj2 minimize). reference_point = (ref_obj1, ref_obj2)."""
    if not pareto_front:
        return 0.0
    normalized = [[-p[0], p[1]] for p in pareto_front]
    ref = [-reference_point[0], reference_point[1]]
    volumes = []
    for point in normalized:
        diff = np.array(ref) - np.array(point)
        if np.all(diff > 0):
            volumes.append(np.prod(diff))
    return sum(volumes) if volumes else 0.0


def calculate_hypervolume_3d(pareto_front, reference_point):
    if not pareto_front:
        return 0.0
    normalized = [[-p[0], -p[1], p[2]] for p in pareto_front]
    ref = [-reference_point[0], -reference_point[1], reference_point[2]]
    volumes = []
    for point in normalized:
        diff = np.array(ref) - np.array(point)
        if np.all(diff > 0):
            volumes.append(np.prod(diff))
    return sum(volumes) if volumes else 0.0


def calculate_hypervolume_from_results(results_file, config=None):
    p = Path(results_file)
    if config is None and p.parent.is_dir():
        config_path = p.parent / "config.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
    objective_mode = (config or {}).get("optimization", {}).get("objectives", "dual_layer")
    single_layer = objective_mode in {"noncoop_only", "coop_only"}

    with open(results_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        solutions = data
    else:
        solutions = data.get("pareto_solutions", [])
    if not solutions:
        return None
    pareto_front = []
    for sol in solutions:
        fitness = sol.get("fitness", [])
        if objective_mode == "noncoop_only" and ("M_wp_noncoop" in sol and "cost" in sol):
            pareto_front.append((float(sol["M_wp_noncoop"]), float(sol["cost"])))
        elif objective_mode == "coop_only" and ("M_wp_coop" in sol and "cost" in sol):
            pareto_front.append((float(sol["M_wp_coop"]), float(sol["cost"])))
        elif single_layer and len(fitness) == 2:
            pareto_front.append((float(fitness[0]), float(fitness[1]) * 100000.0))
        elif len(fitness) >= 3:
            pareto_front.append((fitness[0], fitness[1], fitness[2]))
        elif "coverage" in sol and "redundancy" in sol and "cost" in sol:
            pareto_front.append((sol["coverage"], sol["redundancy"], sol["cost"]))
    if not pareto_front:
        return None
    if single_layer and len(pareto_front[0]) == 2:
        ref_c = max(0, min(p[0] for p in pareto_front) - 0.05)
        ref_cost = max(p[1] for p in pareto_front) + 10000
        ref_point = (ref_c, ref_cost)
        hv = calculate_hypervolume_2d(pareto_front, ref_point)
        max_vol = (max(p[0] for p in pareto_front) - ref_c) * (ref_cost - min(p[1] for p in pareto_front))
        return {
            "hypervolume": hv,
            "normalized_hypervolume": hv / max_vol if max_vol > 0 else 0,
            "pareto_size": len(pareto_front),
            "reference_point": ref_point,
            "objectives": objective_mode,
        }
    ref_c = min(p[0] for p in pareto_front) - 0.1
    ref_r = min(p[1] for p in pareto_front) - 0.1
    ref_cost = max(p[2] for p in pareto_front) + 10000
    ref_point = (ref_c, ref_r, ref_cost)
    hv = calculate_hypervolume_3d(pareto_front, ref_point)
    max_vol = (pareto_front[0][0] - ref_c) * (pareto_front[0][1] - ref_r) * (ref_cost - pareto_front[0][2])
    return {
        "hypervolume": hv,
        "normalized_hypervolume": hv / max_vol if max_vol > 0 else 0,
        "pareto_size": len(pareto_front),
        "reference_point": ref_point,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=str, required=True, help="Results JSON file or results dir")
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()
    results_file = _resolve_results_file(args.results)
    result = calculate_hypervolume_from_results(results_file)
    if result:
        print(f"Hypervolume: {result['hypervolume']:.6f}")
        print(f"Normalized: {result['normalized_hypervolume']:.4f}")
        print(f"Pareto size: {result['pareto_size']}")
        if args.output:
            Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(f"Saved to {args.output}")
    else:
        print("Failed to calculate hypervolume")


if __name__ == "__main__":
    main()
