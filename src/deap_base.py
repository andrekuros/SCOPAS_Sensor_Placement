"""
DEAP (Distributed Evolutionary Algorithms in Python) base for SCOPAS optimization.

Provides a single integration point for all evolutionary algorithms:
- Creator setup (multi-objective fitness, individual type)
- Toolbox registration helpers
- NSGA-II and NSGA-III evolution loops
"""

import random
import copy
import math
from typing import Tuple, List, Dict, Any, Optional, Callable

import numpy as np
from deap import base, creator, tools


# Default weights for SCOPAS: (coverage, redundancy, -cost)
DEFAULT_WEIGHTS = (1.0, 1.0, -1.0)


def setup_multi_objective_creator(weights: Tuple[float, ...] = DEFAULT_WEIGHTS, force: bool = False) -> None:
    """
    Create DEAP creator classes for multi-objective optimization.
    Safe to call multiple times; skips if already defined with same weights.
    Use force=True when switching objective count (e.g. 3 -> 2 for noncoop-only).

    Args:
        weights: Fitness weights, e.g. (1.0, 1.0, -1.0) or (1.0, -1.0) for 2 objectives.
        force: If True, recreate creator even if FitnessMulti exists (e.g. different nobj).
    """
    existing_weights = getattr(getattr(creator, "FitnessMulti", None), "weights", None)
    if force or (existing_weights is not None and existing_weights != weights):
        for name in ("Individual", "FitnessMulti"):
            if hasattr(creator, name):
                delattr(creator, name)
    try:
        creator.FitnessMulti
    except AttributeError:
        creator.create("FitnessMulti", base.Fitness, weights=weights)

    try:
        creator.Individual
    except AttributeError:
        creator.create("Individual", list, fitness=creator.FitnessMulti)


def get_fitness_class():
    """Return the multi-objective fitness class (creator.FitnessMulti)."""
    return getattr(creator, "FitnessMulti")


def get_individual_class():
    """Return the individual class (creator.Individual)."""
    return getattr(creator, "Individual")


def uniform_reference_points(nobj: int, p: int) -> np.ndarray:
    """
    Generate uniform reference points for NSGA-III (number of divisions p, nobj objectives).
    Returns array of shape (n_ref, nobj). Population size should be >= n_ref.
    """
    return np.array(tools.uniform_reference_points(nobj, p))


def nsga3_min_population(nobj: int, p: int) -> int:
    """Minimum recommended population size for NSGA-III (first multiple of 4 >= H)."""
    # H = (p + nobj - 1)! / (p! * (nobj-1)!)
    h = int(math.factorial(p + nobj - 1) / (math.factorial(p) * math.factorial(nobj - 1)))
    return h + (4 - h % 4) if h % 4 else h


def create_toolbox(
    individual_func: Callable,
    evaluate_func: Callable,
    mate_func: Callable,
    mutate_func: Callable,
    map_func: Optional[Callable] = None,
    select_survival: Callable = tools.selNSGA2,
    select_parents: Callable = tools.selTournamentDCD,
) -> base.Toolbox:
    """
    Build a DEAP toolbox with standard operators for multi-objective GA.

    Args:
        individual_func: No-arg callable that returns one individual.
        evaluate_func: (individual) -> tuple of fitness values.
        mate_func: (ind1, ind2) -> (ind1, ind2).
        mutate_func: (ind) -> ind.
        map_func: Optional parallel map (func, iterable) for evaluation.
        select_survival: Selection for survival (e.g. tools.selNSGA2).
        select_parents: Selection for parents (e.g. tools.selTournamentDCD).

    Returns:
        Configured base.Toolbox.
    """
    toolbox = base.Toolbox()
    ind_class = get_individual_class()
    toolbox.register("individual", individual_func)
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)
    toolbox.register("evaluate", evaluate_func)
    toolbox.register("mate", mate_func)
    toolbox.register("mutate", mutate_func)
    toolbox.register("select", select_survival)
    toolbox.register("select_parents", select_parents)
    toolbox.register("clone", copy.deepcopy)
    if map_func is not None:
        toolbox.register("map", map_func)
    return toolbox


