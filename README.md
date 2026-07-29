# Sensor Coverage Optimization for Protected Air Space (SCOPAS) Framework

**BVLOS Sensor Placement and Fusion for Counter-UAS Operations**

Pareto-based multi-objective optimization of heterogeneous sensor networks in 3D urban environments, with rigorous ray-tracing, threat-weighted coverage metrics, and dual-layer airspace analysis.

Inspired by: *"Multi-Sensor Placement and Information Fusion Analysis to Enable Beyond Visual Line of Sight Operations for Small Uncrewed Aerial Vehicles"* (IEEE/AIAA DASC 2023).

This repository is an independent implementation and extension. It references the original SCOPAS concepts and publication while introducing a different software architecture and workflow (including split cooperative/non-cooperative optimization profiles).

---

## Quick Start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Smoke test (< 1 minute, single core)
python run_framework.py --config configs/quick_test.json --mode nsga2

# 3. Full experiment with all visualizations
python run_experiment.py --config configs/city_allocation_assets.json
```

Results are saved to `results/<experiment_name>/<run_id>/`.

---

## Fast Tutorial: External Optimizer + SCOPAS Evaluation Function

Use SCOPAS as the objective evaluator, and run your own optimization algorithm outside the framework.

### 1) Load config and build evaluation context

```python
from src.scopas_core import load_config, load_environment_from_config, evaluate_solution

config = load_config("configs/city_allocation_assets.json")
env = load_environment_from_config(config)
sensor_types = config["sensors"]["types"]
```

### 2) Define one candidate solution format

Each candidate is a Python list of sensors:

```python
candidate = [
    {"type": "Radar", "x": 500, "y": 500, "z": 30},
    {"type": "RF",    "x": 200, "y": 700, "z": 25},
    {"type": "EO",    "x": 400, "y": 300, "z": 35},
]
```

### 3) Evaluate inside your own optimization loop

```python
import random
from src.scopas_core import load_config, load_environment_from_config, evaluate_solution

config = load_config("configs/city_allocation_assets.json")
env = load_environment_from_config(config)
sensor_types = config["sensors"]["types"]

def random_candidate():
    # Simple example generator (replace with your own optimizer logic)
    types = list(sensor_types.keys())
    n = random.randint(3, 6)
    return [
        {
            "type": random.choice(types),
            "x": random.uniform(0, 1000),
            "y": random.uniform(0, 1000),
            "z": random.uniform(20, 60),
        }
        for _ in range(n)
    ]

best = None
for _ in range(20):  # your algorithm iterations
    candidate = random_candidate()
    metrics = evaluate_solution(env, candidate, sensor_types, config=config)

    # Example objective: maximize non-coop coverage, then coop coverage
    score = (metrics["M_wp_noncoop"], metrics["M_wp_coop"])
    if best is None or score > best["score"]:
        best = {"score": score, "candidate": candidate, "metrics": metrics}

print("Best score:", best["score"])
print("Best metrics:", best["metrics"])
```

### 4) What your optimizer receives from SCOPAS

`evaluate_solution(...)` returns metrics you can optimize directly, such as:

- `M_wp_coop`
- `M_wp_noncoop`
- `fused_resilience`
- `cost`
- `num_sensors`

For a complete runnable script, see `examples/custom_algorithm_demo.py`.

---

## Documentation Map

- `README.md` (this file): quick start and day-to-day commands.
- `DOCUMENTATION.md`: full technical reference.
- `docs/QUICK_INTEGRATION_TUTORIAL.md`: step-by-step integration tutorial.

## Usage

### Run an optimization

```bash
python run_framework.py --config configs/<config>.json --mode nsga2
```

Modes: `nsga2` | `nsga3` | `random` | `evaluate`

Objective profiles (for NSGA runs):

- `dual_layer` (default): optimize `(M_wp_coop, M_wp_noncoop, cost)`
- `coop_only`: optimize `(M_wp_coop, cost)` for cooperative/compliant operations
- `noncoop_only`: optimize `(M_wp_noncoop, cost)` for non-cooperative/dark-target operations

```bash
python run_framework.py --config configs/point_defense_airport_sjc.json \
    --mode nsga2 --objective-profile coop_only
