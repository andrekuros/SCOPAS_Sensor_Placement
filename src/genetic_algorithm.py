"""
Genetic Algorithm for C-UAS Sensor Network Optimization (GeoJSON-based)
Uses DEAP (deap_base) as the optimization algorithms base.
"""

import random
import numpy as np
from typing import List, Tuple, Dict, Any, Optional
from deap import creator, tools
from tqdm import tqdm
import time
from multiprocessing import Pool, cpu_count
import functools
import copy
import pickle
from pathlib import Path

from deap_base import (
    setup_multi_objective_creator,
    create_toolbox,
    run_nsga2_evolution,
    uniform_reference_points,
    nsga3_min_population,
)
from environment import UrbanEnvironment
from sensors import create_sensor, create_sensor_from_config
from network_evaluation import NetworkEvaluator, DEFAULT_SITE_ACTIVATION_COST

# DEAP as base: multi-objective creator (coverage, redundancy, -cost)
setup_multi_objective_creator((1.0, 1.0, -1.0))


class SensorNetworkGAGeoJSON:
    """
    Genetic Algorithm for optimizing sensor network deployment using GeoJSON locations.
    """
    
    def __init__(self, environment: UrbanEnvironment,
                 max_sensors: int = 20,
                 min_sensors: int = 1,
                 weights: Tuple[float, float, float] = (1.0, 1.0, 0.001),
                 n_cores: int = None,
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Genetic Algorithm.
        
        Args:
            environment: Urban environment with GeoJSON data
            max_sensors: Maximum number of sensors to deploy
            weights: Weights for (coverage, redundancy, cost)
            n_cores: Number of CPU cores to use for parallelization
            config: Optional config dict; if provided, sensor_types and type params from config['sensors']['types']
        """
        self.environment = environment
        self.max_sensors = max_sensors
        self.min_sensors = max(1, min_sensors)
        self.weights = weights
        self.evaluator = NetworkEvaluator(environment)
        objective_mode = (config or {}).get("optimization", {}).get("objectives", "dual_layer")
        # Single-layer optimization modes (2 objectives)
        self._noncoop_only = objective_mode == "noncoop_only"
        self._coop_only = objective_mode == "coop_only"
        
        # Get sensor locations from GeoJSON
        self.sensor_locations = environment.get_sensor_locations()
        self.num_locations = len(self.sensor_locations)
        
        # Sensor types from config or default
        if config and "sensors" in config and "types" in config:
            self.sensor_types = list(config["sensors"]["types"].keys())
            self.sensor_types_config = config["sensors"]["types"]
        else:
            self.sensor_types = ["Radar", "RF", "EO"]
            self.sensor_types_config = {}
        # Noncoop-only: use only Radar and EO (no RF)
        if self._noncoop_only and "RF" in self.sensor_types:
            self.sensor_types = [t for t in self.sensor_types if t != "RF"]
            self.sensor_types_config = {k: v for k, v in self.sensor_types_config.items() if k != "RF"}
            if not self.sensor_types:
                raw = (config or {}).get("sensors", {}).get("types", {})
                self.sensor_types = [t for t in ("Radar", "EO") if t in raw] or ["Radar", "EO"]
                self.sensor_types_config = {k: raw[k] for k in self.sensor_types if k in raw}
        # Site activation cost (CapEx) for dual-layer evaluation
        self.site_activation_cost = float(
            config.get("site_activation_cost", DEFAULT_SITE_ACTIVATION_COST)
            if config else DEFAULT_SITE_ACTIVATION_COST
        )
        # Orientation options (degrees) for directional sensors: multiple radars at same site can point different ways
        self.orientation_angles = list(config.get("orientation_angles_deg", [0.0, 120.0, 240.0]) if config else [0.0, 120.0, 240.0])
        self.num_orientations = max(1, len(self.orientation_angles))
        
        # Configure parallelization
        if n_cores is None:
            self.n_cores = min(16, cpu_count())  # Use up to 16 cores
        else:
            self.n_cores = min(n_cores, cpu_count())
        
        print(f"Parallelization: {self.n_cores} cores of {cpu_count()} available")
        print(f"Sensor locations: {self.num_locations}")
        print(f"Sensor types: {len(self.sensor_types)} ({', '.join(self.sensor_types)})")
        print(f"Orientation options: {self.num_orientations} directions {self.orientation_angles}")
        
        # Setup DEAP (via deap_base; map registered inside create_toolbox when n_cores > 1)
        self._setup_deap()
    
    def _setup_deap(self):
        """Setup DEAP toolbox via deap_base (single base for all optimization algorithms)."""
        map_func = self._parallel_map if self.n_cores > 1 else None
        self.toolbox = create_toolbox(
            individual_func=self._create_individual,
            evaluate_func=self._evaluate_individual,
            mate_func=self._crossover,
            mutate_func=self._mutate,
            map_func=map_func,
            select_survival=tools.selNSGA2,
            select_parents=tools.selTournamentDCD,
        )
    
    def _create_individual(self) -> creator.Individual:
        """
        Create a random individual (chromosome).
        Gene: (location_index, sensor_type_index, orientation_index, active_bit)
        so multiple radars at the same site can have different directions.
        """
        individual = []
        
        for _ in range(self.max_sensors):
            location_index = random.randint(0, self.num_locations - 1)
            sensor_type_index = random.randint(0, len(self.sensor_types) - 1)
            orientation_index = random.randint(0, self.num_orientations - 1)
            active_bit = random.randint(0, 1)
            individual.append((location_index, sensor_type_index, orientation_index, active_bit))

        # Ensure minimum number of active sensors
        active_indices = [i for i, gene in enumerate(individual) if gene[3] == 1]
        if len(active_indices) < self.min_sensors:
            needed = self.min_sensors - len(active_indices)
            available = [i for i in range(len(individual)) if i not in active_indices]
            chosen = random.sample(available, min(needed, len(available)))
            for idx in chosen:
                loc, stype, orient, _ = individual[idx]
                individual[idx] = (loc, stype, orient, 1)
        
        return creator.Individual(individual)
    
    def _decode_individual(self, individual: creator.Individual) -> List[Any]:
        """
        Decode individual (chromosome) to sensor list.
        Gene: (location_index, sensor_type_index, orientation_index, active_bit).
        Sets sensor.azimuth_deg so radars/EO at same site can point in different directions.
        """
        sensor_list = []
        for gene in individual:
            # Support both 4-tuple (with orientation) and 3-tuple (legacy)
            if len(gene) == 4:
                location_index, sensor_type_index, orientation_index, active_bit = gene
            else:
                location_index, sensor_type_index, active_bit = gene[0], gene[1], gene[2]
                orientation_index = 0
            
            if active_bit != 1:
                continue
            if location_index >= len(self.sensor_locations):
                continue
            location = self.sensor_locations[location_index]
            sensor_type = self.sensor_types[sensor_type_index]
            azimuth = self.orientation_angles[orientation_index % self.num_orientations]
            
            if self.sensor_types_config:
                sensor = create_sensor_from_config(
                    sensor_type, location, self.sensor_types_config.get(sensor_type, {})
                )
            else:
                sensor = create_sensor(sensor_type, location)
            sensor.azimuth_deg = azimuth
            sensor.is_active = True
            sensor_list.append(sensor)
        return sensor_list
    
    def _evaluate_individual(self, individual: creator.Individual) -> Tuple[float]:
        """
        Evaluate individual fitness.
        
        Args:
            individual: Individual chromosome
            
        Returns:
            Fitness tuple
        """
        sensor_list = self._decode_individual(individual)

        # Penalize individuals with too few active sensors
        if len(sensor_list) < self.min_sensors:
            penalty_cost = 1_000_000.0
            if self._noncoop_only or self._coop_only:
                return (0.0, penalty_cost / 100000.0)
            return (0.0, 0.0, penalty_cost / 100000.0)

        results = self.evaluator.evaluate_network_dual_layer(
            sensor_list, site_activation_cost=self.site_activation_cost
        )
        if self._noncoop_only:
            # SCOPAS logic: optimize M_c (noncoop coverage) and cost
            return (results["M_wp_noncoop"], results["fitness"][2])
        if self._coop_only:
            # SCOPAS logic: optimize cooperative weighted protection and cost
            return (results["M_wp_coop"], results["fitness"][2])
        return results["fitness"]

    def _evaluate_individual_parallel(self, individual: creator.Individual) -> Tuple[float]:
        """
        Evaluate individual fitness for parallel processing.
        
        Args:
            individual: Individual chromosome
            
        Returns:
            Fitness tuple
        """
        sensor_list = self._decode_individual(individual)

        if len(sensor_list) < self.min_sensors:
            penalty_cost = 1_000_000.0
            if self._noncoop_only or self._coop_only:
                return (0.0, penalty_cost / 100000.0)
            return (0.0, 0.0, penalty_cost / 100000.0)

        results = self.evaluator.evaluate_network_dual_layer(
            sensor_list, site_activation_cost=self.site_activation_cost
        )
        if self._noncoop_only:
            return (results["M_wp_noncoop"], results["fitness"][2])
        if self._coop_only:
            return (results["M_wp_coop"], results["fitness"][2])
        return results["fitness"]
    
    def _parallel_map(self, func, iterable):
        """
        Parallel map function for DEAP.
        
        Args:
            func: Function to apply
            iterable: Iterable to process
            
        Returns:
            List of results
        """
        if self.n_cores <= 1:
            return list(map(func, iterable))
        
        partial_func = functools.partial(self._evaluate_individual_parallel)
        with Pool(processes=self.n_cores) as pool:
            results = pool.map(partial_func, iterable)
        return results
    
    def _crossover(self, ind1: creator.Individual, ind2: creator.Individual) -> Tuple[creator.Individual, creator.Individual]:
        """
        Two-point crossover operation.
        
        Args:
            ind1: First individual
            ind2: Second individual
            
        Returns:
            Two offspring individuals
        """
        # Two-point crossover
        size = min(len(ind1), len(ind2))
        cxpoint1 = random.randint(1, size - 1)
        cxpoint2 = random.randint(1, size - 1)
        
        if cxpoint2 < cxpoint1:
            cxpoint1, cxpoint2 = cxpoint2, cxpoint1
        
        # Perform crossover
        ind1[cxpoint1:cxpoint2], ind2[cxpoint1:cxpoint2] = ind2[cxpoint1:cxpoint2], ind1[cxpoint1:cxpoint2]
        
        return ind1, ind2
    
    def _mutate(self, individual: creator.Individual) -> creator.Individual:
        """
        Mutation operation. Gene: (location_index, sensor_type_index, orientation_index, active_bit).
        """
        for i in range(len(individual)):
            if random.random() < 0.1:
                gene = individual[i]
                if len(gene) == 4:
                    location_index, sensor_type_index, orientation_index, active_bit = gene
                else:
                    location_index, sensor_type_index, active_bit = gene[0], gene[1], gene[2]
                    orientation_index = 0
                
                if random.random() < 0.3:
                    location_index = random.randint(0, self.num_locations - 1)
                if random.random() < 0.3:
                    sensor_type_index = random.randint(0, len(self.sensor_types) - 1)
                if random.random() < 0.25:
                    orientation_index = random.randint(0, self.num_orientations - 1)
                if random.random() < 0.5:
                    active_bit = 1 - active_bit
                
                individual[i] = (location_index, sensor_type_index, orientation_index, active_bit)

        # Reinforce minimum active sensors (active bit is last element)
        active_bit_idx = 3 if individual and len(individual[0]) == 4 else 2
        active_indices = [idx for idx, gene in enumerate(individual) if gene[active_bit_idx] == 1]
        if len(active_indices) < self.min_sensors:
            deficit = self.min_sensors - len(active_indices)
            available = [idx for idx in range(len(individual)) if idx not in active_indices]
            if available:
                chosen = random.sample(available, min(deficit, len(available)))
                for idx in chosen:
                    g = list(individual[idx])
                    g[active_bit_idx] = 1
                    individual[idx] = tuple(g)
        return individual
    
    def run_evolution(self, population_size: int = 50,
                     generations: int = 100,
                     crossover_prob: float = 0.7,
                     mutation_prob: float = 0.2,
                     verbose: bool = True,
                     show_progress: bool = True,
                     checkpoint_dir: Optional[str] = None,
                     checkpoint_prefix: str = "checkpoint",
                     checkpoint_frequency: int = 1,
                     resume: bool = False,
                     algorithm: str = "nsga2",
                     nsga3_ref_p: int = 6) -> Dict[str, Any]:
        """
        Run the genetic algorithm evolution.

        Args:
            population_size: Size of the population
            generations: Number of generations
            crossover_prob: Crossover probability
            mutation_prob: Mutation probability
            verbose: Whether to print verbose output
            show_progress: Whether to show progress bar
            algorithm: "nsga2" (default) or "nsga3"
            nsga3_ref_p: Number of divisions for NSGA-III reference points (used only if algorithm=="nsga3")

        Returns:
            Dictionary with evolution results
        """
        start_time = time.time()
        use_nsga3 = algorithm.strip().lower() == "nsga3"
        toolbox = self.toolbox
        if use_nsga3:
            n_obj = 3
            ref_points = uniform_reference_points(n_obj, nsga3_ref_p)
            min_pop = nsga3_min_population(n_obj, nsga3_ref_p)
            if population_size < min_pop:
                if verbose:
                    print(f"NSGA-III: population adjusted {population_size} -> {min_pop} (ref_points={len(ref_points)})")
                population_size = min_pop
            sel_nsga3 = functools.partial(tools.selNSGA3, ref_points=ref_points)
            map_func = self._parallel_map if self.n_cores > 1 else None
            toolbox = create_toolbox(
                individual_func=self._create_individual,
                evaluate_func=self._evaluate_individual,
                mate_func=self._crossover,
                mutate_func=self._mutate,
                map_func=map_func,
                select_survival=sel_nsga3,
                select_parents=tools.selRandom,
            )
            if verbose:
                print(f"NSGA-III: {len(ref_points)} reference points (p={nsga3_ref_p}), pop={population_size}")

        checkpoint_enabled = checkpoint_dir is not None
        checkpoint_path: Optional[Path] = None
        if checkpoint_enabled:
            checkpoint_path = Path(checkpoint_dir)
            checkpoint_path.mkdir(parents=True, exist_ok=True)
            if checkpoint_frequency < 1:
                checkpoint_frequency = 1
        
        # Resume from checkpoint if requested
        start_generation = 0
        initial_population = None
        if checkpoint_enabled and resume and checkpoint_path is not None:
            checkpoint_data, checkpoint_file = self._load_latest_checkpoint(checkpoint_path, checkpoint_prefix)
            if checkpoint_data:
                stored_population = checkpoint_data.get('population')
                stored_pop_size = checkpoint_data.get('population_size', population_size)
                if stored_population and len(stored_population) == population_size and stored_pop_size == population_size:
                    initial_population = [self.toolbox.clone(ind) for ind in stored_population]
                    start_generation = checkpoint_data.get('generation', -1) + 1
                    if checkpoint_data.get('random_state'):
                        random.setstate(checkpoint_data['random_state'])
                    if checkpoint_data.get('np_random_state'):
                        np.random.set_state(checkpoint_data['np_random_state'])
                    if verbose:
                        print(f"Resuming evolution from generation {start_generation}/{generations}")
                        if checkpoint_file:
                            print(f"   Checkpoint loaded: {checkpoint_file}")
                elif verbose:
                    print("WARNING: Checkpoint incompatible. Starting fresh run.")
        if initial_population is None and verbose:
            print(f"Evaluating initial population of {population_size} individuals...")

        # Progress bar for run_nsga2_evolution callback
        n_gen_to_run = generations - start_generation
        progress_bar = tqdm(total=n_gen_to_run, desc="Evolution", unit="gen") if show_progress else None

        def progress_cb(gen: int, record: Dict) -> None:
            if progress_bar is not None:
                progress_bar.update(1)
                single_layer = self._noncoop_only or self._coop_only
                avg = record.get('avg', (0, 0, 0) if not single_layer else (0, 0))
                min_ = record.get('min', (0, 0, 0) if not single_layer else (0, 0))
                if self._noncoop_only:
                    progress_bar.set_postfix({'M_c_noncoop': f"{avg[0]:.3f}", 'Min Cost': f"{min_[1]:.3f}"})
                elif self._coop_only:
                    progress_bar.set_postfix({'M_c_coop': f"{avg[0]:.3f}", 'Min Cost': f"{min_[1]:.3f}"})
                else:
                    progress_bar.set_postfix({
                        'M_c_coop': f"{avg[0]:.3f}",
                        'M_c_noncoop': f"{avg[1]:.3f}",
                        'Min Cost': f"{min_[2]:.3f}"
                    })

        def checkpoint_cb(gen: int, pop: List, hof: Any, logbook_list: List) -> None:
            if checkpoint_enabled and checkpoint_path is not None:
                self._save_checkpoint(
                    checkpoint_path, checkpoint_prefix, gen, pop, hof, logbook_list,
                    population_size, verbose
                )

        # Run evolution (DEAP base: NSGA-II or NSGA-III)
        evo_result = run_nsga2_evolution(
            toolbox,
            population_size=population_size,
            generations=generations,
            crossover_prob=crossover_prob,
            mutation_prob=mutation_prob,
            halloffame_size=population_size,
            stats=None,
            verbose=verbose,
            progress_callback=progress_cb,
            checkpoint_callback=checkpoint_cb if checkpoint_enabled else None,
            checkpoint_frequency=checkpoint_frequency,
            initial_population=initial_population,
            start_generation=start_generation,
        )
        if progress_bar is not None:
            progress_bar.close()

        population = evo_result['population']
        pareto_front = evo_result['pareto_front']
        halloffame = evo_result['hall_of_fame']
        logbook = evo_result['logbook']
        stats = evo_result['stats']
        start_generation = evo_result.get('start_generation', 0)

        end_time = time.time()
        execution_time = end_time - start_time
        best_individual = tools.selBest(population, 1)[0]
        best_sensors = self._decode_individual(best_individual)
        best_results = self.evaluator.evaluate_network_dual_layer(
            best_sensors, site_activation_cost=self.site_activation_cost
        )
        final_stats = stats.compile(population)

        if verbose:
            print(f"\nEvolution completed in {execution_time:.2f} seconds")
            print(f"Best individual:")
            print(f"   M_wp_coop:  {best_results['M_wp_coop']:.3f}  M_wp_noncoop: {best_results['M_wp_noncoop']:.3f}")
            print(f"   M_vuln:     coop {best_results['M_vuln_coop']:.3f}  noncoop {best_results['M_vuln_noncoop']:.3f}")
            print(f"   Fused resilience: {best_results['fused_resilience']:.3f}  Asset ROI: ${best_results['asset_security_roi']:,.0f}")
            print(f"   Cost: ${best_results['cost']:.2f} (sites: {best_results['unique_sites']})  Sensors: {best_results['num_sensors']}")

        return {
            'best_individual': best_individual,
            'best_sensors': best_sensors,
            'best_results': best_results,
            'final_stats': final_stats,
            'execution_time': execution_time,
            'population_size': population_size,
            'generations': generations,
            'n_cores': self.n_cores,
            'population': population,
            'hall_of_fame': halloffame,
            'pareto_front': pareto_front,
            'logbook': logbook,
            'start_generation': start_generation
        }

    def decode_individual(self, individual: creator.Individual):
        """Public interface to decode individual to list of Sensor objects."""
        return self._decode_individual(individual)

    def individual_to_sensor_list(self, individual: creator.Individual) -> List[Dict[str, Any]]:
        """Decode individual to standard format: list of {type, x, y, z [, azimuth_deg]} dicts."""
        sensors = self._decode_individual(individual)
        out = []
        for s in sensors:
            d = {"type": getattr(s, "sensor_type", "Unknown"), "x": s.location[0], "y": s.location[1], "z": s.location[2]}
            if hasattr(s, "azimuth_deg"):
                d["azimuth_deg"] = s.azimuth_deg
            out.append(d)
        return out

    def _save_checkpoint(self,
                         directory: Path,
                         prefix: str,
                         generation: int,
                         population: List[creator.Individual],
                         halloffame: tools.HallOfFame,
                         logbook: List[Dict[str, Any]],
                         population_size: int,
                         verbose: bool) -> None:
        """Save checkpoint to disk."""
        filename = directory / f"{prefix}_gen{generation:04d}.pkl"
        data = {
            'generation': generation,
            'population': [self.toolbox.clone(ind) for ind in population],
            'halloffame': [self.toolbox.clone(ind) for ind in halloffame],
            'logbook': copy.deepcopy(logbook),
            'random_state': random.getstate(),
            'np_random_state': np.random.get_state(),
            'population_size': population_size,
            'timestamp': time.time()
        }
        try:
            with open(filename, 'wb') as f:
                pickle.dump(data, f)
            if verbose:
                print(f"Checkpoint saved: {filename}")
        except Exception as exc:
            if verbose:
                print(f"WARNING: Failed to save checkpoint {filename}: {exc}")

    def _load_latest_checkpoint(self,
                                directory: Path,
                                prefix: str) -> Tuple[Optional[Dict[str, Any]], Optional[Path]]:
        """Load latest checkpoint from directory."""
        checkpoints = sorted(directory.glob(f"{prefix}_gen*.pkl"))
        if not checkpoints:
            return None, None
        latest = checkpoints[-1]
        try:
            with open(latest, 'rb') as f:
                data = pickle.load(f)
            return data, latest
        except Exception as exc:
            print(f"WARNING: Could not load checkpoint {latest}: {exc}")
            return None, None


def create_sensor_network_ga_geojson(environment: UrbanEnvironment,
                                    max_sensors: int = 20,
                                    weights: Tuple[float, float, float] = (1.0, 1.0, 0.001),
                                    n_cores: int = None) -> SensorNetworkGAGeoJSON:
    """
    Factory function to create a SensorNetworkGAGeoJSON.
    
    Args:
        environment: Urban environment with GeoJSON data
        max_sensors: Maximum number of sensors
        weights: Weights for fitness function
        n_cores: Number of CPU cores for parallelization
        
    Returns:
        SensorNetworkGAGeoJSON instance
    """
    return SensorNetworkGAGeoJSON(environment, max_sensors, weights, n_cores)
