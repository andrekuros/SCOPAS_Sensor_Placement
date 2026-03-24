# Config Templates (New Users)

Use these templates to start a new scenario quickly:

- `dual_layer_template.json`
- `coop_only_template.json`
- `noncoop_only_template.json`

## Quick steps

1. Copy one template and rename it:

```bash
copy configs\templates\dual_layer_template.json configs\my_new_scenario.json
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
python run_experiment.py --config configs/my_new_scenario.json --split-objectives
```

This generates two runs automatically:
- cooperative objective (`_coop`)
- non-cooperative objective (`_noncoop`)
