# SCOPAS Framework — Technical Documentation

**BVLOS Sensor Placement and Fusion for Counter-UAS Operations**

---

## 1. Overview

SCOPAS optimizes **ground-based sensor networks** for detecting and tracking small UAS in urban environments. It provides:

- **Pareto-based multi-objective optimization** (NSGA-II / NSGA-III): coverage, redundancy/resilience, cost
- **3D voxelized ray-tracing** with building occlusion and per-sensor field-of-view constraints
- **Dual-layer airspace analysis**: cooperative (RF identity) and non-cooperative (Radar/EO/Acoustic) layers
- **Threat-weighted metrics** when critical assets are defined (point defense)
- **Airway-stratified coverage** at configurable flight altitudes
- **OpenStreetMap / GeoJSON** integration for real urban data

Interaction is via **CLI**, **JSON configs**, and **Python imports**. No REST API or plugin system.

Attribution: SCOPAS is an independent implementation inspired by the SCOPAS paper and concepts (Kukulka de Albuquerque et al., DASC 2023), with its own framework structure and workflow.
Quick onboarding: see `docs/QUICK_INTEGRATION_TUTORIAL.md` for a practical integration path.

---

## 2. Installation

```bash
git clone <repo_url>
cd <repository-folder>
pip install -r requirements.txt
```

Python 3.8+ required (3.10+ recommended). All scripts assume the **project root** as working directory.

### Sensor modalities

| Type | Default CapEx | Urban range (small electric sUAS) | Dual-layer role |
|------|---------------|-----------------------------------|-----------------|
| Radar | USD 50,000 | ~2–3 km | Non-cooperative |
| RF | USD 15,000 | ~250 m | Cooperative only |
| EO | USD 25,000 | ~150 m | Non-cooperative |
| Acoustic | USD 8,000 | ~300 m | Non-cooperative |

Full parameter tables and rationale: `docs/SENSORS.md`. Acoustic demos: `docs/DEMO_RUNS.md`.

### Dependencies


| Category      | Packages                                    |
| ------------- | ------------------------------------------- |
| Core          | `numpy`, `scipy`                            |
| Geospatial    | `geopandas`, `shapely`, `osmnx`, `rasterio` |
| Visualization | `matplotlib`, `plotly`                      |
| Optimization  | `deap`                                      |
| Ray-tracing   | `scikit-image`                              |
| Utilities     | `tqdm`                                      |
| Optional      | `numba` (JIT performance)                   |


---

## 3. Entry Points


| Script              | Role                                                 | Key arguments                                                                  |
| ------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------ |
| `run_framework.py`  | **Unified CLI** (evaluate / nsga2 / nsga3 / random)  | `--config`, `--mode`, `--solutions-file`, `--objective-profile`                |
| `run_experiment.py` | **Full pipeline**: optimization + all analysis tools | `--config`, `--mode`, `--skip-3d`, `--skip-optimization`, `--split-objectives` |


### Running an optimization

```bash
python run_framework.py --config configs/city_allocation_assets.json --mode nsga2
```

### Choosing objective profile (recommended for practical deployment)

```bash
# Dual-layer (default): M_wp_coop + M_wp_noncoop + cost
python run_framework.py --config configs/point_defense_airport_sjc.json --mode nsga2 --objective-profile dual_layer

# Cooperative planning only: M_wp_coop + cost
python run_framework.py --config configs/point_defense_airport_sjc.json --mode nsga2 --objective-profile coop_only

# Non-cooperative planning only: M_wp_noncoop + cost
python run_framework.py --config configs/point_defense_airport_sjc.json --mode nsga2 --objective-profile noncoop_only
```

### Running optimization + all visualizations

```bash
python run_experiment.py --config configs/city_allocation_assets.json
```

This runs the optimizer, then automatically generates: Pareto plots, coverage maps, 2D overview, 3D/Cesium exports, hypervolume, convergence plot, flight-level analysis, and cost-vs-coverage analysis.

### Split experiment (coop + noncoop in one command)

```bash
python run_experiment.py --config configs/point_defense_airport_sjc.json --split-objectives
```

This executes two full runs:

- `coop_only` (for compliant/cooperative operations)
- `noncoop_only` (for dark/non-cooperative operations)

