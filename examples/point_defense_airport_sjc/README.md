# Point-defense example — Airport SJC

Case study: threat-weighted sensor placement around **São José dos Campos** airport using SCOPAS (Radar + RF + EO + Acoustic).

- **Config**: `configs/point_defense_airport_sjc.json`  
- **Data**: `data/scenes/airport_sjc/` (buildings, sensors, runways, `scene_meta.json` for Cesium)  
- **Outputs**: `results/point_defense_airport_sjc/<run_id>/` (timestamped unless `output.run_id` is set)
- **Metrics**: dual-layer `M_wp_coop` / `M_wp_noncoop` (noncoop = Radar / EO / Acoustic)

## Reproduce

```bash
python run_framework.py --config configs/point_defense_airport_sjc.json --mode nsga2
```

Full pipeline (plots, maps, hypervolume, …):

```bash
python run_experiment.py --config configs/point_defense_airport_sjc.json --mode nsga2
```

Split cooperative vs non-cooperative optimizations:

```bash
python run_experiment.py --config configs/point_defense_airport_sjc.json --split-objectives --mode nsga2
```

## Typical artifacts

- `evaluation_results.json`, `pareto_front.json` — solutions and metrics  
- `pareto_front.png`, `pareto_dual_layer_targets.png`, `coverage_maps/`, `overview_2d.png` — from `tools/`  
- `best_solution_3d.json`, `cesium_data.json` — 3D / globe export  

Filter by dual-layer floors after a run:

```bash
python tools/select_requirement_solutions.py \
  --results results/point_defense_airport_sjc/<run_id>/ \
  --min-coop 0.90 --min-noncoop 0.35
```

Use `src/scopas_core.py` (`evaluate_solution`) to plug in a custom optimizer while keeping the same scenario.
