# Config Templates (New Users)

Use these templates to start a new scenario quickly:

- `dual_layer_template.json` — `(M_wp_coop, M_wp_noncoop, cost)` with Radar+RF+EO+Acoustic
- `coop_only_template.json` — `(M_wp_coop, cost)` for compliant traffic planning
- `noncoop_only_template.json` — `(M_wp_noncoop, cost)` for dark-target planning (Radar+EO+Acoustic)

All templates include **Acoustic** as a low-cost non-cooperative modality (default USD 8,000 / 300 m urban). See `docs/SENSORS.md`.

## Quick steps

1. Copy one template and rename it:

```bash
cp configs/templates/dual_layer_template.json configs/my_new_scenario.json
```

2. Edit only these fields first:
- `experiment_name`
- `environment.buildings_file`
- `environment.sensor_locations_file`
- `critical_assets`
- `output.run_id`

3. Run optimization:

```bash
python run_framework.py --config configs/my_new_scenario.json --mode nsga2
```

## Practical split workflow

For clearer operations planning (coop vs non-coop), use one base config and run:

```bash
python run_experiment.py --config configs/my_new_scenario.json --split-objectives --skip-3d
```

This generates two runs automatically:
- cooperative objective (`_coop`)
- non-cooperative objective (`_noncoop`)

## Dual-layer requirement floors

In your config `requirements` section, prefer:

```json
"requirements": {
  "min_M_wp_coop": 0.90,
  "min_M_wp_noncoop": 0.35,
  "min_coverage": 0.90,
  "min_overlap": 0.30
}
```

After optimization, filter the Pareto:

```bash
python tools/select_requirement_solutions.py --results results/<exp>/<run>/ \
  --min-coop 0.90 --min-noncoop 0.35
```

## Acoustic and target demos (pre-built)

| Config | Command |
|--------|---------|
| Dual-layer | `python run_experiment.py --config configs/demo_acoustic_dual_layer.json --skip-3d` |
| Non-coop only | `python run_experiment.py --config configs/demo_acoustic_noncoop.json --skip-3d` |
| Split fronts | `python run_experiment.py --config configs/demo_acoustic_split.json --split-objectives --skip-3d` |
| Targets 90/35 | `python run_experiment.py --config configs/demo_targets_coop90_noncoop35.json --skip-3d` |
| Targets 90/50 | `python run_experiment.py --config configs/demo_targets_coop90_noncoop50.json --skip-3d` |

Details: `docs/DEMO_RUNS.md`.