Each run gets a distinct `run_id` suffix (`_coop`, `_noncoop`) and full post-processing outputs.

### Evaluating custom solutions (CLI)

```bash
python run_framework.py --config configs/city_allocation_assets.json \
    --mode evaluate --solutions-file examples/sample_solutions.json --output my_results.json
```

The solutions file is a JSON list of deployments. Each deployment is a list of `{"type", "x", "y", "z"}` dicts.

---

## 4. Configuration (JSON)

One experiment = one config file. All behaviour is driven by the config.

### New user templates

Ready-to-copy templates are in `configs/templates/`:

- `dual_layer_template.json`
- `coop_only_template.json`
- `noncoop_only_template.json`

See `configs/templates/README.md` for a short copy-edit-run workflow.

### Required sections


| Section            | Keys                                                                | Description                                                                                            |
| ------------------ | ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `experiment_name`  | string                                                              | Unique name, used for results directory                                                                |
| `environment`      | `buildings_file`, `sensor_locations_file`, `resolution`             | GeoJSON paths and voxel size (m)                                                                       |
| `sensors.types`    | per-type dict                                                       | `cost`, ranges/FOV, plus type-specific keys (`power_W`, `sensitivity_dBm`, `source_spl_dB`, …). See `docs/SENSORS.md`. |
| `pareto_search`    | `n_samples`, `generations`, `n_cores`, `min_sensors`, `max_sensors` | GA parameters                                                                                          |
| `airway_altitudes` | array of floats                                                     | Flight levels in metres, e.g. `[20, 45, 65]`                                                           |
| `requirements`     | `min_coverage`, `min_overlap`                                       | Thresholds for solution classification                                                                 |
| `output`           | `results_dir`, `save_results`, `generate_plots`                     | Output configuration                                                                                   |


### Optional sections


| Section                   | Keys                                                            | Description                                   |
| ------------------------- | --------------------------------------------------------------- | --------------------------------------------- |
| `critical_assets`         | array of `{id, location, protection_radius, weight_multiplier}` | Enables threat-weighted point-defense metrics |
| `site_activation_cost`    | float                                                           | Fixed cost per unique sensor site             |
| `optimization.objectives` | `"dual_layer" | "coop_only" | "noncoop_only"`                   | Objective profile for optimization            |
| `checkpoint`              | `enabled`, `dir`, `frequency`, `resume`                         | GA checkpoint save/resume                     |
| `analysis`                | `max_solutions`                                                 | Max solutions to keep in Pareto front         |


### Point Defense Metrics

When `critical_assets` is present, the framework computes dual-layer metrics instead of basic coverage/redundancy:


| Base Metric              | Point Defense Upgrade          | Meaning                                                                                          |
| ------------------------ | ------------------------------ | ------------------------------------------------------------------------------------------------ |
| Coverage (M_c)           | **Weighted Protection (M_wp)** | M_wp = sum(Covered x W) / sum(W). Fraction of threat-weighted volume secured.                    |
| Gap (M_g)                | **Vulnerability (M_vuln)**     | M_vuln = 1 - M_wp. Quantifies exposure to threat.                                                |
| Overlap                  | **Fused Resilience**           | % of threat volume covered by both cooperative and non-cooperative sensors (modality diversity). |
| Cost-Effectiveness (C_A) | **Asset Security ROI**         | Total_Cost / M_wp. CapEx per unit of weighted protection.                                        |


**Dual-layer**: M_wp_coop (any sensor) and M_wp_noncoop (Radar/EO/Acoustic only).

### Objective profile semantics


| `optimization.objectives` | Optimized objectives              | Typical use                                      |
| ------------------------- | --------------------------------- | ------------------------------------------------ |
| `dual_layer` (default)    | `(M_wp_coop, M_wp_noncoop, cost)` | Research/benchmark trade-space                   |
| `coop_only`               | `(M_wp_coop, cost)`               | Operational planning for compliant traffic       |
| `noncoop_only`            | `(M_wp_noncoop, cost)`            | Operational planning for non-cooperative threats |


---

## 5. Python API

### Objective Function API (`scopas_core`)

The simplest integration point for external optimizers:

