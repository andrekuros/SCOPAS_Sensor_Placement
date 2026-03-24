"""
MUSCAT Core API - standard evaluation entry point.
Load environment from config, evaluate sensor deployments, return standardized results.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from environment import UrbanEnvironment
from sensors import create_sensor_from_config
from network_evaluation import NetworkEvaluator


def load_config(config_path: str) -> Dict[str, Any]:
    """Load JSON config from path."""
    path = Path(config_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _expand_runways_file(
    runways_path: Path, protection_radius: float = 80.0
) -> List[Dict[str, Any]]:
    """
    Load runways GeoJSON and convert each LineString to a line critical_asset.
    Returns list of assets with geometry "line" and coordinates [[x,y,z], ...].
    """
    path = Path(runways_path)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    features = data.get("features", [])
    assets = []
    for i, feat in enumerate(features):
        geom = feat.get("geometry")
        if not geom or geom.get("type") != "LineString":
            continue
        coords = geom.get("coordinates", [])
        if len(coords) < 2:
            continue
        # Ensure 3D: [x, y] -> [x, y, 0]
        line_coords = [
            [float(c[0]), float(c[1]), float(c[2]) if len(c) > 2 else 0.0]
            for c in coords
        ]
        ref = (feat.get("properties") or {}).get("ref", f"Runway_{i+1}")
        assets.append({
            "id": ref,
            "geometry": "line",
            "coordinates": line_coords,
            "protection_radius": protection_radius,
            "weight_multiplier": 1.0,
        })
    return assets


def load_environment_from_config(config: Dict[str, Any], base_dir: Path = None) -> UrbanEnvironment:
    """
    Build UrbanEnvironment from config.
    Paths in config are relative to base_dir; if None, use current working directory.
    If config contains critical_assets and/or runways_file, generates point-defense threat map.
    """
    if base_dir is None:
        base_dir = Path.cwd()
    env_c = config["environment"]
    buildings = base_dir / env_c["buildings_file"]
    sensors_geo = base_dir / env_c["sensor_locations_file"]
    resolution = float(env_c["resolution"])
    bounds_exp = float(env_c.get("bounds_expansion", 0))
    env = UrbanEnvironment(
        buildings_geojson_path=str(buildings),
        sensor_locations_geojson_path=str(sensors_geo),
        voxel_resolution_m=resolution,
        bounds_expansion_m=bounds_exp,
    )
    critical_assets = list(config.get("critical_assets") or [])
    runways_file = config.get("runways_file")
    if runways_file:
        r_radius = float(config.get("runways_protection_radius", 80.0))
        scene_dir = (base_dir / env_c["buildings_file"]).parent
        r_path = base_dir / runways_file
        if not r_path.exists():
            r_path = scene_dir / runways_file
        if r_path.exists():
            critical_assets.extend(_expand_runways_file(r_path, r_radius))
            exclusion_margin = config.get("runways_exclusion_margin")
            if exclusion_margin is not None:
                env.exclude_sensor_locations_near_runways(str(r_path), float(exclusion_margin))
    if critical_assets:
        env.generate_threat_map(critical_assets)
    return env


def sensor_list_to_objects(
    sensor_list: List[Dict],
    sensor_types_config: Dict[str, Any],
) -> List:
    """Convert list of {type, x, y, z} to list of Sensor instances using config."""
    sensors = []
    for s in sensor_list:
        stype = s.get("type")
        if not stype or stype not in sensor_types_config:
            continue
        loc = (float(s["x"]), float(s["y"]), float(s["z"]))
        type_config = sensor_types_config.get(stype, {})
        sensor = create_sensor_from_config(stype, loc, type_config)
        sensors.append(sensor)
    return sensors


def evaluate_solution(
    environment: UrbanEnvironment,
    sensor_list: List[Dict],
    sensor_types_config: Dict[str, Any],
    weights: tuple = (1.0, 1.0, 0.001),
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Evaluate one sensor deployment. If config has critical_assets (point-defense),
    uses dual-layer evaluation and returns M_wp_coop, M_vuln, fused_resilience, asset_security_roi, etc.
    """
    sensors = sensor_list_to_objects(sensor_list, sensor_types_config)
    if not sensors:
        out = {"coverage": 0.0, "redundancy": 0.0, "cost": 0.0, "num_sensors": 0}
        if config and config.get("critical_assets"):
            out.update({
                "M_wp_coop": 0.0, "M_wp_noncoop": 0.0,
                "M_vuln_coop": 1.0, "M_vuln_noncoop": 1.0,
                "fused_resilience": 0.0, "asset_security_roi": None,
            })
        return out
    evaluator = NetworkEvaluator(environment)
    if config and config.get("critical_assets"):
        site_cost = float(config.get("site_activation_cost", 15000.0))
        raw = evaluator.evaluate_network_dual_layer(sensors, site_activation_cost=site_cost)
        return raw
    raw = evaluator.evaluate_network(sensors, weights=weights)
    return {
        "coverage": raw["coverage"],
        "redundancy": raw["redundancy"],
        "cost": raw["cost"],
        "num_sensors": raw["num_sensors"],
    }