def run_nsga2_evolution(
    toolbox: base.Toolbox,
    population_size: int,
    generations: int,
    crossover_prob: float = 0.7,
    mutation_prob: float = 0.2,
    halloffame_size: Optional[int] = None,
    stats: Optional[tools.Statistics] = None,
    verbose: bool = True,
    progress_callback: Optional[Callable[[int, Dict], None]] = None,
    checkpoint_callback: Optional[Callable[[int, List, Any, List], None]] = None,
    checkpoint_frequency: int = 1,
    initial_population: Optional[List] = None,
    start_generation: int = 0,
) -> Dict[str, Any]:
    """
    Run NSGA-II evolution loop using DEAP primitives.

    Args:
        toolbox: DEAP toolbox with individual, population, evaluate, mate, mutate, select, select_parents, clone.
        population_size: Size of the population.
        generations: Number of generations.
        crossover_prob: Crossover probability.
        mutation_prob: Mutation probability.
        halloffame_size: Max size of hall of fame (default population_size).
        stats: DEAP Statistics object; if None, a default is created.
        verbose: Whether to log.
        progress_callback: Optional callable(gen, record) each generation.
        checkpoint_callback: Optional callable(gen, population, hall_of_fame, logbook) for checkpointing.
        checkpoint_frequency: How often to call checkpoint_callback (every N generations).
        initial_population: If provided, resume from this population (must have valid fitness).
        start_generation: Starting generation index when resuming.

    Returns:
        Dict with: population, pareto_front, hall_of_fame, logbook, stats, generation (last gen index), start_generation.
    """
    if halloffame_size is None:
        halloffame_size = population_size
    hof = tools.HallOfFame(maxsize=halloffame_size)

    if stats is None:
        stats = tools.Statistics(lambda ind: ind.fitness.values)
        stats.register("avg", lambda vals: np.mean(vals, axis=0))
        stats.register("std", lambda vals: np.std(vals, axis=0))
        stats.register("min", lambda vals: np.min(vals, axis=0))
        stats.register("max", lambda vals: np.max(vals, axis=0))

    logbook: List[Dict[str, Any]] = []
    map_ = getattr(toolbox, "map", map)

    if initial_population is not None and len(initial_population) == population_size:
        population = [toolbox.clone(ind) for ind in initial_population]
        invalid = [ind for ind in population if not ind.fitness.valid]
        if invalid:
            fits = map_(toolbox.evaluate, invalid)
            for ind, fit in zip(invalid, fits):
                ind.fitness.values = fit
        population = toolbox.select(population, len(population))
        hof.update(population)
    else:
        population = toolbox.population(n=population_size)
        fitnesses = map_(toolbox.evaluate, population)
        for ind, fit in zip(population, fitnesses):
            ind.fitness.values = fit
        population = toolbox.select(population, len(population))
        hof.update(population)

    for gen in range(start_generation, generations):
        offspring = toolbox.select_parents(population, len(population))
        offspring = [toolbox.clone(ind) for ind in offspring]

        for c1, c2 in zip(offspring[::2], offspring[1::2]):
            if random.random() < crossover_prob:
                toolbox.mate(c1, c2)
                del c1.fitness.values
                del c2.fitness.values

        for mutant in offspring:
            if random.random() < mutation_prob:
                toolbox.mutate(mutant)
                del mutant.fitness.values

        invalid = [ind for ind in offspring if not ind.fitness.valid]
        if invalid:
            fits = map_(toolbox.evaluate, invalid)
            for ind, fit in zip(invalid, fits):
                ind.fitness.values = fit

        population = toolbox.select(population + offspring, population_size)
        hof.update(population)

        record = stats.compile(population)
        logbook.append({"generation": gen, "stats": record})
        if progress_callback:
            progress_callback(gen, record)
        if checkpoint_callback and (checkpoint_frequency < 1 or (gen + 1) % checkpoint_frequency == 0 or gen == generations - 1):
            checkpoint_callback(gen, population, hof, logbook)

    pareto_front = tools.sortNondominated(population, len(population), first_front_only=True)[0]
    return {
        "population": population,
        "pareto_front": pareto_front,
        "hall_of_fame": hof,
        "logbook": logbook,
        "stats": stats,
        "generation": generations - 1,
        "start_generation": start_generation,
    }
