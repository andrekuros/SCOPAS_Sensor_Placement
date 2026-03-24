#!/usr/bin/env python3
"""
Download DEM (SRTM) for a scene. Creates scene_dem.tif in the scene directory.
Requires: pip install elevation rasterio (and system: curl, unzip, GDAL)

Usage:
  python tools/download_dem.py --scene data/scenes/airport_sjc
"""

import argparse
from pathlib import Path

_root = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description="Download SRTM DEM for a scene")
    parser.add_argument("--scene", type=str, required=True, help="Scene dir (e.g. data/scenes/airport_sjc)")
    args = parser.parse_args()
    scene_dir = _root / args.scene
    scene_meta = scene_dir / "scene_meta.json"
    if not scene_meta.exists():
        print("Error: scene_meta.json not found. Run download_osm first.")
        return 1
    meta = __import__("json").loads(scene_meta.read_text(encoding="utf-8"))
    gb = meta.get("geo_bounds", {})
    w, s, e, n = gb.get("west"), gb.get("south"), gb.get("east"), gb.get("north")
    if None in (w, s, e, n):
        print("Error: geo_bounds missing in scene_meta")
        return 1
    try:
        import elevation
        out_path = scene_dir / "scene_dem.tif"
        elevation.clip(bounds=(w, s, e, n), output=str(out_path), product="SRTM3")
        print(f"OK DEM saved: {out_path}")
    except ImportError:
        print("Install: pip install elevation. Also need GDAL, curl, unzip.")
    except Exception as ex:
        print(f"Error: {ex}")
        return 1
    return 0


if __name__ == "__main__":
    exit(main())
