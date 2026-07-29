#!/usr/bin/env python3
"""
Pareto front visualization: coverage and redundancy maps for selected solutions.
Reads from results folder (pareto_results.json or pareto_front.json + config.json).

Heatmaps use upsampling + large colormap LUT for smooth PNGs (display-only; metrics use the voxel grid).

Usage:
  python tools/visualize_pareto_solutions.py --results results/experiment_name/run_id/
  python tools/visualize_pareto_solutions.py --results results/.../pareto_results.json --config configs/...
"""

import sys
from pathlib import Path
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "src"))

import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import argparse
import random

from environment import UrbanEnvironment
from sensors import RadarSensor, RFSensor, EOSensor, AcousticSensor
from network_evaluation import NetworkEvaluator
from visualization import (
    prepare_detection_probability_display,
    prepare_redundancy_sum_display,
    upsample_scalar_field_2d,
    heatmap_colormaps,
)


def _resolve_results_and_config(results_arg):
    """Resolve --results (file or dir) to (results_path, config)."""
    p = Path(results_arg)
    if p.is_file():
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        config = data.get("config")
        if not config and (p.parent / "config.json").exists():
            with open(p.parent / "config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
        return p, data, config
    # Directory: look for pareto_results.json or pareto_front.json + config.json
    pareto_file = p / "pareto_results.json"
    if pareto_file.exists():
        with open(pareto_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        config = data.get("config") or json.loads((p / "config.json").read_text(encoding="utf-8"))
        return pareto_file, data, config
    pareto_file = p / "pareto_front.json"
    config_file = p / "config.json"
    if pareto_file.exists() and config_file.exists():
        with open(pareto_file, "r", encoding="utf-8") as f:
            list_results = json.load(f)
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
        # Convert to legacy format: pareto_solutions with sensor_configuration, Mc, redundancy, cost, sensor_positions
        data = {"pareto_solutions": []}
        for r in list_results:
            sensors_list = r.get("sensors", [])
            config_by_type = {}
            for s in sensors_list:
                t = s.get("type", "Unknown")
                config_by_type[t] = config_by_type.get(t, 0) + 1
            data["pareto_solutions"].append({
                "sensor_configuration": config_by_type,
                "sensor_positions": sensors_list,
                "Mc": r.get("coverage", 0.0),
                "redundancy": r.get("redundancy", 0.0),
                "cost": r.get("cost", 0.0),
                "num_sensors": r.get("num_sensors", 0),
            })
        return pareto_file, data, config
    raise FileNotFoundError(f"No pareto_results.json or pareto_front.json+config.json in {p}")


def load_pareto_results(results_file):
    with open(results_file, "r", encoding="utf-8") as f:
        return json.load(f)


def decode_solution(solution, sensor_locations, sensor_types_config):
    """Build sensor list from solution (sensor_configuration + locations or sensor_positions/sensors)."""
    pos = solution.get("sensor_positions") or solution.get("sensors")
    if pos:
        from sensors import create_sensor_from_config
        sensors = []
        for s in pos:
            stype = s.get("type")
            loc = (float(s["x"]), float(s["y"]), float(s["z"]))
            cfg = sensor_types_config.get(stype, {})
            sens = create_sensor_from_config(stype, loc, cfg)
            if "azimuth_deg" in s:
                sens.azimuth_deg = float(s["azimuth_deg"])
            sensors.append(sens)
        return sensors
    # Legacy: sensor_configuration counts + random locations
    sensors = []
    sensor_config = solution["sensor_configuration"]
    total_sensors = sum(sensor_config.values())
    if total_sensors > len(sensor_locations):
        selected_indices = list(range(len(sensor_locations)))
    else:
        seed = hash(str(sorted(sensor_config.items())))
        random.seed(seed)
        selected_indices = random.sample(range(len(sensor_locations)), total_sensors)
        random.seed()
    sensor_idx = 0
    for sensor_type, count in sorted(sensor_config.items()):
        type_config = sensor_types_config.get(sensor_type, {})
        cost = type_config.get("cost", 1.0)
        for _ in range(count):
            if sensor_idx >= len(selected_indices):
                break
            loc = sensor_locations[selected_indices[sensor_idx]]
            if sensor_type == "Radar":
                sensor = RadarSensor(location=loc, cost=cost)
                sensor.Pt = type_config.get("power_W", 1000.0)
                sensor.G = type_config.get("gain_dB", 30.0)
                sensor.frequency = type_config.get("frequency_Hz", 2.4e9)
                sensor.wavelength = 3e8 / sensor.frequency
            elif sensor_type == "RF":
                sensor = RFSensor(location=loc, cost=cost)
                sensor.sensitivity = type_config.get("sensitivity_dBm", -90.0)
                sensor.frequency = type_config.get("frequency_Hz", 900e6)
            elif sensor_type == "EO":
                sensor = EOSensor(location=loc, cost=cost)
            elif sensor_type == "Acoustic":
                sensor = AcousticSensor(location=loc, cost=cost)
                sensor.source_spl_dB = type_config.get("source_spl_dB", 80.0)
                sensor.max_range = type_config.get("max_range", 300.0)
            else:
                continue
            sensors.append(sensor)
            sensor_idx += 1
    return sensors


def select_solutions(pareto_solutions, criteria="diverse", max_budget=None, budget_criterion="M_wp_coop"):
    """Select solutions to visualize. If max_budget is set, filter by cost <= max_budget and pick best by budget_criterion."""
    if max_budget is not None:
        feasible = [s for s in pareto_solutions if s.get("cost", float("inf")) <= max_budget]
        if not feasible:
            feasible = pareto_solutions
        key = budget_criterion if budget_criterion in ("M_wp_coop", "M_wp_noncoop", "fused_resilience") else "M_wp_coop"
        if key == "fused_resilience":
            best = max(feasible, key=lambda x: x.get(key) or 0)
        else:
            best = max(feasible, key=lambda x: x.get(key) or 0)
        return [best]

    if criteria == "all":
        return pareto_solutions
    has_pd = any(s.get("M_wp_coop") is not None for s in pareto_solutions)
    if criteria == "extremes":
        if has_pd:
            return [
                min(pareto_solutions, key=lambda x: x["cost"]),
                max(pareto_solutions, key=lambda x: x.get("M_wp_coop") or 0),
                max(pareto_solutions, key=lambda x: x.get("fused_resilience") or 0),
            ]
        return [
            min(pareto_solutions, key=lambda x: x["cost"]),
            max(pareto_solutions, key=lambda x: x["Mc"]),
            max(pareto_solutions, key=lambda x: x["redundancy"]),
        ]
    if criteria == "balanced":
        if has_pd:
            balanced = [s for s in pareto_solutions if (s.get("M_wp_coop") or 0) > 0.75]
        else:
            balanced = [s for s in pareto_solutions if s["Mc"] > 0.80]
        balanced.sort(key=lambda x: x["cost"])
        return balanced[:5]
    if criteria == "diverse":
        sort_key = (lambda x: x.get("M_wp_coop") or 0) if has_pd else (lambda x: x["Mc"])
        sorted_sols = sorted(pareto_solutions, key=sort_key)
        n = len(sorted_sols)
        indices = [0, n // 4, n // 2, 3 * n // 4, n - 1]
        return [sorted_sols[i] for i in indices if i < n]
    return pareto_solutions[:5]


def _add_asset_overlay(ax, critical_assets):
    """Draw critical asset locations and protection_radius circles on axis."""
    if not critical_assets:
        return
    for a in critical_assets:
        loc = a.get("location")
        if not loc or len(loc) < 2:
            continue
        x, y = float(loc[0]), float(loc[1])
        r = float(a.get("protection_radius", 100))
        ax.scatter([x], [y], c="purple", s=120, marker="*", edgecolors="black", linewidth=1, zorder=11, label="Asset" if a == critical_assets[0] else "")
        circle = plt.Circle((x, y), r, fill=False, edgecolor="purple", linestyle="--", linewidth=1.2, alpha=0.7)
        ax.add_patch(circle)


def visualize_solution(
    env,
    evaluator,
    sensors,
    solution_info,
    output_file,
    critical_assets=None,
    *,
    coverage_scale="power",
    coverage_p_floor=1e-3,
    coverage_power_gamma=0.45,
    redundancy_gamma=0.5,
    heatmap_upsample=4,
    heatmap_zoom_order=1,
    colormap_lut_size=256,
):
    height_level = 1
    coverage_map = evaluator.get_coverage_map(sensors, height_level=height_level)
    redundancy_map = evaluator.get_redundancy_map(sensors, height_level=height_level)
    if heatmap_upsample > 1:
        zo = int(np.clip(heatmap_zoom_order, 1, 5))
        coverage_map = upsample_scalar_field_2d(
            coverage_map, heatmap_upsample, order=zo, clip_0_1=True
        )
        redundancy_map = upsample_scalar_field_2d(
            redundancy_map, heatmap_upsample, order=zo, clip_0_1=False
        )
        fin = np.isfinite(redundancy_map)
        redundancy_map[fin] = np.maximum(redundancy_map[fin], 0.0)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    try:
        plt.style.use("seaborn-v0_8-whitegrid")
    except Exception:
        pass
    cmap_coverage, cmap_redundancy = heatmap_colormaps(lut_size=int(colormap_lut_size))
    x_min, x_max = env.bounds[0], env.bounds[1]
    y_min, y_max = env.bounds[2], env.bounds[3]
    cov_disp, cov_norm, cov_cbar_label = prepare_detection_probability_display(
        coverage_map,
        scale=coverage_scale,
        p_floor=coverage_p_floor,
        power_gamma=coverage_power_gamma,
    )
    # Bicubic reduces visible voxel squares; upsampled grid supplies smooth samples.
    im1 = ax1.imshow(
        cov_disp.T,
        origin="lower",
        extent=[x_min, x_max, y_min, y_max],
        cmap=cmap_coverage,
        norm=cov_norm,
        alpha=0.8,
        interpolation="bicubic",
    )
    for _, building in env.buildings_df.iterrows():
        geom = building.geometry
        if geom.geom_type == "Polygon":
            ax1.add_patch(patches.Polygon(list(geom.exterior.coords), facecolor="gray", edgecolor="black", linewidth=0.5, alpha=0.4))
    _add_asset_overlay(ax1, critical_assets or [])
    type_color = {"Radar": "#c0392b", "EO": "#27ae60", "RF": "#2980b9", "Acoustic": "#d68910"}
    if sensors:
        for s in sensors:
            x, y, _ = s.location
            az = getattr(s, "azimuth_deg", 0.0)
            angle = 90.0 - az  # 0=East, 90=North -> triangle up=North
            stype = getattr(s, "sensor_type", "Radar")
            color = type_color.get(stype, "#7f8c8d")
            ax1.plot([x], [y], marker=(3, 0, angle), markersize=11, color=color, markeredgecolor="black", markeredgewidth=1.5, linestyle="", zorder=10)
        for stype, color in type_color.items():
            if any(getattr(s, "sensor_type", "") == stype for s in sensors):
                ax1.plot([], [], marker=(3, 0, 0), markersize=11, color=color, markeredgecolor="black", linestyle="", label=stype)
    ax1.set_xlim(x_min, x_max)
    ax1.set_ylim(y_min, y_max)
    ax1.set_xlabel("X (m)", fontsize=11)
    ax1.set_ylabel("Y (m)", fontsize=11)
    mc = solution_info.get("Mc", 0) or 0
    cfg = solution_info.get("sensor_configuration", {})
    title1 = f"Coverage (Mc = {mc*100:.1f}%)"
    if solution_info.get("M_wp_coop") is not None:
        title1 += f"\nM_wp coop: {solution_info['M_wp_coop']*100:.1f}%  noncoop: {(solution_info.get('M_wp_noncoop') or 0)*100:.1f}%"
    title1 += f"\n{len(sensors)} sensors: {cfg}"
    ax1.set_title(title1, fontsize=11)
    ax1.legend(loc="upper left", fontsize=9)
    ax1.grid(True, alpha=0.2)
    plt.colorbar(im1, ax=ax1, fraction=0.046, pad=0.04).set_label(cov_cbar_label)
    red_disp, red_norm, red_cbar_label = prepare_redundancy_sum_display(
        redundancy_map, gamma=redundancy_gamma
    )
    im2 = ax2.imshow(
        red_disp.T,
        origin="lower",
        extent=[x_min, x_max, y_min, y_max],
        cmap=cmap_redundancy,
        norm=red_norm,
        alpha=0.8,
        interpolation="bicubic",
    )
    for _, building in env.buildings_df.iterrows():
        geom = building.geometry
        if geom.geom_type == "Polygon":
            ax2.add_patch(patches.Polygon(list(geom.exterior.coords), facecolor="gray", edgecolor="black", linewidth=0.5, alpha=0.4))
    _add_asset_overlay(ax2, critical_assets or [])
    if sensors:
        for s in sensors:
            x, y, _ = s.location
            az = getattr(s, "azimuth_deg", 0.0)
            angle = 90.0 - az
            stype = getattr(s, "sensor_type", "Radar")
            color = type_color.get(stype, "#7f8c8d")
            ax2.plot([x], [y], marker=(3, 0, angle), markersize=11, color=color, markeredgecolor="black", markeredgewidth=1.5, linestyle="", zorder=10)
        for stype, color in type_color.items():
            if any(getattr(s, "sensor_type", "") == stype for s in sensors):
                ax2.plot([], [], marker=(3, 0, 0), markersize=11, color=color, markeredgecolor="black", linestyle="", label=stype)
    ax2.set_xlim(x_min, x_max)
    ax2.set_ylim(y_min, y_max)
    ax2.set_xlabel("X (m)", fontsize=11)
    ax2.set_ylabel("Y (m)", fontsize=11)
    cost = solution_info.get("cost", 0) or 0
    title2 = f"Redundancy = {solution_info.get('redundancy', 0):.2f}  Cost: ${cost:,.0f}"
    if solution_info.get("fused_resilience") is not None:
        title2 += f"\nFused resilience: {solution_info['fused_resilience']*100:.1f}%"
    ax2.set_title(title2, fontsize=11)
    ax2.legend(loc="upper left", fontsize=9)
    ax2.grid(True, alpha=0.2)
    plt.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04).set_label(red_cbar_label)
    plt.tight_layout()
    plt.savefig(output_file, dpi=200, bbox_inches="tight")
    plt.close()


def main():
    parser = argparse.ArgumentParser(description="Visualize Pareto solutions")
    parser.add_argument("--results", type=str, required=True, help="Results JSON file or results dir (e.g. results/exp/run_id/)")
    parser.add_argument("--config", type=str, default=None, help="Config JSON (optional if results dir has config.json)")
    parser.add_argument("--criteria", type=str, default="diverse", choices=["diverse", "extremes", "balanced", "all"])
    parser.add_argument("--max-budget", type=float, default=None, help="Pick best solution with cost <= this (overrides --criteria for selection)")
    parser.add_argument("--budget-best-criterion", type=str, default="M_wp_coop", choices=["M_wp_coop", "M_wp_noncoop", "fused_resilience"], help="When using --max-budget, maximize this metric among feasible solutions")
    parser.add_argument("--budgets", type=str, default=None, help="Comma-separated budgets (e.g. 150000,250000,400000) to generate one map per budget")
    parser.add_argument("--output-dir", type=str, default=None)
    parser.add_argument(
        "--coverage-scale",
        type=str,
        default="power",
        choices=["power", "log", "linear"],
        help="power (default): P**gamma to color, gamma<1 shrinks dark Pd>0.7 band; linear=raw Pd",
    )
    parser.add_argument(
        "--coverage-p-floor",
        type=float,
        default=1e-3,
        help="Floor for power/log scales (masked zeros unchanged)",
    )
    parser.add_argument(
        "--coverage-power-gamma",
        type=float,
        default=0.45,
        help="For scale=power: gamma<1 = less colormap wasted on Pd 0.8-1 (softer falloff); gamma>1 = emphasize strong Pd",
    )
    parser.add_argument(
        "--redundancy-gamma",
        type=float,
        default=0.5,
        help="PowerNorm on Pd-sum; gamma<1 similar to coverage (less solid dark core)",
    )
    parser.add_argument(
        "--heatmap-upsample",
        type=int,
        default=4,
        help="Upsample voxel grid before colormap (default 4): removes blocky cells in PNGs",
    )
    parser.add_argument(
        "--heatmap-zoom-order",
        type=int,
        default=1,
        help="scipy.ndimage.zoom order: 1=bilinear (default, gentle); 3=cubic (sharper, may ring)",
    )
    parser.add_argument(
        "--colormap-lut-size",
        type=int,
        default=256,
        help="Colormap LUT size (default 256) to avoid green banding from few discrete colors",
    )
    args = parser.parse_args()

    results_path, data, config = _resolve_results_and_config(args.results)
    if args.config:
        with open(args.config, "r", encoding="utf-8") as f:
            config = json.load(f)
    pareto_solutions = data["pareto_solutions"]
    base_dir = results_path.parent if results_path.is_file() else results_path
    env = UrbanEnvironment(
        buildings_geojson_path=str(Path.cwd() / config["environment"]["buildings_file"]),
        sensor_locations_geojson_path=str(Path.cwd() / config["environment"]["sensor_locations_file"]),
        voxel_resolution_m=config["environment"]["resolution"],
    )
    critical_assets = config.get("critical_assets", [])
    if critical_assets:
        env.generate_threat_map(critical_assets)
    evaluator = NetworkEvaluator(env)
    sensor_locations = env.get_sensor_locations()
    sensor_types_config = config.get("sensors", {}).get("types", {})

    if args.budgets:
        budget_list = [float(b.strip()) for b in args.budgets.split(",") if b.strip()]
        selected_list = []
        for b in budget_list:
            sel = select_solutions(pareto_solutions, max_budget=b, budget_criterion=args.budget_best_criterion)
            if sel:
                selected_list.append((b, sel[0]))
    elif args.max_budget is not None:
        selected = select_solutions(pareto_solutions, max_budget=args.max_budget, budget_criterion=args.budget_best_criterion)
        selected_list = [(args.max_budget, s) for s in selected]
    else:
        selected = select_solutions(pareto_solutions, criteria=args.criteria)
        selected_list = [(None, s) for s in selected]

    output_dir = Path(args.output_dir) if args.output_dir else base_dir / "coverage_maps"
    output_dir.mkdir(parents=True, exist_ok=True)
    for i, (budget, solution) in enumerate(selected_list, 1):
        sensors = decode_solution(solution, sensor_locations, sensor_types_config)
        if budget is not None:
            wp = (solution.get("M_wp_coop") or 0) * 100
            output_file = output_dir / f"solution_budget_{int(budget/1000)}k_Mwp{wp:.0f}.png"
        else:
            output_file = output_dir / f"solution_{i:02d}_Mc{(solution.get('Mc') or 0)*100:.0f}.png"
        visualize_solution(
            env,
            evaluator,
            sensors,
            solution,
            output_file,
            critical_assets=critical_assets,
            coverage_scale=args.coverage_scale,
            coverage_p_floor=args.coverage_p_floor,
            coverage_power_gamma=args.coverage_power_gamma,
            redundancy_gamma=args.redundancy_gamma,
            heatmap_upsample=args.heatmap_upsample,
            heatmap_zoom_order=args.heatmap_zoom_order,
            colormap_lut_size=args.colormap_lut_size,
        )
    print(f"Saved to {output_dir}/")


if __name__ == "__main__":
    main()
