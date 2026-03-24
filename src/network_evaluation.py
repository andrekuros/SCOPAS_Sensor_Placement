"""
Optimized Network Evaluation for C-UAS Sensor Network Simulation.
Skips occupied voxels during evaluation.

Supports dual-layer airspace evaluation (cooperative vs non-cooperative coverage)
and site activation cost (CapEx) for UTM/GBSS optimization.
"""

import numpy as np
from typing import List, Dict, Any, Tuple
from environment import UrbanEnvironment
from sensors import Sensor
from propagation import calculate_PD

# Default site activation cost (rooftop/power/backhaul) per unique location
DEFAULT_SITE_ACTIVATION_COST = 15_000.0
# Kinematic/visual sensor types (non-coop); RF is cooperative-only
NONCOOP_SENSOR_TYPES = ("Radar", "EO")


class NetworkEvaluator:
    """
    Optimized network evaluator that skips occupied voxels during evaluation.
    """
    
    def __init__(self, environment: UrbanEnvironment):
        """
        Initialize the network evaluator.
        
        Args:
            environment: Urban environment with voxelized occupancy grid
        """
        self.environment = environment
        self.occupancy_grid = environment.occupancy_grid
        self.grid_shape = environment.grid_shape
        
        # Cache for free voxels (non-occupied)
        self._free_voxels = None
        self._cache_free_voxels()
    
    def _cache_free_voxels(self):
        """
        Cache the indices of free (non-occupied) voxels for faster evaluation.
        """
        # Find all free voxels (value = 0)
        free_indices = np.where(self.occupancy_grid == 0)
        self._free_voxels = list(zip(free_indices[0], free_indices[1], free_indices[2]))
        
        print(f"OK Cached {len(self._free_voxels)} free voxels out of {np.prod(self.grid_shape):,} total voxels")
    
    def get_free_voxels(self) -> List[Tuple[int, int, int]]:
        """
        Get the list of free voxel indices.
        
        Returns:
            List of (i, j, k) voxel indices that are free
        """
        return self._free_voxels
    
    def calculate_network_coverage(self, sensor_list: List[Sensor]) -> float:
        """
        Calculate network coverage (P_Net) for free voxels only.
        
        Args:
            sensor_list: List of active sensors
            
        Returns:
            Average network coverage probability
        """
        if not sensor_list:
            return 0.0
        
        total_coverage = 0.0
        evaluated_voxels = 0
        
        # Iterate only through free voxels
        for i, j, k in self._free_voxels:
            # Convert voxel to world coordinates
            x, y, z = self.environment.voxel_to_world(i, j, k)
            
            # Calculate individual detection probabilities
            individual_probs = []
            for sensor in sensor_list:
                if sensor.is_active:
                    pd = calculate_PD(sensor, (x, y, z), self.environment)
                    individual_probs.append(pd)
            
            if individual_probs:
                # Calculate network coverage: P_Net = 1 - ∏(1 - P_D,i)
                network_prob = 1.0 - np.prod([1.0 - p for p in individual_probs])
                total_coverage += network_prob
                evaluated_voxels += 1
        
        if evaluated_voxels == 0:
            return 0.0
        
        return total_coverage / evaluated_voxels
    
    def calculate_network_redundancy(self, sensor_list: List[Sensor]) -> float:
        """
        Calculate network redundancy (R) for free voxels only.
        
        Args:
            sensor_list: List of active sensors
            
        Returns:
            Average network redundancy
        """
        if not sensor_list:
            return 0.0
        
        total_redundancy = 0.0
        evaluated_voxels = 0
        
        # Iterate only through free voxels
        for i, j, k in self._free_voxels:
            # Convert voxel to world coordinates
            x, y, z = self.environment.voxel_to_world(i, j, k)
            
            # Calculate individual detection probabilities
            individual_probs = []
            for sensor in sensor_list:
                if sensor.is_active:
                    pd = calculate_PD(sensor, (x, y, z), self.environment)
                    individual_probs.append(pd)
            
            if individual_probs:
                # Calculate redundancy: R = ∑P_D,i
                redundancy = sum(individual_probs)
                total_redundancy += redundancy
                evaluated_voxels += 1
        
        if evaluated_voxels == 0:
            return 0.0
        
        return total_redundancy / evaluated_voxels
    
    def calculate_network_cost(self, sensor_list: List[Sensor]) -> float:
        """
        Calculate total network cost (hardware only).
        
        Args:
            sensor_list: List of sensors
            
        Returns:
            Total cost of active sensors
        """
        total_cost = 0.0
        for sensor in sensor_list:
            if sensor.is_active:
                total_cost += sensor.cost
        return total_cost

    def _get_sensor_pd_grid_3d(self, sensor: Sensor) -> np.ndarray:
        """
        Build 3D grid of detection probability P_D for a single sensor.
        Occupied voxels are set to 0 so they do not affect P_Net product.
        """
        grid = np.zeros(self.grid_shape, dtype=np.float64)
        for k in range(self.grid_shape[2]):
            grid[:, :, k] = self.get_coverage_map([sensor], height_level=k)
        return grid

    def _cooperative_and_noncooperative_grids(
        self, sensor_list: List[Sensor]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute cooperative and non-cooperative P_Net 3D grids using numpy masking.
        Cooperative: any sensor (RF, Radar, EO) can detect (compliant / Remote ID).
        Non-cooperative: only Radar or EO (kinematic/visual); RF sensors are masked.
        """
        active = [s for s in sensor_list if s.is_active]
        if not active:
            empty = np.zeros(self.grid_shape, dtype=np.float64)
            return empty, empty

        # Per-sensor 3D P_D grids
        all_grids = [self._get_sensor_pd_grid_3d(s) for s in active]
        coop_grids = all_grids
        noncoop_grids = [
            g for s, g in zip(active, all_grids)
            if getattr(s, "sensor_type", "") in NONCOOP_SENSOR_TYPES
        ]

        # P_Net = 1 - prod(1 - P_D,i); stack (n_sensors, nx, ny, nz) then prod
        def p_net_from_grids(grids: List[np.ndarray]) -> np.ndarray:
            if not grids:
                return np.zeros(self.grid_shape, dtype=np.float64)
            stacked = np.stack([1.0 - g for g in grids], axis=0)
            return 1.0 - np.prod(stacked, axis=0)

        coop_net = p_net_from_grids(coop_grids)
        noncoop_net = p_net_from_grids(noncoop_grids)
        # Avoid NaN/inf from propagation; treat as no coverage
        coop_net = np.nan_to_num(coop_net, nan=0.0, posinf=1.0, neginf=0.0)
        noncoop_net = np.nan_to_num(noncoop_net, nan=0.0, posinf=1.0, neginf=0.0)
        np.clip(coop_net, 0.0, 1.0, out=coop_net)
        np.clip(noncoop_net, 0.0, 1.0, out=noncoop_net)
        return coop_net, noncoop_net

    def calculate_network_coverage_coop(self, sensor_list: List[Sensor]) -> float:
        """
        Cooperative coverage M_c_coop: voxel covered if LoS and within range of ANY sensor
        (RF, Radar, or EO). For compliant drones broadcasting Remote ID.
        """
        if not sensor_list:
            return 0.0
        coop_net, _ = self._cooperative_and_noncooperative_grids(sensor_list)
        free_mask = self.occupancy_grid == 0
        if not np.any(free_mask):
            return 0.0
        weights = getattr(self.environment, "threat_map", None)
        if weights is None or weights.shape != self.occupancy_grid.shape:
            weights = np.where(free_mask, 1.0, 0.0).astype(np.float64)
        sum_w = np.clip(np.sum(weights), 1e-10, None)
        val = np.sum(coop_net * weights) / sum_w
        return float(np.clip(np.nan_to_num(val, nan=0.0), 0.0, 1.0))

    def calculate_network_coverage_noncoop(self, sensor_list: List[Sensor]) -> float:
        """
        Non-cooperative coverage M_c_noncoop: voxel covered only if LoS and within range
        of a Radar or EO sensor (RF sensors masked). For dark drones with no RF.
        """
        if not sensor_list:
            return 0.0
        _, noncoop_net = self._cooperative_and_noncooperative_grids(sensor_list)
        free_mask = self.occupancy_grid == 0
        if not np.any(free_mask):
            return 0.0
        weights = getattr(self.environment, "threat_map", None)
        if weights is None or weights.shape != self.occupancy_grid.shape:
            weights = np.where(free_mask, 1.0, 0.0).astype(np.float64)
        sum_w = np.clip(np.sum(weights), 1e-10, None)
        val = np.sum(noncoop_net * weights) / sum_w
        return float(np.clip(np.nan_to_num(val, nan=0.0), 0.0, 1.0))

    def calculate_fused_resilience(
        self,
        sensor_list: List[Sensor],
        coverage_threshold: float = 0.8,
    ) -> float:
        """
        Fused Resilience: fraction of (weighted) threat volume where voxels have
        Q=1.0 — covered by both RF identity (cooperative) AND kinematic Radar/EO (non-cooperative).
        Modality diversity: proves critical asset is protected by weapon-grade fused track.
        """
        if not sensor_list:
            return 0.0
        coop_net, noncoop_net = self._cooperative_and_noncooperative_grids(sensor_list)
        free_mask = self.occupancy_grid == 0
        if not np.any(free_mask):
            return 0.0
        covered_coop = (coop_net >= coverage_threshold).astype(np.float64)
        covered_noncoop = (noncoop_net >= coverage_threshold).astype(np.float64)
        fused = covered_coop * covered_noncoop  # 1.0 only where both modalities cover
        weights = getattr(self.environment, "threat_map", None)
        if weights is None or weights.shape != self.occupancy_grid.shape:
            weights = np.where(free_mask, 1.0, 0.0).astype(np.float64)
        sum_w = np.clip(np.sum(weights), 1e-10, None)
        val = np.sum(fused * weights) / sum_w
        return float(np.clip(np.nan_to_num(val, nan=0.0), 0.0, 1.0))

    def _get_threat_weights(self) -> np.ndarray:
        """Weights for weighted metrics (threat map or uniform on free voxels)."""
        free_mask = self.occupancy_grid == 0
        weights = getattr(self.environment, "threat_map", None)
        if weights is None or weights.shape != self.occupancy_grid.shape:
            weights = np.where(free_mask, 1.0, 0.0).astype(np.float64)
        return weights

    def calculate_network_cost_with_sites(
        self,
        sensor_list: List[Sensor],
        site_activation_cost: float = DEFAULT_SITE_ACTIVATION_COST,
    ) -> float:
        """
        Total system cost = Sum(hardware) + Sum(unique site activation costs).
        Each unique location_id (sensor position) is charged once to encourage
        co-location and multi-modal fusion nodes.
        """
        hardware = 0.0
        unique_sites = set()
        for sensor in sensor_list:
            if not sensor.is_active:
                continue
            hardware += sensor.cost
            unique_sites.add(sensor.location)
        return hardware + len(unique_sites) * site_activation_cost

    def evaluate_network_dual_layer(
        self,
        sensor_list: List[Sensor],
        site_activation_cost: float = DEFAULT_SITE_ACTIVATION_COST,
        cost_scale: float = 100_000.0,
    ) -> Dict[str, Any]:
        """
        UTM/GBSS dual-layer evaluation for NSGA-II.
        Returns M_c_coop, M_c_noncoop, and total cost (with site activation).
        Fitness tuple: (M_c_coop, M_c_noncoop, cost_scaled) for maximize, maximize, minimize.
        """
        active = [s for s in sensor_list if s.is_active]
        if not active:
            return {
                "M_wp_coop": 0.0,
                "M_wp_noncoop": 0.0,
                "M_vuln_coop": 1.0,
                "M_vuln_noncoop": 1.0,
                "fused_resilience": 0.0,
                "asset_security_roi": float("inf"),
                "asset_security_roi_noncoop": float("inf"),
                "M_c_coop": 0.0,
                "M_c_noncoop": 0.0,
                "coverage": 0.0,
                "redundancy": 0.0,
                "cost": 0.0,
                "cost_hardware": 0.0,
                "cost_sites": 0.0,
                "num_sensors": 0,
                "unique_sites": 0,
                "fitness": (0.0, 0.0, 0.0),
                "evaluated_voxels": len(self._free_voxels),
                "total_voxels": int(np.prod(self.grid_shape)),
            }

        # Weighted Protection Index M_wp (upgrade of SCOPAS M_c)
        M_wp_coop = self.calculate_network_coverage_coop(sensor_list)
        M_wp_noncoop = self.calculate_network_coverage_noncoop(sensor_list)
        # Sanitize so fitness and outputs are never NaN
        M_wp_coop = float(np.clip(np.nan_to_num(M_wp_coop, nan=0.0), 0.0, 1.0))
        M_wp_noncoop = float(np.clip(np.nan_to_num(M_wp_noncoop, nan=0.0), 0.0, 1.0))

        total_cost = self.calculate_network_cost_with_sites(
            sensor_list, site_activation_cost=site_activation_cost
        )
        hardware_cost = self.calculate_network_cost(sensor_list)
        unique_sites = len(set(s.location for s in active))
        cost_sites = unique_sites * site_activation_cost

        # Vulnerability Index M_vuln = 1 - M_wp (upgrade of SCOPAS M_g)
        M_vuln_coop = 1.0 - M_wp_coop
        M_vuln_noncoop = 1.0 - M_wp_noncoop

        # Fused Resilience: % of threat-weighted volume with both RF and kinematic coverage
        fused_resilience = self.calculate_fused_resilience(sensor_list)
        fused_resilience = float(np.clip(np.nan_to_num(fused_resilience, nan=0.0), 0.0, 1.0))

        # Asset Security ROI = Total_Cost / M_wp (upgrade of SCOPAS C_A)
        asset_security_roi = total_cost / max(M_wp_coop, 1e-10)
        asset_security_roi_noncoop = total_cost / max(M_wp_noncoop, 1e-10)
        if not np.isfinite(asset_security_roi):
            asset_security_roi = float("inf")
        if not np.isfinite(asset_security_roi_noncoop):
            asset_security_roi_noncoop = float("inf")

        cost_scaled = total_cost / cost_scale
        fitness = (M_wp_coop, M_wp_noncoop, cost_scaled)

        return {
            "M_wp_coop": M_wp_coop,
            "M_wp_noncoop": M_wp_noncoop,
            "M_vuln_coop": M_vuln_coop,
            "M_vuln_noncoop": M_vuln_noncoop,
            "fused_resilience": fused_resilience,
            "asset_security_roi": asset_security_roi,
            "asset_security_roi_noncoop": asset_security_roi_noncoop,
            "M_c_coop": M_wp_coop,
            "M_c_noncoop": M_wp_noncoop,
            "coverage": M_wp_coop,
            "redundancy": self.calculate_network_redundancy(sensor_list),
            "cost": total_cost,
            "cost_hardware": hardware_cost,
            "cost_sites": cost_sites,
            "num_sensors": len(active),
            "unique_sites": unique_sites,
            "fitness": fitness,
            "evaluated_voxels": len(self._free_voxels),
            "total_voxels": int(np.prod(self.grid_shape)),
        }

    def evaluate_network(self, sensor_list: List[Sensor], 
                        weights: Tuple[float, float, float] = (1.0, 1.0, 0.001)) -> Dict[str, Any]:
        """
        Evaluate the sensor network performance.
        
        Args:
            sensor_list: List of sensors
            weights: Weights for (coverage, redundancy, cost)
            
        Returns:
            Dictionary with evaluation results
        """
        # Calculate metrics
        coverage = self.calculate_network_coverage(sensor_list)
        redundancy = self.calculate_network_redundancy(sensor_list)
        cost = self.calculate_network_cost(sensor_list)
        
        # Calculate weighted fitness
        w1, w2, w3 = weights
        fitness = w1 * coverage + w2 * redundancy - w3 * cost
        
        # Count active sensors
        active_sensors = sum(1 for sensor in sensor_list if sensor.is_active)
        
        return {
            'fitness': fitness,
            'coverage': coverage,
            'redundancy': redundancy,
            'cost': cost,
            'num_sensors': active_sensors,
            'evaluated_voxels': len(self._free_voxels),
            'total_voxels': np.prod(self.grid_shape)
        }
    
    def get_coverage_map(self, sensor_list: List[Sensor], height_level: int = 0) -> np.ndarray:
        """
        Get coverage map for a specific height level.
        
        Args:
            sensor_list: List of sensors
            height_level: Height level (voxel index k)
            
        Returns:
            2D coverage map
        """
        if height_level >= self.grid_shape[2]:
            height_level = self.grid_shape[2] - 1
        
        coverage_map = np.zeros((self.grid_shape[0], self.grid_shape[1]), dtype=float)
        
        # Iterate through voxels at the specified height
        for i in range(self.grid_shape[0]):
            for j in range(self.grid_shape[1]):
                # Skip occupied voxels
                if self.occupancy_grid[i, j, height_level] == 1:
                    coverage_map[i, j] = np.nan  # Mark as occupied
                    continue
                
                # Convert voxel to world coordinates
                x, y, z = self.environment.voxel_to_world(i, j, height_level)
                
                # Calculate individual detection probabilities
                individual_probs = []
                for sensor in sensor_list:
                    if sensor.is_active:
                        pd = calculate_PD(sensor, (x, y, z), self.environment)
                        individual_probs.append(pd)
                
                if individual_probs:
                    # Calculate network coverage
                    network_prob = 1.0 - np.prod([1.0 - p for p in individual_probs])
                    coverage_map[i, j] = network_prob
                else:
                    coverage_map[i, j] = 0.0
        
        return coverage_map
    
    def get_redundancy_map(self, sensor_list: List[Sensor], height_level: int = 0) -> np.ndarray:
        """
        Get redundancy map for a specific height level.
        
        Args:
            sensor_list: List of sensors
            height_level: Height level (voxel index k)
            
        Returns:
            2D redundancy map
        """
        if height_level >= self.grid_shape[2]:
            height_level = self.grid_shape[2] - 1
        
        redundancy_map = np.zeros((self.grid_shape[0], self.grid_shape[1]), dtype=float)
        
        # Iterate through voxels at the specified height
        for i in range(self.grid_shape[0]):
            for j in range(self.grid_shape[1]):
                # Skip occupied voxels
                if self.occupancy_grid[i, j, height_level] == 1:
                    redundancy_map[i, j] = np.nan  # Mark as occupied
                    continue
                
                # Convert voxel to world coordinates
                x, y, z = self.environment.voxel_to_world(i, j, height_level)
                
                # Calculate individual detection probabilities
                individual_probs = []
                for sensor in sensor_list:
                    if sensor.is_active:
                        pd = calculate_PD(sensor, (x, y, z), self.environment)
                        individual_probs.append(pd)
                
                if individual_probs:
                    # Calculate redundancy
                    redundancy = sum(individual_probs)
                    redundancy_map[i, j] = redundancy
                else:
                    redundancy_map[i, j] = 0.0
        
        return redundancy_map
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """
        Get optimization statistics.
        
        Returns:
            Dictionary with optimization statistics
        """
        total_voxels = np.prod(self.grid_shape)
        free_voxels = len(self._free_voxels)
        occupied_voxels = total_voxels - free_voxels
        
        return {
            'total_voxels': total_voxels,
            'free_voxels': free_voxels,
            'occupied_voxels': occupied_voxels,
            'occupancy_ratio': occupied_voxels / total_voxels * 100,
            'optimization_ratio': free_voxels / total_voxels * 100
        }


def create_network_evaluator(environment: UrbanEnvironment) -> NetworkEvaluator:
    """
    Factory function to create a NetworkEvaluator.
    
    Args:
        environment: Urban environment
        
    Returns:
        NetworkEvaluator instance
    """
    return NetworkEvaluator(environment)


def evaluate_sensor_network_optimized(
    sensors: List[Sensor],
    environment: UrbanEnvironment,
    target_altitude: float = None,
    weights: Tuple[float, float, float] = (1.0, 1.0, 0.001)
) -> Dict[str, Any]:
    """
    Convenience function to evaluate a sensor network configuration.
    
    Args:
        sensors: List of sensors to evaluate
        environment: Urban environment
        target_altitude: Optional target altitude (not used with full grid evaluation)
        weights: Weights for (coverage, redundancy, cost)
        
    Returns:
        Dict with evaluation results including:
        - p_net_grid: Grid of network detection probabilities
        - redundancy_grid: Grid of redundancy values
        - avg_p_net: Average network coverage
        - avg_redundancy: Average redundancy
        - fitness: Overall fitness score
    """
    evaluator = NetworkEvaluator(environment)
    results = evaluator.evaluate_network(sensors, weights=weights)
    
    # Criar grids 3D para compatibilidade com métricas SCOPAS
    # Preencher TODAS as camadas de altura para cálculo correto
    p_net_grid = np.zeros(environment.grid_shape, dtype=float)
    redundancy_grid = np.zeros(environment.grid_shape, dtype=float)
    
    # Avaliar cada camada de altura
    print(f"   Avaliando {environment.grid_shape[2]} camadas de altura...")
    for k in range(environment.grid_shape[2]):
        p_net_grid[:, :, k] = evaluator.get_coverage_map(sensors, height_level=k)
        redundancy_grid[:, :, k] = evaluator.get_redundancy_map(sensors, height_level=k)
    
    # Adicionar grids aos resultados
    results['p_net_grid'] = p_net_grid
    results['redundancy_grid'] = redundancy_grid
    results['avg_p_net'] = results['coverage']  # Alias para compatibilidade
    results['avg_redundancy'] = results['redundancy']  # Alias para compatibilidade
    
    return results
