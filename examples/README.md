# Examples

## Quick start

| Script | Purpose |
|--------|---------|
| `evaluate_custom_solution.py` | Evaluate a hand-defined sensor deployment using the full SCOPAS metric suite |
| `custom_algorithm_demo.py` | Plug your own optimizer: random search loop calling `evaluate_solution()` |

## Experiments (legacy)

The `experiments/` subdirectory contains standalone experiment runners from early development. They are kept for reference but are **not the recommended way** to run experiments. Use `run_framework.py` (or `run_experiment.py`) from the project root instead.

| Script | Notes |
|--------|-------|
| `experiments/run_pareto_experiment.py` | Legacy standalone Pareto search (does not use `solutions/`) |
| `experiments/run_pareto_nsga2.py` | Legacy NSGA-II runner with inline analysis |

## Point defense case study

See `point_defense_airport_sjc/README.md` for the airport (SJC) case study documentation.
