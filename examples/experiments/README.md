## SCOPAS — legacy experiment drivers (examples)

Standalone scripts from early development. **Prefer** `run_framework.py` and `run_experiment.py`
from the project root, or the `muscat_core` API for new work.

Run all commands from the **repository root**.

### 1. Custom Pareto search (grid-based)

- **Script**: `examples/experiments/run_pareto_experiment.py`  
- **What it does**:  
  - Samples random sensor configurations.  
  - Computes SCOPAS / MUSCAT-style metrics (Mc, redundancy, cost, airway metrics).  
  - Builds a Pareto front and saves plots and JSON results.  
- **Example**:

```bash
python examples/experiments/run_pareto_experiment.py \
  --config configs/pareto_city_10x10_final.json
```

### 2. NSGA-II Pareto experiment

- **Script**: `examples/experiments/run_pareto_nsga2.py`  
- **What it does**:  
  - Uses `SensorNetworkGAGeoJSON` (DEAP NSGA-II) for multi-objective optimization.  
  - Evaluates solutions with SCOPAS metrics and (optionally) point-defense metrics.  
  - Writes results JSON (legacy scripts may use `pareto_results.json`), 2D/3D Pareto plots, and summary stats.  
- **Example**:

```bash
python examples/experiments/run_pareto_nsga2.py \
  --config configs/pareto_city_10x10_final.json
```

### 3. NSGA-II vs NSGA-III comparison (recommended approach)

The old comparison wrapper was removed during cleanup. Use the unified CLI for side-by-side runs:

```bash
python run_framework.py --config configs/pareto_city_10x10_final.json --mode nsga2
python run_framework.py --config configs/pareto_city_10x10_final.json --mode nsga3
```

