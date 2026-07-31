#!/usr/bin/env python3
"""
Generate a single 2D overview image of the best solution: LoS-aware coverage + sensors.
Usage: python tools/generate_2d_overview.py --results results/point_defense_airport_sjc/airport_run/
"""

import sys
import json
import argparse
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "src"))

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

from environment import UrbanEnvironment
from sensors import create_sensor_from_config
from network_evaluation import NetworkEvaluator
from visualization import (
    prepare_detection_probability_display,
    upsample_scalar_field_2d,
    heatmap_colormaps,
)


def _resolve_results(results_arg):
    p = Path(results_arg)
    if p.is_file():
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, list):
            solutions = [{"sensor_positions": r.get("sensors", []), "coverage": r.get("coverage"), "redundancy": r.get("redundancy"), "cost": r.get("cost"), **r} for r in data]
            config = json.loads((p.parent / "config.json").read_text(encoding="utf-8"))
        else:
            config = data.get("config") or json.loads((p.parent / "config.json").read_text(encoding="utf-8"))
            solutions = data.get("pareto_solutions", [])
        return p.parent, solutions, config
    for name in ["pareto_results.json", "pareto_front.json"]:
        f = p / name
        if f.exists():
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, list):
                solutions = [{"sensor_positions": r.get("sensors", []), "coverage": r.get("coverage"), "redundancy": r.get("redundancy"), "cost": r.get("cost"), **r} for r in data]
                config = json.loads((p / "config.json").read_text(encoding="utf-8"))
            else:
                config = data.get("config") or json.loads((p / "config.json").read_text(encoding="utf-8"))
                solutions = data.get("pareto_solutions", [])
            return p, solutions, config
    raise FileNotFoundError(f"No results in {p}")


def _pick_height_level(env, config) -> int:
    """Prefer a layer near the lowest airway where buildings still occlude."""
    airways = config.get("airway_altitudes") or [20]
    target_z = float(airways[0])
    best_k = 0
    best_dz = float("inf")
    for k in range(env.grid_shape[2]):
        z = env.voxel_to_world(0, 0, k)[2]
        dz = abs(z - target_z)
        # Prefer layers that still contain some occupied buildings when possible
        has_occ = np.any(env.occupancy_grid[:, :, k] == 1)
        score = dz - (5.0 if has_occ else 0.0)
        if score < best_dz:
            best_dz = score
            best_k = k
    return best_k