```python
from src.scopas_core import load_config, load_environment_from_config, evaluate_solution

config = load_config("configs/city_allocation_assets.json")
env = load_environment_from_config(config)
sensor_types = config["sensors"]["types"]

candidate = [
    {"type": "Radar", "x": 500, "y": 500, "z": 30},
    {"type": "RF",    "x": 200, "y": 700, "z": 25},
    {"type": "Acoustic", "x": 350, "y": 450, "z": 20},
]

result = evaluate_solution(env, candidate, sensor_types, config=config)
```

**Key functions:**


| Function                                                | Description                                    |
| ------------------------------------------------------- | ---------------------------------------------- |
| `load_config(path)`                                     | Load JSON config                               |
| `load_environment_from_config(config, base_dir)`        | Build `UrbanEnvironment` (call once, reuse)    |
| `evaluate_solution(env, sensors, sensor_types, config)` | Evaluate one deployment. Returns metrics dict. |
| `run_evaluation(config_path, solutions, base_dir)`      | Batch evaluate multiple deployments            |


**Return values** (when `critical_assets` is in config):

```python
{
    "M_wp_coop": float,           # Weighted protection (cooperative)
    "M_wp_noncoop": float,        # Weighted protection (non-cooperative)
    "M_vuln_coop": float,         # Vulnerability index
    "M_vuln_noncoop": float,
    "fused_resilience": float,    # Dual-layer modality diversity
    "asset_security_roi": float,  # Cost per unit of protection
    "cost": float,                # Total cost (hardware + site activation)
    "num_sensors": int,
    "unique_sites": int
}
```

Without `critical_assets`:

```python
{"coverage": float, "redundancy": float, "cost": float, "num_sensors": int}
```

### Core Modules


| Module                  | Main exports                                                             | Purpose                                                        |
| ----------------------- | ------------------------------------------------------------------------ | -------------------------------------------------------------- |
| `environment.py`        | `UrbanEnvironment`                                                       | Load GeoJSON, 3D voxelization, building occlusion, threat maps |
| `sensors.py`            | `RadarSensor`, `RFSensor`, `EOSensor`, `AcousticSensor`, `create_sensor` | Sensor models                                                  |
| `propagation.py`        | `check_line_of_sight`, `check_elevation_angle`, `calculate_PD`           | Ray-tracing, detection probability                             |
| `network_evaluation.py` | `NetworkEvaluator`                                                       | Coverage maps, redundancy, dual-layer evaluation               |
| `genetic_algorithm.py`  | `SensorNetworkGAGeoJSON`                                                 | NSGA-II/III with GeoJSON sensor locations                      |
| `deap_base.py`          | `setup_multi_objective_creator`, `create_toolbox`                        | DEAP framework setup                                           |
| `scopas_metrics.py`     | `calculate_all_scopas_metrics`                                           | Mc, Mg, CA, overlap                                            |
| `airway_metrics.py`     | `calculate_metrics_per_airway`                                           | Per-altitude metrics                                           |
| `visualization.py`      | Plotting helpers                                                         | matplotlib/plotly utilities                                    |


---

## 6. Analysis Tools

All tools operate on results directories and accept `--results <path>`.


| Tool                                   | Output                                    | Description                                   |
| -------------------------------------- | ----------------------------------------- | --------------------------------------------- |
| `tools/plot_pareto_from_results.py`    | `pareto_front.png`, `pareto_front_3d.png` | 2D and 3D Pareto front plots                  |
| `tools/visualize_pareto_solutions.py`  | `coverage_maps/`                          | Coverage and redundancy heat maps             |
| `tools/analyze_flight_levels.py`       | `coverage_by_flight_level.png`            | Coverage (Mc) at each airway altitude         |
| `tools/analyze_coverage_levels.py`     | `cost_vs_coverage_level.png`              | Minimum cost to achieve coverage thresholds   |
| `tools/calculate_hypervolume.py`       | `hypervolume.json`                        | Hypervolume indicator of Pareto front quality |
| `tools/generate_convergence_plots.py`  | `evolution_convergence.png`               | Objective convergence over generations        |
| `tools/generate_2d_overview.py`        | `overview_2d.png`                         | 2D overview of best solution                  |
| `tools/visualize_multi_airway.py`      | `multi_airway_maps/`                      | Side-by-side altitude comparison maps         |
| `tools/export_best_solution_3d.py`     | `best_solution_3d.json`                   | Best solution for Three.js 3D viewer          |
| `tools/export_for_cesium.py`           | `cesium_data.json`                        | Export for Cesium globe viewer (WGS84)        |
| `tools/generate_all_visualizations.py` | (all above)                               | Run all visualization tools at once           |


