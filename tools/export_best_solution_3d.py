#!/usr/bin/env python3
"""
Export best Pareto solution to JSON for 3D visualization (Three.js).
Reads from results file or results dir (e.g. results/exp/run_id/).

Usage:
  python tools/export_best_solution_3d.py --results results/experiment_name/run_id/
"""

import sys
from pathlib import Path
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "src"))

import json
import numpy as np
import argparse


def _resolve_results(results_arg):
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
                best = max(data, key=lambda s: s.get("coverage", 0))
                if "sensors" in best:
                    best = dict(best)
                    best["sensor_positions"] = best.pop("sensors", best.get("sensor_positions", []))
                    best.setdefault("Mc", best.get("coverage", 0))
                else:
                    best = None
                if not best:
                    raise ValueError("pareto_front.json has no sensors in solutions")
                data = {"pareto_solutions": [best], "experiment_name": config.get("experiment_name", "muscat"), "config": config}
            else:
                config = data.get("config") or json.loads((p / "config.json").read_text(encoding="utf-8"))
            return f, data, config
    raise FileNotFoundError(f"No results in {p}")


def main():
    parser = argparse.ArgumentParser(description="Export best solution for 3D visualization")
    parser.add_argument("--results", type=str, required=True, help="Path to results JSON or results dir")
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    results_path, data, config = _resolve_results(args.results)
    if args.config:
        config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    solutions = data.get("pareto_solutions", [])
    if not solutions:
        print("Error: no pareto_solutions")
        sys.exit(1)
    best = solutions[0]
    if "sensor_positions" not in best and "sensors" in best:
        best["sensor_positions"] = best["sensors"]
    if "sensor_positions" not in best:
        print("Error: solution has no sensor_positions/sensors")
        sys.exit(1)

    env_cfg = config.get("environment", {})
    base = results_path.parent if results_path.is_file() else results_path
    project_root = _root
    buildings_path = project_root / env_cfg.get("buildings_file", "")
    sensor_path = project_root / env_cfg.get("sensor_locations_file", "")
    if not buildings_path.exists():
        buildings_path = base / env_cfg.get("buildings_file", "")
    if not sensor_path.exists():
        sensor_path = base / env_cfg.get("sensor_locations_file", "")
    if not buildings_path.exists() or not sensor_path.exists():
        print("Error: buildings or sensor_locations GeoJSON not found")
        sys.exit(1)

    from environment import UrbanEnvironment
    from network_evaluation import NetworkEvaluator
    from sensors import create_sensor_from_config
    from muscat_core import _expand_runways_file

    env = UrbanEnvironment(
        buildings_geojson_path=str(buildings_path),
        sensor_locations_geojson_path=str(sensor_path),
        voxel_resolution_m=env_cfg.get("resolution", 10.0),
        bounds_expansion_m=env_cfg.get("bounds_expansion", 0),
    )
    critical_assets = list(config.get("critical_assets") or [])
    runways_file = config.get("runways_file")
    if not runways_file:
        scene_meta_path = buildings_path.parent / "scene_meta.json"
        if scene_meta_path.exists():
            try:
                sm = json.loads(scene_meta_path.read_text(encoding="utf-8"))
                runways_file = sm.get("runways_file")
                if runways_file and not (buildings_path.parent / runways_file).exists():
                    runways_file = None
            except Exception:
                pass
    if runways_file:
        scene_dir = buildings_path.parent
        r_path = project_root / runways_file
        if not r_path.exists():
            r_path = scene_dir / runways_file
        if r_path.exists():
            r_radius = float(config.get("runways_protection_radius", 80.0))
            critical_assets.extend(_expand_runways_file(r_path, r_radius))
    if critical_assets:
        env.generate_threat_map(critical_assets)
    x_min, x_max, y_min, y_max, z_min, z_max = env.bounds
    runway_offset = config.get("runways_display_offset")
    offset_x = float(runway_offset[0]) if isinstance(runway_offset, (list, tuple)) and len(runway_offset) >= 2 else 0.0
    offset_y = float(runway_offset[1]) if isinstance(runway_offset, (list, tuple)) and len(runway_offset) >= 2 else 0.0
    margin = float(env_cfg.get("bounds_margin", 250))
    for a in critical_assets:
        if a.get("geometry") == "line":
            for c in a.get("coordinates", []):
                if len(c) >= 2:
                    xx, yy = c[0] + offset_x, c[1] + offset_y
                    x_min = min(x_min, xx - margin)
                    x_max = max(x_max, xx + margin)
                    y_min = min(y_min, yy - margin)
                    y_max = max(y_max, yy + margin)
        elif a.get("location"):
            loc = a["location"]
            r = float(a.get("protection_radius", 100)) + margin
            x_min = min(x_min, loc[0] - r)
            x_max = max(x_max, loc[0] + r)
            y_min = min(y_min, loc[1] - r)
            y_max = max(y_max, loc[1] + r)
    bounds = [float(x_min), float(x_max), float(y_min), float(y_max), float(z_min), float(z_max)]
    sensor_types_config = config.get("sensors", {}).get("types", {})
    sensor_list = []
    for s in best["sensor_positions"]:
        sens = create_sensor_from_config(s["type"], (s["x"], s["y"], s["z"]), sensor_types_config.get(s["type"], {}))
        sens.is_active = True
        sensor_list.append(sens)
    evaluator = NetworkEvaluator(env)

    def to_json_val(v):
        return float(v) if np.isfinite(v) else None

    sensor_detection_grids = []
    for idx, sens in enumerate(sensor_list):
        p_grid = np.zeros(env.grid_shape, dtype=float)
        for k in range(env.grid_shape[2]):
            p_grid[:, :, k] = evaluator.get_coverage_map([sens], height_level=k)
        grid_nested = [[[to_json_val(p_grid[i, j, k]) for k in range(p_grid.shape[2])] for j in range(p_grid.shape[1])] for i in range(p_grid.shape[0])]
        sensor_detection_grids.append({"index": idx, "type": best["sensor_positions"][idx]["type"], "grid": grid_nested})

    buildings_info = env.get_buildings_info()
    buildings = []
    for b in buildings_info:
        entry = {
            "minx": float(b["bounds"][0]), "miny": float(b["bounds"][1]),
            "maxx": float(b["bounds"][2]), "maxy": float(b["bounds"][3]),
            "height": float(b.get("height", 10)),
        }
        if "polygon" in b:
            entry["polygon"] = b["polygon"]
        buildings.append(entry)

    geo_bounds = None
    scene_meta_path = buildings_path.parent / "scene_meta.json"
    if scene_meta_path.exists():
        try:
            scene_meta = json.loads(scene_meta_path.read_text(encoding="utf-8"))
            geo_bounds = scene_meta.get("geo_bounds")
        except Exception:
            pass
    out = {
        "experiment_name": data.get("experiment_name", "muscat"),
        "bounds": bounds,
        "grid_shape": list(env.grid_shape),
        "voxel_resolution": float(env.voxel_resolution),
        "buildings": buildings,
        "sensors": best["sensor_positions"],
        "sensor_detection_grids": sensor_detection_grids,
        "Mc": best.get("Mc", best.get("coverage", 0)),
        "redundancy": best.get("redundancy", 0),
        "cost": best.get("cost", 0),
        "num_sensors": len(best["sensor_positions"]),
    }
    if critical_assets:
        out_ca = []
        for a in critical_assets:
            entry = {
                "id": a.get("id", ""),
                "protection_radius": float(a.get("protection_radius", 100)),
                "weight_multiplier": float(a.get("weight_multiplier", 1.0)),
            }
            if a.get("geometry") == "line":
                entry["geometry"] = "line"
                coords = a.get("coordinates", [])
                entry["coordinates"] = [
                    [float(c[0]) + offset_x, float(c[1]) + offset_y, float(c[2]) if len(c) > 2 else 0.0]
                    for c in coords
                ]
            else:
                loc = a.get("location")
                if loc and len(loc) >= 3:
                    entry["location"] = [float(loc[0]), float(loc[1]), float(loc[2])]
            out_ca.append(entry)
        out["critical_assets"] = out_ca
    for key in ("M_wp_coop", "M_wp_noncoop", "M_vuln_coop", "M_vuln_noncoop", "fused_resilience", "asset_security_roi"):
        if best.get(key) is not None:
            out[key] = to_json_val(best[key])
    if geo_bounds:
        out["geo_bounds"] = geo_bounds
    out_path = Path(args.output) if args.output else base / "best_solution_3d.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"OK Exported: {out_path}")


if __name__ == "__main__":
    main()
