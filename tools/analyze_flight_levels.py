#!/usr/bin/env python3
"""
Analyze coverage at different flight levels (airway altitudes).
Reports and plots Mc per altitude (20 m, 45 m, 65 m or config airway_altitudes).

Usage:
  python tools/analyze_flight_levels.py --results results/city_allocation_assets/city_allocation_assets_20260316_003018/
  python tools/analyze_flight_levels.py --results results/.../ --max-solutions 5 --output coverage_by_flight_level.png
"""

import sys
import json
import argparse
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "src"))

import numpy as np
import matplotlib.pyplot as plt

from environment import UrbanEnvironment
from network_evaluation import NetworkEvaluator
from scopas_core import load_environment_from_config


def load_solutions_and_config(results_path):
    p = Path(results_path)
    if p.is_file():
        data = json.loads(p.read_text(encoding="utf-8"))
        config_path = p.parent / "config.json"
    else:
        for name in ["evaluation_results.json", "pareto_front.json", "pareto_results.json"]:
            f = p / name
            if f.exists():
                data = json.loads(f.read_text(encoding="utf-8"))
                break
        else:
            raise FileNotFoundError(f"No results JSON in {p}")
        config_path = p / "config.json"
    if isinstance(data, list):
        rows = data
        config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    else:
        rows = data.get("pareto_solutions", data.get("evaluation_results", []))
        config = data.get("config") or (json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {})
    return rows, config, p if p.is_dir() else p.parent


def decode_solution(solution, sensor_types_config):
    from sensors import create_sensor_from_config
    pos = solution.get("sensor_positions") or solution.get("sensors")
    if not pos:
        return []
    sensors = []
    for s in pos:
        stype = s.get("type")
        loc = (float(s["x"]), float(s["y"]), float(s["z"]))
        cfg = sensor_types_config.get(stype, {})
        sens = create_sensor_from_config(stype, loc, cfg)
        if "azimuth_deg" in s:
            sens.azimuth_deg = float(s["azimuth_deg"])
        sens.is_active = True
        sensors.append(sens)
    return sensors


def mc_at_layer(coverage_map, occupancy_layer, threshold=0.8):
    """Mc at this height level: fraction of free voxels with coverage >= threshold."""
    valid = (occupancy_layer == 0) & (~np.isnan(coverage_map))
    valid_cells = coverage_map[valid]
    if valid_cells.size == 0:
        return 0.0
    return np.sum(valid_cells >= threshold) / valid_cells.size


def main():
    parser = argparse.ArgumentParser(description="Coverage per flight level (airway altitude)")
    parser.add_argument("--results", required=True, help="Results dir or JSON file")
    parser.add_argument("--max-solutions", type=int, default=3, help="Max number of solutions to analyze (default 3)")
    parser.add_argument("--output", default=None, help="Output PNG path")
    parser.add_argument("--threshold", type=float, default=0.8, help="Coverage threshold for Mc (default 0.8)")
    args = parser.parse_args()

    rows, config, base_dir = load_solutions_and_config(args.results)
    if not rows:
        print("No solutions found")
        return

    airway_altitudes = config.get("airway_altitudes", [20, 45, 65])
    env = load_environment_from_config(config, base_dir=_root)
    evaluator = NetworkEvaluator(env)
    sensor_types_config = config.get("sensors", {}).get("types", {})
    z_min = env.bounds[4]
    res = env.voxel_resolution
    nz = env.grid_shape[2]

    # Select solutions: first, one near middle, one near end (or by cost spread)
    n = min(args.max_solutions, len(rows))
    if n == len(rows):
        indices = list(range(n))
    else:
        indices = [0, len(rows) // 2, len(rows) - 1][:n]
    selected = [rows[i] for i in indices]

    print("Coverage (Mc) by flight level (free voxels only, threshold={:.0%})".format(args.threshold))
    print("=" * 60)

    results_per_solution = []
    for sol_idx, solution in enumerate(selected):
        sensors = decode_solution(solution, sensor_types_config)
        if not sensors:
            continue
        cost = solution.get("cost", 0)
        agg_mc = solution.get("coverage") or solution.get("M_wp_coop") or solution.get("Mc") or 0
        agg_mc = agg_mc * 100 if agg_mc <= 1 else agg_mc
        per_alt = []
        for alt in airway_altitudes:
            layer = int((alt - z_min) / res)
            layer = max(0, min(layer, nz - 1))
            cov_map = evaluator.get_coverage_map(sensors, height_level=layer)
            occ = env.occupancy_grid[:, :, layer]
            mc = mc_at_layer(cov_map, occ, args.threshold)
            per_alt.append((alt, mc * 100))
        results_per_solution.append((sol_idx + 1, cost, agg_mc, per_alt))
        print(f"Solution {sol_idx + 1}  (cost=${cost:,.0f}, aggregate Mc={agg_mc:.1f}%)")
        for alt, mc in per_alt:
            print(f"    {alt:5.0f} m  ->  Mc = {mc:.1f}%")
        print()

    if not results_per_solution:
        print("No valid solutions to plot")
        return

    # Plot: flight level (m) vs Mc (%)
    fig, ax = plt.subplots(figsize=(8, 5))
    for sol_idx, cost, agg_mc, per_alt in results_per_solution:
        alts = [a for a, _ in per_alt]
        mcs = [mc for _, mc in per_alt]
        ax.plot(alts, mcs, "o-", linewidth=2, markersize=8, label=f"Sol {sol_idx} (${cost/1000:.0f}k)")
    ax.set_xlabel("Flight level (m)")
    ax.set_ylabel("Coverage Mc (%)")
    ax.set_title("Coverage by flight level (per-altitude Mc)")
    ax.set_xticks(airway_altitudes)
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    out_file = Path(args.output) if args.output else base_dir / "coverage_by_flight_level.png"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_file, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved: {out_file}")


if __name__ == "__main__":
    main()
