#!/usr/bin/env python3
"""
SCOPAS – Run a complete experiment: optimization + all visualizations and analysis.

Usage:
  python run_experiment.py --config configs/point_defense_airport_sjc.json
  python run_experiment.py --config configs/city_allocation_assets.json --skip-3d
  python run_experiment.py --config configs/point_defense_airport_sjc_noncoop_only.json --mode nsga2
  python run_experiment.py --config configs/point_defense_airport_sjc.json --split-objectives

This replaces the individual run_airport_*.py scripts with a single generic entry point.
"""

import json
import subprocess
import sys
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parent


def run(cmd, cwd=None):
    cwd = cwd or ROOT
    print(f"\n>>> {' '.join(cmd)}\n", flush=True)
    r = subprocess.run(cmd, cwd=cwd)
    if r.returncode != 0:
        print(f"Command failed with exit code {r.returncode}", flush=True)
        sys.exit(r.returncode)


def run_analysis_pipeline(results_dir: Path, experiment_name: str, skip_3d: bool):
    step = 2

    print(f"\n[{step}] Pareto 2D/3D plots...", flush=True)
    run([sys.executable, "tools/plot_pareto_from_results.py", "--results", str(results_dir)])
    step += 1

    print(f"\n[{step}] Coverage maps...", flush=True)
    run([sys.executable, "tools/visualize_pareto_solutions.py", "--results", str(results_dir)])
    step += 1

    print(f"\n[{step}] 2D overview...", flush=True)
    run([sys.executable, "tools/generate_2d_overview.py", "--results", str(results_dir)])
    step += 1

    if not skip_3d:
        print(f"\n[{step}] 3D export...", flush=True)
        run([sys.executable, "tools/export_best_solution_3d.py", "--results", str(results_dir)])
        step += 1
        print(f"\n[{step}] Cesium export...", flush=True)
        run([sys.executable, "tools/export_for_cesium.py", "--results", str(results_dir)])
        step += 1

    hv_out = results_dir / "hypervolume.json"
    print(f"\n[{step}] Hypervolume...", flush=True)
    run([sys.executable, "tools/calculate_hypervolume.py", "--results", str(results_dir), "--output", str(hv_out)])
    step += 1

    print(f"\n[{step}] Convergence plot...", flush=True)
    run([sys.executable, "tools/generate_convergence_plots.py",
         "--results", str(results_dir), "--experiment-name", experiment_name])
    step += 1

    print(f"\n[{step}] Coverage by flight level...", flush=True)
    run([sys.executable, "tools/analyze_flight_levels.py", "--results", str(results_dir)])
    step += 1

    print(f"\n[{step}] Cost vs coverage level...", flush=True)
    run([sys.executable, "tools/analyze_coverage_levels.py", "--results", str(results_dir), "--dual-layer"])


def find_results_dir(config):
    """Find the most recent results subdirectory for this experiment."""
    results_base = Path(config.get("output", {}).get("results_dir", "results"))
    experiment_name = config.get("experiment_name", "experiment")
    results_root = ROOT / "results" / experiment_name
    if not results_root.exists():
        return None
    subdirs = sorted(results_root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for d in subdirs:
        if d.is_dir() and any(d.glob("*.json")):
            return d
    return None


def main():
    parser = argparse.ArgumentParser(description="SCOPAS – Run complete experiment")
    parser.add_argument("--config", required=True, help="Config JSON file")
    parser.add_argument("--mode", default="nsga2", choices=["nsga2", "nsga3", "random"],
                        help="Optimization algorithm (default: nsga2)")
    parser.add_argument("--skip-optimization", action="store_true",
                        help="Skip optimization, only run analysis on existing results")
    parser.add_argument("--skip-3d", action="store_true",
                        help="Skip 3D/Cesium exports")
    parser.add_argument("--split-objectives", action="store_true",
                        help="Run two optimizations: coop_only and noncoop_only, each with full analysis.")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        config_path = ROOT / args.config
    if not config_path.exists():
        print(f"Config not found: {args.config}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    experiment_name = config.get("experiment_name", "experiment")

    print("=" * 60, flush=True)
    print(f"SCOPAS – {experiment_name}", flush=True)
    print(f"Config: {config_path.name}", flush=True)
    print(f"Mode: {args.mode}", flush=True)
    print("=" * 60, flush=True)

    results_dirs = []
    if args.split_objectives:
        objective_profiles = [("coop_only", "coop"), ("noncoop_only", "noncoop")]
        for profile, suffix in objective_profiles:
            print(f"\n[1] Running {args.mode.upper()} optimization ({profile})...", flush=True)
            if not args.skip_optimization:
                run([
                    sys.executable, "run_framework.py", "--config", str(config_path), "--mode", args.mode,
                    "--objective-profile", profile, "--run-id-suffix", suffix
                ])
            results_dir = find_results_dir(config)
            if results_dir is None:
                print(f"No results directory found for profile {profile}.", flush=True)
                sys.exit(1)
            print(f"\nResults dir ({profile}): {results_dir}", flush=True)
            run_analysis_pipeline(results_dir, f"{experiment_name}_{profile}", args.skip_3d)
            results_dirs.append((profile, results_dir))
    else:
        if not args.skip_optimization:
            print(f"\n[1] Running {args.mode.upper()} optimization...", flush=True)
            run([sys.executable, "run_framework.py", "--config", str(config_path), "--mode", args.mode])

        results_dir = find_results_dir(config)
        if results_dir is None:
            print("No results directory found. Run optimization first.", flush=True)
            sys.exit(1)
        print(f"\nResults dir: {results_dir}", flush=True)
        run_analysis_pipeline(results_dir, experiment_name, args.skip_3d)
        results_dirs.append(("default", results_dir))

    # Summary
    print("\n" + "=" * 60, flush=True)
    print(f"Done: {experiment_name}", flush=True)
    for profile, res_dir in results_dirs:
        print(f"Results ({profile}): {res_dir}", flush=True)
    print("Outputs:", flush=True)
    print("  pareto_front.png / pareto_front_3d.png", flush=True)
    print("  coverage_maps/", flush=True)
    print("  overview_2d.png", flush=True)
    print("  evolution_convergence.png", flush=True)
    print("  coverage_by_flight_level.png", flush=True)
    print("  cost_vs_coverage_level.png", flush=True)
    print("  hypervolume.json", flush=True)
    if not args.skip_3d:
        print("  best_solution_3d.json / cesium_data.json", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
