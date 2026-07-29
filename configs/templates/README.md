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

## Acoustic demos (pre-built)

| Config | Command |
|--------|---------|
| Dual-layer | `python run_experiment.py --config configs/demo_acoustic_dual_layer.json --skip-3d` |
| Non-coop only | `python run_experiment.py --config configs/demo_acoustic_noncoop.json --skip-3d` |
| Split fronts | `python run_experiment.py --config configs/demo_acoustic_split.json --split-objectives --skip-3d` |

Details: `docs/DEMO_RUNS.md`.
