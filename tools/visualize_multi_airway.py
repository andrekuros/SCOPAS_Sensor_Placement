#!/usr/bin/env python3
"""
Multi-airway visualization: coverage at multiple altitudes (20m, 45m, 65m).
Reads from results folder. Usage: python tools/visualize_multi_airway.py --results results/exp/run_id/
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
from sensors import RadarSensor, RFSensor, EOSensor, AcousticSensor, create_sensor_from_config
from network_evaluation import NetworkEvaluator
from visualization import (
    prepare_detection_probability_display,
    upsample_scalar_field_2d,
    heatmap_colormaps,
)


def _resolve_results_and_config(results_arg):
    p = Path(results_arg)
    if p.is_file():
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        config = data.get("config")
        if not config and (p.parent / "config.json").exists():
            config = json.loads((p.parent / "config.json").read_text(encoding="utf-8"))
        return p, data, config
    for name in ["pareto_results.json", "pareto_front.json"]:
        f = p / name
        if f.exists():
            data = json.loads(f.read_text(encoding="utf-8"))
            if name == "pareto_front.json" and isinstance(data, list):
                config = json.loads((p / "config.json").read_text(encoding="utf-8"))
                out_sols = []
                for sol in data:
                    sens_list = sol.get("sensors", [])
                    cfg = {}
                    for s in sens_list:
                        t = s.get("type", "Unknown")
                        cfg[t] = cfg.get(t, 0) + 1
                    out_sols.append({"sensor_configuration": cfg, "sensor_positions": sens_list, "sensors": sens_list, "Mc": sol.get("coverage", 0), "redundancy": sol.get("redundancy", 0), "cost": sol.get("cost", 0)})
                data = {"pareto_solutions": out_sols}
            else:
                config = data.get("config") or json.loads((p / "config.json").read_text(encoding="utf-8"))
            return f, data, config
    raise FileNotFoundError(f"No pareto results in {p}")


def decode_solution(solution, sensor_locations, sensor_types_config):
    pos = solution.get("sensor_positions") or solution.get("sensors")
    if pos:
        return [create_sensor_from_config(s["type"], (s["x"], s["y"], s["z"]), sensor_types_config.get(s["type"], {})) for s in pos]
    sensors = []
    sensor_config = solution["sensor_configuration"]
    total = sum(sensor_config.values())
    seed = hash(str(sorted(sensor_config.items())))
    random.seed(seed)
    idx = random.sample(range(len(sensor_locations)), min(total, len(sensor_locations)))
    random.seed()
    si = 0
    for stype, count in sorted(sensor_config.items()):
        cfg = sensor_types_config.get(stype, {})
        cost = cfg.get("cost", 1.0)
        for _ in range(count):
            if si >= len(idx):
                break
            loc = sensor_locations[idx[si]]
            if stype == "Radar":
                s = RadarSensor(location=loc, cost=cost)
                s.Pt = cfg.get("power_W", 1000.0)
                s.G = cfg.get("gain_dB", 30.0)
                s.frequency = cfg.get("frequency_Hz", 2.4e9)
                s.wavelength = 3e8 / s.frequency
            elif stype == "RF":
                s = RFSensor(location=loc, cost=cost)
                s.sensitivity = cfg.get("sensitivity_dBm", -90.0)
                s.frequency = cfg.get("frequency_Hz", 900e6)
            elif stype == "EO":
                s = EOSensor(location=loc, cost=cost)
            elif stype == "Acoustic":
                s = AcousticSensor(location=loc, cost=cost)
                s.source_spl_dB = cfg.get("source_spl_dB", 80.0)
                s.max_range = cfg.get("max_range", 300.0)
            else:
                si += 1
                continue
            sensors.append(s)
            si += 1
    return sensors


def visualize_multi_airway(
    env,
    evaluator,
    sensors,
    solution_info,
    output_file,
    config,
    *,
    coverage_scale="power",
    coverage_p_floor=1e-3,
    coverage_power_gamma=0.45,
    heatmap_upsample=4,
    heatmap_zoom_order=1,
    colormap_lut_size=256,
):
    airway_altitudes = config.get("airway_altitudes", [20, 45, 65])
    n_airways = len(airway_altitudes)
    fig, axes = plt.subplots(1, n_airways, figsize=(18, 6))
    if n_airways == 1:
        axes = [axes]
    cmap, _ = heatmap_colormaps(lut_size=int(colormap_lut_size))
    x_min, x_max, y_min, y_max = env.grid_extent_xy()
    view_x0, view_x1 = float(env.bounds[0]), float(env.bounds[1])
    view_y0, view_y1 = float(env.bounds[2]), float(env.bounds[3])
    for idx, alt in enumerate(airway_altitudes):
        ax = axes[idx]
        layer = int((alt - env.bounds[4]) / env.voxel_resolution)
        layer = max(0, min(layer, env.grid_shape[2] - 1))
        cov = evaluator.get_coverage_map(sensors, height_level=layer)
        valid = cov[~np.isnan(cov)]
        Mc_layer = (np.sum(valid >= 0.8) / valid.size) if valid.size else 0.0
        if heatmap_upsample > 1:
            zo = int(np.clip(heatmap_zoom_order, 1, 5))
            cov = upsample_scalar_field_2d(cov, heatmap_upsample, order=zo, clip_0_1=True)
        cov_disp, cov_norm, _ = prepare_detection_probability_display(
            cov,
            scale=coverage_scale,
            p_floor=coverage_p_floor,
            power_gamma=coverage_power_gamma,
        )
        ax.imshow(
            cov_disp.T,
            origin="lower",
            extent=[x_min, x_max, y_min, y_max],
            cmap=cmap,
            norm=cov_norm,
            alpha=0.9,
            interpolation="nearest",
        )
        for _, b in env.buildings_df.iterrows():
            g = b.geometry
            if g.geom_type == "Polygon":
                ax.add_patch(patches.Polygon(list(g.exterior.coords), facecolor="#9aa0a6", edgecolor="black", linewidth=0.5, alpha=1.0, zorder=3))
        if sensors:
            xs, ys, _ = zip(*[s.location for s in sensors])
            ax.scatter(xs, ys, c="red", s=80, marker="^", edgecolors="black", linewidth=1.5, zorder=10)
        ax.set_xlim(view_x0, view_x1)
        ax.set_ylim(view_y0, view_y1)
        ax.set_xlabel("X (m)")
        ax.set_ylabel("Y (m)")
        ax.set_title(f"Airway {alt}m\nMc={Mc_layer*100:.1f}%")
        ax.grid(True, alpha=0.2)
    fig.suptitle(f"Coverage by airway - Mc={solution_info['Mc']*100:.1f}%, Cost=${solution_info['cost']:,.0f}", fontsize=14, y=1.02)
    plt.tight_layout()
    plt.savefig(output_file, dpi=200, bbox_inches="tight")
    plt.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=str, required=True)
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument(
        "--coverage-scale", type=str, default="power", choices=["power", "log", "linear"]
    )
    parser.add_argument("--coverage-p-floor", type=float, default=1e-3)
    parser.add_argument("--coverage-power-gamma", type=float, default=0.45)
    parser.add_argument("--heatmap-upsample", type=int, default=4)
    parser.add_argument("--heatmap-zoom-order", type=int, default=1)
    parser.add_argument("--colormap-lut-size", type=int, default=256)
    args = parser.parse_args()
    results_path, data, config = _resolve_results_and_config(args.results)
    if args.config:
        config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    base = results_path.parent if results_path.is_file() else results_path
    env = UrbanEnvironment(
        buildings_geojson_path=str(Path.cwd() / config["environment"]["buildings_file"]),
        sensor_locations_geojson_path=str(Path.cwd() / config["environment"]["sensor_locations_file"]),
        voxel_resolution_m=config["environment"]["resolution"],
    )
    evaluator = NetworkEvaluator(env)
    sensor_locations = env.get_sensor_locations()
    sensor_types_config = config.get("sensors", {}).get("types", {})
    solutions = data["pareto_solutions"][:3]
    output_dir = base / "multi_airway_maps"
    output_dir.mkdir(parents=True, exist_ok=True)
    for i, sol in enumerate(solutions):
        sensors = decode_solution(sol, sensor_locations, sensor_types_config)
        out = output_dir / f"solution_{i+1:02d}_multi_airway_Mc{sol['Mc']*100:.0f}.png"
        visualize_multi_airway(
            env,
            evaluator,
            sensors,
            sol,
            out,
            config,
            coverage_scale=args.coverage_scale,
            coverage_p_floor=args.coverage_p_floor,
            coverage_power_gamma=args.coverage_power_gamma,
            heatmap_upsample=args.heatmap_upsample,
            heatmap_zoom_order=args.heatmap_zoom_order,
            colormap_lut_size=args.colormap_lut_size,
        )
    print(f"Saved to {output_dir}/")


if __name__ == "__main__":
    main()
