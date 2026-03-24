#!/usr/bin/env python3
"""
SCOPAS Framework - unified CLI.
Modes: evaluate | nsga2 | nsga3 | random.

Usage:
  python run_framework.py --config configs/quick_test.json --mode nsga2
  python run_framework.py --config configs/... --mode evaluate --solutions-file solutions.json
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from muscat_core import load_config, run_evaluation, save_run_results, get_results_dir, make_run_id


def main():
    parser = argparse.ArgumentParser(description="SCOPAS Framework CLI")
    parser.add_argument("--config", required=True, help="Path to config JSON")
    parser.add_argument("--mode", choices=["evaluate", "nsga2", "nsga3", "random"], required=True)
    parser.add_argument("--solutions-file", default=None, help="For evaluate mode: JSON file with list of solutions")
    parser.add_argument("--output", default=None, help="Optional output JSON for results")
    parser.add_argument(
        "--objective-profile",
        choices=["as_config", "dual_layer", "coop_only", "noncoop_only"],
        default="as_config",
        help="Override optimization objectives profile (default: as_config).",
    )
    parser.add_argument(
        "--run-id-suffix",
        default="",
        help="Optional suffix appended to output.run_id for side-by-side experiment variants.",
    )
    args = parser.parse_args()

    base_dir = Path.cwd()
    config = load_config(args.config)
    if "optimization" not in config:
        config["optimization"] = {}
    if args.objective_profile != "as_config":
        config["optimization"]["objectives"] = args.objective_profile
    if args.run_id_suffix:
        if "output" not in config:
            config["output"] = {}
        base_run_id = config["output"].get("run_id")
        if base_run_id:
            config["output"]["run_id"] = f"{base_run_id}_{args.run_id_suffix}"
        else:
            exp_name = config.get("experiment_name", "experiment")
            config["output"]["run_id"] = f"{exp_name}_{args.run_id_suffix}"

    if args.mode == "evaluate":
        if not args.solutions_file:
            print("evaluate mode requires --solutions-file (JSON: list of solutions, each list of {type,x,y,z})")
            sys.exit(1)
        with open(args.solutions_file, "r", encoding="utf-8") as f:
            solutions = json.load(f)
        if not isinstance(solutions, list) or not solutions:
            print("solutions-file must be a non-empty list of solutions")
            sys.exit(1)
        results = run_evaluation(args.config, solutions, base_dir=base_dir)
        print("Evaluation results:")
        print(json.dumps(results, indent=2, default=str))
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, default=str)
        return

    if args.mode == "nsga2":
        from solutions.nsga2 import run as nsga2_run
        population, results, logbook = nsga2_run(config, config_path=args.config, base_dir=base_dir)
    elif args.mode == "nsga3":
        from solutions.nsga3 import run as nsga3_run
        population, results = nsga3_run(config, config_path=args.config, base_dir=base_dir)
        logbook = []
    elif args.mode == "random":
        from solutions.random_search import run as random_run
        population, results = random_run(config, config_path=args.config, base_dir=base_dir)
        logbook = []
    else:
        print("Unknown mode:", args.mode)
        sys.exit(1)

    print(f"Pareto front: {len(population)} solutions")
    # Standard results layout: results/{experiment_name}/{run_id}/
    out_dir = save_run_results(config, population, results, save_pareto=True)
    # Save evolution logbook for convergence plots (NSGA-II/III)
    if logbook:
        def _to_serializable(obj):
            import numpy as np
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, dict):
                return {k: _to_serializable(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [_to_serializable(x) for x in obj]
            return obj
        with open(out_dir / "evolution_logbook.json", "w", encoding="utf-8") as f:
            json.dump(_to_serializable(logbook), f, indent=2)
        print("Evolution logbook saved (for convergence plots)")
    print("Results saved to", out_dir)
    if args.output:
        with open(Path(args.output), "w", encoding="utf-8") as f:
            json.dump({"population": population, "results": results}, f, indent=2)
        print("Also saved to", args.output)


if __name__ == "__main__":
    main()