```

### Run optimization + all analysis in one step

```bash
python run_experiment.py --config configs/<config>.json [--mode nsga2] [--skip-3d]
```

This runs the optimizer and then automatically generates Pareto plots, coverage maps, convergence plots, hypervolume, flight-level analysis, and cost-vs-coverage analysis.

Split practical planning into two runs (coop + noncoop):

```bash
python run_experiment.py --config configs/point_defense_airport_sjc.json --split-objectives [--mode nsga2]
```

With the default `point_defense_airport_sjc.json` `output.run_id` (`airport_run`), outputs are:

- `results/point_defense_airport_sjc/airport_run_coop/` — cooperative objective only  
- `results/point_defense_airport_sjc/airport_run_noncoop/` — non-cooperative objective only  

Each folder contains a full analysis pipeline (plots, maps, hypervolume, etc.).

### New scenario in 2 minutes (templates)

Templates are available in `configs/templates/`:

- `dual_layer_template.json`
- `coop_only_template.json`
- `noncoop_only_template.json`

Start here: `configs/templates/README.md`

### Evaluate your own solutions

Define your sensor deployment in a JSON file:

```json
[
  [
    {"type": "Radar", "x": 500, "y": 500, "z": 30},
    {"type": "RF",    "x": 200, "y": 700, "z": 25},
    {"type": "EO",    "x": 400, "y": 300, "z": 35}
  ]
]
```

Then evaluate it:

```bash
python run_framework.py --config configs/city_allocation_assets.json \
    --mode evaluate --solutions-file my_solutions.json --output results.json
```

Or from Python:

```python
from src.scopas_core import load_config, load_environment_from_config, evaluate_solution

config = load_config("configs/city_allocation_assets.json")
env = load_environment_from_config(config)
sensor_types = config["sensors"]["types"]

my_sensors = [
    {"type": "Radar", "x": 500, "y": 500, "z": 30},
    {"type": "RF",    "x": 200, "y": 700, "z": 25},
]

