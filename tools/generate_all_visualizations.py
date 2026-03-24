#!/usr/bin/env python3
"""
Generate all visualizations for a results directory (no optimization run).

  python tools/generate_all_visualizations.py --results results/point_defense_airport_sjc/airport_run_noncoop_only/

Produces:
  - Pareto 2D/3D (pareto_front.png, pareto_front_3d.png)
  - Evolution/convergence (evolution_convergence.png) if evolution_logbook.json exists
  - Best solution 3D (best_solution_3d.json)
  - Cesium export (cesium_data.json)
  - Coverage maps (coverage_maps/)
  - 2D overview (overview_2d.png)
  - Hypervolume (hypervolume.json)
"""

import sys
import subprocess
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(cmd, cwd=None):
    cwd = cwd or ROOT
    print(f"  >>> {' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=cwd)
    if r.returncode != 0:
        sys.exit(r.returncode)


def main():
    parser = argparse.ArgumentParser(description="Generate all visualizations for a results dir")
    parser.add_argument("--results", type=str, required=True, help="Results directory (e.g. results/.../airport_run/)")
    parser.add_argument("--no-evolution", action="store_true", help="Skip evolution/convergence plot")
    args = parser.parse_args()

    results_dir = Path(args.results).resolve()
    if not results_dir.is_dir():
        print(f"Results dir not found: {results_dir}")
        sys.exit(1)

    py = sys.executable
    print("=" * 60)
    print("Generating all visualizations")
    print("=" * 60)

    print("\n[1/7] Pareto 2D and 3D...")
    run([py, "tools/plot_pareto_from_results.py", "--results", str(results_dir)])

    print("\n[2/7] Evolution convergence (if logbook present)...")
    if not args.no_evolution and (results_dir / "evolution_logbook.json").exists():
        run([py, "tools/generate_convergence_plots.py", "--results", str(results_dir)])
    else:
        print("  (skipped: no evolution_logbook.json or --no-evolution)")

    print("\n[3/7] Best solution 3D export...")
    run([py, "tools/export_best_solution_3d.py", "--results", str(results_dir)])

    print("\n[4/7] Cesium export...")
    run([py, "tools/export_for_cesium.py", "--results", str(results_dir)])

    print("\n[5/7] Coverage maps...")
    run([py, "tools/visualize_pareto_solutions.py", "--results", str(results_dir)])

    print("\n[6/7] 2D overview...")
    run([py, "tools/generate_2d_overview.py", "--results", str(results_dir)])

    print("\n[7/7] Hypervolume...")
    hv_out = results_dir / "hypervolume.json"
    run([py, "tools/calculate_hypervolume.py", "--results", str(results_dir), "--output", str(hv_out)])

    print("\n" + "=" * 60)
    print("Done. Outputs in:", results_dir)
    print("  - pareto_front.png, pareto_front_3d.png")
    print("  - evolution_convergence.png (if logbook was saved)")
    print("  - best_solution_3d.json, cesium_data.json")
    print("  - coverage_maps/, overview_2d.png, hypervolume.json")
    print("=" * 60)


if __name__ == "__main__":
    main()
