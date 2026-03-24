"""
Urban Environment for C-UAS Sensor Network Simulation (GeoJSON-based)
Implements deterministic 3D urban environment with GeoJSON input and voxelization.
Supports optional DEM/terrain for realistic LoS (line-of-sight) and sensor placement.
"""

import json
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, Polygon
from typing import List, Tuple, Optional, Dict, Any
import os
from pathlib import Path


def _distance_sq_to_polyline_2d(
    xx: np.ndarray, yy: np.ndarray, line_xy: List[List[float]]
) -> np.ndarray:
    """
    Squared distance from each (xx[i,j], yy[i,j]) to the nearest point on the polyline.
    xx, yy: shape (nx, ny). line_xy: list of [x, y] points. Returns shape (nx, ny).
    """
    out = np.full_like(xx, np.inf, dtype=np.float64)
    for k in range(len(line_xy) - 1):
        ax, ay = float(line_xy[k][0]), float(line_xy[k][1])
        bx, ay_b = float(line_xy[k + 1][0]), float(line_xy[k + 1][1])
        by = ay_b
        # Vectorized point-to-segment squared distance
        ap_x = xx - ax
        ap_y = yy - ay
        ab_x = bx - ax
        ab_y = by - ay
        ab_sq = ab_x * ab_x + ab_y * ab_y + 1e-20
        t = np.clip((ap_x * ab_x + ap_y * ab_y) / ab_sq, 0.0, 1.0)
        nearest_x = ax + t * ab_x
        nearest_y = ay + t * ab_y
        d_sq = (xx - nearest_x) ** 2 + (yy - nearest_y) ** 2
        out = np.minimum(out, d_sq)
    return out