def run_evaluation(
    config_path: str,
    solutions: List[List[Dict]],
    base_dir: Path = None,
) -> List[Dict[str, Any]]:
    """
    Evaluate multiple solutions using a single config.

    solutions: list of sensor deployments; each deployment is a list of
               {"type": str, "x": float, "y": float, "z": float}.
    Returns: list of result dicts (one per solution), each with
             coverage, redundancy, cost, num_sensors.
    """
    config = load_config(config_path)
    if base_dir is None:
        base_dir = Path.cwd()
    environment = load_environment_from_config(config, base_dir=base_dir)
    sensor_types_config = config.get("sensors", {}).get("types", {})
    results = []
    for sol in solutions:
        res = evaluate_solution(environment, sol, sensor_types_config, config=config)
        results.append(res)
    return results


def make_run_id(experiment_name: str, config: Dict[str, Any]) -> str:
    """Generate unique run_id: optional config override or {experiment_name}_{timestamp}."""
    over = config.get("output", {}).get("run_id")
    if over:
        return str(over)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{experiment_name}_{ts}"


def get_results_dir(config: Dict[str, Any], run_id: str = None) -> Path:
    """Return results base dir: results/{experiment_name}/{run_id}/."""
    base = Path(config.get("output", {}).get("results_dir", "results"))
    # If results_dir is like "results/pareto_city_10x10_final", use experiment_name for subdir
    experiment_name = config.get("experiment_name", "experiment")
    if run_id is None:
        run_id = make_run_id(experiment_name, config)
    # Standard layout: results/{experiment_name}/{run_id}
    out = Path("results") / experiment_name / run_id
    out.mkdir(parents=True, exist_ok=True)
    return out


def save_run_results(
    config: Dict[str, Any],
    population: List[List[Dict]],
    results: List[Dict[str, Any]],
    run_id: str = None,
    save_pareto: bool = True,
) -> Path:
    """
    Save standard output to results/{experiment_name}/{run_id}/.
    Writes config.json, evaluation_results.json, and optionally pareto_front.json.
    Returns the results directory path.
    """
    if run_id is None:
        run_id = make_run_id(config.get("experiment_name", "experiment"), config)
    out_dir = get_results_dir(config, run_id=run_id)

    with open(out_dir / "config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    evaluation_results = [
        {"solution_id": i + 1, "sensors": population[i], **results[i]}
        for i in range(min(len(population), len(results)))
    ]
    with open(out_dir / "evaluation_results.json", "w", encoding="utf-8") as f:
        json.dump(evaluation_results, f, indent=2)

    if save_pareto and evaluation_results:
        with open(out_dir / "pareto_front.json", "w", encoding="utf-8") as f:
            json.dump(evaluation_results, f, indent=2)

    return out_dir
