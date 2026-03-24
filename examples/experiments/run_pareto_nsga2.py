#!/usr/bin/env python3
"""
MUSCAT Framework - Pareto optimization using NSGA-II
====================================================

Uses NSGA-II (Genetic Algorithm) to find the Pareto front.

Usage:
    python examples/experiments/run_pareto_nsga2.py --config configs/pareto_city_10x10_final.json
"""

import sys
import json
import argparse
from pathlib import Path
import time
import numpy as np
import matplotlib.pyplot as plt
from typing import List, Tuple, Dict

# Adicionar src ao path (raiz do projeto)
ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from environment import UrbanEnvironment
from sensors import RadarSensor, RFSensor, EOSensor
from network_evaluation import NetworkEvaluator
from genetic_algorithm import SensorNetworkGAGeoJSON
from muscat_metrics import calculate_all_muscat_metrics
from airway_metrics import calculate_metrics_per_airway


class ParetoNSGA2Experiment:
    """Pareto experiment using NSGA-II."""
    
    def __init__(self, config_file: str):
        print("="*80)
        print("MUSCAT FRAMEWORK - Pareto with NSGA-II")
        print("="*80)
        
        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        self.experiment_name = self.config.get('experiment_name', 'pareto_nsga2')
        print(f"\n[Experiment] {self.experiment_name}")
        
        self.results_dir = Path(self.config['output']['results_dir'])
        self.results_dir.mkdir(exist_ok=True, parents=True)
        
        self.env = None
        self.evaluator = None
        self.ga = None
        self.analysis_config = self.config.get('analysis', {})
    
    def load_environment(self):
        """Carrega o ambiente urbano."""
        print("\n" + "="*80)
        print("1. LOADING URBAN ENVIRONMENT")
        print("="*80)
        
        env_config = self.config['environment']
        
        self.env = UrbanEnvironment(
            buildings_geojson_path=env_config['buildings_file'],
            sensor_locations_geojson_path=env_config['sensor_locations_file'],
            voxel_resolution_m=env_config['resolution'],
            bounds_expansion_m=env_config.get('bounds_expansion', 0),
        )
        critical_assets = self.config.get("critical_assets", [])
        if critical_assets:
            self.env.generate_threat_map(critical_assets)
        self.evaluator = NetworkEvaluator(self.env)
        
        print(f"\nOK Environment loaded")
        print(f"  Grid: {self.env.grid_shape} voxels")
        print(f"  Locations: {len(self.env.get_sensor_locations())}")
    
    def setup_ga(self):
        """Configura o GA."""
        print("\n" + "="*80)
        print("2. CONFIGURING NSGA-II")
        print("="*80)
        
        ga_config = self.config.get('pareto_search', {})
        
        population_size = ga_config.get('n_samples', 100)
        n_cores = ga_config.get('n_cores', 16)
        min_sensors = ga_config.get('min_sensors', 3)
        max_sensors = ga_config.get('max_sensors', 15)
        
        print(f"Population: {population_size}")
        print(f"Min sensors: {min_sensors}")
        print(f"Max sensors: {max_sensors}")
        print(f"Cores: {n_cores}")
        
        self.ga = SensorNetworkGAGeoJSON(
            environment=self.env,
            max_sensors=max_sensors,
            min_sensors=min_sensors,
            weights=(1.0, 1.0, 0.001),  # Mc, Redundancy, Cost (mantido para compatibilidade interna)
            n_cores=n_cores,
            config=self.config,
        )
        
        self.min_sensors = min_sensors
        
        print(f"\nOK NSGA-II configured")
    
    def run_optimization(self, algorithm: str = "nsga2"):
        """Executa otimização multi-objetivo (NSGA-II ou NSGA-III)."""
        algo_label = "NSGA-III" if algorithm.strip().lower() == "nsga3" else "NSGA-II"
        print("\n" + "="*80)
        print(f"3. RUNNING {algo_label} (Multi-Objective)")
        print("="*80)
        
        ga_config = self.config.get('pareto_search', {})
        population_size = ga_config.get('n_samples', 100)
        generations = ga_config.get('generations', 50)
        nsga3_ref_p = ga_config.get('nsga3_ref_p', 6)
        
        print(f"Algorithm: {algo_label}")
        print(f"Generations: {generations}")
        print(f"Population: {population_size}\n")
        
        checkpoint_config = self.config.get('checkpoint', {})
        checkpoint_enabled = checkpoint_config.get('enabled', False)
        checkpoint_dir = checkpoint_config.get('dir')
        checkpoint_frequency = int(checkpoint_config.get('frequency', 1))
        checkpoint_prefix = checkpoint_config.get('prefix', self.experiment_name.replace(" ", "_"))
        checkpoint_resume = checkpoint_config.get('resume', False)
        checkpoint_path = None
        if checkpoint_enabled and checkpoint_dir:
            checkpoint_path = Path(checkpoint_dir)
            print(f"Checkpoint {'resume enabled' if checkpoint_resume else 'enabled'} at: {checkpoint_path}")
        elif checkpoint_enabled:
            print("WARNING: Checkpoint enabled but 'dir' not set. Saving disabled.")
            checkpoint_enabled = False
        
        start_time = time.time()
        
        ga_results = self.ga.run_evolution(
            population_size=population_size,
            generations=generations,
            verbose=True,
            show_progress=True,
            checkpoint_dir=str(checkpoint_path) if checkpoint_enabled and checkpoint_path else None,
            checkpoint_prefix=checkpoint_prefix,
            checkpoint_frequency=checkpoint_frequency,
            resume=checkpoint_enabled and checkpoint_resume,
            algorithm=algorithm,
            nsga3_ref_p=nsga3_ref_p,
        )

        pareto_front = ga_results.get('pareto_front', [])
        logbook = ga_results.get('logbook', [])
        self.ga_best_results = ga_results.get('best_results', {})
        self.ga_population = ga_results.get('population', [])
        self.ga_execution_time = ga_results.get('execution_time', 0.0)

        elapsed = time.time() - start_time

        print(f"\nOK {algo_label} completed in {elapsed:.1f}s (~{elapsed/60:.1f} min)")
        print(f"OK Pareto front: {len(pareto_front)} solutions")
        if self.ga_best_results:
            print("  Best individual (global averages):")
            print(f"    • M_wp_coop: {self.ga_best_results.get('M_wp_coop', self.ga_best_results.get('coverage', 0.0))*100:.2f}%  M_wp_noncoop: {self.ga_best_results.get('M_wp_noncoop', 0.0)*100:.2f}%")
            print(f"    • Fused resilience: {self.ga_best_results.get('fused_resilience', 0.0):.3f}  Asset ROI: ${self.ga_best_results.get('asset_security_roi', 0):,.0f}")
            print(f"    • Total cost: ${self.ga_best_results.get('cost', 0.0):,.0f}  Active sensors: {self.ga_best_results.get('num_sensors', 0)}")

        return pareto_front, logbook
    
    def analyze_pareto_front(self, pareto_front):
        """Analisa e salva resultados."""
        print("\n" + "="*80)
        print("4. ANALYZING PARETO FRONT")
        print("="*80)
        
        solutions = []
        max_solutions = self.analysis_config.get('max_solutions')
        if max_solutions is not None:
            max_solutions = max(1, int(max_solutions))
            if len(pareto_front) > max_solutions:
                print(f"\nWARNING: Front has {len(pareto_front)} solutions; analyzing first {max_solutions}")
            pareto_iterable = pareto_front[:max_solutions]
        else:
            pareto_iterable = pareto_front

        site_cost = self.config.get('site_activation_cost', 15000.0)
        use_point_defense = bool(self.config.get('critical_assets'))

        for idx, individual in enumerate(pareto_iterable):
            # Decodificar
            sensors = self.ga.decode_individual(individual)

            if len(sensors) == 0:
                continue

            # Dual-layer / Point Defense metrics (when critical_assets set)
            pd_metrics = {}
            if use_point_defense:
                pd_metrics = self.evaluator.evaluate_network_dual_layer(
                    sensors, site_activation_cost=site_cost
                )

            # Calcular métricas (3D) legacy MUSCAT
            grid_shape = self.env.grid_shape
            p_net_grid = np.zeros(grid_shape, dtype=float)
            redundancy_grid = np.zeros(grid_shape, dtype=float)

            for k in range(grid_shape[2]):
                p_net_grid[:, :, k] = self.evaluator.get_coverage_map(sensors, height_level=k)
                redundancy_grid[:, :, k] = self.evaluator.get_redundancy_map(sensors, height_level=k)

            metrics = calculate_all_muscat_metrics(
                sensors,
                p_net_grid,
                redundancy_grid,
                sensor_detections_list=None,
                threshold=0.8
            )
            metrics['Overlap'] = metrics.get('overlap', metrics.get('avg_redundancy', 0.0))
            if pd_metrics:
                metrics['M_wp_coop'] = pd_metrics.get('M_wp_coop', 0.0)
                metrics['M_wp_noncoop'] = pd_metrics.get('M_wp_noncoop', 0.0)
                metrics['M_vuln_coop'] = pd_metrics.get('M_vuln_coop', 1.0)
                metrics['M_vuln_noncoop'] = pd_metrics.get('M_vuln_noncoop', 1.0)
                metrics['fused_resilience'] = pd_metrics.get('fused_resilience', 0.0)
                metrics['asset_security_roi'] = pd_metrics.get('asset_security_roi', float('inf'))

            # Métricas por aerovia
            airway_altitudes = self.config.get('airway_altitudes', [20, 45, 65])
            airway_metrics = calculate_metrics_per_airway(
                sensors, p_net_grid, redundancy_grid,
                self.env.occupancy_grid, airway_altitudes,
                self.env.voxel_resolution, self.env.bounds[4],
                threshold=0.8
            )
            metrics['airway_metrics'] = airway_metrics

            # Configuração e posições (para visualização 3D)
            sensor_config = {}
            sensor_positions = []
            for sensor in sensors:
                stype = getattr(sensor, 'sensor_type', 'Unknown')
                sensor_config[stype] = sensor_config.get(stype, 0) + 1
                x, y, z = sensor.location
                sensor_positions.append({'type': stype, 'x': float(x), 'y': float(y), 'z': float(z)})

            # Coverage/cost for solution: use M_wp_coop when Point Defense, else Mc
            coverage_val = pd_metrics.get('M_wp_coop', metrics['Mc']) if pd_metrics else metrics['Mc']
            cost_val = pd_metrics.get('cost', metrics.get('total_cost', 0.0)) if pd_metrics else metrics.get('total_cost', 0.0)

            # Status (GREEN se atende requisitos); use M_wp_coop for Point Defense
            req = self.config.get('requirements', {})
            overlap_val = metrics['Overlap']
            status = 'GREEN' if (
                coverage_val >= req.get('min_coverage', 0.75) and
                overlap_val >= req.get('min_overlap', 0.35)
            ) else 'yellow'

            solution = {
                'solution_id': idx + 1,
                'rank': 1,
                'sensor_configuration': sensor_config,
                'sensor_positions': sensor_positions,
                'fitness': list(individual.fitness.values),
                'Mc': metrics['Mc'],
                'M_wp_coop': pd_metrics.get('M_wp_coop', None),
                'M_wp_noncoop': pd_metrics.get('M_wp_noncoop', None),
                'fused_resilience': pd_metrics.get('fused_resilience', None),
                'asset_security_roi': pd_metrics.get('asset_security_roi', None),
                'redundancy': metrics['Overlap'],
                'cost': cost_val,
                'status': status,
                'metrics': metrics
            }
            solutions.append(solution)

        # Ordenar por cobertura (M_wp_coop se Point Defense, senão Mc)
        sort_key = lambda x: (x.get('M_wp_coop') if x.get('M_wp_coop') is not None else x['Mc'])
        solutions.sort(key=sort_key, reverse=True)
        
        # Salvar JSON
        results = {
            'experiment_name': self.experiment_name,
            'config': self.config,
            'pareto_solutions': solutions
        }
        
        results_file = self.results_dir / 'pareto_results.json'
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"OK Results saved: {results_file}")
        
        # Gerar gráficos Pareto
        self.plot_pareto_front(solutions)
        
        # Summary
        green_count = sum(1 for s in solutions if s['status'] == 'GREEN')
        coverages = [s['Mc']*100 for s in solutions]
        costs = [s['cost']/1000 for s in solutions]
        wp_coop = [s['M_wp_coop']*100 for s in solutions if s.get('M_wp_coop') is not None]
        fused = [s['fused_resilience'] for s in solutions if s.get('fused_resilience') is not None]

        print(f"\nSUMMARY:")
        print(f"  • Pareto solutions: {len(solutions)}  GREEN: {green_count}")
        print(f"  • Coverage (Mc): {min(coverages):.1f}% - {max(coverages):.1f}%  Cost: ${min(costs):.0f}K - ${max(costs):.0f}K")
        if wp_coop:
            print(f"  • M_wp_coop: {min(wp_coop):.1f}% - {max(wp_coop):.1f}%  Fused resilience: {min(fused):.2f} - {max(fused):.2f}" if fused else f"  • M_wp_coop: {min(wp_coop):.1f}% - {max(wp_coop):.1f}%")
        
        return results
    
    def plot_pareto_front(self, solutions):
        """Plot Pareto front; use Point Defense metrics when present."""
        costs_k = [s['cost'] / 1000 for s in solutions]
        colors = ['green' if s['status'] == 'GREEN' else 'yellow' for s in solutions]
        use_pd = any(s.get('M_wp_coop') is not None for s in solutions)

        try:
            plt.style.use('seaborn-v0_8-whitegrid')
        except Exception:
            pass
        font_title = 12
        font_axis = 11

        if use_pd:
            wp_coop = [(s.get('M_wp_coop') or 0) * 100 for s in solutions]
            fused = [(s.get('fused_resilience') or 0) * 100 for s in solutions]
            wp_noncoop = [(s.get('M_wp_noncoop') or 0) * 100 for s in solutions]

            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
            fig.suptitle(self.experiment_name, fontsize=font_title, y=1.02)

            ax1.scatter(costs_k, wp_coop, c=colors, s=100, alpha=0.8, edgecolors='black', linewidths=0.8)
            ax1.set_xlabel('Cost ($K)', fontsize=font_axis)
            ax1.set_ylabel('M_wp coop (%)', fontsize=font_axis)
            ax1.set_title('Weighted protection (coop) vs cost', fontsize=font_title)
            ax1.grid(True, alpha=0.3)

            ax2.scatter(costs_k, fused, c=colors, s=100, alpha=0.8, edgecolors='black', linewidths=0.8)
            ax2.set_xlabel('Cost ($K)', fontsize=font_axis)
            ax2.set_ylabel('Fused resilience (%)', fontsize=font_axis)
            ax2.set_title('Fused resilience vs cost', fontsize=font_title)
            ax2.grid(True, alpha=0.3)

            plt.tight_layout()
            plt.savefig(self.results_dir / 'pareto_front.png', dpi=300, bbox_inches='tight')
            print(f"  OK Saved: {self.results_dir / 'pareto_front.png'}")
            plt.close()

            from mpl_toolkits.mplot3d import Axes3D
            fig = plt.figure(figsize=(10, 8))
            ax = fig.add_subplot(111, projection='3d')
            fig.suptitle(self.experiment_name, fontsize=font_title, y=1.02)
            ax.scatter(wp_coop, wp_noncoop, costs_k, c=colors, s=100, alpha=0.8, edgecolors='black', linewidths=0.8)
            ax.set_xlabel('M_wp coop (%)', fontsize=font_axis)
            ax.set_ylabel('M_wp noncoop (%)', fontsize=font_axis)
            ax.set_zlabel('Cost ($K)', fontsize=font_axis)
            ax.set_title('Pareto front (Point Defense)', fontsize=font_title)
            plt.tight_layout()
            plt.savefig(self.results_dir / 'pareto_front_3d.png', dpi=300, bbox_inches='tight')
            print(f"  OK Saved: {self.results_dir / 'pareto_front_3d.png'}")
            plt.close()
        else:
            coverages = [s['Mc'] * 100 for s in solutions]
            redundancies = [s['redundancy'] for s in solutions]

            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
            fig.suptitle(self.experiment_name, fontsize=font_title, y=1.02)

            ax1.scatter(costs_k, coverages, c=colors, s=100, alpha=0.8, edgecolors='black', linewidths=0.8)
            ax1.set_xlabel('Cost ($K)', fontsize=font_axis)
            ax1.set_ylabel('Coverage (%)', fontsize=font_axis)
            ax1.set_title('Coverage vs cost', fontsize=font_title)
            ax1.grid(True, alpha=0.3)

            ax2.scatter(costs_k, redundancies, c=colors, s=100, alpha=0.8, edgecolors='black', linewidths=0.8)
            ax2.set_xlabel('Cost ($K)', fontsize=font_axis)
            ax2.set_ylabel('Redundancy', fontsize=font_axis)
            ax2.set_title('Redundancy vs cost', fontsize=font_title)
            ax2.grid(True, alpha=0.3)

            plt.tight_layout()
            plt.savefig(self.results_dir / 'pareto_front.png', dpi=300, bbox_inches='tight')
            print(f"  OK Saved: {self.results_dir / 'pareto_front.png'}")
            plt.close()

            from mpl_toolkits.mplot3d import Axes3D
            fig = plt.figure(figsize=(10, 8))
            ax = fig.add_subplot(111, projection='3d')
            fig.suptitle(self.experiment_name, fontsize=font_title, y=1.02)
            ax.scatter(coverages, redundancies, costs_k, c=colors, s=100, alpha=0.8, edgecolors='black', linewidths=0.8)
            ax.set_xlabel('Coverage (%)', fontsize=font_axis)
            ax.set_ylabel('Redundancy', fontsize=font_axis)
            ax.set_zlabel('Cost ($K)', fontsize=font_axis)
            ax.set_title('Pareto front 3D', fontsize=font_title)
            plt.tight_layout()
            plt.savefig(self.results_dir / 'pareto_front_3d.png', dpi=300, bbox_inches='tight')
            print(f"  OK Saved: {self.results_dir / 'pareto_front_3d.png'}")
            plt.close()
    
    def run(self):
        """Executa experimento completo."""
        start_time = time.time()
        
        self.load_environment()
        self.setup_ga()
        pareto_front, logbook = self.run_optimization()
        results = self.analyze_pareto_front(pareto_front)
        
        total_time = time.time() - start_time
        
        print("\n" + "="*80)
        print(f"EXPERIMENT COMPLETED IN {total_time:.1f}s (~{total_time/60:.1f} min)")
        print("="*80)
        
        return results


def main():
    parser = argparse.ArgumentParser(description='Pareto optimization with NSGA-II')
    parser.add_argument('--config', type=str, required=True, help='Config JSON file')
    args = parser.parse_args()
    
    experiment = ParetoNSGA2Experiment(args.config)
    experiment.run()


if __name__ == '__main__':
    main()