Coverage heat maps default to `power` (`--coverage-scale power`, `--coverage-power-gamma` default `0.45`): color follows `Pd**gamma`, so `gamma < 1` uses less of the green ramp in the 0.8-1.0 plateau (less "solid dark disk + sudden step"). Use `linear` only if you want a literal 0-1 bar (often looks worse). Also: 256-level LUT, upsample 4x, bilinear + bicubic (display-only). Redundancy default: `--redundancy-gamma 0.5` (same idea on Pd sums).

---

## 7. Data

### Input format

- **Buildings**: GeoJSON with polygon geometries and a `height` attribute (metres)
- **Sensor locations**: GeoJSON with point geometries and a `height` attribute (metres)

Paths in configs are relative to the project root unless absolute.

### Provided scenes


| Scene                        | Location                   | Path                                                          |
| ---------------------------- | -------------------------- | ------------------------------------------------------------- |
| Synthetic city (1 km x 1 km) | Generic                    | `data/examples/city_10x10_`*                                  |
| Airport SJC                  | Real (Sao Jose dos Campos) | `data/scenes/airport_sjc/`                                    |
| Stadium/Arena                | Generic                    | `data/scenes/stadium_arena/`                                  |
| Open Farm                    | Generic                    | `data/scenes/open_farm/`                                      |
| Central Buildings            | Generic                    | `data/scenes/central_buildings_city/`                         |
| Avenida Paulista             | Real (Sao Paulo)           | `data/case_studies/avenida_paulista/` (requires OSM download) |


### Downloading OSM data

```bash
python src/download_osm.py --city avenida_paulista \
    --lat -23.5613 --lon -46.6563 --radius 2000 \
    --output data/case_studies/avenida_paulista
```

### Downloading terrain (DEM)

```bash
python tools/download_dem.py --scene data/scenes/airport_sjc
```

---

## 8. Output Structure

Each optimization run creates:

```
results/<experiment_name>/<run_id>/
|-- config.json                   # Copy of the config used
|-- evaluation_results.json       # Evaluated Pareto solutions with metrics
|-- pareto_front.json             # Pareto front data (standard output)
|-- pareto_front.png              # 2D Pareto plot
|-- pareto_front_3d.png           # 3D Pareto plot
|-- overview_2d.png               # 2D best-solution overview
|-- evolution_convergence.png     # Convergence over generations
|-- coverage_by_flight_level.png  # Coverage at each altitude
|-- cost_vs_coverage_level.png    # Cost vs coverage threshold
|-- hypervolume.json              # Hypervolume indicator
|-- coverage_maps/                # Per-solution coverage heat maps
|-- multi_airway_maps/            # Per-altitude comparison maps
|-- best_solution_3d.json         # For Three.js viewer
`-- cesium_data.json              # For Cesium viewer
```

Notes:

- `<run_id>` can be timestamped or explicit (`output.run_id`).
- Some tools still accept legacy `pareto_results.json` when present.
- **Cesium export** (`tools/export_for_cesium.py`) expects a `scene_meta.json` in the scene directory (e.g. `data/scenes/airport_sjc/`). Synthetic example scenes under `data/examples/` typically do not include it — use `run_experiment.py --skip-3d` for those, or add scene metadata for your area.

---

## 9. Tests

```bash
python -m unittest tests.test_scopas -v
```

Fast subset (excludes the ~20–40 s NSGA-II smoke test):

```bash
python -m unittest tests.test_scopas.TestConfig tests.test_scopas.TestEnvironment tests.test_scopas.TestEvaluation tests.test_scopas.TestCLI tests.test_scopas.TestOutputHelpers -v
```

---

## 10. Base Reference Paper

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