result = evaluate_solution(env, my_sensors, sensor_types, config=config)
# result = {M_wp_coop, M_wp_noncoop, fused_resilience, cost, num_sensors, ...}
```

See `examples/evaluate_custom_solution.py` and `examples/custom_algorithm_demo.py` for complete examples.

### Post-processing tools

All tools work on existing results directories:

```bash
python tools/plot_pareto_from_results.py    --results results/<exp>/<run>/
python tools/visualize_pareto_solutions.py  --results results/<exp>/<run>/
python tools/analyze_flight_levels.py       --results results/<exp>/<run>/
python tools/analyze_coverage_levels.py     --results results/<exp>/<run>/ --dual-layer
python tools/calculate_hypervolume.py       --results results/<exp>/<run>/
python tools/generate_convergence_plots.py  --results results/<exp>/<run>/
python tools/generate_2d_overview.py        --results results/<exp>/<run>/
python tools/visualize_multi_airway.py      --results results/<exp>/<run>/
python tools/export_best_solution_3d.py     --results results/<exp>/<run>/
python tools/export_for_cesium.py           --results results/<exp>/<run>/
```

---

## Provided Configs

| Config | Scene | Description |
|--------|-------|-------------|
| `quick_test.json` | Synthetic city | Smoke test (8 pop, 3 gen, 1 core). Use to verify installation. |
| `pareto_city_10x10_final.json` | Synthetic city | Full city benchmark (1 km x 1 km, 196 buildings) |
| `city_allocation_assets.json` | Synthetic city | City with 5 critical assets, threat-weighted dual-layer metrics |
| `point_defense_airport_sjc.json` | Airport SJC | Real-world airport scene with runway corridors |
| `point_defense_airport_sjc_coop_only.json` | Airport SJC | Cooperative objective only (M_wp_coop + cost) |
| `point_defense_airport_sjc_noncoop_only.json` | Airport SJC | Non-cooperative objectives only (M_wp_noncoop + cost) |
| `point_defense_airport_sjc_noncoop_90.json` | Airport SJC | Target M_c_noncoop >= 0.90 |
| `point_defense_airport_sjc_3h.json` | Airport SJC | Long run with checkpoint/resume |
| `point_defense_airport_sjc_reference_long.json` | Airport SJC | Extended reference run (large search; long runtime) |
| `point_defense_airport_sjc_no_rf_95.json` | Airport SJC | Radar + EO only, 95% protection, 15 m resolution |
| `point_defense_experiment.json` | Synthetic city | Point defense with critical assets |
| `point_defense_stadium_arena.json` | Stadium | Stadium/arena protection scenario |
| `open_farm.json` | Open farm | Rural open-field scenario |
| `central_buildings_city.json` | Central buildings | Central urban district |
| `pareto_sp_avenida.json` | Avenida Paulista | Real-world urban canyon (requires data download, see `data/README.md`) |

---

## Configuration Reference

A config JSON file defines:

```jsonc
{
  "experiment_name": "my_experiment",           // Unique name for results directory
  "environment": {
    "type": "synthetic",                        // or "real"
    "buildings_file": "data/.../buildings.geojson",
    "sensor_locations_file": "data/.../sensors.geojson",
    "resolution": 20.0                          // Voxel size in meters
  },
  "airway_altitudes": [20, 45, 65],             // Flight levels to analyze (m)
  "sensors": {
    "types": {
      "Radar": {"cost": 50000, "power_W": 1000, "gain_dB": 30, "frequency_Hz": 1e10},
      "RF":    {"cost": 15000, "sensitivity_dBm": -90, "frequency_Hz": 9e8},
      "EO":    {"cost": 25000},
      "Acoustic": {"cost": 8000, "max_range": 300, "source_spl_dB": 80}
    }
  },
  "pareto_search": {
    "n_samples": 80,                            // Population size
    "generations": 45,                          // Number of generations
    "n_cores": 8,                               // Parallel cores
    "min_sensors": 3,
    "max_sensors": 15
  },
  "optimization": {
    "objectives": "dual_layer"                // dual_layer | coop_only | noncoop_only
  },
  "site_activation_cost": 15000,                // Fixed cost per unique site
  "critical_assets": [                          // Triggers threat-weighted metrics
    {"id": "Hospital", "location": [500,500,30], "protection_radius": 120, "weight_multiplier": 1.0}
  ],
  "requirements": {"min_coverage": 0.75, "min_overlap": 0.35},
  "output": {"results_dir": "results/my_experiment", "save_results": true}
}
```

When `critical_assets` is present, the framework computes dual-layer metrics (M_wp_coop, M_wp_noncoop, fused_resilience) instead of basic coverage/redundancy.

---

## Project Structure

```
<repository-root>/
|-- run_framework.py             # Unified CLI (evaluate | nsga2 | nsga3 | random)
|-- run_experiment.py            # Run optimization + all analysis tools
|-- requirements.txt
|
|-- src/                         # Core framework
|   |-- scopas_core.py           # Entry point: load config, evaluate solutions
|   |-- environment.py           # 3D voxelized urban environment
|   |-- sensors.py               # Sensor models (Radar, RF, EO, Acoustic)
|   |-- propagation.py           # Ray-tracing, P_D, line-of-sight
|   |-- network_evaluation.py    # Dual-layer network metrics (M_wp, fused resilience)
|   |-- genetic_algorithm.py     # NSGA-II/III engine with DEAP
|   |-- scopas_metrics.py        # SCOPAS metrics (Mc, Mg, CA, overlap)
|   |-- airway_metrics.py        # Per-altitude airway metrics
|   |-- visualization.py         # Plotting utilities
|   |-- download_osm.py          # Download building data from OpenStreetMap
|   `-- dem.py                   # Digital elevation model support
|
|-- solutions/                   # Built-in solvers
|   |-- nsga2.py                 # NSGA-II (recommended)
|   |-- nsga3.py                 # NSGA-III
|   `-- random_search.py         # Random Pareto search (baseline)
|
|-- tools/                       # Post-processing and analysis
|   |-- plot_pareto_from_results.py
|   |-- visualize_pareto_solutions.py
|   |-- analyze_flight_levels.py
|   |-- analyze_coverage_levels.py
|   |-- calculate_hypervolume.py
|   |-- generate_convergence_plots.py
|   |-- generate_2d_overview.py
|   |-- visualize_multi_airway.py
|   |-- export_best_solution_3d.py
|   |-- export_for_cesium.py
|   |-- generate_all_visualizations.py
|   `-- download_dem.py
|
|-- configs/                     # Experiment configurations
|-- data/                        # Input data (GeoJSON scenes)
|   |-- examples/                # Synthetic scenes
|   |-- scenes/                  # Prepared real/synthetic scenes
|   `-- case_studies/            # Real-world case studies
|-- examples/                    # Usage examples and demos
|-- results/                     # Output (auto-generated)
|-- visualizations/              # HTML 3D viewer (Three.js) + Cesium data notes
`-- tests/                       # Unit tests
```