class UrbanEnvironment:
    """
    Represents a deterministic 3D urban environment for sensor deployment simulation.
    Loads buildings and sensor locations from GeoJSON files and creates a voxelized occupancy grid.
    
    Attributes:
        buildings_df: GeoDataFrame with building footprints and heights
        sensor_locations_df: GeoDataFrame with sensor deployment locations
        occupancy_grid: 3D numpy array (0=free space, 1=occupied by buildings)
        voxel_resolution: Resolution of voxelization in meters
        bounds: Bounding box of the scenario (x_min, x_max, y_min, y_max, z_min, z_max)
        grid_shape: Shape of the occupancy grid (nx, ny, nz)
    """
    
    def __init__(self, buildings_geojson_path: str, 
                 sensor_locations_geojson_path: str,
                 voxel_resolution_m: float = 10.0,
                 bounds_expansion_m: float = 0.0):
        """
        Initialize the urban environment from GeoJSON files.
        
        Args:
            buildings_geojson_path: Path to GeoJSON file with building footprints
            sensor_locations_geojson_path: Path to GeoJSON file with sensor locations
            voxel_resolution_m: Resolution of voxelization in meters
        """
        self.voxel_resolution = voxel_resolution_m
        self._bounds_expansion = max(0.0, float(bounds_expansion_m))
        
        # Load GeoJSON files
        self._load_geojson_files(buildings_geojson_path, sensor_locations_geojson_path)
        
        # Calculate bounds and create occupancy grid
        self._calculate_bounds()
        self._create_occupancy_grid()
        
        # Voxelize the scenario
        self._voxelize_scenario()
        # Point-defense threat map (Gaussian weights around critical assets). Set by generate_threat_map().
        self.threat_map = None
        # Terrain (DEM): optional elevation grid for LoS. Set by _load_terrain().
        self._terrain_grid = None
        self._terrain_bounds = None
        self._load_terrain(buildings_geojson_path)
    
    def generate_threat_map(
        self,
        critical_assets: List[Dict[str, Any]],
        base_weight: float = 100.0,
    ) -> np.ndarray:
        """
        Compute a 3D weighted threat map W(x,y,z) for point-defense evaluation.
        Supports point assets: weight = base * exp(-d²/(2σ²)) with d = distance to point.
        Supports line assets (e.g. runways): weight = base * exp(-d²/(2σ²)) with d = distance
        to nearest point on the line (2D corridor, same weight at all heights).
        Occupied voxels get weight 0. Saves result in self.threat_map for the evaluator.
        
        Args:
            critical_assets: List of dicts. Point: id, location [x,y,z], protection_radius, weight_multiplier.
                Line: id, geometry "line", coordinates [[x,y,z],...], protection_radius, weight_multiplier.
            base_weight: Peak weight at asset (e.g. 100)
        Returns:
            3D float array of shape grid_shape
        """
        if not critical_assets:
            self.threat_map = np.where(self.occupancy_grid == 0, 1.0, 0.0).astype(np.float64)
            return self.threat_map
        
        nx, ny, nz = self.grid_shape
        x_min, x_max, y_min, y_max, z_min, z_max = self.bounds
        res = self.voxel_resolution
        ii, jj, kk = np.meshgrid(np.arange(nx), np.arange(ny), np.arange(nz), indexing="ij")
        xx = x_min + (ii + 0.5) * res
        yy = y_min + (jj + 0.5) * res
        zz = z_min + (kk + 0.5) * res
        
        threat_map = np.zeros(self.grid_shape, dtype=np.float64)
        for asset in critical_assets:
            geom = asset.get("geometry", "point")
            sigma = float(asset.get("protection_radius", 100.0))
            if sigma <= 0:
                sigma = 100.0
            w_mult = float(asset.get("weight_multiplier", 1.0))
            
            if geom == "line":
                coords = asset.get("coordinates", [])
                if len(coords) < 2:
                    continue
                # 2D distance to polyline (runway corridor); same weight at all z
                d_sq_2d = _distance_sq_to_polyline_2d(
                    xx[:, :, 0], yy[:, :, 0],
                    [[float(c[0]), float(c[1])] for c in coords],
                )
                d_sq = np.broadcast_to(d_sq_2d[:, :, np.newaxis], self.grid_shape)
                w = w_mult * base_weight * np.exp(-d_sq / (2.0 * sigma ** 2))
                threat_map = np.maximum(threat_map, w)
            else:
                loc = asset.get("location")
                if not loc or len(loc) < 3:
                    continue
                ax, ay, az = float(loc[0]), float(loc[1]), float(loc[2])
                d_sq = (xx - ax) ** 2 + (yy - ay) ** 2 + (zz - az) ** 2
                w = w_mult * base_weight * np.exp(-d_sq / (2.0 * sigma ** 2))
                threat_map = np.maximum(threat_map, w)
        
        threat_map[self.occupancy_grid == 1] = 0.0
        self.threat_map = threat_map
        total_w = float(np.sum(threat_map))
        print(f"OK Threat map generated: {len(critical_assets)} assets, total weight={total_w:.0f}")
        return self.threat_map

    def _load_terrain(self, buildings_path: str) -> None:
        """Load DEM if scene_dem.tif exists in scene dir. Sets _terrain_grid and _terrain_bounds."""
        try:
            from dem import load_dem_for_scene
            scene_dir = Path(buildings_path).resolve().parent
            x_min, x_max, y_min, y_max = self.bounds[0], self.bounds[1], self.bounds[2], self.bounds[3]
            scene_bounds = (x_min, x_max, y_min, y_max)
            result = load_dem_for_scene(scene_dir, scene_bounds, self.voxel_resolution)
            if result:
                self._terrain_grid, self._terrain_bounds = result
                print(f"OK Terrain/DEM loaded for LoS (shape {self._terrain_grid.shape})")
        except Exception as e:
            self._terrain_grid = None
            self._terrain_bounds = None

    def terrain_height(self, x: float, y: float) -> float:
        """Return terrain elevation in meters at (x,y). Returns 0 if no DEM loaded."""
        if self._terrain_grid is None or self._terrain_bounds is None:
            return 0.0
        try:
            from dem import sample_terrain
            return sample_terrain(self._terrain_grid, self._terrain_bounds, x, y)
        except Exception:
            return 0.0

    def has_terrain(self) -> bool:
        return self._terrain_grid is not None

    def _load_geojson_files(self, buildings_path: str, sensor_locations_path: str):
        """
        Load GeoJSON files into GeoDataFrames.
        
        Args:
            buildings_path: Path to buildings GeoJSON
            sensor_locations_path: Path to sensor locations GeoJSON
        """
        # Load buildings
        if not os.path.exists(buildings_path):
            raise FileNotFoundError(f"Buildings GeoJSON file not found: {buildings_path}")
        
        self.buildings_df = gpd.read_file(buildings_path)
        
        # Validate buildings GeoDataFrame
        if 'height' not in self.buildings_df.columns:
            raise ValueError("Buildings GeoJSON must have a 'height' column")
        
        # Load sensor locations
        if not os.path.exists(sensor_locations_path):
            raise FileNotFoundError(f"Sensor locations GeoJSON file not found: {sensor_locations_path}")
        
        self.sensor_locations_df = gpd.read_file(sensor_locations_path)
        
        # Validate sensor locations GeoDataFrame
        if 'height' not in self.sensor_locations_df.columns:
            raise ValueError("Sensor locations GeoJSON must have a 'height' column")
        
        print(f"OK Loaded {len(self.buildings_df)} buildings from {buildings_path}")
        print(f"OK Loaded {len(self.sensor_locations_df)} sensor locations from {sensor_locations_path}")
    
    def _calculate_bounds(self):
        """
        Calculate the bounding box of the scenario.
        """
        # Get bounds from buildings
        buildings_bounds = self.buildings_df.bounds
        
        x_min = buildings_bounds['minx'].min()
        x_max = buildings_bounds['maxx'].max()
        y_min = buildings_bounds['miny'].min()
        y_max = buildings_bounds['maxy'].max()
        z_min = 0.0
        # Add margin above tallest building for airway analysis
        z_max = self.buildings_df['height'].max() + 40.0  # 60m + 40m = 100m
        
        # Extend bounds to include sensor locations
        sensor_bounds = self.sensor_locations_df.bounds
        x_min = min(x_min, sensor_bounds['minx'].min())
        x_max = max(x_max, sensor_bounds['maxx'].max())
        y_min = min(y_min, sensor_bounds['miny'].min())
        y_max = max(y_max, sensor_bounds['maxy'].max())
        z_max = max(z_max, self.sensor_locations_df['height'].max())
        
        if self._bounds_expansion > 0:
            x_min -= self._bounds_expansion
            x_max += self._bounds_expansion
            y_min -= self._bounds_expansion
            y_max += self._bounds_expansion
        
        self.bounds = (x_min, x_max, y_min, y_max, z_min, z_max)
        
        print(f"OK Scenario bounds: X=[{x_min:.1f}, {x_max:.1f}], Y=[{y_min:.1f}, {y_max:.1f}], Z=[{z_min:.1f}, {z_max:.1f}]")
    
    def _create_occupancy_grid(self):
        """
        Create the 3D occupancy grid based on bounds and resolution.
        """
        x_min, x_max, y_min, y_max, z_min, z_max = self.bounds
        
        # Calculate grid dimensions
        nx = int(np.ceil((x_max - x_min) / self.voxel_resolution))
        ny = int(np.ceil((y_max - y_min) / self.voxel_resolution))
        nz = int(np.ceil((z_max - z_min) / self.voxel_resolution))
        
        self.grid_shape = (nx, ny, nz)
        
        # Initialize occupancy grid (0 = free space, 1 = occupied)
        self.occupancy_grid = np.zeros(self.grid_shape, dtype=np.int8)
        
        print(f"OK Created occupancy grid with shape {self.grid_shape} ({nx*ny*nz:,} voxels)")
    
    def _voxelize_scenario(self):
        """
        Voxelize the scenario by marking occupied voxels.
        """
        x_min, x_max, y_min, y_max, z_min, z_max = self.bounds
        
        occupied_voxels = 0
        
        # Iterate through each building
        for idx, building in self.buildings_df.iterrows():
            geometry = building.geometry
            height = building.height
            
            # Get building bounds
            building_bounds = geometry.bounds  # (minx, miny, maxx, maxy)
            
            # Calculate voxel indices for building bounds
            min_i = max(0, int((building_bounds[0] - x_min) / self.voxel_resolution))
            max_i = min(self.grid_shape[0], int((building_bounds[2] - x_min) / self.voxel_resolution) + 1)
            min_j = max(0, int((building_bounds[1] - y_min) / self.voxel_resolution))
            max_j = min(self.grid_shape[1], int((building_bounds[3] - y_min) / self.voxel_resolution) + 1)
            
            # Calculate height in voxels
            max_k = min(self.grid_shape[2], int(height / self.voxel_resolution))
            
            # Mark voxels as occupied
            for i in range(min_i, max_i):
                for j in range(min_j, max_j):
                    # Convert voxel indices back to world coordinates
                    voxel_x = x_min + i * self.voxel_resolution + self.voxel_resolution / 2
                    voxel_y = y_min + j * self.voxel_resolution + self.voxel_resolution / 2
                    
                    # Check if voxel center is inside building polygon
                    voxel_point = Point(voxel_x, voxel_y)
                    if geometry.contains(voxel_point) or geometry.touches(voxel_point):
                        # Mark all height levels up to building height
                        for k in range(max_k):
                            if self.occupancy_grid[i, j, k] == 0:
                                self.occupancy_grid[i, j, k] = 1
                                occupied_voxels += 1
        
        total_voxels = np.prod(self.grid_shape)
        occupancy_ratio = occupied_voxels / total_voxels * 100
        
        print(f"OK Voxelization complete: {occupied_voxels:,} occupied voxels ({occupancy_ratio:.1f}% of total)")
    
    def world_to_voxel(self, x: float, y: float, z: float) -> Tuple[int, int, int]:
        """
        Convert world coordinates to voxel indices.
        
        Args:
            x, y, z: World coordinates
            
        Returns:
            Voxel indices (i, j, k)
        """
        x_min, x_max, y_min, y_max, z_min, z_max = self.bounds
        
        i = int((x - x_min) / self.voxel_resolution)
        j = int((y - y_min) / self.voxel_resolution)
        k = int((z - z_min) / self.voxel_resolution)
        
        # Clamp to grid bounds
        i = max(0, min(self.grid_shape[0] - 1, i))
        j = max(0, min(self.grid_shape[1] - 1, j))
        k = max(0, min(self.grid_shape[2] - 1, k))
        
        return i, j, k
    
    def voxel_to_world(self, i: int, j: int, k: int) -> Tuple[float, float, float]:
        """
        Convert voxel indices to world coordinates.
        
        Args:
            i, j, k: Voxel indices
            
        Returns:
            World coordinates (x, y, z)
        """
        x_min, x_max, y_min, y_max, z_min, z_max = self.bounds
        
        x = x_min + i * self.voxel_resolution + self.voxel_resolution / 2
        y = y_min + j * self.voxel_resolution + self.voxel_resolution / 2
        z = z_min + k * self.voxel_resolution + self.voxel_resolution / 2
        
        return x, y, z
    
    def get_sensor_locations(self, num_locations: Optional[int] = None) -> List[Tuple[float, float, float]]:
        """
        Get sensor deployment locations from the GeoDataFrame.
        
        Args:
            num_locations: Number of locations to return (None = all)
            
        Returns:
            List of (x, y, z) coordinates
        """
        locations = []
        
        for idx, row in self.sensor_locations_df.iterrows():
            if num_locations is not None and len(locations) >= num_locations:
                break
                
            geometry = row.geometry
            height = row.height
            
            if geometry.geom_type == 'Point':
                x, y = geometry.x, geometry.y
                locations.append((x, y, height))
        
        return locations

    def exclude_sensor_locations_near_runways(
        self, runways_geojson_path: str, margin_m: float
    ) -> int:
        """
        Remove sensor candidate locations that lie within margin_m of any runway.
        Used to enforce "no sensors on runway or within 50m" rules.
        Returns the number of locations removed.
        """
        path = Path(runways_geojson_path)
        if not path.exists():
            return 0
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        segments = []
        for feat in data.get("features", []):
            geom = feat.get("geometry")
            if not geom or geom.get("type") != "LineString":
                continue
            coords = geom.get("coordinates", [])
            for k in range(len(coords) - 1):
                ax, ay = float(coords[k][0]), float(coords[k][1])
                bx, by = float(coords[k + 1][0]), float(coords[k + 1][1])
                segments.append((ax, ay, bx, by))
        if not segments:
            return 0

        def dist_sq_point_to_segment(px, py, ax, ay, bx, by):
            ab_x, ab_y = bx - ax, by - ay
            ap_x, ap_y = px - ax, py - ay
            ab_sq = ab_x * ab_x + ab_y * ab_y + 1e-20
            t = np.clip((ap_x * ab_x + ap_y * ab_y) / ab_sq, 0.0, 1.0)
            nx, ny = ax + t * ab_x, ay + t * ab_y
            return (px - nx) ** 2 + (py - ny) ** 2

        margin_sq = margin_m * margin_m
        to_drop = []
        for idx, row in self.sensor_locations_df.iterrows():
            geom = row.geometry
            if geom.geom_type != "Point":
                continue
            px, py = geom.x, geom.y
            d_sq_min = float("inf")
            for (ax, ay, bx, by) in segments:
                d_sq = dist_sq_point_to_segment(px, py, ax, ay, bx, by)
                d_sq_min = min(d_sq_min, d_sq)
            if d_sq_min < margin_sq:
                to_drop.append(idx)
        if to_drop:
            self.sensor_locations_df = self.sensor_locations_df.drop(to_drop).reset_index(drop=True)
            print(f"OK Excluded {len(to_drop)} sensor locations within {margin_m}m of runways")
            return len(to_drop)
        return 0
    
    def is_voxel_occupied(self, i: int, j: int, k: int) -> bool:
        """
        Check if a voxel is occupied.
        
        Args:
            i, j, k: Voxel indices
            
        Returns:
            True if occupied, False if free
        """
        if 0 <= i < self.grid_shape[0] and 0 <= j < self.grid_shape[1] and 0 <= k < self.grid_shape[2]:
            return self.occupancy_grid[i, j, k] == 1
        return False
    
    def is_point_occupied(self, x: float, y: float, z: float) -> bool:
        """
        Check if a world coordinate point is occupied.
        
        Args:
            x, y, z: World coordinates
            
        Returns:
            True if occupied, False if free
        """
        i, j, k = self.world_to_voxel(x, y, z)
        return self.is_voxel_occupied(i, j, k)
    
    def get_environment_info(self) -> Dict[str, Any]:
        """
        Get information about the environment.
        
        Returns:
            Dictionary with environment information
        """
        x_min, x_max, y_min, y_max, z_min, z_max = self.bounds
        
        return {
            'bounds': self.bounds,
            'dimensions': (x_max - x_min, y_max - y_min, z_max - z_min),
            'voxel_resolution': self.voxel_resolution,
            'grid_shape': self.grid_shape,
            'total_voxels': np.prod(self.grid_shape),
            'occupied_voxels': np.sum(self.occupancy_grid),
            'num_buildings': len(self.buildings_df),
            'num_sensor_locations': len(self.sensor_locations_df)
        }
    
    def get_buildings_info(self) -> List[Dict[str, Any]]:
        """
        Get information about buildings.
        
        Returns:
            List of building information dictionaries
        """
        buildings_info = []
        
        for idx, building in self.buildings_df.iterrows():
            geometry = building.geometry
            height = building.height
            info = {
                'id': idx,
                'name': building.get('name', f'Building {idx}'),
                'height': height,
                'bounds': geometry.bounds,
                'area': geometry.area
            }
            if hasattr(geometry, 'exterior') and geometry.exterior is not None:
                info['polygon'] = [[float(c[0]), float(c[1])] for c in geometry.exterior.coords]
            buildings_info.append(info)
        
        return buildings_info
    
    def get_sensor_locations_info(self) -> List[Dict[str, Any]]:
        """
        Get information about sensor locations.
        
        Returns:
            List of sensor location information dictionaries
        """
        locations_info = []
        
        for idx, location in self.sensor_locations_df.iterrows():
            geometry = location.geometry
            height = location.height
            
            locations_info.append({
                'id': idx,
                'name': location.get('name', f'Location {idx}'),
                'type': location.get('type', 'unknown'),
                'height': height,
                'coordinates': (geometry.x, geometry.y, height)
            })
        
        return locations_info


def create_urban_environment_from_geojson(buildings_path: str, 
                                         sensor_locations_path: str,
                                         voxel_resolution: float = 10.0) -> UrbanEnvironment:
    """
    Factory function to create an UrbanEnvironment from GeoJSON files.
    
    Args:
        buildings_path: Path to buildings GeoJSON file
        sensor_locations_path: Path to sensor locations GeoJSON file
        voxel_resolution: Voxel resolution in meters
        
    Returns:
        UrbanEnvironment instance
    """
    return UrbanEnvironment(buildings_path, sensor_locations_path, voxel_resolution)
