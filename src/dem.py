"""
Digital Elevation Model (DEM) loading for terrain-aware optimization.
Supports SRTM (via elevation package) and GeoTIFF rasters.
"""

import numpy as np
from pathlib import Path
from typing import Optional, Tuple
import json


def load_dem_for_scene(
    scene_dir: Path,
    scene_bounds: Tuple[float, float, float, float],
    resolution_m: float = 15.0,
) -> Optional[Tuple[np.ndarray, Tuple[float, float, float, float]]]:
    """
    Load or create DEM for a scene. Returns (elevation_grid, bounds) or None.
    elevation_grid: 2D array (ny, nx) height in meters, aligned with scene (x,y).
    bounds: (x_min, x_max, y_min, y_max) in scene coordinates.
    """
    scene_meta_path = Path(scene_dir) / "scene_meta.json"
    if not scene_meta_path.exists():
        return None
    meta = json.loads(scene_meta_path.read_text(encoding="utf-8"))
    origin = meta.get("utm_origin", [0, 0])
    epsg = meta.get("epsg", 4326)
    geo_bounds = meta.get("geo_bounds", {})
    west = geo_bounds.get("west")
    south = geo_bounds.get("south")
    east = geo_bounds.get("east")
    north = geo_bounds.get("north")
    if west is None or south is None or east is None or north is None:
        return None

    dem_path = Path(scene_dir) / "scene_dem.tif"
    if dem_path.exists():
        try:
            import rasterio
            from rasterio.warp import reproject, Resampling
            with rasterio.open(dem_path) as src:
                dem_data = src.read(1)
                dem_transform = src.transform
                dem_crs = src.crs
                x_min, y_min = scene_bounds[0], scene_bounds[2]
                x_max, y_max = scene_bounds[1], scene_bounds[3]
                nx = int(np.ceil((x_max - x_min) / resolution_m))
                ny = int(np.ceil((y_max - y_min) / resolution_m))
                out_shape = (ny, nx)
                out_transform = rasterio.transform.from_bounds(
                    origin[0] + x_min, origin[1] + y_min,
                    origin[0] + x_max, origin[1] + y_max,
                    nx, ny
                )
                out_grid = np.full(out_shape, np.nan, dtype=np.float32)
                from rasterio.crs import CRS
                reproject(
                    dem_data, out_grid,
                    src_transform=dem_transform, src_crs=dem_crs,
                    dst_transform=out_transform, dst_crs=CRS.from_epsg(epsg),
                    resampling=Resampling.bilinear
                )
                out_grid = np.nan_to_num(out_grid, nan=0.0)
                return out_grid, (x_min, x_max, y_min, y_max)
        except Exception as e:
            print(f"DEM load warning: {e}")
            return None

    # Try to download SRTM
    try:
        import elevation
        import rasterio
        dem_path.parent.mkdir(parents=True, exist_ok=True)
        elevation.clip(bounds=(west, south, east, north), output=str(dem_path), product="SRTM3")
        if dem_path.exists():
            return load_dem_for_scene(scene_dir, scene_bounds, resolution_m)
    except ImportError:
        pass
    except Exception as e:
        print(f"SRTM download skipped: {e}")
    return None


def sample_terrain(
    dem_grid: np.ndarray,
    bounds: Tuple[float, float, float, float],
    x: float, y: float,
) -> float:
    """Sample terrain height at (x,y) in scene coordinates. Returns meters."""
    x_min, x_max, y_min, y_max = bounds
    if x < x_min or x > x_max or y < y_min or y > y_max:
        return 0.0
    ny, nx = dem_grid.shape
    i = int((x - x_min) / (x_max - x_min) * (nx - 1)) if nx > 1 else 0
    j = int((y - y_min) / (y_max - y_min) * (ny - 1)) if ny > 1 else 0
    i = max(0, min(nx - 1, i))
    j = max(0, min(ny - 1, j))
    return float(dem_grid[j, i])