---

## Metrics

| Metric | Description |
|--------|-------------|
| **M_wp_coop** | Threat-weighted cooperative coverage (RF sensors) |
| **M_wp_noncoop** | Threat-weighted non-cooperative coverage (Radar, EO, Acoustic) |
| **Fused Resilience** | Combined dual-layer resilience score |
| **M_c** | Global area coverage fraction |
| **Cost** | Total deployment cost (sensor + site activation) |
| **C_A** | Cost per unit coverage (asset security ROI) |
| **Overlap** | Average sensor redundancy per voxel |

---

## Tests

```bash
python -m unittest tests.test_scopas -v
```

Quick subset (no NSGA-II smoke, a few seconds):

```bash
python -m unittest tests.test_scopas.TestConfig tests.test_scopas.TestEnvironment tests.test_scopas.TestEvaluation tests.test_scopas.TestCLI tests.test_scopas.TestOutputHelpers -v
```

---

## Citation

```bibtex
@inproceedings{kukulka2023multisensor,
  author    = {P. Kukulka de Albuquerque and others},
  title     = {Multi-Sensor Placement and Information Fusion Analysis to Enable
               Beyond Visual Line of Sight Operations for Small Uncrewed Aerial Vehicles},
  booktitle = {IEEE/AIAA Digital Avionics Systems Conference (DASC)},
  year      = {2023},
  address   = {Barcelona, Spain}
}
```

---

## Troubleshooting

**ImportError**: Run `pip install -r requirements.txt`.

**Slow execution**: Increase `resolution` (e.g. 20 → 30 m), reduce `n_samples` or `generations`, or reduce `max_sensors`.

**Low coverage**: Check sensor parameters, verify building density is reasonable, try more candidate sensor locations.

**Cesium export fails** (`scene_meta.json not found`): Only scenes that include `scene_meta.json` (e.g. `data/scenes/airport_sjc/`) support `tools/export_for_cesium.py`. For synthetic examples under `data/examples/`, use `run_experiment.py --skip-3d` or add metadata for your scene.

**What gets committed**: `results/`, `logs/`, and `cache/` are listed in `.gitignore` (regenerate outputs locally). `results/README.md` is tracked as documentation.

---

## Sharing / reproducibility

- **Smoke test**: `configs/quick_test.json` (fast NSGA-II).
- **Reference experiments** (paper-style benchmarks): `configs/pareto_city_10x10_final.json` (city), `configs/point_defense_airport_sjc.json` (airport; use `--split-objectives` for separate coop/noncoop fronts).
- **Docs map**: this file → quick commands; `DOCUMENTATION.md` → full reference; `docs/QUICK_INTEGRATION_TUTORIAL.md` → onboarding; `docs/SENSORS.md` → sensor parameters.