def main():
    parser = argparse.ArgumentParser(description="Generate 2D overview of best solution")
    parser.add_argument("--results", required=True, help="Results dir or JSON file")
    parser.add_argument("--output", default=None, help="Output path (default: <results_dir>/overview_2d.png)")
    parser.add_argument("--show-max-range", action="store_true",
                        help="Overlay dashed max-range rings (not LoS; for scale only)")
    args = parser.parse_args()
    base_dir, solutions, config = _resolve_results(args.results)
    if not solutions:
        print("No solutions to visualize")
        return
    best = max(solutions, key=lambda s: (s.get("M_wp_coop") or s.get("coverage") or 0))
    if "sensor_positions" not in best and "sensors" in best:
        best["sensor_positions"] = best["sensors"]
    env_cfg = config["environment"]
    env = UrbanEnvironment(
        buildings_geojson_path=str(_root / env_cfg["buildings_file"]),
        sensor_locations_geojson_path=str(_root / env_cfg["sensor_locations_file"]),
        voxel_resolution_m=env_cfg["resolution"],
        bounds_expansion_m=env_cfg.get("bounds_expansion", 0),
    )
    critical_assets = list(config.get("critical_assets") or [])
    if config.get("runways_file"):
        from scopas_core import _expand_runways_file
        r_path = _root / config["runways_file"]
        if not r_path.exists():
            r_path = (_root / env_cfg["buildings_file"]).parent / config["runways_file"]
        if r_path.exists():
            critical_assets = list(critical_assets) + _expand_runways_file(r_path, float(config.get("runways_protection_radius", 80)))
    if critical_assets:
        env.generate_threat_map(critical_assets)
    sensor_types = config.get("sensors", {}).get("types", {})
    sensors = []
    for s in best["sensor_positions"]:
        sens = create_sensor_from_config(s["type"], (s["x"], s["y"], s["z"]), sensor_types.get(s["type"], {}))
        if "azimuth_deg" in s:
            sens.azimuth_deg = float(s["azimuth_deg"])
        sensors.append(sens)

    evaluator = NetworkEvaluator(env)
    height_level = _pick_height_level(env, config)
    z_view = env.voxel_to_world(0, 0, height_level)[2]
    coverage_map = evaluator.get_coverage_map(sensors, height_level=height_level)
    # Smooth display (upsample + bicubic) while keeping grid_extent_xy for alignment
    coverage_map = upsample_scalar_field_2d(coverage_map, 4, order=1, clip_0_1=True)
    cov_disp, cov_norm, cov_cbar_label = prepare_detection_probability_display(
        coverage_map, scale="power", p_floor=1e-3, power_gamma=0.45
    )
    cmap_cov, _ = heatmap_colormaps(lut_size=256)

    x_min, x_max, y_min, y_max = env.grid_extent_xy()
    view_x0, view_x1 = float(env.bounds[0]), float(env.bounds[1])
    view_y0, view_y1 = float(env.bounds[2]), float(env.bounds[3])
    fig, ax = plt.subplots(1, 1, figsize=(12, 10))
    im = ax.imshow(
        cov_disp.T,
        origin="lower",
        extent=[x_min, x_max, y_min, y_max],
        cmap=cmap_cov,
        norm=cov_norm,
        alpha=0.88,
        interpolation="bicubic",
        zorder=1,
    )
    for _, building in env.buildings_df.iterrows():
        geom = building.geometry
        if geom.geom_type == "Polygon":
            ax.add_patch(patches.Polygon(
                list(geom.exterior.coords),
                facecolor="#d0d0d0", edgecolor="black", linewidth=0.5, alpha=0.45, zorder=3,
            ))
    for a in critical_assets:
        if a.get("geometry") == "line":
            coords = a.get("coordinates", [])
            if len(coords) >= 2:
                xs = [c[0] for c in coords]
                ys = [c[1] for c in coords]
                ax.plot(xs, ys, color="gold", linewidth=4, label="Runway", zorder=5)
        elif a.get("location"):
            x, y = a["location"][0], a["location"][1]
            r = a.get("protection_radius", 100)
            ax.scatter([x], [y], c="purple", s=200, marker="*", edgecolors="black", zorder=10)
            ax.add_patch(patches.Circle((x, y), r, fill=False, edgecolor="purple", linestyle="--", linewidth=1.5, zorder=5))

    type_color = {"Radar": "red", "RF": "blue", "EO": "green", "Acoustic": "orange"}
    type_ranges = {}
    for s in sensors:
        r = getattr(s, "max_range", 2000.0)
        x, y, _ = s.location
        color = type_color.get(getattr(s, "sensor_type", "Radar"), "gray")
        if args.show_max_range:
            ax.add_patch(patches.Circle(
                (x, y), r, fill=False, edgecolor=color, linewidth=1.0,
                linestyle=":", alpha=0.45, zorder=4,
            ))
        az = getattr(s, "azimuth_deg", 0.0)
        angle = 90.0 - az
        ax.plot([x], [y], marker=(3, 0, angle), markersize=10, color=color,
                markeredgecolor="black", markeredgewidth=1, zorder=10)
        t = getattr(s, "sensor_type", "?")
        type_ranges[t] = r
    for stype, color in type_color.items():
        if any(getattr(s, "sensor_type", "") == stype for s in sensors):
            ax.plot([], [], marker=(3, 0, 0), markersize=10, color=color,
                    markeredgecolor="black", linestyle="", label=stype)

    ax.set_xlim(view_x0, view_x1)
    ax.set_ylim(view_y0, view_y1)
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_title(
        f"Best solution – 2D overview (LoS-aware P_Net @ z≈{z_view:.0f} m)\n"
        f"Buildings occlude Radar/EO/RF; heatmap = network detection probability"
    )
    ax.grid(True, alpha=0.2)
    ax.set_aspect("equal")
    if any(getattr(s, "sensor_type", "") in type_color for s in sensors):
        ax.legend(loc="upper right", fontsize=9)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04).set_label(cov_cbar_label)
    note = "LoS-aware coverage (aligned grid extent). Light gray = buildings."
    if args.show_max_range:
        note += " Dotted rings = nominal max range only."
    ax.text(0.5, -0.02, note, transform=ax.transAxes, fontsize=9, ha="center", style="italic", color="gray")

    mc = best.get("Mc", best.get("coverage")) or 0
    txt = f"Mc: {mc*100:.2f}%\nCost: ${best.get('cost', 0):,.0f}\nRedundancy: {best.get('redundancy', 0):.2f}"
    if best.get("M_wp_coop") is not None:
        txt += f"\nM_wp coop: {best['M_wp_coop']*100:.2f}%\nM_wp noncoop: {(best.get('M_wp_noncoop') or 0)*100:.2f}%"
    if best.get("M_vuln_coop") is not None:
        txt += f"\nM_vuln coop: {best['M_vuln_coop']:.3f}\nM_vuln noncoop: {best.get('M_vuln_noncoop', 0):.3f}"
    if best.get("fused_resilience") is not None:
        txt += f"\nFused resilience: {best['fused_resilience']*100:.2f}%"
    if best.get("asset_security_roi") is not None and np.isfinite(best.get("asset_security_roi")):
        txt += f"\nAsset ROI: ${best['asset_security_roi']:,.0f}"
    if type_ranges:
        txt += "\n\nMax range (nominal): " + "  |  ".join(f"{t}: {type_ranges[t]:.0f}m" for t in sorted(type_ranges.keys()))
    ax.text(0.02, 0.98, txt, transform=ax.transAxes, fontsize=10, verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.9), zorder=20)
    out = Path(args.output) if args.output else base_dir / "overview_2d.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(out, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Saved: {out} (LoS coverage at height_level={height_level}, z≈{z_view:.1f}m)")


if __name__ == "__main__":
    main()
