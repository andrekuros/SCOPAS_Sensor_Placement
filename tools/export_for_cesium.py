#!/usr/bin/env python3
"""
Export SCOPAS best solution for Cesium 3D viewer (WGS84).
Converts scene coordinates to geographic and writes cesium_data.json.
Requires scene_meta.json with utm_origin and epsg.

Usage:
  python tools/export_for_cesium.py --results results/point_defense_airport_sjc/pareto_results.json
  python tools/export_for_cesium.py --results ... --config configs/point_defense_airport_sjc.json
"""

import sys
from pathlib import Path
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "src"))

import json
import argparse
from typing import List, Tuple

import geopandas as gpd
from shapely.geometry import box


def _scene_to_wgs84(x: float, y: float, z: float, origin: List[float], epsg: int) -> Tuple[float, float, float]:
    """Convert scene (x,y,z) meters to (lon, lat, alt_m)."""
    utm_x = origin[0] + x
    utm_y = origin[1] + y
    gdf = gpd.GeoDataFrame(
        geometry=[gpd.points_from_xy([utm_x], [utm_y])[0]],
        crs=epsg
    )
    gdf = gdf.to_crs(epsg=4326)
    lon = float(gdf.geometry.x.iloc[0])
    lat = float(gdf.geometry.y.iloc[0])
    return lon, lat, z


def main():
    parser = argparse.ArgumentParser(description="Export for Cesium 3D viewer (WGS84)")
    parser.add_argument("--results", type=str, required=True)
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    # Reuse export logic from export_best_solution_3d
    from tools.export_best_solution_3d import _resolve_results
    results_path, data, config = _resolve_results(args.results)
    if args.config:
        config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    best = data.get("pareto_solutions", [{}])[0]
    if "sensor_positions" not in best and "sensors" in best:
        best["sensor_positions"] = best["sensors"]
    if "sensor_positions" not in best:
        print("Error: no sensor_positions")
        sys.exit(1)

    env_cfg = config.get("environment", {})
    base = results_path.parent if results_path.is_file() else results_path
    buildings_path = _root / env_cfg.get("buildings_file", "")
    if not buildings_path.exists():
        buildings_path = base / env_cfg.get("buildings_file", "")
    scene_dir = buildings_path.parent
    scene_meta_path = scene_dir / "scene_meta.json"
    if not scene_meta_path.exists():
        print("Error: scene_meta.json not found (run download_osm for the scene first)")
        sys.exit(1)
    scene_meta = json.loads(scene_meta_path.read_text(encoding="utf-8"))
    origin = scene_meta.get("utm_origin", [0, 0])
    epsg = scene_meta.get("epsg", 4326)
    geo_bounds = scene_meta.get("geo_bounds", {})

    runway_offset = config.get("runways_display_offset")
    if isinstance(runway_offset, (list, tuple)) and len(runway_offset) >= 2:
        ox_off, oy_off = float(runway_offset[0]), float(runway_offset[1])
    else:
        ox_off, oy_off = 0.0, 0.0

    # Buildings: file has scene coords (translated UTM). Add origin -> real UTM -> WGS84
    buildings_gdf = gpd.read_file(buildings_path)
    buildings_gdf["geometry"] = buildings_gdf.geometry.translate(xoff=origin[0], yoff=origin[1])
    if buildings_gdf.crs and int(buildings_gdf.crs.to_epsg() or 0) != epsg:
        buildings_gdf = buildings_gdf.set_crs(epsg=epsg, allow_override=True)
    elif not buildings_gdf.crs:
        buildings_gdf = buildings_gdf.set_crs(epsg=epsg)
    buildings_wgs = buildings_gdf.to_crs(epsg=4326)
    building_features = []
    for _, row in buildings_wgs.iterrows():
        geom = row.geometry
        h = float(row.get("height", 10))
        if geom.geom_type == "Polygon":
            coords = [[c[0], c[1]] for c in geom.exterior.coords]
            building_features.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [coords]}, "properties": {"height": h}})
        elif geom.geom_type == "MultiPolygon":
            for poly in geom.geoms:
                coords = [[c[0], c[1]] for c in poly.exterior.coords]
                building_features.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [coords]}, "properties": {"height": h}})
    buildings_geojson = {"type": "FeatureCollection", "features": building_features}

    # Sensors: points in WGS84
    sensors_wgs = []
    for s in best["sensor_positions"]:
        lon, lat, alt = _scene_to_wgs84(s["x"], s["y"], s["z"], origin, epsg)
        sensors_wgs.append({"type": s["type"], "lon": lon, "lat": lat, "alt": alt})

    # Critical assets: points and lines
    critical_assets = list(config.get("critical_assets") or [])
    from scopas_core import _expand_runways_file
    runways_file = config.get("runways_file")
    if runways_file:
        r_path = scene_dir / runways_file
        if r_path.exists():
            r_radius = float(config.get("runways_protection_radius", 80.0))
            critical_assets.extend(_expand_runways_file(r_path, r_radius))
    assets_wgs = []
    for a in critical_assets:
        if a.get("geometry") == "line":
            coords = a.get("coordinates", [])
            line_wgs = []
            for c in coords:
                x, y = float(c[0]) + ox_off, float(c[1]) + oy_off
                lon, lat, _ = _scene_to_wgs84(x, y, c[2] if len(c) > 2 else 0, origin, epsg)
                line_wgs.append([lon, lat])
            assets_wgs.append({"type": "line", "id": a.get("id", ""), "coordinates": line_wgs, "width": float(a.get("protection_radius", 80))})
        else:
            loc = a.get("location")
            if loc and len(loc) >= 3:
                lon, lat, alt = _scene_to_wgs84(loc[0], loc[1], loc[2], origin, epsg)
                assets_wgs.append({"type": "point", "id": a.get("id", ""), "lon": lon, "lat": lat, "alt": alt, "radius": float(a.get("protection_radius", 100))})

    out = {
        "experiment_name": data.get("experiment_name", "scopas"),
        "geo_bounds": geo_bounds,
        "buildings": buildings_geojson,
        "sensors": sensors_wgs,
        "critical_assets": assets_wgs,
        "Mc": best.get("Mc", best.get("coverage", 0)),
        "redundancy": best.get("redundancy", 0),
        "cost": best.get("cost", 0),
        "num_sensors": len(best["sensor_positions"]),
        "M_wp_coop": best.get("M_wp_coop"),
        "M_wp_noncoop": best.get("M_wp_noncoop"),
        "fused_resilience": best.get("fused_resilience"),
        "asset_security_roi": best.get("asset_security_roi"),
    }
    out_path = Path(args.output) if args.output else base / "cesium_data.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"OK Exported for Cesium: {out_path}")


if __name__ == "__main__":
    main()
