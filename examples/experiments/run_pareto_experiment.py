#!/usr/bin/env python3
"""
MUSCAT Framework - Experimento de Otimização Pareto
====================================================

Este script explora a fronteira de Pareto para balancear custo e requisitos
atendidos, sem comparar com configurações específicas do MUSCAT.

Uso:
    python examples/experiments/run_pareto_experiment.py --config configs/pareto_city_3x2.json
"""

import sys
import json
import argparse
from pathlib import Path
import time
import numpy as np
import matplotlib.pyplot as plt
import random
from typing import List, Tuple, Dict
from multiprocessing import Pool, cpu_count
import functools

# Adicionar src ao path (raiz do projeto)
ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from environment import UrbanEnvironment
from sensors import RadarSensor, RFSensor, EOSensor
from network_evaluation import NetworkEvaluator
from muscat_metrics import calculate_all_muscat_metrics, check_muscat_requirements
from airway_metrics import calculate_metrics_per_airway, format_airway_results_table


class ParetoExperiment:
    """Experimento focado em análise de fronteira de Pareto."""
    
    def __init__(self, config_file: str):
        print("="*80)
        print("MUSCAT FRAMEWORK - Análise de Fronteira de Pareto")
        print("="*80)
        
        with open(config_file, 'r') as f:
            self.config = json.load(f)
        
        self.experiment_name = self.config.get('experiment_name', 'pareto_experiment')
        print(f"\n📋 Experimento: {self.experiment_name}")
        print(f"📄 Descrição: {self.config.get('description', 'N/A')}")
        
        self.results_dir = Path(self.config['output']['results_dir'])
        self.results_dir.mkdir(exist_ok=True, parents=True)
        
        self.env = None
        self.evaluator = None
        self.sensor_locations = []
        self.pareto_solutions = []
    
    def load_environment(self):
        """Carrega o ambiente urbano."""
        print("\n" + "="*80)
        print("1. CARREGANDO AMBIENTE URBANO")
        print("="*80)
        
        env_config = self.config['environment']
        
        buildings_file = env_config['buildings_file']
        sensors_file = env_config['sensor_locations_file']
        resolution = env_config['resolution']
        
        print(f"Tipo: {env_config['type']}")
        print(f"Prédios: {buildings_file}")
        print(f"Sensores: {sensors_file}")
        print(f"Resolução: {resolution}m\n")
        
        self.env = UrbanEnvironment(
            buildings_geojson_path=buildings_file,
            sensor_locations_geojson_path=sensors_file,
            voxel_resolution_m=resolution,
            bounds_expansion_m=env_config.get("bounds_expansion", 0),
        )
        critical_assets = self.config.get("critical_assets", [])
        if critical_assets:
            self.env.generate_threat_map(critical_assets)
        self.evaluator = NetworkEvaluator(self.env)
        self.sensor_locations = self.env.get_sensor_locations()
        
        print(f"\n✓ Ambiente carregado com sucesso")
        print(f"  Grid: {self.env.grid_shape} voxels")
        print(f"  Área: {self.env.bounds[1]:.0f}m × {self.env.bounds[3]:.0f}m")
        print(f"  Locais disponíveis: {len(self.sensor_locations)}")
    
    def create_individual(self) -> List[Tuple[str, bool]]:
        """Cria indivíduo aleatório (configuração de sensores)."""
        sensor_types = ['Radar', 'RF', 'EO']
        n_locs = len(self.sensor_locations)
        
        # Obter limites de sensores da configuração (se existir)
        min_sensors = self.config.get('pareto_search', {}).get('min_sensors', 3)
        max_sensors = self.config.get('pareto_search', {}).get('max_sensors', 
                                                                min(20, int(n_locs * 0.3)))
        
        # Limitar número de sensores ativos
        n_active = random.randint(min_sensors, max_sensors)
        active_indices = random.sample(range(n_locs), n_active)
        
        individual = []
        for i in range(n_locs):
            sensor_type = random.choice(sensor_types)
            is_active = i in active_indices
            individual.append((sensor_type, is_active))
        
        return individual
    
    def decode_individual(self, individual: List[Tuple[str, bool]]) -> List:
        """Decodifica indivíduo em lista de sensores."""
        sensors = []
        sensor_types_config = self.config['sensors']['types']
        
        for idx, (sensor_type, is_active) in enumerate(individual):
            if not is_active or idx >= len(self.sensor_locations):
                continue
            
            loc = self.sensor_locations[idx]
            type_config = sensor_types_config.get(sensor_type, {})
            cost = type_config.get('cost', 1.0)
            
            if sensor_type == 'Radar':
                sensor = RadarSensor(location=loc, cost=cost)
                # Configurar parâmetros específicos
                sensor.Pt = type_config.get('power_W', 1000.0)
                sensor.G = type_config.get('gain_dB', 30.0)
                sensor.frequency = type_config.get('frequency_Hz', 2.4e9)
                sensor.wavelength = 3e8 / sensor.frequency
                
            elif sensor_type == 'RF':
                sensor = RFSensor(location=loc, cost=cost)
                sensor.sensitivity = type_config.get('sensitivity_dBm', -90.0)
                sensor.frequency = type_config.get('frequency_Hz', 900e6)
                
            elif sensor_type == 'EO':
                sensor = EOSensor(location=loc, cost=cost)
            else:
                continue
            
            sensors.append(sensor)
        
        return sensors
    
    def evaluate_individual(self, individual: List[Tuple[str, bool]]) -> Tuple[float, float, float, Dict]:
        """
        Avalia indivíduo.
        
        Returns:
            (Mc, avg_redundancy, cost, metrics_dict)
        """
        sensors = self.decode_individual(individual)
        
        if len(sensors) == 0:
            return (0.0, 0.0, 0.0, {})
        
        # Avaliar cobertura 3D
        p_net_grid = np.zeros(self.env.grid_shape, dtype=float)
        redundancy_grid = np.zeros(self.env.grid_shape, dtype=float)
        
        for k in range(self.env.grid_shape[2]):
            p_net_grid[:, :, k] = self.evaluator.get_coverage_map(sensors, height_level=k)
            redundancy_grid[:, :, k] = self.evaluator.get_redundancy_map(sensors, height_level=k)
        
        # Métricas MUSCAT gerais
        metrics = calculate_all_muscat_metrics(
            sensors, p_net_grid, redundancy_grid=redundancy_grid, threshold=0.8
        )
        
        # Métricas por aerovia (20m, 50m, 100m)
        airway_altitudes = self.config.get('airway_altitudes', [20, 50, 100])
        airway_metrics = calculate_metrics_per_airway(
            sensors,
            p_net_grid,
            redundancy_grid,
            self.env.occupancy_grid,
            airway_altitudes=airway_altitudes,
            voxel_resolution=self.env.voxel_resolution,
            z_min=self.env.bounds[4],
            threshold=0.8
        )
        
        metrics['airway_metrics'] = airway_metrics
        
        # Verificar requisitos
        requirements = check_muscat_requirements(
            metrics,
            min_coverage=self.config['requirements']['min_coverage'],
            min_overlap=self.config['requirements']['min_overlap']
        )
        
        metrics.update(requirements)
        
        Mc = metrics['Mc']
        redundancy = metrics.get('avg_redundancy', 0.0)
        cost = metrics['total_cost']
        
        return (Mc, redundancy, cost, metrics)
    
    def dominates(self, obj1: Tuple, obj2: Tuple) -> bool:
        """
        Verifica se obj1 domina obj2 no sentido de Pareto.
        
        Objetivos: (maximize Mc, maximize redundancy, minimize cost)
        """
        better_in_all = True
        strictly_better_in_one = False
        
        # Mc (maior é melhor)
        if obj1[0] < obj2[0]:
            better_in_all = False
        elif obj1[0] > obj2[0]:
            strictly_better_in_one = True
        
        # Redundancy (maior é melhor)
        if obj1[1] < obj2[1]:
            better_in_all = False
        elif obj1[1] > obj2[1]:
            strictly_better_in_one = True
        
        # Cost (menor é melhor)
        if obj1[2] > obj2[2]:
            better_in_all = False
        elif obj1[2] < obj2[2]:
            strictly_better_in_one = True
        
        return better_in_all and strictly_better_in_one
    
    def find_pareto_front(self, population_objectives: List[Tuple]) -> List[int]:
        """
        Encontra índices das soluções na fronteira de Pareto.
        """
        n = len(population_objectives)
        is_pareto = [True] * n
        
        for i in range(n):
            for j in range(n):
                if i != j and self.dominates(population_objectives[j], population_objectives[i]):
                    is_pareto[i] = False
                    break
        
        return [i for i in range(n) if is_pareto[i]]
    
    def _evaluate_wrapper(self, individual):
        """Wrapper para avaliação paralela."""
        Mc, redundancy, cost, metrics = self.evaluate_individual(individual)
        return (individual, Mc, redundancy, cost, metrics)
    
    def run_pareto_search(self):
        """Executa busca pela fronteira de Pareto com paralelização."""
        print("\n" + "="*80)
        print("2. BUSCA PELA FRONTEIRA DE PARETO (PARALELIZADA)")
        print("="*80)
        
        pareto_config = self.config.get('pareto_search', {})
        n_samples = pareto_config.get('n_samples', 100)
        n_cores = pareto_config.get('n_cores', min(16, cpu_count()))
        
        print(f"🚀 Configuração:")
        print(f"  • Amostras: {n_samples}")
        print(f"  • Cores: {n_cores} de {cpu_count()} disponíveis")
        print(f"  • Speedup esperado: ~{n_cores}x\n")
        
        # Gerar população inicial
        print(f"Gerando {n_samples} configurações aleatórias...")
        population_to_eval = [self.create_individual() for _ in range(n_samples)]
        
        # Avaliar em paralelo
        print(f"Avaliando {n_samples} configurações com {n_cores} cores...\n")
        start_time = time.time()
        
        if n_cores > 1:
            with Pool(processes=n_cores) as pool:
                results = pool.map(self._evaluate_wrapper, population_to_eval)
        else:
            results = [self._evaluate_wrapper(ind) for ind in population_to_eval]
        
        eval_time = time.time() - start_time
        
        # Processar resultados
        population = []
        objectives = []
        metrics_list = []
        
        for individual, Mc, redundancy, cost, metrics in results:
            population.append(individual)
            objectives.append((Mc, redundancy, cost))
            metrics_list.append(metrics)
        
        print(f"✓ {n_samples} configurações avaliadas em {eval_time:.1f}s")
        print(f"  • Tempo médio por configuração: {eval_time/n_samples:.2f}s")
        if n_cores > 1:
            print(f"  • Speedup real: ~{(eval_time/n_samples)*n_samples/eval_time:.1f}x")
        
        # Encontrar fronteira de Pareto
        print("\nIdentificando fronteira de Pareto...")
        pareto_indices = self.find_pareto_front(objectives)
        
        print(f"✓ Fronteira de Pareto: {len(pareto_indices)} soluções ótimas")
        
        # Armazenar soluções Pareto
        self.pareto_solutions = []
        for idx in range(len(pareto_indices)):
            i = pareto_indices[idx]
            solution = {
                'individual': population[i],
                'objectives': objectives[i],
                'metrics': metrics_list[i],
                'Mc': objectives[i][0],
                'redundancy': objectives[i][1],
                'cost': objectives[i][2]
            }
            self.pareto_solutions.append(solution)
        
        # Ordenar por custo
        self.pareto_solutions.sort(key=lambda x: x['cost'])
        
        # Mostrar soluções
        print("\n" + "="*80)
        print("SOLUÇÕES NA FRONTEIRA DE PARETO")
        print("="*80)
        print(f"\n{'#':<4} {'Mc (%)':<10} {'Redund.':<10} {'Custo':<12} {'Status':<10} {'Sensores':<12}")
        print("-" * 80)
        
        for i, sol in enumerate(self.pareto_solutions):
            metrics = sol['metrics']
            status = metrics.get('status', 'unknown').upper()
            
            # Contar sensores
            sensors = self.decode_individual(sol['individual'])
            sensor_counts = {}
            for s in sensors:
                stype = s.__class__.__name__.replace('Sensor', '')
                sensor_counts[stype] = sensor_counts.get(stype, 0) + 1
            
            sensor_str = "+".join([f"{c}{t}" for t, c in sensor_counts.items()])
            
            print(f"{i+1:<4} {sol['Mc']*100:<10.2f} {sol['redundancy']:<10.2f} "
                  f"{sol['cost']:<12.0f} {status:<10} {sensor_str:<12}")
    
    def analyze_tradeoffs(self):
        """Analisa trade-offs na fronteira de Pareto."""
        print("\n" + "="*80)
        print("3. ANÁLISE DE TRADE-OFFS")
        print("="*80)
        
        # Filtrar soluções que atendem requisitos
        req_coverage = self.config['requirements']['min_coverage']
        req_overlap = self.config['requirements']['min_overlap']
        
        green_solutions = [s for s in self.pareto_solutions 
                          if s['metrics'].get('status') == 'green']
        
        yellow_solutions = [s for s in self.pareto_solutions 
                           if s['metrics'].get('status') == 'yellow']
        
        red_solutions = [s for s in self.pareto_solutions 
                        if s['metrics'].get('status') == 'red']
        
        print(f"\n🟢 GREEN (todos requisitos): {len(green_solutions)} soluções")
        print(f"🟡 YELLOW (1 requisito): {len(yellow_solutions)} soluções")
        print(f"🔴 RED (0 requisitos): {len(red_solutions)} soluções")
        
        if green_solutions:
            print("\n✨ MELHOR SOLUÇÃO (GREEN com menor custo):")
            best = green_solutions[0]  # já ordenado por custo
            
            sensors = self.decode_individual(best['individual'])
            sensor_counts = {}
            for s in sensors:
                stype = s.__class__.__name__.replace('Sensor', '')
                sensor_counts[stype] = sensor_counts.get(stype, 0) + 1
            
            print(f"  Configuração: {'+'.join([f'{c}{t}' for t, c in sensor_counts.items()])}")
            print(f"  Cobertura (Mc): {best['Mc']*100:.2f}%")
            print(f"  Redundância: {best['redundancy']:.2f}")
            print(f"  Custo: ${best['cost']:,.0f}")
            print(f"  CA: {best['metrics'].get('CA', 0):.2f}")
            
            print("\n📊 ALTERNATIVAS GREEN (balanceando custo vs cobertura):")
            for i, sol in enumerate(green_solutions[:5]):  # Top 5
                sensors = self.decode_individual(sol['individual'])
                sensor_counts = {}
                for s in sensors:
                    stype = s.__class__.__name__.replace('Sensor', '')
                    sensor_counts[stype] = sensor_counts.get(stype, 0) + 1
                
                print(f"\n  {i+1}. {'+'.join([f'{c}{t}' for t, c in sensor_counts.items()])}")
                print(f"     Mc={sol['Mc']*100:.1f}%, Redund={sol['redundancy']:.2f}, "
                      f"Custo=${sol['cost']:,.0f}")
        else:
            print("\n⚠️  Nenhuma solução GREEN encontrada")
            print(f"    Requisitos: Mc ≥ {req_coverage*100:.0f}%, Overlap ≥ {req_overlap*100:.0f}%")
            
            if yellow_solutions:
                print("\n🟡 Melhor solução YELLOW:")
                best_yellow = min(yellow_solutions, key=lambda x: x['cost'])
                print(f"  Mc={best_yellow['Mc']*100:.1f}%, Redund={best_yellow['redundancy']:.2f}, "
                      f"Custo=${best_yellow['cost']:,.0f}")
    
    def generate_visualizations(self):
        """Gera visualizações da fronteira de Pareto."""
        print("\n" + "="*80)
        print("4. GERANDO VISUALIZAÇÕES")
        print("="*80)
        
        if not self.pareto_solutions:
            print("⚠️  Nenhuma solução para visualizar")
            return
        
        # Extrair dados
        costs = [s['cost'] for s in self.pareto_solutions]
        coverages = [s['Mc'] * 100 for s in self.pareto_solutions]
        redundancies = [s['redundancy'] for s in self.pareto_solutions]
        statuses = [s['metrics'].get('status', 'unknown') for s in self.pareto_solutions]
        
        # Cores por status
        color_map = {'green': '#00ff00', 'yellow': '#ffff00', 'red': '#ff0000', 'unknown': '#808080'}
        colors = [color_map.get(s, '#808080') for s in statuses]
        
        # 1. Custo vs Cobertura
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        
        axes[0].scatter(costs, coverages, c=colors, s=100, alpha=0.7, edgecolors='black')
        axes[0].set_xlabel('Custo Total ($)', fontsize=12)
        axes[0].set_ylabel('Cobertura Mc (%)', fontsize=12)
        axes[0].set_title('Fronteira de Pareto: Custo vs Cobertura', fontsize=14, fontweight='bold')
        axes[0].grid(True, alpha=0.3)
        
        # Linha de requisito mínimo
        min_coverage = self.config['requirements']['min_coverage'] * 100
        axes[0].axhline(y=min_coverage, color='red', linestyle='--', label=f'Mc mínimo ({min_coverage}%)')
        axes[0].legend()
        
        # 2. Custo vs Redundância
        axes[1].scatter(costs, redundancies, c=colors, s=100, alpha=0.7, edgecolors='black')
        axes[1].set_xlabel('Custo Total ($)', fontsize=12)
        axes[1].set_ylabel('Redundância Média', fontsize=12)
        axes[1].set_title('Fronteira de Pareto: Custo vs Redundância', fontsize=14, fontweight='bold')
        axes[1].grid(True, alpha=0.3)
        
        # Linha de requisito mínimo
        min_overlap = self.config['requirements']['min_overlap']
        axes[1].axhline(y=min_overlap, color='red', linestyle='--', label=f'Overlap mínimo ({min_overlap})')
        axes[1].legend()
        
        plt.tight_layout()
        
        output_file = self.results_dir / "pareto_front.png"
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"✓ Gráfico salvo: {output_file}")
        plt.close()
        
        # 3. Gráfico 3D
        from mpl_toolkits.mplot3d import Axes3D
        
        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection='3d')
        
        ax.scatter(coverages, redundancies, costs, c=colors, s=100, alpha=0.7, edgecolors='black')
        ax.set_xlabel('Cobertura Mc (%)', fontsize=11)
        ax.set_ylabel('Redundância', fontsize=11)
        ax.set_zlabel('Custo ($)', fontsize=11)
        ax.set_title('Fronteira de Pareto 3D', fontsize=14, fontweight='bold')
        
        output_file_3d = self.results_dir / "pareto_front_3d.png"
        plt.savefig(output_file_3d, dpi=300, bbox_inches='tight')
        print(f"✓ Gráfico 3D salvo: {output_file_3d}")
        plt.close()
    
    def save_results(self):
        """Salva resultados em JSON."""
        print("\n" + "="*80)
        print("5. SALVANDO RESULTADOS")
        print("="*80)
        
        results_json = []
        for i, sol in enumerate(self.pareto_solutions):
            sensors = self.decode_individual(sol['individual'])
            sensor_counts = {}
            for s in sensors:
                stype = s.__class__.__name__.replace('Sensor', '')
                sensor_counts[stype] = sensor_counts.get(stype, 0) + 1
            
            result = {
                'rank': i + 1,
                'sensor_configuration': sensor_counts,
                'Mc': float(sol['Mc']),
                'redundancy': float(sol['redundancy']),
                'cost': float(sol['cost']),
                'status': sol['metrics'].get('status', 'unknown'),
                'metrics': {k: float(v) if isinstance(v, (int, float, np.number)) else v 
                           for k, v in sol['metrics'].items() 
                           if k not in ['config_spec']}
            }
            results_json.append(result)
        
        output_data = {
            'experiment_name': self.experiment_name,
            'description': self.config.get('description', ''),
            'config': self.config,
            'n_pareto_solutions': len(self.pareto_solutions),
            'pareto_solutions': results_json,
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        results_file = self.results_dir / "pareto_results.json"
        with open(results_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"✓ Resultados salvos: {results_file}")
    
    def run(self):
        """Executa experimento completo."""
        start_time = time.time()
        
        try:
            self.load_environment()
            self.run_pareto_search()
            self.analyze_tradeoffs()
            self.generate_visualizations()
            self.save_results()
            
            total_time = time.time() - start_time
            
            print("\n" + "="*80)
            print("✅ EXPERIMENTO CONCLUÍDO COM SUCESSO!")
            print("="*80)
            print(f"Tempo total: {total_time/60:.1f} minutos")
            print(f"Soluções Pareto: {len(self.pareto_solutions)}")
            print(f"Resultados em: {self.results_dir}/")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Erro durante execução: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    parser = argparse.ArgumentParser(
        description='MUSCAT Framework - Análise de Fronteira de Pareto',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplo de uso:
  python examples/experiments/run_pareto_experiment.py --config configs/pareto_city_3x2.json
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        required=True,
        help='Caminho para arquivo de configuração JSON'
    )
    
    args = parser.parse_args()
    
    if not Path(args.config).exists():
        print(f"❌ Arquivo de configuração não encontrado: {args.config}")
        sys.exit(1)
    
    experiment = ParetoExperiment(args.config)
    success = experiment.run()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

